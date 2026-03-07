"""Per-chapter export helpers for PDF splitting."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from ....config.schema import IOConfig
from ....core.errors import PdfProcessingError, format_error_message
from ....core.models import ChapterDefinition, ChapterOutput
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ...io.dependencies import PdfReader, PdfWriter
from .models import ChapterExportProgress
from .writer import atomic_write_pdf


def export_single_chapter(
    *,
    reader: PdfReader,
    chapter: ChapterDefinition,
    output_path: Path,
    chapter_index: int,
    total_chapters: int,
    page_offset: int,
    io_config: IOConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
    on_progress: Callable[[ChapterExportProgress], None] | None,
) -> ChapterOutput:
    """Export one chapter to a PDF file.

    Summary:
        Emit progress, build the per-chapter writer, and persist the final PDF atomically.
    Inputs:
        - reader: Loaded PDF reader.
        - chapter: Chapter definition being exported.
        - output_path: Destination path for the chapter PDF.
        - chapter_index: 1-based chapter index.
        - total_chapters: Total number of chapters in the export run.
        - page_offset: Effective page offset for range conversion.
        - io_config: IO configuration controlling write behavior.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified caller location.
        - on_progress: Optional progress callback.
    Outputs:
        - ChapterOutput describing the exported file.
    Side effects:
        Writes one chapter PDF to disk and may emit progress events.
    Error handling:
        Raises PdfProcessingError when page extraction fails and propagates IoError from writes.
    Ties to other methods:
        Used by split_pdf_into_chapters for each validated chapter.
    Why this exists:
        Isolating per-chapter work keeps the main export loop small and easy to debug.
    """
    token.check(location)
    deadline.check(location)
    _emit_progress(
        on_progress=on_progress,
        phase="start",
        chapter=chapter,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        output_path=output_path,
    )
    writer = _build_chapter_writer(
        reader=reader,
        chapter=chapter,
        page_offset=page_offset,
        deadline=deadline,
        token=token,
        location=location,
    )
    atomic_write_pdf(
        output_path,
        writer=writer,
        io_config=io_config,
        deadline=deadline,
        token=token,
        location=location,
    )
    _emit_progress(
        on_progress=on_progress,
        phase="complete",
        chapter=chapter,
        chapter_index=chapter_index,
        total_chapters=total_chapters,
        output_path=output_path,
    )
    return ChapterOutput(chapter=chapter, output_path=output_path)


def _build_chapter_writer(
    *,
    reader: PdfReader,
    chapter: ChapterDefinition,
    page_offset: int,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> PdfWriter:
    """Build a PdfWriter containing the pages for one chapter.

    Summary:
        Convert a chapter range into page copies on a fresh PdfWriter instance.
    Inputs:
        - reader: Loaded PDF reader.
        - chapter: Chapter definition being exported.
        - page_offset: Effective page offset for range conversion.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified caller location.
    Outputs:
        - PdfWriter populated with the chapter pages.
    Side effects:
        Reads pages from the source PDF reader.
    Error handling:
        Raises PdfProcessingError when the chapter range resolves outside the reader page list.
    Ties to other methods:
        Used by export_single_chapter.
    Why this exists:
        Page-copy logic is the core PDF manipulation hotspot and deserves a dedicated helper.
    """
    error_location = "chapter_splitter.pdf.splitting.engine.chapter_export._build_chapter_writer"
    context = f" Context: {location}." if location else ""
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
    return writer


def _emit_progress(
    *,
    on_progress: Callable[[ChapterExportProgress], None] | None,
    phase: Literal["start", "complete"],
    chapter: ChapterDefinition,
    chapter_index: int,
    total_chapters: int,
    output_path: Path,
) -> None:
    """Emit a chapter export progress event when a callback is configured.

    Summary:
        Normalize progress event creation so the main export loop does not duplicate event wiring.
    Inputs:
        - on_progress: Optional progress callback.
        - phase: Progress phase.
        - chapter: Chapter definition being exported.
        - chapter_index: 1-based chapter index.
        - total_chapters: Total number of chapters in the export run.
        - output_path: Destination path for the chapter PDF.
    Outputs:
        - None.
    Side effects:
        Invokes the supplied progress callback when present.
    Error handling:
        No-ops when on_progress is None.
    Ties to other methods:
        Used by export_single_chapter.
    Why this exists:
        Progress creation should remain consistent across start and completion events.
    """
    if on_progress is None:
        return
    on_progress(
        ChapterExportProgress(
            phase=phase,
            chapter=chapter,
            index=chapter_index,
            total=total_chapters,
            output_path=output_path,
        )
    )


__all__ = ["export_single_chapter"]
