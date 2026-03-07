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
    """Detect chapters using an already-loaded reader instance.

    Summary:
        Extract outline entries, choose the appropriate detection strategy, and build a unified
        report for higher-level interfaces.
    Inputs:
        - reader: Reader supporting outlines and text extraction.
        - total_pages: Total pages in the document.
        - pdf_path: PDF path used for contextual error messages.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics configuration.
        - request: DetectionRequest controlling strategy selection and TOC hinting.
        - location: Fully qualified module and method name.
    Outputs:
        - ChapterDetectionReport describing chapters, confidence, and warnings.
    Side effects:
        Reads outlines and extracts page text to scan TOC candidates.
    Error handling:
        Raises PdfProcessingError when total_pages is invalid and propagates cancellation/timeouts.
    Ties to other methods:
        Delegates strategy-specific work to outline_strategy.py and toc_strategy.py.
    Why this exists:
        Reusing an already-open reader avoids duplicate IO in the GUI workflow.
    """
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
    """Validate the unified detector page count input.

    Summary:
        Reject invalid page counts before strategy-specific logic executes.
    Inputs:
        - total_pages: Total pages reported for the loaded reader.
        - location: Fully qualified caller location.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        Raises PdfProcessingError when total_pages is less than one.
    Ties to other methods:
        Used by detect_chapters_in_reader.
    Why this exists:
        Early validation keeps downstream outline and TOC branches simpler and more predictable.
    """
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
