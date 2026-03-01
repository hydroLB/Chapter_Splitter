"""Unit tests for metrics abstraction helpers."""

from __future__ import annotations

from collections.abc import Mapping

from chapter_splitter.observability import NoOpMetrics


class _ProbeMetrics(NoOpMetrics):
    """Test helper that records observations emitted by timer contexts."""

    def __init__(self, clock_values: list[float]) -> None:
        self._clock_values = clock_values
        self.observations: list[tuple[str, float, Mapping[str, str] | None]] = []
        super().__init__(monotonic=self._clock)

    def _clock(self) -> float:
        return self._clock_values.pop(0)

    def observe(
        self,
        metric: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> None:
        self.observations.append((metric, value, tags))


def test_noop_metrics_counter_and_observe_are_safe() -> None:
    """Verify no-op metrics APIs accept calls without raising exceptions."""
    metrics = NoOpMetrics()
    metrics.increment("chapter_splitter.test.counter")
    metrics.increment("chapter_splitter.test.counter", value=3, tags={"k": "v"})
    metrics.observe("chapter_splitter.test.value", 1.5)
    metrics.observe("chapter_splitter.test.value", 2.5, tags={"k": "v"})


def test_noop_metrics_timer_emits_elapsed_observation() -> None:
    """Verify timer context emits deterministic elapsed seconds to observe."""
    metrics = _ProbeMetrics([10.0, 10.25])
    with metrics.timer("chapter_splitter.test.seconds", tags={"scope": "unit"}):
        pass

    assert len(metrics.observations) == 1
    name, value, tags = metrics.observations[0]
    assert name == "chapter_splitter.test.seconds"
    assert value == 0.25
    assert tags == {"scope": "unit"}
