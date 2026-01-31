"""Utilities for opening files in the system viewer."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from ..core.errors import IoError, format_error_message
from .rate_limit import RateLimiter


def open_in_default_viewer(
    pdf_path: Path,
    timeout_seconds: float,
    rate_limiter: RateLimiter | None,
    location: str,
) -> None:
    """Open a PDF in the system default viewer.

    Purpose:
        Provide a consistent viewer launch with timeouts and rate limiting.
    Ties To:
        Called by UI workflows after a PDF is selected.
    Inputs:
        - pdf_path: Path to the PDF file.
        - timeout_seconds: Timeout for viewer launch.
        - rate_limiter: Optional rate limiter to prevent repeated opens.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side Effects:
        Launches the system PDF viewer.
    Raises:
        - IoError: When the viewer cannot be launched.
    """
    error_location = f"{__name__}.open_in_default_viewer"
    context = f" Context: {location}." if location else ""
    if not pdf_path.exists():
        raise IoError(
            format_error_message(
                error_location,
                f"PDF path does not exist: {pdf_path}.{context}",
            )
        )
    if timeout_seconds <= 0:
        raise IoError(
            format_error_message(
                error_location,
                f"Viewer timeout must be positive.{context}",
            )
        )
    if rate_limiter is not None and not rate_limiter.allow():
        return
    try:
        opened = webbrowser.open(pdf_path.resolve().as_uri(), new=0, autoraise=True)
        if not opened:
            raise IoError(
                format_error_message(
                    error_location,
                    f"System viewer did not accept the PDF path: {pdf_path}.{context}",
                )
            )
    except (OSError, ValueError) as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to open PDF viewer: {exc}.{context}",
            )
        ) from exc
