"""Chapter Splitter public package API."""

from __future__ import annotations

from .config import Settings, load_config
from .config.loader import load_settings
from .core import (
    CancellationError,
    CancellationToken,
    ChapterDefinition,
    ChapterOutput,
    ChapterSplitterError,
    ConfigurationError,
    IoError,
    PdfProcessingError,
    ValidationError,
)
from .io import ChapterFileSessionMetadata, load_chapter_file, write_chapter_file
from .pdf import (
    ChapterDetectionReport,
    ChapterExportProgress,
    DetectionRequest,
    detect_chapters,
    detect_chapters_from_outlines,
    split_pdf_into_chapters,
)

__all__ = [
    "CancellationError",
    "CancellationToken",
    "ChapterDefinition",
    "ChapterDetectionReport",
    "ChapterExportProgress",
    "ChapterFileSessionMetadata",
    "ChapterOutput",
    "ChapterSplitterError",
    "ConfigurationError",
    "DetectionRequest",
    "IoError",
    "PdfProcessingError",
    "Settings",
    "ValidationError",
    "detect_chapters",
    "detect_chapters_from_outlines",
    "load_chapter_file",
    "load_config",
    "load_settings",
    "split_pdf_into_chapters",
    "write_chapter_file",
]
