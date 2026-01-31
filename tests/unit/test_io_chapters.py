"""Unit tests for chapter file loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from chapter_splitter.core.errors import IoError, ValidationError
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.io.chapters import load_chapter_file
from chapter_splitter.utils.timing import Deadline


def test_load_chapter_file_requires_existing_path(tmp_path: Path) -> None:
    """Verify loader fails when chapter file does not exist.

    Purpose:
        Provide immediate feedback for CLI users pointing at the wrong file.
    Ties To:
        Covers chapter_splitter.io.chapters.load_chapter_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    with pytest.raises(IoError):
        load_chapter_file(
            tmp_path / "missing.toml",
            deadline=deadline,
            token=token,
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_rejects_invalid_toml(tmp_path: Path) -> None:
    """Verify invalid TOML is rejected as a validation error.

    Purpose:
        Avoid undefined behavior when chapter files are malformed.
    Ties To:
        Covers chapter_splitter.io.chapters.load_chapter_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a temporary file.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    path = tmp_path / "bad.toml"
    path.write_text("[invalid", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_chapter_file(
            path,
            deadline=deadline,
            token=token,
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_rejects_missing_chapters_array(tmp_path: Path) -> None:
    """Verify loader requires a top-level chapters array.

    Purpose:
        Keep the chapter file schema strict and predictable.
    Ties To:
        Covers chapter_splitter.io.chapters.load_chapter_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a temporary file.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    path = tmp_path / "chapters.toml"
    path.write_text("[meta]\nname = 'x'\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_chapter_file(
            path,
            deadline=deadline,
            token=token,
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_parses_valid_entries(tmp_path: Path) -> None:
    """Verify loader parses valid chapter definitions.

    Purpose:
        Ensure CLI chapter files map to ChapterDefinition objects.
    Ties To:
        Covers chapter_splitter.io.chapters.load_chapter_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes and reads a temporary file.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    path = tmp_path / "chapters.toml"
    path.write_text(
        """
[[chapters]]
title = "Intro"
start_page = 1
end_page = 2
""",
        encoding="utf-8",
    )
    chapters = load_chapter_file(
        path,
        deadline=deadline,
        token=token,
        location="tests.unit.test_io_chapters",
    )
    assert len(chapters) == 1
    assert chapters[0].title == "Intro"
    assert chapters[0].start_page == 1
    assert chapters[0].end_page == 2
