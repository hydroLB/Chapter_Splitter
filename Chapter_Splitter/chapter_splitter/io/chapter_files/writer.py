"""Chapter-file writing helpers."""

from __future__ import annotations

import os
import secrets
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from ...core.errors import IoError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...pdf.detection.report import ChapterDetectionReport
from ...utils.timing import Deadline
from .models import ChapterFileSessionMetadata
from .render import render_chapters_toml


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

    Summary:
        Validate the output path, render TOML, and persist it through an atomic rename.
    Inputs:
        - path: Output file path for the TOML chapter file.
        - chapters: Chapter definitions to serialize.
        - report: Optional detection report metadata.
        - session: Optional session metadata to include in the output file.
        - overwrite: Whether to overwrite an existing file at path.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Writes a TOML file to disk via an atomic rename.
    Error handling:
        Raises IoError when output paths are invalid or writes fail.
    Ties to other methods:
        Delegates to render_chapters_toml for serialization and _write_payload_atomically for IO.
    Why this exists:
        GUI and CLI workflows need a deterministic chapter-file writer with strong safety checks.
    """
    error_location = "chapter_splitter.io.chapter_files.writer.write_chapter_file"
    token.check(location)
    deadline.check(location)
    _validate_output_path(
        path=path,
        overwrite=overwrite,
        error_location=error_location,
        location=location,
    )
    payload = render_chapters_toml(chapters=chapters, report=report, session=session)
    _write_payload_atomically(
        path=path,
        payload=payload,
        token=token,
        deadline=deadline,
        error_location=error_location,
        location=location,
    )


def _validate_output_path(
    *,
    path: Path,
    overwrite: bool,
    error_location: str,
    location: str,
) -> None:
    """Validate and prepare the target chapter-file path.

    Summary:
        Ensure the output path is a Path, respect overwrite policy, and create its parent
        directory when needed.
    Inputs:
        - path: Candidate output file path.
        - overwrite: Whether existing files may be replaced.
        - error_location: Fully qualified helper location for error messages.
        - location: Fully qualified caller location.
    Outputs:
        - None.
    Side effects:
        Creates parent directories on disk when they do not already exist.
    Error handling:
        Raises IoError when the path is invalid, blocked by overwrite policy, or cannot be created.
    Ties to other methods:
        Used by write_chapter_file.
    Why this exists:
        Output-path validation is separate from TOML rendering and atomic write mechanics.
    """
    context = f" Context: {location}." if location else ""
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


def _write_payload_atomically(
    *,
    path: Path,
    payload: str,
    token: CancellationToken,
    deadline: Deadline,
    error_location: str,
    location: str,
) -> None:
    """Write a TOML payload to disk via a temporary file and atomic rename.

    Summary:
        Persist the rendered chapter TOML text safely so interrupted writes do not leave partial
        files behind.
    Inputs:
        - path: Final output path.
        - payload: Rendered TOML payload.
        - token: Cancellation token for graceful shutdown.
        - deadline: Deadline tracker for timeout enforcement.
        - error_location: Fully qualified helper location for error messages.
        - location: Fully qualified caller location.
    Outputs:
        - None.
    Side effects:
        Writes a temporary file and atomically replaces the destination path.
    Error handling:
        Raises IoError when writing or replacing the file fails and cleans up temp files best
        effort.
    Ties to other methods:
        Used by write_chapter_file.
    Why this exists:
        Atomic writes are a separate concern from payload rendering and path validation.
    """
    context = f" Context: {location}." if location else ""
    token.check(location)
    deadline.check(location)

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


__all__ = ["write_chapter_file"]
