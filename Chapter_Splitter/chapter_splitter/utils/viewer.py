"""Utilities for opening files in the system viewer."""

from __future__ import annotations

import math
import threading
import webbrowser
from pathlib import Path

from ..core.errors import IoError, format_error_message
from .rate_limit import RateLimiter


def open_path_in_default_viewer(
    path: Path,
    timeout_seconds: float,
    rate_limiter: RateLimiter | None,
    location: str,
) -> None:
    """Open a file or directory in the system default viewer.

    Summary:
        Open a filesystem path in the default system viewer using a shared implementation for PDFs
        and output folders.
    Inputs:
        - path: Filesystem path to open.
        - timeout_seconds: Timeout for viewer launch.
        - rate_limiter: Optional rate limiter to prevent repeated opens.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Launches the system default viewer for the provided path.
    Error handling:
        Raises IoError with a location-tagged message when the path is invalid or the viewer fails.
    Ties to other methods:
        Used by open_in_default_viewer and the GUI export flow when opening output folders.
    Why this exists:
        The GUI needs to open both PDFs and directories while keeping behavior consistent and
        centrally validated.
    """
    error_location = f"{__name__}.open_path_in_default_viewer"
    context = f" Context: {location}." if location else ""
    if not isinstance(path, Path):
        raise IoError(format_error_message(error_location, f"path must be a Path.{context}"))
    if not path.exists():
        raise IoError(
            format_error_message(
                error_location,
                f"Path does not exist: {path}.{context}",
            )
        )
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise IoError(
            format_error_message(
                error_location,
                f"Viewer timeout must be positive.{context}",
            )
        )
    if rate_limiter is not None and not rate_limiter.allow():
        return
    opened: bool | None = None
    worker_error: Exception | None = None

    def _launch_viewer() -> None:
        nonlocal opened, worker_error
        try:
            opened = webbrowser.open(path.resolve().as_uri(), new=0, autoraise=True)
        except (OSError, ValueError) as exc:
            worker_error = exc

    thread = threading.Thread(
        target=_launch_viewer,
        name="chapter_splitter.utils.viewer.open_path_in_default_viewer",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise IoError(
            format_error_message(
                error_location,
                f"System viewer timed out after {timeout_seconds} seconds: {path}.{context}",
            )
        )
    if worker_error is not None:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to open system viewer: {worker_error}.{context}",
            )
        ) from worker_error
    if not opened:
        raise IoError(
            format_error_message(
                error_location,
                f"System viewer did not accept the path: {path}.{context}",
            )
        )


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
    open_path_in_default_viewer(pdf_path, timeout_seconds, rate_limiter, location)
