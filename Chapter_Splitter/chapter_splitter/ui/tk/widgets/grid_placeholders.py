"""Pure helper utilities for chapter grid placeholder bookkeeping.

This module intentionally avoids importing Tkinter so it can be tested in headless
environments where Tk cannot be initialized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


def shift_indices(placeholders: Mapping[int, T], start: int, delta: int) -> dict[int, T]:
    """Shift placeholder indices at and after an insertion point.

    Purpose:
        Keep placeholder indices aligned when a new row is inserted into the backing list.
    Inputs:
        - placeholders: Existing placeholder mapping.
        - start: Index where the insertion happens.
        - delta: Amount to shift indices by (positive for inserts).
    Outputs:
        - New placeholder mapping with shifted keys.
    """
    if delta == 0:
        return dict(placeholders)
    return {(idx + delta if idx >= start else idx): values for idx, values in placeholders.items()}


def first_none_index(rows: Sequence[object | None]) -> int | None:
    """Return the index of the first None slot in a row list."""
    for idx, row in enumerate(rows):
        if row is None:
            return idx
    return None
