"""Rate limiting helpers to prevent repeated actions."""

from __future__ import annotations

import time

from ..core.errors import ValidationError, format_error_message


class RateLimiter:
    """Simple time based rate limiter.

    Purpose:
        Throttle repeated actions to avoid UI or IO overload.
    Ties To:
        Used by UI action handlers and viewer launch logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        """Initialize the rate limiter.

        Purpose:
            Limit how often an action can run to avoid UI or IO overload.
        Ties To:
            Used by UI actions and viewer launch logic.
        Inputs:
            - min_interval_seconds: Minimum interval between actions.
        Outputs:
            - None.
        Side Effects:
            Stores the initial last action time.
        Raises:
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
        self._last_action_time = 0.0

    def allow(self) -> bool:
        """Return whether a new action is allowed right now.

        Purpose:
            Enforce a minimum interval between repeated actions.
        Ties To:
            Called before auto detect and export actions in the UI.
        Inputs:
            - None.
        Outputs:
            - True when the action is allowed.
        Side Effects:
            Updates the last action time when allowed.
        Raises:
            - None.
        """
        now = time.monotonic()
        if now - self._last_action_time < self._min_interval_seconds:
            return False
        self._last_action_time = now
        return True
