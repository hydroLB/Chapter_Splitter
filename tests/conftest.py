"""Pytest fixtures for chapter splitter tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.shared.pdf_factory import create_sample_pdf


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Provide a sample PDF file.

    Purpose:
        Supply a deterministic PDF for integration and performance tests.
    Ties To:
        Used by tests that need a real PDF file on disk.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - Path to the generated PDF.
    Side Effects:
        Writes a PDF file into the temporary directory.
    Raises:
        - RuntimeError: When PDF generation fails.
    """
    return create_sample_pdf(tmp_path / "sample.pdf", page_count=8, outline_titles=None)


@pytest.fixture()
def outlined_pdf(tmp_path: Path) -> Path:
    """Provide a sample PDF with outline metadata.

    Purpose:
        Supply a PDF that includes outlines for detection tests.
    Ties To:
        Used by outline detection integration tests.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - Path to the generated PDF.
    Side Effects:
        Writes a PDF file into the temporary directory.
    Raises:
        - RuntimeError: When PDF generation fails.
    """
    return create_sample_pdf(
        tmp_path / "outlined.pdf",
        page_count=6,
        outline_titles=["Intro", "Body", "Conclusion"],
    )
