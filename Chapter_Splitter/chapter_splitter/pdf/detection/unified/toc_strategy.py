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
    """Run forced TOC detection."""
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
    """Run the default TOC fallback branch."""
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
    """Run TOC chapter detection with shared configuration."""
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
