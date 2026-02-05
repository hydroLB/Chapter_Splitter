"""PDF splitting operations for chapter exports."""

from __future__ import annotations

import os
import secrets
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO, cast

from ...config.schema import IOConfig, RetryConfig, ValidationConfig
from ...core.errors import IoError, PdfProcessingError, ValidationError, format_error_message
from ...core.models import ChapterDefinition, ChapterOutput
from ...core.runtime import CancellationToken
from ...core.validation import validate_chapters
from ...utils.filenames import safe_filename
from ...utils.timing import Deadline
from ..io.dependencies import PdfWriter
from ..io.loader import get_total_pages, load_reader


def _format_collision_hint(io_config: IOConfig) -> str:
    """Build a consistent config hint for collision errors.

    Summary:
        Provide a short hint that points to the config knob that controls collision behavior.
    Inputs:
        - io_config: IO configuration used by the pipeline.
    Outputs:
        - Human readable hint string.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by collision handling branches in split_pdf_into_chapters.
    Why this exists:
        Collision errors are common user friction points; consistent hints reduce support burden.
    """
    return (
        "To change this behavior, update io.output_collision_policy " "(error, overwrite, suffix)."
    )


def _with_suffix(base: str, index: int) -> str:
    """Return a deterministic filename stem with a numeric suffix.

    Summary:
        Append a " (n)" suffix to a filename stem without changing the extension.
    Inputs:
        - base: Base filename stem.
        - index: Numeric suffix (>= 2).
    Outputs:
        - Suffixed filename stem.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when index is invalid.
    Ties to other methods:
        Used by _resolve_output_paths for suffix collision policy.
    Why this exists:
        Suffixing provides a non-destructive collision policy that keeps outputs user-friendly.
    """
    error_location = f"{__name__}._with_suffix"
    if index < 2:
        raise ValidationError(
            format_error_message(
                error_location,
                f"Suffix index must be >= 2 (got {index}).",
            )
        )
    return f"{base} ({index})"


def _resolve_output_paths(
    chapters: list[ChapterDefinition],
    output_dir: Path,
    io_config: IOConfig,
    location: str,
) -> list[Path]:
    """Resolve final output paths with configured collision handling.

    Summary:
        Convert chapter titles into output paths, applying collision policy against existing
        files and within-run duplicates.
    Inputs:
        - chapters: Validated chapters for export.
        - output_dir: Output directory for chapter PDFs.
        - io_config: IO configuration controlling collision policy.
        - location: Fully qualified module and method name.
    Outputs:
        - List of final output paths, in the same order as chapters.
    Side effects:
        Checks filesystem state for existing output files.
    Error handling:
        Raises ValidationError for duplicate sanitized filenames when policy is error; raises
        IoError when existing files block export under policy error.
    Ties to other methods:
        Used by split_pdf_into_chapters before writing any bytes.
    Why this exists:
        Resolving all paths up-front avoids partial exports when a late chapter collides.
    """
    error_location = f"{__name__}._resolve_output_paths"
    context = f" Context: {location}." if location else ""
    policy = io_config.output_collision_policy
    max_suffix = io_config.output_collision_max_suffix
    resolved: list[Path] = []
    used_stems: set[str] = set()
    used_paths: set[Path] = set()

    for chapter in chapters:
        stem = safe_filename(chapter.title)
        if policy in ("error", "overwrite") and stem in used_stems:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Multiple chapter titles sanitize to the same output filename stem "
                    f"'{stem}'. Rename the chapters or set io.output_collision_policy='suffix'."
                    f"{context}",
                )
            )
        used_stems.add(stem)

        if policy == "error":
            candidate = output_dir / f"{stem}.pdf"
            if candidate.exists():
                raise IoError(
                    format_error_message(
                        error_location,
                        f"Output file already exists: {candidate}.{context} "
                        f"{_format_collision_hint(io_config)}",
                    )
                )
            resolved.append(candidate)
            used_paths.add(candidate)
            continue

        if policy == "overwrite":
            candidate = output_dir / f"{stem}.pdf"
            resolved.append(candidate)
            used_paths.add(candidate)
            continue

        if policy != "suffix":
            raise IoError(
                format_error_message(
                    error_location,
                    f"Unsupported output collision policy '{policy}'.{context}",
                )
            )

        for idx in range(1, max_suffix + 1):
            candidate_stem = stem if idx == 1 else _with_suffix(stem, idx)
            candidate = output_dir / f"{candidate_stem}.pdf"
            if candidate in used_paths:
                continue
            if candidate.exists():
                continue
            resolved.append(candidate)
            used_paths.add(candidate)
            break
        else:
            raise IoError(
                format_error_message(
                    error_location,
                    f"Unable to find an available output filename for '{stem}' after "
                    f"{max_suffix - 1} suffix attempts.{context}",
                )
            )

    return resolved


def _atomic_write_pdf(
    out_path: Path,
    *,
    writer: PdfWriter,
    io_config: IOConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> None:
    """Write a PDF output via a temporary file and atomic rename.

    Summary:
        Prevent partial output files by writing to a temp file in the target directory and then
        atomically replacing the destination path.
    Inputs:
        - out_path: Final output path to create or replace.
        - writer: PdfWriter containing the pages to export.
        - io_config: IO configuration controlling write timeout and fsync behavior.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Writes a temporary file and then moves it into place.
    Error handling:
        Raises IoError when writes or renames fail; cleans up temporary files best-effort.
    Ties to other methods:
        Used by split_pdf_into_chapters for each chapter output.
    Why this exists:
        Users should never be left with corrupted or half-written PDFs if an export is interrupted.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}._atomic_write_pdf"
    context = f" Context: {location}." if location else ""

    tmp_path: Path | None = None
    try:
        # Keep the temp file on the same filesystem for an atomic replace.
        tmp_prefix = f".{out_path.stem}.tmp-"
        tmp_suffix = f"-{secrets.token_hex(6)}{out_path.suffix}"
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(out_path.parent),
            prefix=tmp_prefix,
            suffix=tmp_suffix,
        ) as handle:
            tmp_path = Path(handle.name)
            write_deadline = Deadline(io_config.pdf_write_timeout_seconds)
            write_deadline.check(location)
            writer.write(cast(BinaryIO, handle))
            handle.flush()
            if io_config.fsync_writes:
                os.fsync(handle.fileno())
            write_deadline.check(location)

        # replace is atomic on POSIX when tmp is in the same directory.
        tmp_path.replace(out_path)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to write chapter output: {out_path}.{context}",
            )
        ) from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()


def _validate_offset_ranges(
    chapters: Iterable[ChapterDefinition],
    *,
    total_pages: int,
    page_offset: int,
    location: str,
) -> None:
    """Validate that applying a page offset does not push indices out of bounds.

    Summary:
        Catch out-of-range exports early with an actionable error message that references the
        configured page offset.
    Inputs:
        - chapters: Chapters to validate.
        - total_pages: Total pages in the PDF.
        - page_offset: Page offset applied when converting to indices.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when a chapter range becomes invalid after applying the offset.
    Ties to other methods:
        Used by split_pdf_into_chapters after validate_chapters passes.
    Why this exists:
        Page offset is a sharp tool; validating it prevents confusing IndexError failures later.
    """
    error_location = f"{__name__}._validate_offset_ranges"
    context = f" Context: {location}." if location else ""
    for chapter in chapters:
        page_range = chapter.to_page_range(page_offset, location)
        if page_range.start_index < 0 or page_range.end_index >= total_pages:
            raise ValidationError(
                format_error_message(
                    error_location,
                    f"Chapter '{chapter.title}' maps to indices "
                    f"[{page_range.start_index}, {page_range.end_index}] with "
                    f"page_offset={page_offset}, but total_pages={total_pages}.{context}",
                )
            )


def split_pdf_into_chapters(
    pdf_path: Path,
    chapters: list[ChapterDefinition],
    page_offset: int,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    validation_config: ValidationConfig,
    io_config: IOConfig,
    location: str,
) -> list[ChapterOutput]:
    """Split a PDF into chapter files.

    Purpose:
        Export chapter specific PDF files from a single source document.
    Ties To:
        Used by the UI export action and CLI split command.
    Inputs:
        - pdf_path: Path to the source PDF.
        - chapters: List of ChapterDefinition objects.
        - page_offset: Offset applied when converting to zero based indices.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - retry_config: Retry policy for PDF loading.
        - validation_config: Validation rules for chapters.
        - io_config: IO configuration for output behavior.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterOutput objects with exported paths.
    Side Effects:
        Reads the PDF and writes chapter files to disk.
    Raises:
        - IoError: When file operations fail.
        - PdfProcessingError: When PDF manipulation fails.
    """
    token.check(location)
    error_location = f"{__name__}.split_pdf_into_chapters"
    context = f" Context: {location}." if location else ""
    read_deadline = Deadline(io_config.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    deadline.check(location)

    validated = validate_chapters(
        chapters=chapters,
        total_pages=total_pages,
        max_chapters=validation_config.max_chapters,
        require_unique_titles=validation_config.require_unique_titles,
        sort_chapters_by_start_page=validation_config.sort_chapters_by_start_page,
        reject_overlapping_ranges=validation_config.reject_overlapping_ranges,
        location=location,
    )

    output_dir = pdf_path.parent / f"{pdf_path.stem}{io_config.output_dir_suffix}"
    try:
        output_dir.mkdir(exist_ok=True)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Unable to create output directory: {output_dir}.{context}",
            )
        ) from exc
    if not output_dir.is_dir():
        raise IoError(
            format_error_message(
                error_location,
                f"Output directory path exists but is not a directory: {output_dir}.{context}",
            )
        )

    outputs: list[ChapterOutput] = []
    _validate_offset_ranges(
        validated,
        total_pages=total_pages,
        page_offset=page_offset,
        location=location,
    )
    out_paths = _resolve_output_paths(validated, output_dir, io_config, location)

    for chapter, out_path in zip(validated, out_paths, strict=True):
        token.check(location)
        deadline.check(location)
        page_range = chapter.to_page_range(page_offset, location)
        writer = PdfWriter()
        try:
            for page_idx in range(page_range.start_index, page_range.end_index + 1):
                token.check(location)
                deadline.check(location)
                writer.add_page(reader.pages[page_idx])
        except (IndexError, TypeError) as exc:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"Page index out of range for chapter {chapter.title}.{context}",
                )
            ) from exc

        _atomic_write_pdf(
            out_path,
            writer=writer,
            io_config=io_config,
            deadline=deadline,
            token=token,
            location=location,
        )
        outputs.append(ChapterOutput(chapter=chapter, output_path=out_path))
    return outputs
