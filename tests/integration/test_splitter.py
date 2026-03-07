"""Integration tests for PDF splitting."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pytest

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import CancellationToken, ChapterDefinition, IoError, ValidationError
from chapter_splitter.pdf.splitting import split_pdf_into_chapters
from chapter_splitter.utils import Deadline


def test_split_pdf_into_chapters_creates_outputs(sample_pdf: Path) -> None:
    """Verify splitting creates the expected output files.

    Summary:
        Ensure split_pdf_into_chapters writes chapter PDFs to disk.
    Ties to other methods:
        Covers chapter_splitter.pdf.splitting.splitter.split_pdf_into_chapters.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
    Outputs:
        - None.
    Side effects:
        Writes chapter PDFs into the output directory.
    Error handling:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_splitter")
    chapters = [
        ChapterDefinition(title="Alpha", start_page=1, end_page=2),
        ChapterDefinition(title="Beta", start_page=3, end_page=4),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )
    assert len(outputs) == 2
    for output in outputs:
        assert output.output_path.exists()
        assert output.output_path.read_bytes().startswith(b"%PDF")


def test_split_rejects_existing_output_when_policy_error(sample_pdf: Path) -> None:
    """Verify policy error blocks export when an output path already exists.

    Summary:
        Ensure collision handling is explicit and avoids overwriting user files by default.
    Ties to other methods:
        Covers io.output_collision_policy behavior in split_pdf_into_chapters.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
    Outputs:
        - None.
    Side effects:
        Creates a colliding file in the output directory.
    Error handling:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "error"
    chapters = [ChapterDefinition(title="Alpha", start_page=1, end_page=1)]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "Alpha.pdf").write_bytes(b"existing")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(IoError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )


def test_split_suffix_policy_generates_unique_paths(sample_pdf: Path) -> None:
    """Verify suffix collision policy generates unique output filenames.

    Summary:
        Ensure exports can succeed even when titles or existing files collide.
    Ties to other methods:
        Covers io.output_collision_policy='suffix' behavior in split_pdf_into_chapters.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
    Outputs:
        - None.
    Side effects:
        Writes multiple chapter outputs.
    Error handling:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "suffix"
    settings.io.output_collision_max_suffix = 10
    chapters = [
        ChapterDefinition(title="Alpha/", start_page=1, end_page=1),
        ChapterDefinition(title="Alpha:", start_page=2, end_page=2),
    ]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "Alpha_.pdf").write_bytes(b"existing")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )
    out_names = {output.output_path.name for output in outputs}
    assert out_names == {"Alpha_ (2).pdf", "Alpha_ (3).pdf"}


def test_split_validates_overlapping_ranges(sample_pdf: Path) -> None:
    """Verify overlap validation prevents ambiguous exports.

    Summary:
        Ensure chapter definitions cannot duplicate pages across outputs when configured.
    Ties to other methods:
        Covers validation.reject_overlapping_ranges in validate_chapters.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.validation.reject_overlapping_ranges = True
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=3),
        ChapterDefinition(title="Two", start_page=3, end_page=4),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(ValidationError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )


def test_split_atomic_overwrite_does_not_corrupt_existing_file_on_failure(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify atomic writing preserves existing output files if a write fails.

    Summary:
        Prevent partial files and ensure overwrite does not corrupt existing chapter exports.
    Ties to other methods:
        Covers the temporary-file + atomic replace logic in the split pipeline.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Creates a colliding output file and forces a write failure.
    Error handling:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    chapters = [ChapterDefinition(title="Alpha", start_page=1, end_page=1)]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / "Alpha.pdf"
    out_path.write_bytes(b"ORIGINAL")

    class _FailingWriter:
        def add_page(self, _page: object) -> None:
            return None

        def write(self, handle: BinaryIO) -> None:
            handle.write(b"partial")
            raise OSError("simulated write failure")

    monkeypatch.setattr(
        "chapter_splitter.pdf.splitting.splitter.PdfWriter",
        _FailingWriter,
    )

    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(IoError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )
    assert out_path.read_bytes() == b"ORIGINAL"
    assert not any(output_dir.glob(".Alpha.tmp-*"))
