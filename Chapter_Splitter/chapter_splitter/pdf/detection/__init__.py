"""PDF detection helpers."""

from __future__ import annotations

from .detector import (
    DetectionRequest,
    detect_chapters,
    detect_chapters_in_reader,
    format_detection_report,
)
from .outlines import (
    OutlineReaderProtocol,
    detect_chapters_from_outlines,
    detect_chapters_from_outlines_reader,
    extract_outline_entries,
)
from .report import ChapterDetectionReport
from .toc import detect_chapters_from_toc_page

__all__ = [
    "ChapterDetectionReport",
    "DetectionRequest",
    "OutlineReaderProtocol",
    "detect_chapters",
    "detect_chapters_in_reader",
    "detect_chapters_from_outlines",
    "detect_chapters_from_outlines_reader",
    "detect_chapters_from_toc_page",
    "extract_outline_entries",
    "format_detection_report",
]
