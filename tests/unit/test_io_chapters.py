"""Unit tests for chapter file loading."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from chapter_splitter.core.errors import IoError, ValidationError
from chapter_splitter.core.models import ChapterDefinition
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.io.chapters import (
    ChapterFileSessionMetadata,
    load_chapter_file,
    load_chapter_file_with_metadata,
    write_chapter_file,
)
from chapter_splitter.pdf.detection.report import ChapterDetectionReport
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


def test_load_chapter_file_with_metadata_returns_session_data(tmp_path: Path) -> None:
    """Verify chapter loader returns optional session metadata when present.

    Purpose:
        Allow GUI workflows to warn on mismatched PDFs during imports.
    Ties To:
        Covers chapter_splitter.io.chapters.load_chapter_file_with_metadata.
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
[session]
pdf_path = "/tmp/book.pdf"
total_pages = 10
saved_at = "2026-02-05T00:00:00+00:00"
source = "gui"

[[chapters]]
title = "Intro"
start_page = 1
end_page = 2
""",
        encoding="utf-8",
    )
    meta, chapters = load_chapter_file_with_metadata(
        path,
        deadline=deadline,
        token=token,
        location="tests.unit.test_io_chapters",
    )
    assert meta is not None
    assert meta.pdf_path == "/tmp/book.pdf"
    assert meta.total_pages == 10
    assert meta.saved_at == "2026-02-05T00:00:00+00:00"
    assert meta.source == "gui"
    assert len(chapters) == 1


def test_write_chapter_file_writes_session_and_chapters(tmp_path: Path) -> None:
    """Verify writer produces a TOML file containing session metadata and chapters.

    Purpose:
        Ensure GUI exports are deterministic and can be re-imported later.
    Ties To:
        Covers chapter_splitter.io.chapters.write_chapter_file session rendering.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a TOML file to disk.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    out_path = tmp_path / "export.toml"
    session = ChapterFileSessionMetadata(
        pdf_path="/tmp/book.pdf",
        total_pages=10,
        saved_at="2026-02-05T00:00:00+00:00",
        source="gui",
    )
    write_chapter_file(
        out_path,
        chapters=[ChapterDefinition(title="Intro", start_page=1, end_page=2)],
        report=None,
        session=session,
        overwrite=True,
        deadline=deadline,
        token=token,
        location="tests.unit.test_io_chapters",
    )
    data = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert data["session"]["pdf_path"] == "/tmp/book.pdf"
    assert data["session"]["total_pages"] == 10
    assert data["chapters"][0]["title"] == "Intro"
    assert "detection" not in data


def test_write_chapter_file_writes_detection_when_provided(tmp_path: Path) -> None:
    """Verify writer includes [detection] metadata when a report is provided.

    Purpose:
        Preserve CLI detect diagnostics in exported chapter files.
    Ties To:
        Covers chapter_splitter.io.chapters.write_chapter_file detection rendering.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a TOML file to disk.
    Raises:
        - None.
    """
    token = CancellationToken()
    deadline = Deadline(1.0)
    out_path = tmp_path / "detect.toml"
    report = ChapterDetectionReport(
        strategy="outlines",
        chapters=(),
        confidence=0.9,
        warnings=(),
        outline_entries=2,
        toc_start_page=None,
        toc_pages_scanned=0,
    )
    write_chapter_file(
        out_path,
        chapters=[ChapterDefinition(title="One", start_page=1, end_page=1)],
        report=report,
        session=None,
        overwrite=True,
        deadline=deadline,
        token=token,
        location="tests.unit.test_io_chapters",
    )
    data = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert data["detection"]["strategy"] == "outlines"
    assert data["chapters"][0]["title"] == "One"
