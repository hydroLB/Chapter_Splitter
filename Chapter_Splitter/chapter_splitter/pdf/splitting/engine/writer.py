"""Atomic PDF writing helpers for chapter exports."""

from __future__ import annotations

import os
import secrets
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO, cast

from ....config.schema import IOConfig
from ....core.errors import IoError, format_error_message
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ...io.dependencies import PdfWriter


def atomic_write_pdf(
    out_path: Path,
    *,
    writer: PdfWriter,
    io_config: IOConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> None:
    """Write a PDF output via a temporary file and atomic rename.

    Summary:
        Prevent partial output files by writing to a temporary file in the target directory and
        then atomically replacing the destination path.
    Inputs:
        - out_path: Final output path to create or replace.
        - writer: PdfWriter containing the pages to export.
        - io_config: IO configuration controlling write timeout and fsync behavior.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for cooperative cancellation.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Writes a temporary file and then moves it into place.
    Error handling:
        Raises IoError when writes or renames fail and cleans up temp files best effort.
    Ties to other methods:
        Used by split_pdf_into_chapters for each chapter output.
    Why this exists:
        Users should never be left with corrupted or half-written PDFs if an export is interrupted.
    """
    token.check(location)
    deadline.check(location)
    error_location = "chapter_splitter.pdf.splitting.engine.writer.atomic_write_pdf"
    context = f" Context: {location}." if location else ""

    tmp_path: Path | None = None
    try:
        tmp_prefix = f".{out_path.stem}.tmp-"
        tmp_suffix = f"-{secrets.token_hex(6)}{out_path.suffix}"
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(out_path.parent),
            prefix=tmp_prefix,
            suffix=tmp_suffix,
        ) as handle:
            tmp_path = Path(handle.name)
            _write_pdf_bytes(
                writer=writer,
                handle=cast(BinaryIO, handle),
                io_config=io_config,
                location=location,
            )
        tmp_path.replace(out_path)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to write chapter output: {out_path}.{context}",
            )
        ) from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()


def _write_pdf_bytes(
    *,
    writer: PdfWriter,
    handle: BinaryIO,
    io_config: IOConfig,
    location: str,
) -> None:
    """Write PDF bytes into an already-open temp file handle.

    Summary:
        Perform the low-level writer serialization and durability steps for a chapter export.
    Inputs:
        - writer: PdfWriter containing the pages to export.
        - handle: Open writable binary handle for the temporary file.
        - io_config: IO configuration controlling write timeout and fsync behavior.
        - location: Fully qualified caller location.
    Outputs:
        - None.
    Side effects:
        Writes bytes to the file handle and may call fsync.
    Error handling:
        Propagates exceptions raised by PdfWriter or the underlying file handle.
    Ties to other methods:
        Used by atomic_write_pdf.
    Why this exists:
        Separating raw write mechanics keeps atomic_write_pdf focused on temp-file orchestration.
    """
    write_deadline = Deadline(io_config.pdf_write_timeout_seconds)
    write_deadline.check(location)
    writer.write(handle)
    handle.flush()
    if io_config.fsync_writes:
        os.fsync(handle.fileno())
    write_deadline.check(location)


__all__ = ["atomic_write_pdf"]
