"""Unit tests for PDF page label extraction."""

from __future__ import annotations

from typing import cast

import pytest

from chapter_splitter.core.errors import PdfProcessingError
from chapter_splitter.pdf.io.dependencies import PdfReader
from chapter_splitter.pdf.io.labels import extract_page_labels


class _ReaderWithLabels:
    def __init__(self, labels: list[object] | None) -> None:
        self.page_labels = labels


def test_extract_page_labels_returns_none_when_missing() -> None:
    """Verify missing labels return None.

    Purpose:
        Allow callers to fall back to numeric page numbers.
    Ties To:
        Covers chapter_splitter.pdf.io.labels.extract_page_labels.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    reader = cast(PdfReader, _ReaderWithLabels(labels=None))
    assert extract_page_labels(reader, "tests.unit.test_pdf_labels") is None


def test_extract_page_labels_rejects_non_string_labels() -> None:
    """Verify non-string labels are rejected.

    Purpose:
        Keep label mapping deterministic and safe.
    Ties To:
        Covers chapter_splitter.pdf.io.labels.extract_page_labels.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    reader = cast(PdfReader, _ReaderWithLabels(labels=[1, 2]))
    with pytest.raises(PdfProcessingError):
        extract_page_labels(reader, "tests.unit.test_pdf_labels")


def test_extract_page_labels_requires_attribute() -> None:
    """Verify readers without label support raise a processing error.

    Purpose:
        Fail with a clear error when a reader implementation is incompatible.
    Ties To:
        Covers chapter_splitter.pdf.io.labels.extract_page_labels.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    reader = cast(PdfReader, object())
    with pytest.raises(PdfProcessingError):
        extract_page_labels(reader, "tests.unit.test_pdf_labels")
