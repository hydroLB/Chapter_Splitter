"""Unit tests for grid placeholder helpers."""

from __future__ import annotations

from chapter_splitter.ui.tk.widgets.grid_placeholders import first_none_index, shift_indices


def test_shift_indices_shifts_at_and_after_start() -> None:
    """Verify shift_indices shifts placeholder keys at the insertion point."""
    placeholders = {0: "a", 2: "b", 5: "c"}
    assert shift_indices(placeholders, start=2, delta=1) == {0: "a", 3: "b", 6: "c"}


def test_first_none_index_returns_first_none() -> None:
    """Verify first_none_index returns the first None slot."""
    sentinel = object()
    assert first_none_index([sentinel, None, None]) == 1
    assert first_none_index([sentinel, sentinel]) is None
