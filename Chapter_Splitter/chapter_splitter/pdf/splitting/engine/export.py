"""PDF chapter export orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ....config.schema import IOConfig, RetryConfig, ValidationConfig
from ....core.models import ChapterDefinition, ChapterOutput
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from .chapter_export import export_single_chapter
from .collisions import resolve_output_paths
from .models import ChapterExportProgress
from .preparation import (
    prepare_output_directory,
    validate_export_chapters,
    validate_offset_ranges,
)
from .source import load_source_document, resolve_effective_page_offset


def split_pdf_into_chapters(
    pdf_path: Path,
    chapters: list[ChapterDefinition],
    page_offset: int | None,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    validation_config: ValidationConfig,
    io_config: IOConfig,
    location: str,
    output_dir: Path | None = None,
    *,
    on_progress: Callable[[ChapterExportProgress], None] | None = None,
) -> list[ChapterOutput]:
    """Split a PDF into chapter files.

    Summary:
        Validate chapters, resolve export destinations, and write one PDF per chapter.
    Inputs:
        - pdf_path: Path to the source PDF.
        - chapters: List of ChapterDefinition objects.
        - page_offset: Optional offset applied when converting to zero-based indices.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - retry_config: Retry policy for PDF loading.
        - validation_config: Validation rules for chapters.
        - io_config: IO configuration for output behavior.
        - location: Fully qualified module and method name.
        - output_dir: Optional output directory override.
        - on_progress: Optional progress callback receiving per-chapter start and complete events.
    Outputs:
        - List of ChapterOutput objects with exported paths.
    Side effects:
        Reads the source PDF and writes chapter files to disk.
    Error handling:
        Raises IO, PDF processing, or validation errors when export cannot complete safely.
    Ties to other methods:
        Delegates source loading, validation, path resolution, and per-chapter writes to helper
        modules within the engine package.
    Why this exists:
        The UI and CLI need one deterministic export pipeline with shared validation rules.
    """
    token.check(location)
    reader, total_pages = load_source_document(
        pdf_path=pdf_path,
        io_config=io_config,
        retry_config=retry_config,
        token=token,
        location=location,
    )
    deadline.check(location)

    effective_page_offset = resolve_effective_page_offset(
        reader=reader,
        page_offset=page_offset,
        io_config=io_config,
        location=location,
    )
    validated = validate_export_chapters(
        chapters=chapters,
        total_pages=total_pages,
        validation_config=validation_config,
        location=location,
    )
    effective_output_dir = prepare_output_directory(
        pdf_path=pdf_path,
        io_config=io_config,
        output_dir=output_dir,
        location=location,
    )
    validate_offset_ranges(
        validated,
        total_pages=total_pages,
        page_offset=effective_page_offset,
        location=location,
    )
    out_paths = resolve_output_paths(validated, effective_output_dir, io_config, location)

    outputs: list[ChapterOutput] = []
    total_chapters = len(validated)
    for idx, (chapter, out_path) in enumerate(zip(validated, out_paths, strict=True), start=1):
        outputs.append(
            export_single_chapter(
                reader=reader,
                chapter=chapter,
                output_path=out_path,
                chapter_index=idx,
                total_chapters=total_chapters,
                page_offset=effective_page_offset,
                io_config=io_config,
                deadline=deadline,
                token=token,
                location=location,
                on_progress=on_progress,
            )
        )
    return outputs


__all__ = ["split_pdf_into_chapters"]
