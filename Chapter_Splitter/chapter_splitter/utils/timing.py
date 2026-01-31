"""Timing utilities for deadlines and timeouts."""

from __future__ import annotations

import time

from ..core.errors import CancellationError, format_error_message


class Deadline:
    """Track an operation deadline and enforce timeouts.

    Purpose:
        Provide timeout tracking for IO and processing operations.
    Ties To:
        Used by PDF loading, splitting, and config timeouts.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, timeout_seconds: float) -> None:
        """Initialize a deadline timer.

        Purpose:
            Track elapsed time for long running operations.
        Ties To:
            Used by PDF processing and IO operations.
        Inputs:
            - timeout_seconds: Maximum allowed duration.
        Outputs:
            - None.
        Side Effects:
            Captures the start time for the deadline.
        Raises:
            - CancellationError: When timeout_seconds is not positive.
        """
        if timeout_seconds <= 0:
            raise CancellationError(
                format_error_message(
                    "chapter_splitter.utils.timing.Deadline.__init__",
                    "Timeout must be positive.",
                )
            )
        self._timeout_seconds = timeout_seconds
        self._start_time = time.monotonic()

    def check(self, location: str) -> None:
        """Raise when the deadline has been exceeded.

        Purpose:
            Enforce timeouts consistently across IO and processing loops.
        Ties To:
            Called by PDF splitting and outline detection.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - CancellationError: When the deadline has been exceeded.
        """
        error_location = f"{__name__}.Deadline.check"
        context = f" Context: {location}." if location else ""
        if self.elapsed_seconds() > self._timeout_seconds:
            raise CancellationError(
                format_error_message(error_location, f"Operation timed out.{context}")
            )

    def elapsed_seconds(self) -> float:
        """Return elapsed time since the deadline started.

        Purpose:
            Provide visibility into elapsed time for diagnostics.
        Ties To:
            Used by benchmark scripts and debug logging.
        Inputs:
            - None.
        Outputs:
            - Elapsed time in seconds.
        Side Effects:
            None.
        Raises:
            - None.
        """
        return time.monotonic() - self._start_time
