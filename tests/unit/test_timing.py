"""Unit tests for timing utilities."""

from __future__ import annotations

import math
import time

import pytest

from chapter_splitter.core import CancellationError
from chapter_splitter.utils import Deadline


def test_deadline_rejects_non_finite_timeout() -> None:
    """Verify non-finite timeouts are rejected."""
    with pytest.raises(CancellationError):
        Deadline(math.nan)
    with pytest.raises(CancellationError):
        Deadline(math.inf)


def test_deadline_check_raises_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify deadline check raises after the timeout has been exceeded."""
    times = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    deadline = Deadline(0.1)
    deadline.check("tests.unit.test_timing")
    with pytest.raises(CancellationError):
        deadline.check("tests.unit.test_timing")
