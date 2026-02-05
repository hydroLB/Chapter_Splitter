"""Unit tests for unified chapter detection selection logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chapter_splitter.config.schema import DetectionConfig
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.pdf.detection.detector import DetectionRequest, detect_chapters_in_reader
from chapter_splitter.utils.timing import Deadline


@dataclass(frozen=True, slots=True)
class _OutlineItem:
    title: str
    page: int


@dataclass(frozen=True, slots=True)
class _Page:
    text: str

    def extract_text(self) -> str:
        return self.text


class _Reader:
    def __init__(self, outline: list[object] | None, pages: list[_Page]) -> None:
        self.outline = outline
        self._pages = pages

    @property
    def pages(self) -> list[_Page]:
        return self._pages

    def get_destination_page_number(self, dest: object) -> int:
        item = dest
        if not isinstance(item, _OutlineItem):
            raise TypeError("Expected _OutlineItem")
        return item.page - 1


def _detection_config(enable_toc: bool) -> DetectionConfig:
    return DetectionConfig(
        enable_toc_fallback=enable_toc,
        toc_auto_scan_max_start_page=8,
        toc_scan_max_pages=3,
        toc_entry_regexes=(
            r"^(?P<title>.+?)\s+\.\.{2,}\s*(?P<page>\d+)\s*$",
            r"^(?P<title>.+?)\s+(?P<page>\d+)\s*$",
        ),
        toc_ignore_title_regexes=(r"(?i)^(table of contents|contents)$",),
        toc_min_entries=2,
        toc_max_entries=50,
    )


def test_unified_detector_prefers_outlines_when_present() -> None:
    """Verify outlines are preferred when available."""

    reader = _Reader(
        outline=[
            _OutlineItem(title="Intro", page=1),
            _OutlineItem(title="Chapter 1", page=5),
        ],
        pages=[_Page(text="")] * 10,
    )
    report = detect_chapters_in_reader(
        reader=reader,
        total_pages=10,
        pdf_path=Path("sample.pdf"),
        deadline=Deadline(1.0),
        token=CancellationToken(),
        detection_config=_detection_config(enable_toc=True),
        request=DetectionRequest(toc_hint_page=2, force_strategy=None),
        location="tests.unit.test_unified_detector",
    )
    assert report.strategy == "outlines"
    assert len(report.chapters) == 2
    assert report.confidence >= 0.8


def test_unified_detector_falls_back_to_toc_when_outlines_missing() -> None:
    """Verify TOC fallback is used when outlines are missing."""

    toc_text = "\n".join(
        [
            "Contents",
            "Intro .......... 1",
            "Chapter 1 ....... 5",
            "Chapter 2 ....... 9",
        ]
    )
    reader = _Reader(
        outline=None,
        pages=[
            _Page(text=toc_text),
            _Page(text=""),
            _Page(text=""),
        ],
    )
    report = detect_chapters_in_reader(
        reader=reader,
        total_pages=12,
        pdf_path=Path("sample.pdf"),
        deadline=Deadline(1.0),
        token=CancellationToken(),
        detection_config=_detection_config(enable_toc=True),
        request=DetectionRequest(toc_hint_page=1, force_strategy=None),
        location="tests.unit.test_unified_detector",
    )
    assert report.strategy == "toc"
    assert len(report.chapters) == 3
    assert report.toc_start_page == 1
    assert report.confidence > 0.0


def test_unified_detector_returns_none_when_toc_disabled_and_no_outlines() -> None:
    """Verify detector returns an empty report when no strategies are available."""

    reader = _Reader(outline=None, pages=[_Page(text="")])
    report = detect_chapters_in_reader(
        reader=reader,
        total_pages=3,
        pdf_path=Path("sample.pdf"),
        deadline=Deadline(1.0),
        token=CancellationToken(),
        detection_config=_detection_config(enable_toc=False),
        request=DetectionRequest(toc_hint_page=1, force_strategy=None),
        location="tests.unit.test_unified_detector",
    )
    assert report.strategy == "none"
    assert report.chapters == ()
    assert report.confidence == 0.0
    assert any("disabled" in warning.lower() for warning in report.warnings)
