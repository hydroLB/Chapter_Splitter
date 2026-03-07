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
    """Extract filtered outline entries for unified detection.

    Summary:
        Read and normalize outline entries once so all strategy branches can reuse the result.
    Inputs:
        - reader: Reader supporting outline access.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection configuration containing outline filters.
        - location: Fully qualified caller location.
    Outputs:
        - List of normalized outline title and page pairs.
    Side effects:
        Reads outline metadata from the loaded PDF reader.
    Error handling:
        Propagates exceptions raised by extract_outline_entries.
    Ties to other methods:
        Used by detect_chapters_in_reader before choosing a strategy.
    Why this exists:
        Outline extraction is shared work and should not be repeated per branch.
    """
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
    """Run forced outline detection.

    Summary:
        Execute the outline strategy and return either a success report or an explicit empty one.
    Inputs:
        - reader: Reader supporting outline extraction.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics controlling outline merging.
        - outline_entries: Previously extracted outline entries.
        - warnings: Mutable warning accumulator.
        - location: Fully qualified caller location.
    Outputs:
        - ChapterDetectionReport for the forced outlines branch.
    Side effects:
        Reads outline-derived chapter information from the reader.
    Error handling:
        Returns a canonical empty report when no outline chapters are found.
    Ties to other methods:
        Used by detect_chapters_in_reader when request.force_strategy is "outlines".
    Why this exists:
        Forced strategies should remain explicit and easy to reason about.
    """
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
    """Try outlines before any TOC fallback.

    Summary:
        Run the preferred outline strategy and return a report only when it produced chapters.
    Inputs:
        - reader: Reader supporting outline extraction.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics controlling outline merging.
        - outline_entries: Previously extracted outline entries.
        - warnings: Mutable warning accumulator.
        - location: Fully qualified caller location.
    Outputs:
        - ChapterDetectionReport when outlines succeed, otherwise None.
    Side effects:
        Reads outline-derived chapter information from the reader.
    Error handling:
        Returns None when no outline chapters are found.
    Ties to other methods:
        Used by detect_chapters_in_reader in the default strategy path.
    Why this exists:
        The default pipeline prefers outlines when they are available and usable.
    """
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
    """Run outline chapter detection with shared configuration.

    Summary:
        Convert extracted outline entries into chapter definitions using the configured merge
        rules.
    Inputs:
        - reader: Reader supporting outline access.
        - total_pages: Total pages in the document.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - detection_config: Detection heuristics controlling outline merging.
        - outline_entries: Previously extracted outline entries.
        - location: Fully qualified caller location.
    Outputs:
        - List of detected chapter definitions.
    Side effects:
        Reads outline information from the PDF reader.
    Error handling:
        Propagates exceptions raised by detect_chapters_from_outlines_reader.
    Ties to other methods:
        Used by forced and preferred outline branches in this module.
    Why this exists:
        Outline detection parameters should be assembled in one place.
    """
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
