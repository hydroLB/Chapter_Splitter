"""Staged and transactional PDF writing helpers for chapter exports."""

from __future__ import annotations

import os
import secrets
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from ....config.schema import IOConfig
from ....core.errors import IoError, format_error_message
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ...io.dependencies import PdfWriter


@dataclass(slots=True)
class StagedPdf:
    """A serialized chapter waiting to be published at its final path."""

    staged_path: Path
    output_path: Path
    backup_path: Path | None = None
    installed: bool = False


def stage_pdf(
    out_path: Path,
    *,
    writer: PdfWriter,
    io_config: IOConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> StagedPdf:
    """Serialize a PDF to a hidden staging file beside its final destination."""
    token.check(location)
    deadline.check(location)
    error_location = "chapter_splitter.pdf.splitting.engine.writer.stage_pdf"
    context = f" Context: {location}." if location else ""

    tmp_path: Path | None = None
    staged_successfully = False
    try:
        tmp_prefix = f".{out_path.stem}.stage-"
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
        staged_successfully = True
        return StagedPdf(staged_path=tmp_path, output_path=out_path)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Failed to write chapter output: {out_path}.{context}",
            )
        ) from exc
    finally:
        if tmp_path is not None and tmp_path.exists() and not staged_successfully:
            with suppress(OSError):
                tmp_path.unlink()


def commit_pdf_batch(staged_pdfs: list[StagedPdf], *, allow_overwrite: bool) -> None:
    """Publish all staged PDFs, restoring the prior filesystem state on commit failure.

    Each install uses an atomic filesystem primitive, but the batch necessarily performs multiple
    operations. Backups and reverse-order rollback provide transactional behavior for ordinary
    filesystem failures; process termination during the commit window remains a platform limit.
    """
    rollback_complete = True
    try:
        for staged in staged_pdfs:
            if allow_overwrite:
                if staged.output_path.exists():
                    if not staged.output_path.is_file():
                        raise IsADirectoryError(staged.output_path)
                    staged.backup_path = _backup_path_for(staged.output_path)
                    _replace_path(staged.output_path, staged.backup_path)
                _replace_path(staged.staged_path, staged.output_path)
                staged.installed = True
            else:
                _link_path(staged.staged_path, staged.output_path)
                staged.installed = True
                staged.staged_path.unlink()
    except OSError as exc:
        rollback_complete = _rollback_pdf_batch(staged_pdfs)
        output_path = _current_output_path(staged_pdfs)
        raise IoError(
            format_error_message(
                "chapter_splitter.pdf.splitting.engine.writer.commit_pdf_batch",
                f"Failed to commit chapter output batch near: {output_path}.",
            )
        ) from exc
    else:
        for staged in staged_pdfs:
            if staged.backup_path is not None:
                with suppress(OSError):
                    staged.backup_path.unlink()
    finally:
        cleanup_staged_pdfs(staged_pdfs, remove_backups=rollback_complete)


def cleanup_staged_pdfs(staged_pdfs: list[StagedPdf], *, remove_backups: bool = True) -> None:
    """Remove staging artifacts and disposable backups best effort."""
    for staged in staged_pdfs:
        artifacts: list[Path | None] = [staged.staged_path]
        if remove_backups:
            artifacts.append(staged.backup_path)
        for artifact in artifacts:
            if artifact is not None and artifact.exists():
                with suppress(OSError):
                    artifact.unlink()


def _rollback_pdf_batch(staged_pdfs: list[StagedPdf]) -> bool:
    """Undo installed outputs and report whether every original was restored."""
    rollback_complete = True
    for staged in reversed(staged_pdfs):
        if staged.installed and staged.output_path.exists():
            try:
                staged.output_path.unlink()
            except OSError:
                rollback_complete = False
        if staged.backup_path is not None and staged.backup_path.exists():
            try:
                _replace_path(staged.backup_path, staged.output_path)
            except OSError:
                rollback_complete = False
    return rollback_complete


def _backup_path_for(output_path: Path) -> Path:
    """Create a collision-resistant hidden backup pathname beside an overwrite target."""
    while True:
        candidate = output_path.parent / (
            f".{output_path.stem}.backup-{secrets.token_hex(12)}{output_path.suffix}"
        )
        if not candidate.exists():
            return candidate


def _replace_path(source: Path, destination: Path) -> None:
    """Rename source to destination through a narrow failure-injection seam."""
    source.replace(destination)


def _link_path(source: Path, destination: Path) -> None:
    """Atomically install a staged file only when the destination does not exist."""
    os.link(source, destination)


def _current_output_path(staged_pdfs: list[StagedPdf]) -> Path:
    """Return the first uninstalled output, or the last output for commit diagnostics."""
    for staged in staged_pdfs:
        if not staged.installed:
            return staged.output_path
    return staged_pdfs[-1].output_path


def _write_pdf_bytes(
    *,
    writer: PdfWriter,
    handle: BinaryIO,
    io_config: IOConfig,
    location: str,
) -> None:
    """Write PDF bytes into an already-open temp file handle."""
    write_deadline = Deadline(io_config.pdf_write_timeout_seconds)
    write_deadline.check(location)
    writer.write(handle)
    handle.flush()
    if io_config.fsync_writes:
        os.fsync(handle.fileno())
    write_deadline.check(location)


__all__ = ["StagedPdf", "cleanup_staged_pdfs", "commit_pdf_batch", "stage_pdf"]
