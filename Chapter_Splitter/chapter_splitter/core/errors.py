"""Error taxonomy and error message helpers for the application."""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Typed error code values for stable cross-boundary handling.

    Summary:
        Provide a small, explicit error code set that remains stable across CLI, UI, and logs.
    Ties to other methods:
        Used by ChapterSplitterError subclasses and centralized error mapping.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    UNKNOWN = "CHAPTER_SPLITTER_UNKNOWN"
    CONFIGURATION = "CHAPTER_SPLITTER_CONFIGURATION"
    VALIDATION = "CHAPTER_SPLITTER_VALIDATION"
    PDF_PROCESSING = "CHAPTER_SPLITTER_PDF_PROCESSING"
    IO = "CHAPTER_SPLITTER_IO"
    UI = "CHAPTER_SPLITTER_UI"
    CANCELLATION = "CHAPTER_SPLITTER_CANCELLATION"
    INTERNAL = "CHAPTER_SPLITTER_INTERNAL"


class ChapterSplitterError(Exception):
    """Base class for all application errors.

    Summary:
        Provide a common error type for all application specific failures.
    Ties to other methods:
        Inherited by configuration, validation, PDF, IO, UI, and cancellation errors.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code: ErrorCode = ErrorCode.UNKNOWN

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        """Initialize a ChapterSplitterError with a message.

        Summary:
            Store a clear error message for downstream handling and logging.
        Ties to other methods:
            Used by all custom exceptions in the application.
        Inputs:
            - message: Error message string.
        Outputs:
            - None.
        Side effects:
            Initializes the exception base class.
        Error handling:
            - None.
        """
        self.code: ErrorCode = code or self.default_code
        super().__init__(message)


class ConfigurationError(ChapterSplitterError):
    """Error raised when configuration loading or validation fails.

    Summary:
        Signal configuration issues with consistent error typing.
    Ties to other methods:
        Used by config loading, schema validation, and registry logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.CONFIGURATION


class ValidationError(ChapterSplitterError):
    """Error raised when input validation fails.

    Summary:
        Represent invalid user or file inputs during validation steps.
    Ties to other methods:
        Used by validators, CLI parsing, and UI input handling.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.VALIDATION


class PdfProcessingError(ChapterSplitterError):
    """Error raised when PDF parsing or writing fails.

    Summary:
        Identify PDF parsing, metadata, and writing failures.
    Ties to other methods:
        Used by PDF loader, outline detection, and splitting logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.PDF_PROCESSING


class IoError(ChapterSplitterError):
    """Error raised when file system or process IO fails.

    Summary:
        Signal errors interacting with files or external processes.
    Ties to other methods:
        Used by chapter file loading, viewer launching, and PDF output.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.IO


class UiError(ChapterSplitterError):
    """Error raised when UI workflows or widgets fail.

    Summary:
        Distinguish UI failures from core or IO errors.
    Ties to other methods:
        Used by Tk dialogs, window builders, and grid widgets.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.UI


class CancellationError(ChapterSplitterError):
    """Error raised when an operation is cancelled or times out.

    Summary:
        Report cancellations and timeouts in a consistent error type.
    Ties to other methods:
        Used by Deadline, CancellationToken, and long running operations.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    default_code = ErrorCode.CANCELLATION


def format_error_message(location: str, detail: str) -> str:
    """Create a clear, location aware error message.

    Summary:
        Provide a consistent error message format for all raised exceptions.
    Ties to other methods:
        Used by config loaders, validators, PDF processing, and UI workflows.
    Inputs:
        - location: Fully qualified module and method name.
        - detail: Human readable explanation of the failure.
    Outputs:
        - A formatted error message string.
    Side effects:
        None.
    Error handling:
        - None.
    """
    return f"{location} failed. {detail}"
