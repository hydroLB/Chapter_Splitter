"""Integration tests for outline detection."""

from __future__ import annotations

from pathlib import Path

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import CancellationToken
from chapter_splitter.pdf.detection import detect_chapters_from_outlines
from chapter_splitter.utils import Deadline


def test_detect_chapters_from_outlines(outlined_pdf: Path) -> None:
    """Verify outline detection returns chapters.

    Purpose:
        Ensure detect_chapters_from_outlines returns chapter definitions.
    Ties To:
        Covers chapter_splitter.pdf.detection.outlines.detect_chapters_from_outlines.
    Inputs:
        - outlined_pdf: Fixture providing a PDF with outlines.
    Outputs:
        - None.
    Side Effects:
        Reads the PDF file from disk.
    Raises:
        - None.
    """
    settings = load_settings(None, "tests.integration.test_outlines")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    chapters = detect_chapters_from_outlines(
        outlined_pdf,
        deadline,
        token,
        settings.retry,
        settings.io,
        "tests.integration.test_outlines",
        detection_config=settings.detection,
    )
    assert len(chapters) >= 1
    assert chapters[0].start_page == 1
