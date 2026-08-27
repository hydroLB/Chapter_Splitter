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
    """Build a no-result detection report."""
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
    """Build an outline-strategy detection report."""
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
    """Build a TOC-strategy detection report."""
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
    """Estimate confidence for outline-derived chapters."""
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
