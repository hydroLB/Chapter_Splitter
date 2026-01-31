"""Load chapter definitions from a TOML file."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

from ..core.errors import IoError, ValidationError, format_error_message
from ..core.models import ChapterDefinition
from ..core.runtime import CancellationToken
from ..utils.timing import Deadline


def load_chapter_file(
    path: Path,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> list[ChapterDefinition]:
    """Load chapter definitions from a TOML file.

    Purpose:
        Provide a file based input format for CLI driven chapter definitions.
    Ties To:
        Used by the CLI split command.
    Inputs:
        - path: Path to the TOML file containing chapter definitions.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects.
    Side Effects:
        Reads the chapter file from disk.
    Raises:
        - IoError: When the file cannot be read.
        - ValidationError: When chapter definitions are invalid.
    """
    error_location = f"{__name__}.load_chapter_file"
    context = f" Context: {location}." if location else ""
    token.check(location)
    deadline.check(location)
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
                error_location, f"Chapter file must contain a TOML table.{context}"
            )
        )
    chapters_raw = data.get("chapters")
    if not isinstance(chapters_raw, list):
        raise ValidationError(
            format_error_message(
                error_location, f"Chapter file must define a 'chapters' array.{context}"
            )
        )
    chapters: list[ChapterDefinition] = []
    for entry in chapters_raw:
        token.check(location)
        deadline.check(location)
        if not isinstance(entry, Mapping):
            raise ValidationError(
                format_error_message(
                    error_location, f"Each chapter entry must be a table.{context}"
                )
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
        chapters.append(ChapterDefinition(title=title, start_page=start_page, end_page=end_page))
    return chapters
