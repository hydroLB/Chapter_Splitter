"""Minimal metrics abstraction with a no-op default implementation."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Protocol


class MetricsSink(Protocol):
    """Interface for application metrics emitters.

    Summary:
        Provide a small, dependency-free contract for counters and timing observations.
    Ties to other methods:
        Used by app and CLI boundaries for instrumentation hooks.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Depends on implementation.
    Error handling:
        - None.
    """

    def increment(
        self,
        metric: str,
        *,
        value: int = 1,
        tags: Mapping[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""

    def observe(
        self,
        metric: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> None:
        """Record a numeric observation for a metric."""

    @contextmanager
    def timer(
        self,
        metric: str,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> Iterator[None]:
        """Record elapsed seconds in a timing metric."""
        yield


class NoOpMetrics:
    """No-op metrics sink used as the default instrumentation backend.

    Summary:
        Keep instrumentation calls safe and deterministic when no metrics backend is configured.
    Ties to other methods:
        Used by app and CLI boundaries as the default metrics sink.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self, monotonic: Callable[[], float] | None = None) -> None:
        """Initialize the no-op sink with an injectable monotonic clock.

        Summary:
            Allow deterministic timing tests without introducing external dependencies.
        Ties to other methods:
            Used by timer for elapsed time calculation.
        Inputs:
            - monotonic: Optional monotonic clock function.
        Outputs:
            - None.
        Side effects:
            Stores the monotonic callback.
        Error handling:
            - None.
        """
        self._monotonic = monotonic or time.monotonic

    def increment(
        self,
        metric: str,
        *,
        value: int = 1,
        tags: Mapping[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Summary:
            Provide a compatible no-op counter API.
        Ties to other methods:
            Called by app and CLI instrumentation hooks.
        Inputs:
            - metric: Metric name.
            - value: Increment value.
            - tags: Optional key-value metric tags.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        _ = (metric, value, tags)

    def observe(
        self,
        metric: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> None:
        """Record a numeric observation.

        Summary:
            Provide a compatible no-op observation API.
        Ties to other methods:
            Called by timer and explicit observation hooks.
        Inputs:
            - metric: Metric name.
            - value: Observation value.
            - tags: Optional key-value metric tags.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        _ = (metric, value, tags)

    @contextmanager
    def timer(
        self,
        metric: str,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> Iterator[None]:
        """Measure elapsed time and forward it to observe.

        Summary:
            Keep timing instrumentation simple and backend-agnostic.
        Ties to other methods:
            Used by app and CLI boundaries around command execution.
        Inputs:
            - metric: Metric name.
            - tags: Optional key-value metric tags.
        Outputs:
            - Context manager yielding control to the caller block.
        Side effects:
            Emits an observation through observe.
        Error handling:
            - None.
        """
        start = self._monotonic()
        try:
            yield
        finally:
            elapsed = max(0.0, self._monotonic() - start)
            self.observe(metric, elapsed, tags=tags)
