"""Internal unified chapter detection package."""

from __future__ import annotations

from .formatting import format_detection_report
from .request import DetectionRequest, UnifiedReaderProtocol
from .service import detect_chapters_in_reader
from .source import detect_chapters

__all__ = [
    "DetectionRequest",
    "UnifiedReaderProtocol",
    "detect_chapters",
    "detect_chapters_in_reader",
    "format_detection_report",
]
