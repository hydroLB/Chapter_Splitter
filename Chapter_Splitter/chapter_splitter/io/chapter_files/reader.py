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
    """Load chapter definitions from a TOML file.

    Summary:
        Provide a file-based input format for CLI and GUI chapter definitions.
    Inputs:
        - path: Path to the TOML file containing chapter definitions.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects.
    Side effects:
        Reads the chapter file from disk.
    Error handling:
        Raises IoError or ValidationError when the file cannot be read or parsed.
    Ties to other methods:
        Delegates to load_chapter_file_with_metadata and discards optional session metadata.
    Why this exists:
        Most callers only need chapters, so the simpler API should remain available.
    """
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
    """Load chapter definitions and optional session metadata from a TOML file.

    Summary:
        Parse the chapter-file TOML document, validate its structure, and return session metadata
        plus chapter definitions.
    Inputs:
        - path: Path to the TOML file containing chapter definitions.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - Tuple of optional session metadata and chapter list.
    Side effects:
        Reads the chapter file from disk.
    Error handling:
        Raises IoError or ValidationError when the file cannot be read or parsed.
    Ties to other methods:
        Used by GUI import workflows and load_chapter_file.
    Why this exists:
        GUI workflows need session metadata while preserving the stable core chapter schema.
    """
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
    """Read and parse a TOML document from disk.

    Summary:
        Enforce file existence, read the text, parse TOML, and validate the root table shape.
    Inputs:
        - path: Path to the TOML file to read.
        - token: Cancellation token for graceful shutdown.
        - deadline: Deadline tracker for timeout enforcement.
        - location: Fully qualified caller location.
        - error_location: Fully qualified helper location for error messages.
    Outputs:
        - Parsed TOML root table.
    Side effects:
        Reads bytes from disk.
    Error handling:
        Raises IoError or ValidationError when the file is missing, unreadable, or malformed.
    Ties to other methods:
        Used by load_chapter_file_with_metadata.
    Why this exists:
        File reading and TOML parsing should be isolated from chapter-specific validation.
    """
    context = f" Context: {location}." if location else ""
    if not path.exists():
        raise IoError(
            format_error_message(error_location, f"Chapter file not found: {path}.{context}")
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
    """Extract the required chapters array from a parsed TOML document.

    Summary:
        Validate that the root document defines a top-level "chapters" array.
    Inputs:
        - data: Parsed TOML root table.
        - error_location: Fully qualified helper location for error messages.
        - location: Fully qualified caller location.
    Outputs:
        - Raw chapter entries as a list.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when the chapters array is missing or malformed.
    Ties to other methods:
        Used by load_chapter_file_with_metadata.
    Why this exists:
        The stable file contract centers on the [[chapters]] array and should be validated early.
    """
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
    """Parse raw TOML chapter entries into ChapterDefinition objects.

    Summary:
        Validate chapter entry shapes and convert them into typed chapter definitions.
    Inputs:
        - chapters_raw: Raw TOML chapter entries.
        - token: Cancellation token for graceful shutdown.
        - deadline: Deadline tracker for timeout enforcement.
        - error_location: Fully qualified helper location for error messages.
        - location: Fully qualified caller location.
    Outputs:
        - Parsed chapter definitions.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when any chapter entry is malformed.
    Ties to other methods:
        Used by load_chapter_file_with_metadata.
    Why this exists:
        Per-entry validation is the tightest parsing loop and should stay isolated and readable.
    """
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
    """Parse one raw chapter entry into a ChapterDefinition.

    Summary:
        Validate the fields of a single chapter table and construct the typed model.
    Inputs:
        - entry: Raw chapter entry from the TOML document.
        - error_location: Fully qualified helper location for error messages.
        - location: Fully qualified caller location.
    Outputs:
        - Parsed ChapterDefinition.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when the entry or any required field is malformed.
    Ties to other methods:
        Used by _parse_chapter_entries.
    Why this exists:
        Isolating single-entry parsing keeps the loop body small and debuggable.
    """
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
    if not isinstance(start_page, int) or not isinstance(end_page, int):
        raise ValidationError(
            format_error_message(error_location, f"Chapter pages must be integers.{context}")
        )
    return ChapterDefinition(title=title, start_page=start_page, end_page=end_page)


__all__ = ["load_chapter_file", "load_chapter_file_with_metadata"]
