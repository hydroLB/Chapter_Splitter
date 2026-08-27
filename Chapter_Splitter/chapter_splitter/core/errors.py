"""Error taxonomy and error message helpers for the application."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Typed error code values for stable cross-boundary handling."""

    UNKNOWN = "CHAPTER_SPLITTER_UNKNOWN"
    CONFIGURATION = "CHAPTER_SPLITTER_CONFIGURATION"
    VALIDATION = "CHAPTER_SPLITTER_VALIDATION"
    PDF_PROCESSING = "CHAPTER_SPLITTER_PDF_PROCESSING"
    IO = "CHAPTER_SPLITTER_IO"
    UI = "CHAPTER_SPLITTER_UI"
    CANCELLATION = "CHAPTER_SPLITTER_CANCELLATION"
    INTERNAL = "CHAPTER_SPLITTER_INTERNAL"


class ChapterSplitterError(Exception):
    """Base class for all application errors."""

    default_code: ErrorCode = ErrorCode.UNKNOWN

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        """Initialize a ChapterSplitterError with a message."""
        self.code: ErrorCode = code or self.default_code
        super().__init__(message)


class ConfigurationError(ChapterSplitterError):
    """Error raised when configuration loading or validation fails."""

    default_code = ErrorCode.CONFIGURATION


class ValidationError(ChapterSplitterError):
    """Error raised when input validation fails."""

    default_code = ErrorCode.VALIDATION


class PdfProcessingError(ChapterSplitterError):
    """Error raised when PDF parsing or writing fails."""

    default_code = ErrorCode.PDF_PROCESSING


class IoError(ChapterSplitterError):
    """Error raised when file system or process IO fails."""

    default_code = ErrorCode.IO


class UiError(ChapterSplitterError):
    """Error raised when UI workflows or widgets fail."""

    default_code = ErrorCode.UI


class CancellationError(ChapterSplitterError):
    """Error raised when an operation is cancelled or times out."""

    default_code = ErrorCode.CANCELLATION


def format_error_message(location: str, detail: str) -> str:
    """Create a clear, location aware error message."""
    return f"{location} failed. {detail}"
