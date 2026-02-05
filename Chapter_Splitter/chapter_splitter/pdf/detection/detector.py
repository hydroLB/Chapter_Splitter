"""Unified chapter detection entrypoint combining multiple strategies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...config.schema import DetectionConfig, IOConfig, RetryConfig
from ...core.errors import PdfProcessingError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline
from ..io.loader import get_total_pages, load_reader
from .outlines import (
    OutlineReaderProtocol,
    detect_chapters_from_outlines_reader,
    extract_outline_entries,
)
from .report import ChapterDetectionReport, ChapterDetectionStrategy
from .toc import TextExtractableReaderProtocol, detect_best_toc_chapters


class UnifiedReaderProtocol(OutlineReaderProtocol, TextExtractableReaderProtocol, Protocol):
    """Reader protocol supporting both outlines and text extraction."""


@dataclass(frozen=True, slots=True)
class DetectionRequest:
    """Detection request options for unified detection."""

    toc_hint_page: int | None
    force_strategy: ChapterDetectionStrategy | None


def detect_chapters(
    pdf_path: Path,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    io_config: IOConfig,
    detection_config: DetectionConfig,
    request: DetectionRequest,
    location: str,
) -> ChapterDetectionReport:
    """Detect chapters using outlines first and TOC fallback when configured.

    Summary:
        Load the PDF reader, enforce time bounds, and run unified detection.
    Inputs:
        - pdf_path: PDF file path.
        - deadline: Deadline tracker for overall operation timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - retry_config: Retry configuration used when opening the PDF.
        - io_config: IO configuration including read timeouts.
        - detection_config: Detection heuristics configuration.
        - request: DetectionRequest controlling strategy selection and hinting.
        - location: Fully qualified module and method name.
    Outputs:
        - ChapterDetectionReport describing chapters, confidence, and warnings.
    Side effects:
        Reads PDF bytes from disk and parses outlines/text.
    Error handling:
        Raises PdfProcessingError with a contextual message when inputs are invalid or detection
        fails.
    Ties to other methods:
        Delegates to detect_chapters_in_reader after load_reader/get_total_pages succeed.
    Why this exists:
        The GUI and future CLI should share a single, consistent detection behavior and report
        shape.
    """
    token.check(location)
    read_deadline = Deadline(io_config.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    deadline.check(location)
    return detect_chapters_in_reader(
        reader=reader,
        total_pages=total_pages,
        pdf_path=pdf_path,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        request=request,
        location=location,
    )


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
        Extract outline entries, then choose between outlines and TOC strategies, returning a
        structured report for UI rendering and logging.
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
        Raises PdfProcessingError when total_pages is invalid; propagates cancellation/timeouts.
    Ties to other methods:
        Uses extract_outline_entries, detect_chapters_from_outlines_reader, and
        detect_best_toc_chapters.
    Why this exists:
        The GUI already opens the PDF to gather metadata, so reusing the reader avoids duplicate
        IO.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.detect_chapters_in_reader"
    context = f" Context: {location}." if location else ""
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"total_pages must be >= 1 (got {total_pages}).{context}",
            )
        )
    warnings: list[str] = []

    force = request.force_strategy
    toc_hint = request.toc_hint_page

    outline_entries = extract_outline_entries(reader, deadline, token, location)

    if force == "outlines":
        chapters = detect_chapters_from_outlines_reader(
            reader=reader,
            total_pages=total_pages,
            deadline=deadline,
            token=token,
            location=location,
            entries=outline_entries,
        )
        confidence = _confidence_for_outlines(outline_entries, chapters)
        if not chapters:
            warnings.append("No chapters detected from outlines.")
            return ChapterDetectionReport(
                strategy="none",
                chapters=(),
                confidence=0.0,
                warnings=tuple(warnings),
                outline_entries=len(outline_entries),
                toc_start_page=None,
                toc_pages_scanned=0,
            )
        return ChapterDetectionReport(
            strategy="outlines",
            chapters=tuple(chapters),
            confidence=confidence,
            warnings=tuple(warnings),
            outline_entries=len(outline_entries),
            toc_start_page=None,
            toc_pages_scanned=0,
        )

    if force == "toc":
        toc_report = detect_best_toc_chapters(
            reader=reader,
            total_pages=total_pages,
            detection=detection_config,
            deadline=deadline,
            token=token,
            toc_hint_page=toc_hint,
            location=location,
            force_hint_page=True,
        )
        warnings.extend(toc_report.warnings)
        if not toc_report.chapters:
            warnings.append("No chapters detected from TOC.")
            return ChapterDetectionReport(
                strategy="none",
                chapters=(),
                confidence=0.0,
                warnings=tuple(warnings),
                outline_entries=len(outline_entries),
                toc_start_page=toc_report.toc_start_page,
                toc_pages_scanned=toc_report.pages_scanned,
            )
        return ChapterDetectionReport(
            strategy="toc",
            chapters=tuple(toc_report.chapters),
            confidence=toc_report.confidence,
            warnings=tuple(warnings),
            outline_entries=len(outline_entries),
            toc_start_page=toc_report.toc_start_page,
            toc_pages_scanned=toc_report.pages_scanned,
        )

    chapters_outlines = detect_chapters_from_outlines_reader(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        location=location,
        entries=outline_entries,
    )
    if chapters_outlines:
        confidence = _confidence_for_outlines(outline_entries, chapters_outlines)
        return ChapterDetectionReport(
            strategy="outlines",
            chapters=tuple(chapters_outlines),
            confidence=confidence,
            warnings=tuple(warnings),
            outline_entries=len(outline_entries),
            toc_start_page=None,
            toc_pages_scanned=0,
        )

    if not detection_config.enable_toc_fallback:
        warnings.append("No chapters detected from outlines and TOC fallback is disabled.")
        return ChapterDetectionReport(
            strategy="none",
            chapters=(),
            confidence=0.0,
            warnings=tuple(warnings),
            outline_entries=len(outline_entries),
            toc_start_page=None,
            toc_pages_scanned=0,
        )

    toc_report = detect_best_toc_chapters(
        reader=reader,
        total_pages=total_pages,
        detection=detection_config,
        deadline=deadline,
        token=token,
        toc_hint_page=toc_hint,
        location=location,
    )
    warnings.extend(toc_report.warnings)
    if toc_report.chapters:
        return ChapterDetectionReport(
            strategy="toc",
            chapters=tuple(toc_report.chapters),
            confidence=toc_report.confidence,
            warnings=tuple(warnings),
            outline_entries=len(outline_entries),
            toc_start_page=toc_report.toc_start_page,
            toc_pages_scanned=toc_report.pages_scanned,
        )
    warnings.append("No chapters detected from outlines or TOC.")
    return ChapterDetectionReport(
        strategy="none",
        chapters=(),
        confidence=0.0,
        warnings=tuple(warnings),
        outline_entries=len(outline_entries),
        toc_start_page=toc_report.toc_start_page,
        toc_pages_scanned=toc_report.pages_scanned,
    )


def _confidence_for_outlines(
    outline_entries: list[tuple[str, int]],
    chapters: list[ChapterDefinition],
) -> float:
    """Estimate confidence for outline-derived chapters.

    Summary:
        Provide a conservative confidence estimate based on how many outline entries were usable.
    Inputs:
        - outline_entries: Extracted outline (title, page) pairs.
        - chapters: Parsed chapters derived from outline entries.
    Outputs:
        - Confidence score in the range [0.0, 1.0].
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by detect_chapters_in_reader when outlines detection succeeds.
    Why this exists:
        The GUI needs a simple confidence signal to communicate result quality without exposing
        internals.
    """
    if not chapters:
        return 0.0
    if len(outline_entries) >= 3:
        return 0.92
    if len(outline_entries) == 2:
        return 0.85
    return 0.75


def format_detection_report(report: ChapterDetectionReport) -> str:
    """Format a ChapterDetectionReport for display in a dialog.

    Summary:
        Produce a concise, human-readable description of strategy, chapter count, confidence, and
        warnings.
    Inputs:
        - report: Detection report to format.
    Outputs:
        - Multi-line string suitable for message boxes.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by the GUI workflow after detect_chapters_in_reader completes.
    Why this exists:
        Keeping formatting centralized avoids UI-specific string logic scattered across callbacks.
    """
    percent = int(round(max(0.0, min(1.0, report.confidence)) * 100))
    base = (
        f"Detected {len(report.chapters)} chapters via {report.strategy} ({percent}% confidence)."
    )
    if report.strategy == "toc" and report.toc_start_page is not None:
        base = (
            f"Detected {len(report.chapters)} chapters via toc starting at page "
            f"{report.toc_start_page} ({percent}% confidence)."
        )
    if not report.warnings:
        return base
    return base + "\n\nWarnings:\n- " + "\n- ".join(report.warnings)
