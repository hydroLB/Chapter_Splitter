"""Validation and output preparation helpers for PDF splitting."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ....config.schema import IOConfig, ValidationConfig
from ....core.errors import IoError, ValidationError, format_error_message
from ....core.models import ChapterDefinition
from ....core.validation import validate_chapters


def validate_export_chapters(
    *,
    chapters: list[ChapterDefinition],
    total_pages: int,
    validation_config: ValidationConfig,
    location: str,
) -> list[ChapterDefinition]:
    """Validate chapter definitions for export."""
    return validate_chapters(
        chapters=chapters,
        total_pages=total_pages,
        max_chapters=validation_config.max_chapters,
        require_unique_titles=validation_config.require_unique_titles,
        sort_chapters_by_start_page=validation_config.sort_chapters_by_start_page,
        reject_overlapping_ranges=validation_config.reject_overlapping_ranges,
        location=location,
    )


def prepare_output_directory(
    *,
    pdf_path: Path,
    io_config: IOConfig,
    output_dir: Path | None,
    location: str,
) -> Path:
    """Create and validate the output directory for chapter PDFs."""
    error_location = "chapter_splitter.pdf.splitting.engine.preparation.prepare_output_directory"
    context = f" Context: {location}." if location else ""
    effective_output_dir = output_dir or (
        pdf_path.parent / f"{pdf_path.stem}{io_config.output_dir_suffix}"
    )
    try:
        effective_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Unable to create output directory: {effective_output_dir}.{context}",
            )
        ) from exc
    if not effective_output_dir.is_dir():
        raise IoError(
            format_error_message(
                error_location,
                "Output directory path exists but is not a directory: "
                f"{effective_output_dir}.{context}",
            )
        )
    return effective_output_dir


def validate_offset_ranges(
    chapters: Iterable[ChapterDefinition],
    *,
    total_pages: int,
    page_offset: int,
    location: str,
) -> None:
    """Validate that applying a page offset does not push indices out of bounds."""
    error_location = "chapter_splitter.pdf.splitting.engine.preparation.validate_offset_ranges"
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


__all__ = [
    "prepare_output_directory",
    "validate_export_chapters",
    "validate_offset_ranges",
]
