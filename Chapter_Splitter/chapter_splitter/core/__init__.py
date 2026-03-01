"""Public core API for domain models, errors, and runtime controls."""

from __future__ import annotations

from .error_mapping import ErrorPayload, map_error
from .errors import (
    CancellationError,
    ChapterSplitterError,
    ConfigurationError,
    ErrorCode,
    IoError,
    PdfProcessingError,
    UiError,
    ValidationError,
    format_error_message,
)
from .models import ChapterDefinition, ChapterOutput, PageRange
from .runtime import CancellationToken, register_signal_handlers
from .validation import validate_chapters, validate_page_range

__all__ = [
    "CancellationError",
    "CancellationToken",
    "ChapterDefinition",
    "ChapterOutput",
    "ChapterSplitterError",
    "ConfigurationError",
    "ErrorCode",
    "ErrorPayload",
    "IoError",
    "PageRange",
    "PdfProcessingError",
    "UiError",
    "ValidationError",
    "format_error_message",
    "map_error",
    "register_signal_handlers",
    "validate_chapters",
    "validate_page_range",
]
