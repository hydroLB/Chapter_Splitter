"""PDF reader helpers with retries and timeouts."""

from __future__ import annotations

from pathlib import Path

from pypdf.errors import PdfReadError

from ...config.schema import RetryConfig
from ...core.errors import IoError, PdfProcessingError, format_error_message
from ...core.runtime import CancellationToken
from ...utils.retry import retry_with_backoff
from ...utils.timing import Deadline
from .dependencies import PdfReader


def load_reader(
    pdf_path: Path,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    location: str,
) -> PdfReader:
    """Load a PdfReader with retries and deadline checks.

    Purpose:
        Provide resilient PDF loading with clear error reporting.
    Ties To:
        Used by outline detection and splitting workflows.
    Inputs:
        - pdf_path: Path to the PDF file.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - retry_config: Retry configuration for transient failures.
        - location: Fully qualified module and method name.
    Outputs:
        - PdfReader instance.
    Side Effects:
        Reads the PDF file from disk.
    Raises:
        - IoError: When the file cannot be read after retries.
        - PdfProcessingError: When the PDF content is invalid.
    """
    error_location = f"{__name__}.load_reader"
    context = f" Context: {location}." if location else ""
    if not pdf_path.exists():
        raise IoError(
            format_error_message(error_location, f"PDF path does not exist: {pdf_path}.{context}")
        )

    def _open() -> PdfReader:
        """Open a PDF reader instance.

        Purpose:
            Isolate reader creation for retry and timeout control.
        Ties To:
            Used by load_reader as the retried action.
        Inputs:
            - None.
        Outputs:
            - PdfReader instance.
        Side Effects:
            Opens the PDF file from disk.
        Raises:
            - PdfProcessingError: When the PDF content is invalid.
        """
        token.check(location)
        deadline.check(location)
        try:
            return PdfReader(str(pdf_path))
        except PdfReadError as exc:
            raise PdfProcessingError(
                format_error_message(error_location, f"Invalid PDF content: {pdf_path}.{context}")
            ) from exc

    try:
        return retry_with_backoff(
            _open,
            exceptions=(OSError,),
            max_attempts=retry_config.max_attempts,
            initial_delay_seconds=retry_config.initial_delay_seconds,
            max_delay_seconds=retry_config.max_delay_seconds,
            jitter_ratio=retry_config.jitter_ratio,
            location=location,
            token=token,
        )
    except IoError as exc:
        raise IoError(
            format_error_message(error_location, f"Unable to load PDF: {pdf_path}.{context}")
        ) from exc


def get_total_pages(reader: PdfReader, location: str) -> int:
    """Return page count for the given reader.

    Purpose:
        Provide a clear, validated page count for a PDF reader.
    Ties To:
        Used by splitting and validation workflows.
    Inputs:
        - reader: PdfReader instance.
        - location: Fully qualified module and method name.
    Outputs:
        - Total page count.
    Side Effects:
        None.
    Raises:
        - PdfProcessingError: When the reader has no pages.
    """
    error_location = f"{__name__}.get_total_pages"
    context = f" Context: {location}." if location else ""
    total_pages = len(reader.pages)
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF has no pages.{context}")
        )
    return total_pages
