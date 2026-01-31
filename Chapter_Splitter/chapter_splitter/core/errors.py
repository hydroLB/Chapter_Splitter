"""Error taxonomy and error message helpers for the application."""

from __future__ import annotations


class ChapterSplitterError(Exception):
    """Base class for all application errors.

    Purpose:
        Provide a common error type for all application specific failures.
    Ties To:
        Inherited by configuration, validation, PDF, IO, UI, and cancellation errors.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, message: str) -> None:
        """Initialize a ChapterSplitterError with a message.

        Purpose:
            Store a clear error message for downstream handling and logging.
        Ties To:
            Used by all custom exceptions in the application.
        Inputs:
            - message: Error message string.
        Outputs:
            - None.
        Side Effects:
            Initializes the exception base class.
        Raises:
            - None.
        """
        super().__init__(message)


class ConfigurationError(ChapterSplitterError):
    """Error raised when configuration loading or validation fails.

    Purpose:
        Signal configuration issues with consistent error typing.
    Ties To:
        Used by config loading, schema validation, and registry logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


class ValidationError(ChapterSplitterError):
    """Error raised when input validation fails.

    Purpose:
        Represent invalid user or file inputs during validation steps.
    Ties To:
        Used by validators, CLI parsing, and UI input handling.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


class PdfProcessingError(ChapterSplitterError):
    """Error raised when PDF parsing or writing fails.

    Purpose:
        Identify PDF parsing, metadata, and writing failures.
    Ties To:
        Used by PDF loader, outline detection, and splitting logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


class IoError(ChapterSplitterError):
    """Error raised when file system or process IO fails.

    Purpose:
        Signal errors interacting with files or external processes.
    Ties To:
        Used by chapter file loading, viewer launching, and PDF output.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


class UiError(ChapterSplitterError):
    """Error raised when UI workflows or widgets fail.

    Purpose:
        Distinguish UI failures from core or IO errors.
    Ties To:
        Used by Tk dialogs, window builders, and grid widgets.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


class CancellationError(ChapterSplitterError):
    """Error raised when an operation is cancelled or times out.

    Purpose:
        Report cancellations and timeouts in a consistent error type.
    Ties To:
        Used by Deadline, CancellationToken, and long running operations.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """


def format_error_message(location: str, detail: str) -> str:
    """Create a clear, location aware error message.

    Purpose:
        Provide a consistent error message format for all raised exceptions.
    Ties To:
        Used by config loaders, validators, PDF processing, and UI workflows.
    Inputs:
        - location: Fully qualified module and method name.
        - detail: Human readable explanation of the failure.
    Outputs:
        - A formatted error message string.
    Side Effects:
        None.
    Raises:
        - None.
    """
    return f"{location} failed. {detail}"
