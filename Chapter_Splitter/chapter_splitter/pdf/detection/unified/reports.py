"""Report helpers for unified chapter detection."""

from __future__ import annotations

from ....core.models import ChapterDefinition
from ..report import ChapterDetectionReport
from ..toc import TocDetectionReport


def build_none_report(
    *,
    warnings: list[str],
    outline_entries: int,
    toc_start_page: int | None,
    toc_pages_scanned: int,
) -> ChapterDetectionReport:
    """Build a no-result detection report.

    Summary:
        Produce the canonical report shape used when no chapters were detected.
    Inputs:
        - warnings: Accumulated warnings explaining why detection failed.
        - outline_entries: Number of outline entries examined.
        - toc_start_page: Optional TOC start page used during fallback scanning.
        - toc_pages_scanned: Number of TOC pages scanned.
    Outputs:
        - ChapterDetectionReport with strategy set to "none".
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by service helpers for forced and fallback detection branches.
    Why this exists:
        Keeping the empty-report shape centralized avoids repeated construction logic.
    """
    return ChapterDetectionReport(
        strategy="none",
        chapters=(),
        confidence=0.0,
        warnings=tuple(warnings),
        outline_entries=outline_entries,
        toc_start_page=toc_start_page,
        toc_pages_scanned=toc_pages_scanned,
    )


def build_outlines_report(
    *,
    chapters: list[ChapterDefinition],
    warnings: list[str],
    outline_entries: list[tuple[str, int]],
) -> ChapterDetectionReport:
    """Build an outline-strategy detection report.

    Summary:
        Convert outline-derived chapter results into the shared report payload.
    Inputs:
        - chapters: Chapters derived from outline entries.
        - warnings: Accumulated warning messages.
        - outline_entries: Outline entries examined during detection.
    Outputs:
        - ChapterDetectionReport with strategy set to "outlines".
    Side effects:
        None.
    Error handling:
        Returns a zero-confidence report when no chapters were produced.
    Ties to other methods:
        Used by service helpers after successful outline detection.
    Why this exists:
        Centralizing report creation keeps confidence and metadata rules consistent.
    """
    return ChapterDetectionReport(
        strategy="outlines",
        chapters=tuple(chapters),
        confidence=confidence_for_outlines(outline_entries, chapters),
        warnings=tuple(warnings),
        outline_entries=len(outline_entries),
        toc_start_page=None,
        toc_pages_scanned=0,
    )


def build_toc_report(
    *,
    toc_report: TocDetectionReport,
    warnings: list[str],
    outline_entries: int,
) -> ChapterDetectionReport:
    """Build a TOC-strategy detection report.

    Summary:
        Convert a TOC detection result into the shared chapter detection report payload.
    Inputs:
        - toc_report: Raw TOC detection result.
        - warnings: Accumulated warning messages.
        - outline_entries: Number of outline entries examined earlier in the pipeline.
    Outputs:
        - ChapterDetectionReport with strategy set to "toc".
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by service helpers after TOC detection succeeds.
    Why this exists:
        The unified detector should present TOC results in the same structure as other strategies.
    """
    return ChapterDetectionReport(
        strategy="toc",
        chapters=tuple(toc_report.chapters),
        confidence=toc_report.confidence,
        warnings=tuple(warnings),
        outline_entries=outline_entries,
        toc_start_page=toc_report.toc_start_page,
        toc_pages_scanned=toc_report.pages_scanned,
    )


def confidence_for_outlines(
    outline_entries: list[tuple[str, int]],
    chapters: list[ChapterDefinition],
) -> float:
    """Estimate confidence for outline-derived chapters.

    Summary:
        Provide a conservative confidence estimate based on how many outline entries were usable.
    Inputs:
        - outline_entries: Extracted outline title and page pairs.
        - chapters: Parsed chapters derived from outline entries.
    Outputs:
        - Confidence score in the range [0.0, 1.0].
    Side effects:
        None.
    Error handling:
        Returns 0.0 when no chapters were produced.
    Ties to other methods:
        Used by build_outlines_report.
    Why this exists:
        The GUI needs a simple signal for result quality without exposing raw heuristics.
    """
    if not chapters:
        return 0.0
    if len(outline_entries) >= 3:
        return 0.92
    if len(outline_entries) == 2:
        return 0.85
    return 0.75


__all__ = [
    "build_none_report",
    "build_outlines_report",
    "build_toc_report",
    "confidence_for_outlines",
]
