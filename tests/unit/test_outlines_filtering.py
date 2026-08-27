"""Unit tests for outline filtering and post-processing."""

from __future__ import annotations

from dataclasses import dataclass

from chapter_splitter.core import CancellationToken
from chapter_splitter.pdf.detection import (
    OutlineReaderProtocol,
    detect_chapters_from_outlines_reader,
    extract_outline_entries,
)
from chapter_splitter.utils import Deadline


@dataclass(frozen=True, slots=True)
class _Item:
    title: str
    page_number: int


@dataclass(frozen=True, slots=True)
class _FakeReader(OutlineReaderProtocol):
    outline: list[object] | None

    def get_destination_page_number(self, dest: object) -> int:
        if not isinstance(dest, _Item):
            raise TypeError("tests.unit.test_outlines_filtering requires _Item destinations")
        return dest.page_number


def test_extract_outline_entries_prefers_deeper_items_when_top_level_is_ignored() -> None:
    """Verify ignored depth-0 titles allow falling back to deeper outline entries."""
    reader = _FakeReader(
        outline=[
            _Item("Contents", 0),
            [
                _Item("Chapter 1", 0),
                _Item("Chapter 2", 2),
            ],
        ]
    )
    token = CancellationToken()
    deadline = Deadline(1.0)
    entries = extract_outline_entries(
        reader,
        deadline,
        token,
        "tests.unit.test_outlines_filtering",
        outline_min_depth=0,
        outline_ignore_title_regexes=(r"(?i)^contents$",),
    )
    assert entries == [("Chapter 1", 1), ("Chapter 2", 3)]


def test_extract_outline_entries_respects_min_depth() -> None:
    """Verify outline_min_depth selects the shallowest eligible depth."""
    reader = _FakeReader(
        outline=[
            _Item("Book", 0),
            [
                _Item("Chapter 1", 0),
                _Item("Chapter 2", 2),
            ],
        ]
    )
    token = CancellationToken()
    deadline = Deadline(1.0)
    entries = extract_outline_entries(
        reader,
        deadline,
        token,
        "tests.unit.test_outlines_filtering",
        outline_min_depth=1,
        outline_ignore_title_regexes=(),
    )
    assert entries == [("Chapter 1", 1), ("Chapter 2", 3)]


def test_detect_chapters_from_outlines_reader_merges_tiny_ranges_forward() -> None:
    """Verify tiny ranges are merged into the next chapter when possible."""
    reader = _FakeReader(outline=None)
    token = CancellationToken()
    deadline = Deadline(1.0)
    chapters = detect_chapters_from_outlines_reader(
        reader=reader,
        total_pages=12,
        deadline=deadline,
        token=token,
        location="tests.unit.test_outlines_filtering",
        entries=[("A", 1), ("B", 2), ("C", 10)],
        outline_merge_tiny_max_pages=2,
        outline_merge_tiny_title_joiner=" / ",
    )
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [
        ("A / B", 1, 9),
        ("C", 10, 12),
    ]


def test_detect_chapters_from_outlines_reader_respects_explicit_empty_entries() -> None:
    """Verify a pre-filtered empty result does not trigger outline re-extraction."""
    reader = _FakeReader(outline=[_Item("Unexpected", 0)])

    chapters = detect_chapters_from_outlines_reader(
        reader=reader,
        total_pages=12,
        deadline=Deadline(1.0),
        token=CancellationToken(),
        location="tests.unit.test_outlines_filtering",
        entries=[],
    )

    assert chapters == []
