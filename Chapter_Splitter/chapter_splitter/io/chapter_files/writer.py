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
    """Write chapter definitions to a TOML file."""
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
        overwrite=overwrite,
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
    """Validate and prepare the target chapter-file path."""
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
    overwrite: bool,
    token: CancellationToken,
    deadline: Deadline,
    error_location: str,
    location: str,
) -> None:
    """Write a TOML payload to disk via a temporary file and atomic rename."""
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
        if overwrite:
            tmp_path.replace(path)
        else:
            # Commit without a check-then-replace race: the hard link is
            # atomic and fails if another process already claimed the path.
            os.link(tmp_path, path)
            tmp_path.unlink()
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
