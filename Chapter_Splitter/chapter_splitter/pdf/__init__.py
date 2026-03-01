"""Public PDF API covering detection, IO, and splitting."""

from __future__ import annotations

from .detection import (
    ChapterDetectionReport,
    DetectionRequest,
    detect_chapters,
    detect_chapters_from_outlines,
    detect_chapters_from_toc_page,
    detect_chapters_in_reader,
    format_detection_report,
)
from .io import (
    PdfReader,
    PdfWriter,
    extract_page_labels,
    get_total_pages,
    infer_page_offset_from_labels,
    load_reader,
)
from .splitting import ChapterExportProgress, split_pdf_into_chapters

__all__ = [
    "ChapterDetectionReport",
    "ChapterExportProgress",
    "DetectionRequest",
    "PdfReader",
    "PdfWriter",
    "detect_chapters",
    "detect_chapters_in_reader",
    "detect_chapters_from_outlines",
    "detect_chapters_from_toc_page",
    "extract_page_labels",
    "format_detection_report",
    "get_total_pages",
    "infer_page_offset_from_labels",
    "load_reader",
    "split_pdf_into_chapters",
]
