"""Unit tests for PDF loader boundary checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf.errors import FileNotDecryptedError, PdfReadError  # type: ignore[attr-defined]

from chapter_splitter.config.schema import RetryConfig
from chapter_splitter.core import CancellationToken, IoError, PdfProcessingError
from chapter_splitter.pdf.io import loader as pdf_loader
from chapter_splitter.utils import Deadline


def _retry_config() -> RetryConfig:
    """Return a single-attempt retry policy for loader boundary tests."""
    return RetryConfig(
        max_attempts=1,
        initial_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter_ratio=0.0,
    )


def test_load_reader_rejects_directory_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify directory inputs fail before retry/open logic runs."""
    pdf_dir = tmp_path / "book.pdf"
    pdf_dir.mkdir()
    retry_called = False
    reader_called = False

    def _unexpected_retry(*_args: object, **_kwargs: object) -> object:
        nonlocal retry_called
        retry_called = True
        raise AssertionError("retry_with_backoff should not be called for directories")

    def _unexpected_reader(*_args: object, **_kwargs: object) -> object:
        nonlocal reader_called
        reader_called = True
        raise AssertionError("PdfReader should not be called for directories")

    monkeypatch.setattr(pdf_loader, "retry_with_backoff", _unexpected_retry)
    monkeypatch.setattr(pdf_loader, "PdfReader", _unexpected_reader)

    with pytest.raises(IoError, match="PDF path is not a file"):
        pdf_loader.load_reader(
            pdf_dir,
            deadline=Deadline(1.0),
            token=CancellationToken(),
            retry_config=RetryConfig(
                max_attempts=3,
                initial_delay_seconds=0.01,
                max_delay_seconds=0.05,
                jitter_ratio=0.0,
            ),
            location="tests.unit.test_pdf_loader",
        )

    assert retry_called is False
    assert reader_called is False


def test_load_reader_maps_encrypted_pdf_error_with_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Encryption errors raised while opening become actionable domain PDF errors."""
    pdf_path = tmp_path / "encrypted.pdf"
    pdf_path.touch()
    source_error = FileNotDecryptedError("File has not been decrypted")

    def _raise_encrypted(*_args: object, **_kwargs: object) -> object:
        raise source_error

    monkeypatch.setattr(pdf_loader, "PdfReader", _raise_encrypted)

    with pytest.raises(PdfProcessingError, match="encrypted.*requires a password") as caught:
        pdf_loader.load_reader(
            pdf_path,
            Deadline(1.0),
            CancellationToken(),
            _retry_config(),
            "tests.unit.test_pdf_loader",
        )

    assert caught.value.__cause__ is source_error


def test_load_reader_maps_unreadable_pdf_error_with_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exhausted storage read keeps the original OS failure as its cause."""
    pdf_path = tmp_path / "unreadable.pdf"
    pdf_path.touch()
    source_error = OSError("permission denied")

    def _raise_unreadable(*_args: object, **_kwargs: object) -> object:
        raise source_error

    monkeypatch.setattr(pdf_loader, "PdfReader", _raise_unreadable)

    with pytest.raises(IoError, match="Unable to load PDF") as caught:
        pdf_loader.load_reader(
            pdf_path,
            Deadline(1.0),
            CancellationToken(),
            _retry_config(),
            "tests.unit.test_pdf_loader",
        )

    assert caught.value.__cause__ is source_error


class _FailingPages:
    """Page collection that raises while pypdf lazily resolves its length."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def __len__(self) -> int:
        raise self._error


class _ReaderWithFailingPages:
    """Minimal reader double exposing a lazy page collection."""

    def __init__(self, error: BaseException) -> None:
        self.pages = _FailingPages(error)


def test_get_total_pages_maps_encrypted_pdf_error_with_cause() -> None:
    """Encrypted PDFs fail with an actionable domain error at the lazy page boundary."""
    source_error = FileNotDecryptedError("File has not been decrypted")

    with pytest.raises(PdfProcessingError, match="encrypted.*requires a password") as caught:
        pdf_loader.get_total_pages(
            _ReaderWithFailingPages(source_error),  # type: ignore[arg-type]
            "tests.unit.test_pdf_loader",
        )

    assert caught.value.__cause__ is source_error


def test_get_total_pages_maps_lazy_pdf_read_error_with_cause() -> None:
    """Corrupt lazy page trees fail as domain PDF errors without leaking pypdf exceptions."""
    source_error = PdfReadError("broken page tree")

    with pytest.raises(PdfProcessingError, match="damaged or unsupported") as caught:
        pdf_loader.get_total_pages(
            _ReaderWithFailingPages(source_error),  # type: ignore[arg-type]
            "tests.unit.test_pdf_loader",
        )

    assert caught.value.__cause__ is source_error


def test_get_total_pages_maps_lazy_storage_error_with_cause() -> None:
    """Storage failures during lazy page reads fail as actionable domain IO errors."""
    source_error = OSError("read failed")

    with pytest.raises(IoError, match="page count from storage") as caught:
        pdf_loader.get_total_pages(
            _ReaderWithFailingPages(source_error),  # type: ignore[arg-type]
            "tests.unit.test_pdf_loader",
        )

    assert caught.value.__cause__ is source_error
