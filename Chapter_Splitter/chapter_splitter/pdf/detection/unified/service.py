"""Unified chapter detection orchestration."""

from __future__ import annotations

from pathlib import Path

from ....config.schema import DetectionConfig
from ....core.errors import PdfProcessingError, format_error_message
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ..report import ChapterDetectionReport
from .outline_strategy import (
    detect_forced_outlines,
    detect_preferred_outlines,
    extract_filtered_outline_entries,
)
from .reports import build_none_report
from .request import DetectionRequest, UnifiedReaderProtocol
from .toc_strategy import detect_forced_toc, detect_toc_fallback


def detect_chapters_in_reader(
    reader: UnifiedReaderProtocol,
    total_pages: int,
    pdf_path: Path,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    request: DetectionRequest,
    location: str,
) -> ChapterDetectionReport:
    """Detect chapters using an already-loaded reader instance."""
    token.check(location)
    deadline.check(location)
    _validate_total_pages(total_pages=total_pages, location=location)

    warnings: list[str] = []
    outline_entries = extract_filtered_outline_entries(
        reader=reader,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        location=location,
    )

    if request.force_strategy == "outlines":
        return detect_forced_outlines(
            reader=reader,
            total_pages=total_pages,
            deadline=deadline,
            token=token,
            detection_config=detection_config,
            outline_entries=outline_entries,
            warnings=warnings,
            location=location,
        )

    if request.force_strategy == "toc":
        return detect_forced_toc(
            reader=reader,
            total_pages=total_pages,
            deadline=deadline,
            token=token,
            detection_config=detection_config,
            toc_hint_page=request.toc_hint_page,
            outline_entries=outline_entries,
            warnings=warnings,
            location=location,
        )

    preferred_report = detect_preferred_outlines(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        outline_entries=outline_entries,
        warnings=warnings,
        location=location,
    )
    if preferred_report is not None:
        return preferred_report

    if not detection_config.enable_toc_fallback:
        warnings.append("No chapters detected from outlines and TOC fallback is disabled.")
        return build_none_report(
            warnings=warnings,
            outline_entries=len(outline_entries),
            toc_start_page=None,
            toc_pages_scanned=0,
        )

    return detect_toc_fallback(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        toc_hint_page=request.toc_hint_page,
        outline_entries=outline_entries,
        warnings=warnings,
        location=location,
        pdf_path=pdf_path,
    )


def _validate_total_pages(*, total_pages: int, location: str) -> None:
    """Validate the unified detector page count input."""
    error_location = "chapter_splitter.pdf.detection.unified.service._validate_total_pages"
    context = f" Context: {location}." if location else ""
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"total_pages must be >= 1 (got {total_pages}).{context}",
            )
        )


__all__ = ["detect_chapters_in_reader"]
