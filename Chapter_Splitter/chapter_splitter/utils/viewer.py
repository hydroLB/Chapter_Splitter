"""Utilities for opening files in the system viewer."""

from __future__ import annotations

import math
import os
import subprocess  # nosec B404
import sys
import threading
import webbrowser
from pathlib import Path
from shutil import which

from ..core.errors import IoError, format_error_message
from .rate_limit import RateLimiter


def _open_path_native(path: Path, location: str) -> bool:
    """Open a path using OS-native open mechanisms."""
    if sys.platform == "win32":
        # startfile uses ShellExecute and is the most native option on Windows.
        os.startfile(str(path))  # type: ignore[attr-defined]  # nosec B606
        return True

    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", str(path)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603 B607
        return True

    opener = which("xdg-open")
    if opener is not None:
        subprocess.Popen(
            [opener, str(path)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603
        return True

    gio = which("gio")
    if gio is not None:
        subprocess.Popen(
            [gio, "open", str(path)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603
        return True

    # Fall back to webbrowser when no native opener is available.
    return False


def open_path_in_default_viewer(
    path: Path,
    timeout_seconds: float,
    rate_limiter: RateLimiter | None,
    location: str,
) -> None:
    """Open a file or directory in the system default viewer."""
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
            resolved = path.resolve()
            if _open_path_native(resolved, location):
                opened = True
                return
            opened = webbrowser.open(resolved.as_uri(), new=0, autoraise=True)
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
