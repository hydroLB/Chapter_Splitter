"""Load chapter definitions from a TOML file."""

from __future__ import annotations

import os
import secrets
import tempfile
import tomllib
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import IoError, ValidationError, format_error_message
from ..core.models import ChapterDefinition
from ..core.runtime import CancellationToken
from ..pdf.detection.report import ChapterDetectionReport
from ..utils.timing import Deadline


@dataclass(frozen=True, slots=True)
class ChapterFileSessionMetadata:
    """Optional session metadata stored alongside chapters.

    Purpose:
        Capture lightweight session context so GUI exports can be re-used safely across runs.
    Ties To:
        Parsed by load_chapter_file_with_metadata and written by write_chapter_file.
    Inputs:
        - pdf_path: Optional PDF path this chapter set applies to.
        - total_pages: Optional total page count observed at export time.
        - saved_at: Optional ISO-8601 timestamp string describing when the file was written.
        - source: Optional string describing the producing workflow (gui, cli-detect, etc).
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    pdf_path: str | None
    total_pages: int | None
    saved_at: str | None
    source: str | None


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

    Purpose:
        Allow chapter files to include session metadata while preserving the core `[[chapters]]`
        schema used by CLI and GUI workflows.
    Ties To:
        Used by GUI import workflows and `load_chapter_file`.
    Inputs:
        - path: Path to the TOML file containing chapter definitions.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - Tuple of (optional session metadata, chapter list).
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
    session_meta = _parse_session_metadata(data.get("session"), location=location)
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
    return session_meta, chapters


def write_chapter_file(
    path: Path,
    chapters: Iterable[ChapterDefinition],
    *,
    report: ChapterDetectionReport | None = None,
    session: ChapterFileSessionMetadata | None = None,
    overwrite: bool,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> None:
    """Write chapter definitions to a TOML file.

    Purpose:
        Provide a deterministic writer for chapter definition files produced by detection.
    Ties To:
        Used by the CLI detect subcommand.
    Inputs:
        - path: Output file path for the TOML chapter file.
        - chapters: Chapter definitions to serialize.
        - report: Optional detection report metadata (strategy, confidence, warnings).
        - session: Optional session metadata to include in the output file.
        - overwrite: Whether to overwrite an existing file at path.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side Effects:
        Writes a TOML file to disk via an atomic rename.
    Raises:
        - IoError: When output paths are invalid or writes fail.
    """
    error_location = f"{__name__}.write_chapter_file"
    context = f" Context: {location}." if location else ""
    token.check(location)
    deadline.check(location)

    if not isinstance(path, Path):
        raise IoError(format_error_message(error_location, f"path must be a Path.{context}"))
    if not str(path).strip():
        raise IoError(format_error_message(error_location, f"Output path must be set.{context}"))

    if path.exists() and not overwrite:
        raise IoError(
            format_error_message(
                error_location,
                f"Output file already exists: {path}.{context} Use --overwrite to replace it.",
            )
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Unable to create output directory: {path.parent}.{context}",
            )
        ) from exc
    if not path.parent.is_dir():
        raise IoError(
            format_error_message(
                error_location,
                f"Output parent path is not a directory: {path.parent}.{context}",
            )
        )

    token.check(location)
    deadline.check(location)
    payload = _render_chapters_toml(chapters=chapters, report=report, session=session)

    tmp_path: Path | None = None
    try:
        tmp_prefix = f".{path.stem}.tmp-"
        tmp_suffix = f"-{secrets.token_hex(6)}{path.suffix}"
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=str(path.parent),
            prefix=tmp_prefix,
            suffix=tmp_suffix,
            encoding="utf-8",
            newline="\n",
        ) as handle:
            tmp_path = Path(handle.name)
            token.check(location)
            deadline.check(location)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            token.check(location)
            deadline.check(location)
        tmp_path.replace(path)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to write chapter file: {path}.{context}",
            )
        ) from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()


def _render_chapters_toml(
    *,
    chapters: Iterable[ChapterDefinition],
    report: ChapterDetectionReport | None,
    session: ChapterFileSessionMetadata | None,
) -> str:
    """Render chapters and detection metadata into TOML text.

    Purpose:
        Generate a TOML payload that can round-trip through load_chapter_file while still
        carrying detection diagnostics for users.
    Ties To:
        Used by write_chapter_file.
    Inputs:
        - chapters: ChapterDefinition objects to serialize.
        - report: ChapterDetectionReport metadata to embed.
    Outputs:
        - TOML string.
    Side Effects:
        None.
    Raises:
        - None.
    """
    lines: list[str] = []
    lines.append("# Generated by chapter-splitter")
    lines.append("")

    if session is not None:
        lines.append("[session]")
        if session.pdf_path is not None:
            lines.append(f'pdf_path = "{_toml_escape(session.pdf_path)}"')
        if session.total_pages is not None:
            lines.append(f"total_pages = {int(session.total_pages)}")
        if session.saved_at is not None:
            lines.append(f'saved_at = "{_toml_escape(session.saved_at)}"')
        if session.source is not None:
            lines.append(f'source = "{_toml_escape(session.source)}"')
        lines.append("")

    if report is not None:
        lines.append("[detection]")
        lines.append(f'strategy = "{_toml_escape(report.strategy)}"')
        lines.append(f"confidence = {float(report.confidence):.6f}")
        lines.append(f"outline_entries = {int(report.outline_entries)}")
        if report.toc_start_page is not None:
            lines.append(f"toc_start_page = {int(report.toc_start_page)}")
        lines.append(f"toc_pages_scanned = {int(report.toc_pages_scanned)}")
        lines.append(
            "warnings = [" + ", ".join(f'"{_toml_escape(w)}"' for w in report.warnings) + "]"
        )
        lines.append("")

    for chapter in chapters:
        lines.append("[[chapters]]")
        lines.append(f'title = "{_toml_escape(chapter.title)}"')
        lines.append(f"start_page = {int(chapter.start_page)}")
        lines.append(f"end_page = {int(chapter.end_page)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _toml_escape(value: str) -> str:
    """Escape a string for use in a TOML basic string.

    Purpose:
        Keep chapter titles and warning messages safe for TOML output.
    Ties To:
        Used by _render_chapters_toml.
    Inputs:
        - value: Raw string to escape.
    Outputs:
        - Escaped string safe for TOML basic string quoting.
    Side Effects:
        None.
    Raises:
        - None.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
    return escaped


def _parse_session_metadata(
    raw: object,
    *,
    location: str,
) -> ChapterFileSessionMetadata | None:
    """Parse the optional [session] table from a chapter file.

    Purpose:
        Preserve forward-compatible metadata without making it required.
    Ties To:
        Used by load_chapter_file_with_metadata.
    Inputs:
        - raw: Raw TOML value for the 'session' key.
        - location: Fully qualified module and method name.
    Outputs:
        - ChapterFileSessionMetadata when present, otherwise None.
    Side Effects:
        None.
    Raises:
        - ValidationError: When the session table exists but is malformed.
    """
    error_location = f"{__name__}._parse_session_metadata"
    context = f" Context: {location}." if location else ""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session must be a table when present.{context}",
            )
        )
    pdf_path = raw.get("pdf_path")
    if pdf_path is not None and not isinstance(pdf_path, str):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.pdf_path must be a string when present.{context}",
            )
        )
    total_pages = raw.get("total_pages")
    if total_pages is not None and not isinstance(total_pages, int):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.total_pages must be an integer when present.{context}",
            )
        )
    saved_at = raw.get("saved_at")
    if saved_at is not None and not isinstance(saved_at, str):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.saved_at must be a string when present.{context}",
            )
        )
    source = raw.get("source")
    if source is not None and not isinstance(source, str):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.source must be a string when present.{context}",
            )
        )
    return ChapterFileSessionMetadata(
        pdf_path=pdf_path,
        total_pages=total_pages,
        saved_at=saved_at,
        source=source,
    )
