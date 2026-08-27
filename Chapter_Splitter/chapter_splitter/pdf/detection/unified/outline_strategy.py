"""Outline-first strategy helpers for unified chapter detection."""

from __future__ import annotations

from ....config.schema import DetectionConfig
from ....core.models import ChapterDefinition
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ..outlines import detect_chapters_from_outlines_reader, extract_outline_entries
from ..report import ChapterDetectionReport
from .reports import build_none_report, build_outlines_report
from .request import UnifiedReaderProtocol


def extract_filtered_outline_entries(
    *,
    reader: UnifiedReaderProtocol,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    location: str,
) -> list[tuple[str, int]]:
    """Extract filtered outline entries for unified detection."""
    return extract_outline_entries(
        reader,
        deadline,
        token,
        location,
        outline_min_depth=detection_config.outline_min_depth,
        outline_ignore_title_regexes=detection_config.outline_ignore_title_regexes,
    )


def detect_forced_outlines(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    outline_entries: list[tuple[str, int]],
    warnings: list[str],
    location: str,
) -> ChapterDetectionReport:
    """Run forced outline detection."""
    chapters = _detect_outline_chapters(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        outline_entries=outline_entries,
        location=location,
    )
    if not chapters:
        warnings.append("No chapters detected from outlines.")
        return build_none_report(
            warnings=warnings,
            outline_entries=len(outline_entries),
            toc_start_page=None,
            toc_pages_scanned=0,
        )
    return build_outlines_report(
        chapters=chapters,
        warnings=warnings,
        outline_entries=outline_entries,
    )


def detect_preferred_outlines(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    outline_entries: list[tuple[str, int]],
    warnings: list[str],
    location: str,
) -> ChapterDetectionReport | None:
    """Try outlines before any TOC fallback."""
    chapters = _detect_outline_chapters(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        outline_entries=outline_entries,
        location=location,
    )
    if not chapters:
        return None
    return build_outlines_report(
        chapters=chapters,
        warnings=warnings,
        outline_entries=outline_entries,
    )


def _detect_outline_chapters(
    *,
    reader: UnifiedReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    detection_config: DetectionConfig,
    outline_entries: list[tuple[str, int]],
    location: str,
) -> list[ChapterDefinition]:
    """Run outline chapter detection with shared configuration."""
    return detect_chapters_from_outlines_reader(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        location=location,
        entries=outline_entries,
        outline_merge_tiny_max_pages=detection_config.outline_merge_tiny_max_pages,
        outline_merge_tiny_title_joiner=detection_config.outline_merge_tiny_title_joiner,
    )


__all__ = [
    "detect_forced_outlines",
    "detect_preferred_outlines",
    "extract_filtered_outline_entries",
]
