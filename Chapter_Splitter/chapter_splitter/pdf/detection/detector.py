"""Unified chapter detection public API facade."""

from __future__ import annotations

from .unified import (
    DetectionRequest,
    UnifiedReaderProtocol,
    detect_chapters,
    detect_chapters_in_reader,
    format_detection_report,
)

__all__ = [
    "DetectionRequest",
    "UnifiedReaderProtocol",
    "detect_chapters",
    "detect_chapters_in_reader",
    "format_detection_report",
]
