"""Unit tests for TOC-based chapter detection fallback."""

from __future__ import annotations

from dataclasses import dataclass

from chapter_splitter.config.schema import DetectionConfig
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.pdf.detection.toc import detect_chapters_from_toc_page
from chapter_splitter.utils.timing import Deadline


@dataclass(frozen=True, slots=True)
class _FakePage:
    text: str

    def extract_text(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class _FakeReader:
    pages: list[_FakePage]


def _default_detection() -> DetectionConfig:
    return DetectionConfig(
        enable_toc_fallback=True,
        toc_auto_scan_max_start_page=5,
        toc_scan_max_pages=3,
        toc_entry_regexes=(
            r"^(?P<title>.+?)\s+\.\.{2,}\s*(?P<page>\d+)\s*$",
            r"^(?P<title>.+?)\s+(?P<page>\d+)\s*$",
        ),
        toc_ignore_title_regexes=(r"(?i)^(table of contents|contents)$",),
        toc_min_entries=2,
        toc_max_entries=50,
    )


def test_detect_chapters_from_toc_page_parses_dotted_leaders() -> None:
    """Verify TOC detection parses dotted-leader entries into chapter ranges.

    Purpose:
        Ensure the fallback parser produces deterministic chapter ranges without PDF outlines.
    Ties To:
        Covers chapter_splitter.pdf.detection.toc.detect_chapters_from_toc_page.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    reader = _FakeReader(
        pages=[
            _FakePage(text="Cover"),
            _FakePage(
                text="\n".join(
                    [
                        "Contents",
                        "Intro .......... 1",
                        "Chapter 1 ....... 5",
                        "Chapter 2 ....... 12",
                    ]
                )
            ),
            _FakePage(text="More TOC stuff"),
        ]
    )
    token = CancellationToken()
    chapters = detect_chapters_from_toc_page(
        reader=reader,
        toc_start_page=2,
        total_pages=20,
        detection=_default_detection(),
        deadline=Deadline(1.0),
        token=token,
        location="tests.unit.test_toc_detection",
    )
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [
        ("Intro", 1, 4),
        ("Chapter 1", 5, 11),
        ("Chapter 2", 12, 20),
    ]


def test_detect_chapters_from_toc_page_returns_empty_when_insufficient_entries() -> None:
    """Verify TOC detection returns an empty list when it cannot find enough entries.

    Purpose:
        Avoid populating the grid with low-confidence or partial TOC parses.
    Ties To:
        Covers chapter_splitter.pdf.detection.toc.detect_chapters_from_toc_page.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    reader = _FakeReader(
        pages=[
            _FakePage(text="Contents\nAppendix .... 9999"),
        ]
    )
    token = CancellationToken()
    chapters = detect_chapters_from_toc_page(
        reader=reader,
        toc_start_page=1,
        total_pages=10,
        detection=_default_detection(),
        deadline=Deadline(1.0),
        token=token,
        location="tests.unit.test_toc_detection",
    )
    assert chapters == []
