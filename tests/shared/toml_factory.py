"""Deterministic TOML fixture helpers for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def write_chapters_toml(path: Path, chapters: Sequence[tuple[str, int, int]]) -> Path:
    """Write a deterministic chapters TOML file."""
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
    """Write a deterministic logging override TOML file."""
    if not file_path.strip():
        raise ValueError(
            "tests.shared.toml_factory.write_quiet_logging_override requires file_path"
        )
    payload = (
        f'[logging]\nconsole_enabled = false\nfile_enabled = false\nfile_path = "{file_path}"\n'
    )
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path
