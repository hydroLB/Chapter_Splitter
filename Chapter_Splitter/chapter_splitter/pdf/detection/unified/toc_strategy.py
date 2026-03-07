"""TOC strategy helpers for unified chapter detection."""

from __future__ import annotations

from pathlib import Path

from ....config.schema import DetectionConfig
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ..report import ChapterDetectionReport
from ..toc import TocDetectionReport, detect_best_toc_chapters
from .reports import build_none_report, build_toc_report
from .request import UnifiedReaderProtocol


def detect_forced_toc(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    toc_hint_page: int | None,
    outline_entries: list[tuple[str, int]],
    warnings: list[str],
    location: str,
) -> ChapterDetectionReport:
    """Run forced TOC detection.

    Summary:
        Execute TOC detection with the requested hint policy and wrap the result in a unified
        report.
    Inputs:
        - reader: Reader supporting text extraction.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics for TOC scanning.
        - toc_hint_page: Optional TOC hint page supplied by the caller.
        - outline_entries: Previously extracted outline entries.
        - warnings: Mutable warning accumulator.
        - location: Fully qualified caller location.
    Outputs:
        - ChapterDetectionReport for the forced TOC branch.
    Side effects:
        Extracts page text from the reader while scanning TOC candidates.
    Error handling:
        Returns a canonical empty report when no TOC chapters are found.
    Ties to other methods:
        Used by detect_chapters_in_reader when request.force_strategy is "toc".
    Why this exists:
        Forced TOC detection should bypass outline preference logic cleanly.
    """
    toc_report = _detect_toc_chapters(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        toc_hint_page=toc_hint_page,
        location=location,
        force_hint_page=True,
    )
    warnings.extend(toc_report.warnings)
    if not toc_report.chapters:
        warnings.append("No chapters detected from TOC.")
        return build_none_report(
            warnings=warnings,
            outline_entries=len(outline_entries),
            toc_start_page=toc_report.toc_start_page,
            toc_pages_scanned=toc_report.pages_scanned,
        )
    return build_toc_report(
        toc_report=toc_report,
        warnings=warnings,
        outline_entries=len(outline_entries),
    )


def detect_toc_fallback(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    toc_hint_page: int | None,
    outline_entries: list[tuple[str, int]],
    warnings: list[str],
    location: str,
    pdf_path: Path,
) -> ChapterDetectionReport:
    """Run the default TOC fallback branch.

    Summary:
        Execute TOC detection only after outlines fail and return the appropriate unified report.
    Inputs:
        - reader: Reader supporting text extraction.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics for TOC scanning.
        - toc_hint_page: Optional TOC hint page supplied by the caller.
        - outline_entries: Previously extracted outline entries.
        - warnings: Mutable warning accumulator.
        - location: Fully qualified caller location.
        - pdf_path: Loaded PDF path preserved for API parity with the caller.
    Outputs:
        - ChapterDetectionReport describing TOC fallback results.
    Side effects:
        Extracts page text from the reader while scanning TOC candidates.
    Error handling:
        Returns a canonical empty report when fallback also fails.
    Ties to other methods:
        Used by detect_chapters_in_reader after outline detection returns no chapters.
    Why this exists:
        Separating fallback behavior keeps the primary control flow linear and readable.
    """
    del pdf_path
    toc_report = _detect_toc_chapters(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        toc_hint_page=toc_hint_page,
        location=location,
        force_hint_page=False,
    )
    warnings.extend(toc_report.warnings)
    if toc_report.chapters:
        return build_toc_report(
            toc_report=toc_report,
            warnings=warnings,
            outline_entries=len(outline_entries),
        )
    warnings.append("No chapters detected from outlines or TOC.")
    return build_none_report(
        warnings=warnings,
        outline_entries=len(outline_entries),
        toc_start_page=toc_report.toc_start_page,
        toc_pages_scanned=toc_report.pages_scanned,
    )


def _detect_toc_chapters(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    toc_hint_page: int | None,
    location: str,
    force_hint_page: bool,
) -> TocDetectionReport:
    """Run TOC chapter detection with shared configuration.

    Summary:
        Execute TOC scanning with the caller-selected hinting behavior.
    Inputs:
        - reader: Reader supporting text extraction.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics for TOC scanning.
        - toc_hint_page: Optional TOC hint page supplied by the caller.
        - location: Fully qualified caller location.
        - force_hint_page: Whether the hint page must be used as the TOC start.
    Outputs:
        - TocDetectionReport produced by detect_best_toc_chapters.
    Side effects:
        Extracts page text from the reader while scanning TOC candidates.
    Error handling:
        Propagates exceptions raised by detect_best_toc_chapters.
    Ties to other methods:
        Used by forced and fallback TOC branches in this module.
    Why this exists:
        TOC detection configuration should be assembled in one place.
    """
    return detect_best_toc_chapters(
        reader=reader,
        total_pages=total_pages,
        detection=detection_config,
        deadline=deadline,
        token=token,
        toc_hint_page=toc_hint_page,
        location=location,
        force_hint_page=force_hint_page,
    )


__all__ = ["detect_forced_toc", "detect_toc_fallback"]
