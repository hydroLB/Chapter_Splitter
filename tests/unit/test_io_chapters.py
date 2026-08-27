"""Unit tests for chapter file loading."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from chapter_splitter.core import CancellationToken, ChapterDefinition, IoError, ValidationError
from chapter_splitter.io import (
    ChapterFileSessionMetadata,
    load_chapter_file,
    load_chapter_file_with_metadata,
    write_chapter_file,
)
from chapter_splitter.pdf.detection import ChapterDetectionReport
from chapter_splitter.utils import Deadline


def test_load_chapter_file_requires_existing_path(tmp_path: Path) -> None:
    """Verify loader fails when chapter file does not exist."""
    token = CancellationToken()
    deadline = Deadline(1.0)
    with pytest.raises(IoError):
        load_chapter_file(
            tmp_path / "missing.toml",
            deadline=deadline,
            token=token,
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_rejects_directory_path(tmp_path: Path) -> None:
    """Verify loader rejects directories before attempting to read TOML."""
    token = CancellationToken()
    deadline = Deadline(1.0)
    chapter_dir = tmp_path / "chapters.toml"
    chapter_dir.mkdir()

    with pytest.raises(IoError, match="Chapter file path is not a file"):
        load_chapter_file(
            chapter_dir,
            deadline=deadline,
            token=token,
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_rejects_invalid_toml(tmp_path: Path) -> None:
    """Verify invalid TOML is rejected as a validation error."""
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
    """Verify loader requires a top-level chapters array."""
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
    """Verify loader parses valid chapter definitions."""
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


@pytest.mark.parametrize("field", ["start_page", "end_page"])
def test_load_chapter_file_rejects_boolean_page_fields(tmp_path: Path, field: str) -> None:
    """Verify TOML booleans are not accepted as integer page numbers."""
    path = tmp_path / "chapters.toml"
    values: dict[str, str] = {"start_page": "1", "end_page": "2"}
    values[field] = "true"
    path.write_text(
        "\n".join(
            (
                "[[chapters]]",
                'title = "Intro"',
                f"start_page = {values['start_page']}",
                f"end_page = {values['end_page']}",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Chapter pages must be integers"):
        load_chapter_file(
            path,
            deadline=Deadline(1.0),
            token=CancellationToken(),
            location="tests.unit.test_io_chapters",
        )


def test_load_chapter_file_with_metadata_returns_session_data(tmp_path: Path) -> None:
    """Verify chapter loader returns optional session metadata when present."""
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


def test_load_chapter_file_rejects_boolean_total_pages(tmp_path: Path) -> None:
    """Verify session page totals reject TOML booleans despite Python's numeric bool type."""
    path = tmp_path / "chapters.toml"
    path.write_text(
        """
[session]
total_pages = false

[[chapters]]
title = "Intro"
start_page = 1
end_page = 2
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="session.total_pages must be an integer"):
        load_chapter_file_with_metadata(
            path,
            deadline=Deadline(1.0),
            token=CancellationToken(),
            location="tests.unit.test_io_chapters",
        )


def test_write_chapter_file_writes_session_and_chapters(tmp_path: Path) -> None:
    """Verify writer produces a TOML file containing session metadata and chapters."""
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


def test_write_chapter_file_round_trips_control_characters_and_unicode(tmp_path: Path) -> None:
    """Verify all C0 controls, DEL, and ordinary Unicode survive TOML serialization."""
    token = CancellationToken()
    deadline = Deadline(1.0)
    out_path = tmp_path / "controls.toml"
    title = "Controls:" + "".join(chr(codepoint) for codepoint in range(0x20)) + "\x7f — 雪"
    session = ChapterFileSessionMetadata(
        pdf_path="/tmp/café/雪.pdf\r\n",
        total_pages=1,
        saved_at=None,
        source="gui\x00\x1f",
    )

    write_chapter_file(
        out_path,
        chapters=[ChapterDefinition(title=title, start_page=1, end_page=1)],
        report=None,
        session=session,
        overwrite=True,
        deadline=deadline,
        token=token,
        location="tests.unit.test_io_chapters",
    )

    payload = out_path.read_text(encoding="utf-8")
    parsed = tomllib.loads(payload)
    assert parsed["chapters"][0]["title"] == title
    assert parsed["session"]["pdf_path"] == session.pdf_path
    assert parsed["session"]["source"] == session.source
    assert "雪" in payload
    title_line = next(line for line in payload.splitlines() if line.startswith("title = "))
    assert all(ord(character) >= 0x20 for character in title_line)

    loaded_session, chapters = load_chapter_file_with_metadata(
        out_path,
        deadline=Deadline(1.0),
        token=CancellationToken(),
        location="tests.unit.test_io_chapters",
    )
    assert loaded_session == session
    assert chapters[0].title == title


def test_write_chapter_file_writes_detection_when_provided(tmp_path: Path) -> None:
    """Verify writer includes [detection] metadata when a report is provided."""
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


def test_write_chapter_file_never_clobbers_a_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserve a destination created between validation and commit."""
    out_path = tmp_path / "race.toml"
    real_link = os.link

    def create_destination_then_link(source: Path, destination: Path) -> None:
        destination.write_text("created by another process", encoding="utf-8")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", create_destination_then_link)

    with pytest.raises(IoError, match="Failed to write chapter file"):
        write_chapter_file(
            out_path,
            chapters=[ChapterDefinition(title="One", start_page=1, end_page=1)],
            report=None,
            session=None,
            overwrite=False,
            deadline=Deadline(1.0),
            token=CancellationToken(),
            location="tests.unit.test_io_chapters",
        )

    assert out_path.read_text(encoding="utf-8") == "created by another process"
