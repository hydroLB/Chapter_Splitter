"""Rate limiting helpers to prevent repeated actions."""

from __future__ import annotations

import time

from ..core.errors import ValidationError, format_error_message


class RateLimiter:
    """Simple time based rate limiter.

    Summary:
        Throttle repeated actions to avoid UI or IO overload.
    Ties to other methods:
        Used by UI action handlers and viewer launch logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        """Initialize the rate limiter.

        Summary:
            Limit how often an action can run to avoid UI or IO overload.
        Ties to other methods:
            Used by UI actions and viewer launch logic.
        Inputs:
            - min_interval_seconds: Minimum interval between actions.
        Outputs:
            - None.
        Side effects:
            Stores the initial last action time.
        Error handling:
            - ValidationError: When the interval is negative.
        """
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
        """Return whether a new action is allowed right now.

        Summary:
            Enforce a minimum interval between repeated actions.
        Ties to other methods:
            Called before auto detect and export actions in the UI.
        Inputs:
            - None.
        Outputs:
            - True when the action is allowed.
        Side effects:
            Updates the last action time when allowed.
        Error handling:
            - None.
        """
        now = time.monotonic()
        if (
            self._last_action_time is not None
            and now - self._last_action_time < self._min_interval_seconds
        ):
            return False
        self._last_action_time = now
        return True
