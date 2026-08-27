"""CLI argument parsing helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from .._version import __version__
from ..core.errors import ChapterSplitterError, format_error_message


class ParsedArgs:
    """Strongly typed CLI arguments container."""

    def __init__(
        self,
        command: str,
        config: Path | None,
        pdf: Path | None,
        chapters: Path | None,
        out: Path | None,
        strategy: str | None,
        toc_hint_page: int | None,
        overwrite: bool,
        output_dir: Path | None,
        collision_policy: str | None,
        page_offset: int | None,
    ) -> None:
        self.command = command
        self.config = config
        self.pdf = pdf
        self.chapters = chapters
        self.out = out
        self.strategy = strategy
        self.toc_hint_page = toc_hint_page
        self.overwrite = overwrite
        self.output_dir = output_dir
        self.collision_policy = collision_policy
        self.page_offset = page_offset


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="chapter-splitter",
        description="Split a PDF into chapters using a config driven workflow.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to an override configuration TOML file.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI workflow.")
    gui_parser.set_defaults(command="gui")

    split_parser = subparsers.add_parser("split", help="Split a PDF with a chapter file.")
    split_parser.add_argument("--pdf", type=Path, required=True, help="Path to the PDF file.")
    split_parser.add_argument(
        "--chapters",
        type=Path,
        required=True,
        help="Path to a TOML file containing chapter ranges.",
    )
    split_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the output directory for chapter PDFs.",
    )
    split_parser.add_argument(
        "--collision-policy",
        choices=("error", "overwrite", "suffix"),
        default=None,
        help="Override io.output_collision_policy for this run.",
    )
    split_parser.add_argument(
        "--page-offset",
        type=int,
        default=None,
        help="Override io.page_offset for this run (non-negative).",
    )
    split_parser.set_defaults(command="split")

    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect chapters from a PDF and write a chapters TOML file.",
    )
    detect_parser.add_argument("--pdf", type=Path, required=True, help="Path to the PDF file.")
    detect_parser.add_argument(
        "--strategy",
        choices=("auto", "outlines", "toc"),
        default="auto",
        help="Detection strategy: auto, outlines, or toc.",
    )
    detect_parser.add_argument(
        "--toc-hint-page",
        type=int,
        default=None,
        help=(
            "1-based page number where the Table of Contents starts (required for --strategy toc)."
        ),
    )
    detect_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the generated chapters TOML file (default: <pdf>.chapters.toml).",
    )
    detect_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file when it already exists.",
    )
    detect_parser.set_defaults(command="detect")
    return parser


def parse_args(argv: list[str] | None, location: str) -> ParsedArgs:
    """Parse and validate CLI arguments."""
    parser = build_parser()
    namespace = parser.parse_args(argv)
    command = require_str(namespace.command, "command", location)
    config = optional_path(namespace.config, "config", location)
    pdf = optional_path(namespace.pdf if hasattr(namespace, "pdf") else None, "pdf", location)
    chapters = optional_path(
        namespace.chapters if hasattr(namespace, "chapters") else None,
        "chapters",
        location,
    )
    out = optional_path(namespace.out if hasattr(namespace, "out") else None, "out", location)
    strategy = optional_str(
        namespace.strategy if hasattr(namespace, "strategy") else None,
        "strategy",
        location,
    )
    toc_hint_page = optional_int(
        namespace.toc_hint_page if hasattr(namespace, "toc_hint_page") else None,
        "toc_hint_page",
        location,
    )
    overwrite = bool(getattr(namespace, "overwrite", False))
    output_dir = optional_path(
        namespace.output_dir if hasattr(namespace, "output_dir") else None,
        "output_dir",
        location,
    )
    collision_policy = optional_str(
        namespace.collision_policy if hasattr(namespace, "collision_policy") else None,
        "collision_policy",
        location,
    )
    page_offset = optional_int(
        namespace.page_offset if hasattr(namespace, "page_offset") else None,
        "page_offset",
        location,
    )
    return ParsedArgs(
        command=command,
        config=config,
        pdf=pdf,
        chapters=chapters,
        out=out,
        strategy=strategy,
        toc_hint_page=toc_hint_page,
        overwrite=overwrite,
        output_dir=output_dir,
        collision_policy=collision_policy,
        page_offset=page_offset,
    )


def require_str(value: object, name: str, location: str) -> str:
    """Validate and return a required non-empty string."""
    error_location = "chapter_splitter.cli._require_str"
    context = f" Context: {location}." if location else ""
    if not isinstance(value, str) or not value.strip():
        raise ChapterSplitterError(
            format_error_message(
                error_location, f"Argument '{name}' must be a non empty string.{context}"
            )
        )
    return value


def optional_str(value: object, name: str, location: str) -> str | None:
    """Validate and return an optional string."""
    error_location = "chapter_splitter.cli._optional_str"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be a string.{context}")
    )


def optional_int(value: object, name: str, location: str) -> int | None:
    """Validate and return an optional integer."""
    error_location = "chapter_splitter.cli._optional_int"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be an integer.{context}")
    )


def optional_path(value: object, name: str, location: str) -> Path | None:
    """Validate and return an optional path."""
    error_location = "chapter_splitter.cli._optional_path"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be a path.{context}")
    )
