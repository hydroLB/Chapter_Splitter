"""Unit tests for retry and rate-limiting helpers."""

from __future__ import annotations

import random
import time

import pytest

from chapter_splitter.core import CancellationError, CancellationToken, IoError, ValidationError
from chapter_splitter.utils import RateLimiter, retry_with_backoff


def test_retry_with_backoff_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify retry helper retries transient failures before succeeding.

    Purpose:
        Prevent one-off failures from breaking workflows.
    Ties To:
        Covers chapter_splitter.utils.retry.retry_with_backoff.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches time.sleep and random.random for determinism.
    Raises:
        - None.
    """
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(random, "random", lambda: 0.0)

    calls: list[int] = []

    def action() -> str:
        calls.append(len(calls) + 1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    seen: list[int] = []

    def on_retry(attempt: int, _exc: BaseException) -> None:
        seen.append(attempt)

    assert (
        retry_with_backoff(
            action=action,
            exceptions=(ValueError,),
            max_attempts=5,
            initial_delay_seconds=0.01,
            max_delay_seconds=0.5,
            jitter_ratio=0.0,
            location="tests.unit.test_retry_and_rate_limit",
            on_retry=on_retry,
            token=None,
        )
        == "ok"
    )
    assert seen == [1, 2]
    assert sleeps


def test_retry_with_backoff_exhaustion_raises_io_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify exhaustion raises a stable IoError.

    Purpose:
        Keep error handling consistent at workflow boundaries.
    Ties To:
        Covers chapter_splitter.utils.retry.retry_with_backoff.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches time.sleep for determinism.
    Raises:
        - None.
    """
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def action() -> None:
        raise ValueError("always")

    with pytest.raises(IoError):
        retry_with_backoff(
            action=action,
            exceptions=(ValueError,),
            max_attempts=2,
            initial_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter_ratio=0.0,
            location="tests.unit.test_retry_and_rate_limit",
        )


def test_retry_with_backoff_validates_attempt_count() -> None:
    """Verify invalid attempt count is rejected.

    Purpose:
        Prevent silent retry misconfiguration.
    Ties To:
        Covers chapter_splitter.utils.retry.retry_with_backoff.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(IoError):
        retry_with_backoff(
            action=lambda: "x",
            exceptions=(Exception,),
            max_attempts=0,
            initial_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter_ratio=0.0,
            location="tests.unit.test_retry_and_rate_limit",
        )


def test_retry_with_backoff_rejects_invalid_delay_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify invalid delay bounds are rejected with a stable IoError.

    Purpose:
        Prevent invalid retry configuration from failing later with low-signal exceptions.
    Ties To:
        Covers chapter_splitter.utils.retry.retry_with_backoff.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches time.sleep for determinism.
    Raises:
        - None.
    """
    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if seconds < 0:
            raise ValueError(f"sleep length must be non-negative, got {seconds}")

    monkeypatch.setattr(time, "sleep", _sleep)

    def action() -> None:
        raise ValueError("always")

    with pytest.raises(IoError):
        retry_with_backoff(
            action=action,
            exceptions=(ValueError,),
            max_attempts=2,
            initial_delay_seconds=0.1,
            max_delay_seconds=-1.0,
            jitter_ratio=0.0,
            location="tests.unit.test_retry_and_rate_limit",
        )
    assert not sleeps


def test_retry_with_backoff_respects_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify cancellation stops the retry loop.

    Purpose:
        Ensure long-running retries have a clear cancellation path.
    Ties To:
        Covers chapter_splitter.utils.retry.retry_with_backoff.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Cancels a token before retries.
    Raises:
        - None.
    """
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    token = CancellationToken()
    token.cancel("stop", "tests.unit.test_retry_and_rate_limit")

    with pytest.raises(CancellationError):
        retry_with_backoff(
            action=lambda: (_ for _ in ()).throw(ValueError("x")),
            exceptions=(ValueError,),
            max_attempts=3,
            initial_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter_ratio=0.0,
            location="tests.unit.test_retry_and_rate_limit",
            token=token,
        )


def test_rate_limiter_enforces_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the rate limiter enforces a minimum interval.

    Purpose:
        Prevent UI actions from being triggered too rapidly.
    Ties To:
        Covers chapter_splitter.utils.rate_limit.RateLimiter.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches time.monotonic for determinism.
    Raises:
        - None.
    """
    times = iter([1.0, 1.1, 2.1])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    limiter = RateLimiter(1.0)
    assert limiter.allow() is True
    assert limiter.allow() is False
    assert limiter.allow() is True


def test_rate_limiter_rejects_negative_interval() -> None:
    """Verify negative interval is rejected.

    Purpose:
        Keep configuration strict and avoid surprising behavior.
    Ties To:
        Covers RateLimiter.__init__ validation.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ValidationError):
        RateLimiter(-1.0)


def test_rate_limiter_allows_first_action_at_time_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the first action is allowed even when monotonic starts at zero.

    Purpose:
        Ensure the rate limiter does not mistakenly block the initial action on platforms where
        time.monotonic() can return 0.0 at process start.
    Ties To:
        Covers chapter_splitter.utils.rate_limit.RateLimiter.allow.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches time.monotonic for determinism.
    Raises:
        - None.
    """
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    limiter = RateLimiter(1.0)
    assert limiter.allow() is True
