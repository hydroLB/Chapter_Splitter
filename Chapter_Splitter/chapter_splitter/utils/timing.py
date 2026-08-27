"""Timing utilities for deadlines and timeouts."""

from __future__ import annotations

import math
import time

from ..core.errors import CancellationError, format_error_message


class Deadline:
    """Track an operation deadline and enforce timeouts."""

    def __init__(self, timeout_seconds: float) -> None:
        """Initialize a deadline timer."""
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise CancellationError(
                format_error_message(
                    "chapter_splitter.utils.timing.Deadline.__init__",
                    "Timeout must be positive.",
                )
            )
        self._timeout_seconds = timeout_seconds
        self._start_time = time.monotonic()

    def check(self, location: str) -> None:
        """Raise when the deadline has been exceeded."""
        error_location = f"{__name__}.Deadline.check"
        context = f" Context: {location}." if location else ""
        if self.elapsed_seconds() > self._timeout_seconds:
            raise CancellationError(
                format_error_message(error_location, f"Operation timed out.{context}")
            )

    def elapsed_seconds(self) -> float:
        """Return elapsed time since the deadline started."""
        return time.monotonic() - self._start_time
