"""Retry helpers with exponential backoff and jitter."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Callable
from typing import TypeVar

from ..core.errors import IoError, format_error_message
from ..core.runtime import CancellationToken

T = TypeVar("T")


def retry_with_backoff(
    action: Callable[[], T],
    exceptions: tuple[type[BaseException], ...],
    max_attempts: int,
    initial_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float,
    location: str,
    on_retry: Callable[[int, BaseException], None] | None = None,
    token: CancellationToken | None = None,
) -> T:
    """Retry an action with exponential backoff and jitter.

    Summary:
        Provide a centralized retry policy for transient failures.
    Ties to other methods:
        Used by PDF loading and viewer launch operations.
    Inputs:
        - action: Callable to execute.
        - exceptions: Exception types to retry.
        - max_attempts: Maximum retry attempts.
        - initial_delay_seconds: Initial delay between attempts.
        - max_delay_seconds: Maximum delay between attempts.
        - jitter_ratio: Jitter ratio applied to the delay.
        - location: Fully qualified module and method name.
        - on_retry: Optional callback executed before each retry.
        - token: Optional cancellation token to stop retries.
    Outputs:
        - Result of the action when successful.
    Side effects:
        Sleeps between attempts.
    Error handling:
        - IoError: When all attempts fail.
    """
    error_location = f"{__name__}.retry_with_backoff"
    context = f" Context: {location}." if location else ""
    if max_attempts < 1:
        raise IoError(
            format_error_message(error_location, f"Retry attempts must be at least 1.{context}")
        )
    if not math.isfinite(initial_delay_seconds) or initial_delay_seconds < 0:
        raise IoError(
            format_error_message(
                error_location,
                f"Initial delay must be finite and non negative.{context}",
            )
        )
    if not math.isfinite(max_delay_seconds) or max_delay_seconds < 0:
        raise IoError(
            format_error_message(
                error_location,
                f"Max delay must be finite and non negative.{context}",
            )
        )
    if max_delay_seconds < initial_delay_seconds:
        raise IoError(
            format_error_message(
                error_location,
                f"Max delay must be >= initial delay.{context}",
            )
        )
    if not math.isfinite(jitter_ratio) or not 0 <= jitter_ratio <= 1:
        raise IoError(
            format_error_message(
                error_location,
                f"Jitter ratio must be finite and between 0 and 1.{context}",
            )
        )
    delay = max(0.0, initial_delay_seconds)
    for attempt in range(1, max_attempts + 1):
        if token is not None:
            token.check(location)
        try:
            return action()
        except exceptions as exc:
            if attempt >= max_attempts:
                raise IoError(
                    format_error_message(
                        error_location,
                        f"Retries exhausted after {attempt} attempts.{context}",
                    )
                ) from exc
            if on_retry is not None:
                on_retry(attempt, exc)
            jitter_unit = secrets.randbelow(1_000_000) / 1_000_000
            jitter = delay * jitter_ratio * jitter_unit
            sleep_for = max(0.0, min(max_delay_seconds, delay + jitter))
            if token is not None:
                token.check(location)
            time.sleep(sleep_for)
            delay = min(max_delay_seconds, delay * 2 if delay > 0 else 0.1)
    raise IoError(
        format_error_message(error_location, f"Retry loop terminated unexpectedly.{context}")
    )
