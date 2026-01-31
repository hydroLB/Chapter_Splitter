"""PDF splitting operations for chapter exports."""

from __future__ import annotations

from pathlib import Path

from ...config.schema import IOConfig, RetryConfig, ValidationConfig
from ...core.errors import IoError, PdfProcessingError, format_error_message
from ...core.models import ChapterDefinition, ChapterOutput
from ...core.runtime import CancellationToken
from ...core.validation import validate_chapters
from ...utils.filenames import safe_filename
from ...utils.timing import Deadline
from ..io.dependencies import PdfWriter
from ..io.loader import get_total_pages, load_reader


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

    outputs: list[ChapterOutput] = []
    for chapter in validated:
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

        filename = safe_filename(chapter.title)
        out_path = output_dir / f"{filename}.pdf"
        if out_path.exists() and not io_config.output_overwrite:
            raise IoError(
                format_error_message(
                    error_location,
                    f"Output file already exists: {out_path}.{context}",
                )
            )
        try:
            with out_path.open("wb") as handle:
                write_deadline = Deadline(io_config.pdf_write_timeout_seconds)
                write_deadline.check(location)
                writer.write(handle)
                write_deadline.check(location)
        except OSError as exc:
            raise IoError(
                format_error_message(
                    error_location,
                    f"Failed to write chapter output: {out_path}.{context}",
                )
            ) from exc
        outputs.append(ChapterOutput(chapter=chapter, output_path=out_path))
    return outputs
