"""PDF reader helpers with retries and timeouts."""

from __future__ import annotations

from pathlib import Path

from pypdf.errors import FileNotDecryptedError, PdfReadError  # type: ignore[attr-defined]

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
    """Load a PdfReader with retries and deadline checks."""
    error_location = f"{__name__}.load_reader"
    context = f" Context: {location}." if location else ""
    if not pdf_path.exists():
        raise IoError(
            format_error_message(error_location, f"PDF path does not exist: {pdf_path}.{context}")
        )
    if not pdf_path.is_file():
        raise IoError(
            format_error_message(error_location, f"PDF path is not a file: {pdf_path}.{context}")
        )

    def _open() -> PdfReader:
        """Open a PDF reader instance."""
        token.check(location)
        deadline.check(location)
        try:
            return PdfReader(str(pdf_path))
        except FileNotDecryptedError as exc:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"PDF is encrypted and requires a password: {pdf_path}.{context}",
                )
            ) from exc
        except PdfReadError as exc:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"Invalid PDF content: {pdf_path}. The file may be damaged or unsupported."
                    f"{context}",
                )
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
        source_error = exc.__cause__ if isinstance(exc.__cause__, OSError) else exc
        raise IoError(
            format_error_message(error_location, f"Unable to load PDF: {pdf_path}.{context}")
        ) from source_error


def get_total_pages(reader: PdfReader, location: str) -> int:
    """Return page count for the given reader."""
    error_location = f"{__name__}.get_total_pages"
    context = f" Context: {location}." if location else ""
    try:
        total_pages = len(reader.pages)
    except FileNotDecryptedError as exc:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"Unable to read PDF pages because the file is encrypted and requires a password."
                f"{context}",
            )
        ) from exc
    except PdfReadError as exc:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"Unable to read the PDF page count. The file may be damaged or unsupported."
                f"{context}",
            )
        ) from exc
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Unable to read the PDF page count from storage.{context}",
            )
        ) from exc
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF has no pages.{context}")
        )
    return total_pages
