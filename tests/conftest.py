"""Pytest fixtures for chapter splitter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.shared.pdf_factory import create_sample_pdf
from tests.shared.toml_factory import write_chapters_toml, write_quiet_logging_override


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Provide a sample PDF file."""
    return create_sample_pdf(tmp_path / "sample.pdf", page_count=8, outline_titles=None)


@pytest.fixture()
def outlined_pdf(tmp_path: Path) -> Path:
    """Provide a sample PDF with outline metadata."""
    return create_sample_pdf(
        tmp_path / "outlined.pdf",
        page_count=6,
        outline_titles=["Intro", "Body", "Conclusion"],
    )


@pytest.fixture()
def standard_chapters_file(tmp_path: Path) -> Path:
    """Provide a deterministic two-chapter TOML file."""
    return write_chapters_toml(
        tmp_path / "chapters.toml",
        chapters=(
            ("One", 1, 2),
            ("Two", 3, 4),
        ),
    )


@pytest.fixture()
def quiet_logging_override_file(tmp_path: Path) -> Path:
    """Provide a deterministic logging override file for CLI tests."""
    return write_quiet_logging_override(tmp_path / "override.toml")
