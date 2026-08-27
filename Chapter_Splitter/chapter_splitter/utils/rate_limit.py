"""Rate limiting helpers to prevent repeated actions."""

from __future__ import annotations

import time

from ..core.errors import ValidationError, format_error_message


class RateLimiter:
    """Simple time based rate limiter."""

    def __init__(self, min_interval_seconds: float) -> None:
        """Initialize the rate limiter."""
        if min_interval_seconds < 0:
            raise ValidationError(
                format_error_message(
                    "chapter_splitter.utils.rate_limit.RateLimiter.__init__",
                    "Minimum interval must be non negative.",
                )
            )
        self._min_interval_seconds = min_interval_seconds
        self._last_action_time: float | None = None

    def allow(self) -> bool:
        """Return whether a new action is allowed right now."""
        now = time.monotonic()
        if (
            self._last_action_time is not None
            and now - self._last_action_time < self._min_interval_seconds
        ):
            return False
        self._last_action_time = now
        return True
