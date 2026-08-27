"""Chapter-file reading helpers."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

from ...core.errors import IoError, ValidationError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline
from .models import ChapterFileSessionMetadata
from .session import parse_session_metadata


def load_chapter_file(
    path: Path,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> list[ChapterDefinition]:
    """Load chapter definitions from a TOML file."""
    _meta, chapters = load_chapter_file_with_metadata(
        path,
        deadline=deadline,
        token=token,
        location=location,
    )
    return chapters


def load_chapter_file_with_metadata(
    path: Path,
    *,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> tuple[ChapterFileSessionMetadata | None, list[ChapterDefinition]]:
    """Load chapter definitions and optional session metadata from a TOML file."""
    error_location = "chapter_splitter.io.chapter_files.reader.load_chapter_file_with_metadata"
    token.check(location)
    deadline.check(location)
    data = _read_toml_table(
        path=path,
        token=token,
        deadline=deadline,
        location=location,
        error_location=error_location,
    )
    chapters_raw = _extract_chapters_array(
        data=data,
        error_location=error_location,
        location=location,
    )
    session_meta = parse_session_metadata(data.get("session"), location=location)
    chapters = _parse_chapter_entries(
        chapters_raw=chapters_raw,
        token=token,
        deadline=deadline,
        error_location=error_location,
        location=location,
    )
    return session_meta, chapters


def _read_toml_table(
    *,
    path: Path,
    token: CancellationToken,
    deadline: Deadline,
    location: str,
    error_location: str,
) -> dict[str, object]:
    """Read and parse a TOML document from disk."""
    context = f" Context: {location}." if location else ""
    if not path.exists():
        raise IoError(
            format_error_message(error_location, f"Chapter file not found: {path}.{context}")
        )
    if not path.is_file():
        raise IoError(
            format_error_message(
                error_location, f"Chapter file path is not a file: {path}.{context}"
            )
        )
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IoError(
            format_error_message(error_location, f"Unable to read chapter file: {path}.{context}")
        ) from exc
    token.check(location)
    deadline.check(location)
    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(
            format_error_message(error_location, f"Invalid TOML in chapter file: {path}.{context}")
        ) from exc
    if not isinstance(data, dict):
        raise ValidationError(
            format_error_message(
                error_location,
                f"Chapter file must contain a TOML table.{context}",
            )
        )
    return data


def _extract_chapters_array(
    *,
    data: dict[str, object],
    error_location: str,
    location: str,
) -> list[object]:
    """Extract the required chapters array from a parsed TOML document."""
    context = f" Context: {location}." if location else ""
    chapters_raw = data.get("chapters")
    if not isinstance(chapters_raw, list):
        raise ValidationError(
            format_error_message(
                error_location,
                f"Chapter file must define a 'chapters' array.{context}",
            )
        )
    return chapters_raw


def _parse_chapter_entries(
    *,
    chapters_raw: list[object],
    token: CancellationToken,
    deadline: Deadline,
    error_location: str,
    location: str,
) -> list[ChapterDefinition]:
    """Parse raw TOML chapter entries into ChapterDefinition objects."""
    chapters: list[ChapterDefinition] = []
    for entry in chapters_raw:
        token.check(location)
        deadline.check(location)
        chapters.append(
            _parse_chapter_entry(
                entry=entry,
                error_location=error_location,
                location=location,
            )
        )
    return chapters


def _parse_chapter_entry(
    *,
    entry: object,
    error_location: str,
    location: str,
) -> ChapterDefinition:
    """Parse one raw chapter entry into a ChapterDefinition."""
    context = f" Context: {location}." if location else ""
    if not isinstance(entry, Mapping):
        raise ValidationError(
            format_error_message(error_location, f"Each chapter entry must be a table.{context}")
        )
    title = entry.get("title")
    start_page = entry.get("start_page")
    end_page = entry.get("end_page")
    if not isinstance(title, str):
        raise ValidationError(
            format_error_message(error_location, f"Chapter title must be a string.{context}")
        )
    if (
        not isinstance(start_page, int)
        or isinstance(start_page, bool)
        or not isinstance(end_page, int)
        or isinstance(end_page, bool)
    ):
        raise ValidationError(
            format_error_message(error_location, f"Chapter pages must be integers.{context}")
        )
    return ChapterDefinition(title=title, start_page=start_page, end_page=end_page)


__all__ = ["load_chapter_file", "load_chapter_file_with_metadata"]
