"""Integration tests for PDF splitting."""

from __future__ import annotations

from pathlib import Path

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core.models import ChapterDefinition
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.pdf.splitting.splitter import split_pdf_into_chapters
from chapter_splitter.utils.timing import Deadline


def test_split_pdf_into_chapters_creates_outputs(sample_pdf: Path) -> None:
    """Verify splitting creates the expected output files.

    Purpose:
        Ensure split_pdf_into_chapters writes chapter PDFs to disk.
    Ties To:
        Covers chapter_splitter.pdf.splitting.splitter.split_pdf_into_chapters.
    Inputs:
        - sample_pdf: Fixture providing a temporary PDF path.
    Outputs:
        - None.
    Side Effects:
        Writes chapter PDFs into the output directory.
    Raises:
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
        page_offset=settings.io.page_offset,
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
