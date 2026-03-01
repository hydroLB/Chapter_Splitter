"""Pytest fixtures for chapter splitter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.shared.pdf_factory import create_sample_pdf
from tests.shared.toml_factory import write_chapters_toml, write_quiet_logging_override


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


@pytest.fixture()
def standard_chapters_file(tmp_path: Path) -> Path:
    """Provide a deterministic two-chapter TOML file.

    Purpose:
        Reuse a single, deterministic chapter fixture across CLI and integration tests.
    Ties To:
        Used by smoke tests that need basic chapter definitions.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - Path to a chapter TOML file.
    Side Effects:
        Writes a chapter TOML file into the temporary directory.
    Raises:
        - ValueError: When fixture chapter definitions are invalid.
    """
    return write_chapters_toml(
        tmp_path / "chapters.toml",
        chapters=(
            ("One", 1, 2),
            ("Two", 3, 4),
        ),
    )


@pytest.fixture()
def quiet_logging_override_file(tmp_path: Path) -> Path:
    """Provide a deterministic logging override file for CLI tests.

    Purpose:
        Ensure CLI smoke tests avoid noisy log side effects.
    Ties To:
        Used by CLI tests that invoke the entrypoint directly.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - Path to a TOML override file.
    Side Effects:
        Writes a TOML file into the temporary directory.
    Raises:
        - ValueError: When fixture values are invalid.
    """
    return write_quiet_logging_override(tmp_path / "override.toml")
