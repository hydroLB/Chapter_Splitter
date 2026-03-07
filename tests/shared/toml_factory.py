"""Deterministic TOML fixture helpers for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def write_chapters_toml(path: Path, chapters: Sequence[tuple[str, int, int]]) -> Path:
    """Write a deterministic chapters TOML file.

    Purpose:
        Centralize chapter file fixture generation so tests avoid inline ad-hoc TOML strings.
    Ties To:
        Used by pytest fixtures and smoke tests that require chapter definitions on disk.
    Inputs:
        - path: Destination path for the TOML file.
        - chapters: Sequence of tuples in the form (title, start_page, end_page).
    Outputs:
        - Path to the written TOML file.
    Side Effects:
        Writes a UTF-8 TOML file with normalized newline handling.
    Raises:
        - ValueError: When no chapters are provided.
    """
    if not chapters:
        raise ValueError(
            "tests.shared.toml_factory.write_chapters_toml requires at least one chapter"
        )

    lines: list[str] = []
    for title, start_page, end_page in chapters:
        lines.extend(
            [
                "[[chapters]]",
                f'title = "{title}"',
                f"start_page = {start_page}",
                f"end_page = {end_page}",
                "",
            ]
        )
    payload = "\n".join(lines).rstrip() + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path


def write_quiet_logging_override(path: Path, file_path: str = "cli.log") -> Path:
    """Write a deterministic logging override TOML file.

    Purpose:
        Keep CLI smoke tests deterministic by disabling console and file logging output.
    Ties To:
        Used by pytest fixtures and smoke tests for CLI invocations.
    Inputs:
        - path: Destination path for the TOML file.
        - file_path: Relative log file path used in logging config.
    Outputs:
        - Path to the written TOML file.
    Side Effects:
        Writes a UTF-8 TOML file with normalized newline handling.
    Raises:
        - ValueError: When file_path is empty.
    """
    if not file_path.strip():
        raise ValueError(
            "tests.shared.toml_factory.write_quiet_logging_override requires file_path"
        )
    payload = (
        f'[logging]\nconsole_enabled = false\nfile_enabled = false\nfile_path = "{file_path}"\n'
    )
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path
