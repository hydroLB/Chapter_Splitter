"""PDF chapter export orchestration."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from ....config.schema import IOConfig, RetryConfig, ValidationConfig
from ....core.models import ChapterDefinition, ChapterOutput
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from .chapter_export import stage_single_chapter
from .collisions import resolve_output_paths
from .models import ChapterExportProgress
from .preparation import (
    prepare_output_directory,
    validate_export_chapters,
    validate_offset_ranges,
)
from .source import load_source_document, resolve_effective_page_offset
from .writer import StagedPdf, cleanup_staged_pdfs, commit_pdf_batch


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
    """Split a PDF into chapter files."""
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
    planned_output_dir = output_dir or (
        pdf_path.parent / f"{pdf_path.stem}{io_config.output_dir_suffix}"
    )
    output_dir_existed = planned_output_dir.exists()
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
    staged_pdfs: list[StagedPdf] = []
    total_chapters = len(validated)
    try:
        for idx, (chapter, out_path) in enumerate(zip(validated, out_paths, strict=True), start=1):
            output, staged_pdf = stage_single_chapter(
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
            outputs.append(output)
            staged_pdfs.append(staged_pdf)
        token.check(location)
        deadline.check(location)
        commit_pdf_batch(
            staged_pdfs,
            allow_overwrite=io_config.output_collision_policy == "overwrite",
        )
    except BaseException:
        cleanup_staged_pdfs(staged_pdfs, remove_backups=False)
        if not output_dir_existed:
            with suppress(OSError):
                effective_output_dir.rmdir()
        raise
    return outputs


__all__ = ["split_pdf_into_chapters"]
