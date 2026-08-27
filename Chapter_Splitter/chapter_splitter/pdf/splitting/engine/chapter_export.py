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
from .writer import StagedPdf, stage_pdf


def stage_single_chapter(
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
) -> tuple[ChapterOutput, StagedPdf]:
    """Build and serialize one chapter without publishing its final path."""
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
    staged_pdf = stage_pdf(
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
    return ChapterOutput(chapter=chapter, output_path=output_path), staged_pdf


def _build_chapter_writer(
    *,
    reader: PdfReader,
    chapter: ChapterDefinition,
    page_offset: int,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> PdfWriter:
    """Build a PdfWriter containing the pages for one chapter."""
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
    """Emit a chapter export progress event when a callback is configured."""
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


__all__ = ["stage_single_chapter"]
