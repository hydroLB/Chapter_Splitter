"""Unit tests for PDF page label extraction."""

from __future__ import annotations

from typing import cast

import pytest

from chapter_splitter.core import PdfProcessingError
from chapter_splitter.pdf.io import PdfReader, extract_page_labels, infer_page_offset_from_labels


class _ReaderWithLabels:
    def __init__(self, labels: list[object] | None) -> None:
        self.page_labels = labels


def test_extract_page_labels_returns_none_when_missing() -> None:
    """Verify missing labels return None."""
    reader = cast(PdfReader, _ReaderWithLabels(labels=None))
    assert extract_page_labels(reader, "tests.unit.test_pdf_labels") is None


def test_extract_page_labels_rejects_non_string_labels() -> None:
    """Verify non-string labels are rejected."""
    reader = cast(PdfReader, _ReaderWithLabels(labels=[1, 2]))
    with pytest.raises(PdfProcessingError):
        extract_page_labels(reader, "tests.unit.test_pdf_labels")


def test_extract_page_labels_requires_attribute() -> None:
    """Verify readers without label support raise a processing error."""
    reader = cast(PdfReader, object())
    with pytest.raises(PdfProcessingError):
        extract_page_labels(reader, "tests.unit.test_pdf_labels")


def test_infer_page_offset_from_labels_returns_offset_when_numeric_run_exists() -> None:
    """Verify offset inference finds the start of numeric page labels."""
    labels = ["i", "ii", "iii", "1", "2", "3", "4"]
    assert (
        infer_page_offset_from_labels(
            labels,
            min_sequential_numeric_labels=3,
            location="tests.unit.test_pdf_labels",
        )
        == 3
    )


def test_infer_page_offset_from_labels_returns_none_when_run_is_too_short() -> None:
    """Verify inference respects the sequential run threshold."""
    labels = ["x", "1", "x", "2"]
    assert (
        infer_page_offset_from_labels(
            labels,
            min_sequential_numeric_labels=2,
            location="tests.unit.test_pdf_labels",
        )
        is None
    )


def test_infer_page_offset_from_labels_rejects_invalid_threshold() -> None:
    """Verify inference rejects invalid thresholds."""
    with pytest.raises(PdfProcessingError):
        infer_page_offset_from_labels(
            ["1"],
            min_sequential_numeric_labels=0,
            location="tests.unit.test_pdf_labels",
        )
