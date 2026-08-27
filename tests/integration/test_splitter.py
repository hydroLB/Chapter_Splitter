"""Integration tests for PDF splitting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

import pytest

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import CancellationToken, ChapterDefinition, IoError, ValidationError
from chapter_splitter.pdf.splitting import split_pdf_into_chapters
from chapter_splitter.utils import Deadline


def test_split_pdf_into_chapters_creates_outputs(sample_pdf: Path) -> None:
    """Verify splitting creates the expected output files."""
    settings = load_settings(None, "tests.integration.test_splitter")
    chapters = [
        ChapterDefinition(title="Alpha", start_page=1, end_page=2),
        ChapterDefinition(title="Beta", start_page=3, end_page=4),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )
    assert len(outputs) == 2
    for output in outputs:
        assert output.output_path.exists()
        assert output.output_path.read_bytes().startswith(b"%PDF")


def test_split_rejects_existing_output_when_policy_error(sample_pdf: Path) -> None:
    """Verify policy error blocks export when an output path already exists."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "error"
    chapters = [ChapterDefinition(title="Alpha", start_page=1, end_page=1)]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "Alpha.pdf").write_bytes(b"existing")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(IoError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )


def test_split_suffix_policy_generates_unique_paths(sample_pdf: Path) -> None:
    """Verify suffix collision policy generates unique output filenames."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "suffix"
    settings.io.output_collision_max_suffix = 10
    chapters = [
        ChapterDefinition(title="Alpha/", start_page=1, end_page=1),
        ChapterDefinition(title="Alpha:", start_page=2, end_page=2),
    ]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "Alpha_.pdf").write_bytes(b"existing")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )
    out_names = {output.output_path.name for output in outputs}
    assert out_names == {"Alpha_ (2).pdf", "Alpha_ (3).pdf"}


@pytest.mark.parametrize("collision_policy", ["error", "overwrite"])
def test_split_rejects_case_insensitive_within_run_collisions(
    sample_pdf: Path,
    collision_policy: Literal["error", "overwrite"],
) -> None:
    """Non-suffix policies must not target one file twice on case-insensitive filesystems."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = collision_policy
    chapters = [
        ChapterDefinition(title="Chapter", start_page=1, end_page=1),
        ChapterDefinition(title="chapter", start_page=2, end_page=2),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()

    with pytest.raises(ValidationError, match="same cross-platform output filename"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    assert not list(output_dir.glob("*.pdf"))


def test_split_suffix_policy_normalizes_unicode_and_case_collisions(sample_pdf: Path) -> None:
    """Suffix allocation uses portable keys while preserving readable output capitalization."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "suffix"
    settings.io.output_collision_max_suffix = 10
    chapters = [
        ChapterDefinition(title="Résumé", start_page=1, end_page=1),
        ChapterDefinition(title="résumé", start_page=2, end_page=2),
        ChapterDefinition(title="Re\u0301sume\u0301", start_page=3, end_page=3),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()

    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )

    assert [output.output_path.name for output in outputs] == [
        "Résumé.pdf",
        "résumé (2).pdf",
        "Résumé (3).pdf",
    ]


def test_split_error_policy_rejects_case_variant_existing_output(sample_pdf: Path) -> None:
    """Existing names should collide using portable rules even on case-sensitive filesystems."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "error"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    existing_path = output_dir / "INTRO.pdf"
    existing_path.write_bytes(b"existing")

    with pytest.raises(IoError, match="conflicts cross-platform"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=[ChapterDefinition(title="Intro", start_page=1, end_page=1)],
            page_offset=None,
            deadline=Deadline(settings.io.operation_timeout_seconds),
            token=CancellationToken(),
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    assert existing_path.read_bytes() == b"existing"
    assert {path.name for path in output_dir.iterdir()} == {"INTRO.pdf"}


def test_split_suffix_policy_skips_case_variant_existing_output(sample_pdf: Path) -> None:
    """Suffix allocation should reserve portable keys for files from previous runs."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "suffix"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "RÉSUMÉ.pdf").write_bytes(b"existing")

    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=[ChapterDefinition(title="Résumé", start_page=1, end_page=1)],
        page_offset=None,
        deadline=Deadline(settings.io.operation_timeout_seconds),
        token=CancellationToken(),
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )

    assert [output.output_path.name for output in outputs] == ["Résumé (2).pdf"]


def test_split_overwrite_policy_reuses_case_variant_existing_output(sample_pdf: Path) -> None:
    """Overwrite mode should replace the portable match instead of creating a second name."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    existing_path = output_dir / "INTRO.pdf"
    existing_path.write_bytes(b"existing")

    outputs = split_pdf_into_chapters(
        pdf_path=sample_pdf,
        chapters=[ChapterDefinition(title="Intro", start_page=1, end_page=1)],
        page_offset=None,
        deadline=Deadline(settings.io.operation_timeout_seconds),
        token=CancellationToken(),
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="tests.integration.test_splitter",
    )

    assert [output.output_path for output in outputs] == [existing_path]
    assert existing_path.read_bytes().startswith(b"%PDF")
    assert {path.name for path in output_dir.iterdir()} == {"INTRO.pdf"}


def test_split_validates_overlapping_ranges(sample_pdf: Path) -> None:
    """Verify overlap validation prevents ambiguous exports."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.validation.reject_overlapping_ranges = True
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=3),
        ChapterDefinition(title="Two", start_page=3, end_page=4),
    ]
    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(ValidationError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )


def test_split_atomic_overwrite_does_not_corrupt_existing_file_on_failure(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify atomic writing preserves existing output files if a write fails."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    chapters = [ChapterDefinition(title="Alpha", start_page=1, end_page=1)]
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / "Alpha.pdf"
    out_path.write_bytes(b"ORIGINAL")

    class _FailingWriter:
        def add_page(self, _page: object) -> None:
            return None

        def write(self, handle: BinaryIO) -> None:
            handle.write(b"partial")
            raise OSError("simulated write failure")

    monkeypatch.setattr(
        "chapter_splitter.pdf.splitting.splitter.PdfWriter",
        _FailingWriter,
    )

    deadline = Deadline(settings.io.operation_timeout_seconds)
    token = CancellationToken()
    with pytest.raises(IoError):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )
    assert out_path.read_bytes() == b"ORIGINAL"
    assert not any(output_dir.glob(".Alpha.tmp-*"))


def test_split_staging_failure_leaves_entire_batch_unchanged(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later serialization failure must not publish or overwrite any chapter."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    alpha_path = output_dir / "Alpha.pdf"
    alpha_path.write_bytes(b"ALPHA ORIGINAL")

    writer_module = cast(Any, sys.modules["chapter_splitter.pdf.splitting.engine.writer"])
    real_write_pdf_bytes = writer_module._write_pdf_bytes
    write_count = 0

    def _fail_second_stage(**kwargs: Any) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("simulated second chapter staging failure")
        real_write_pdf_bytes(**kwargs)

    monkeypatch.setattr(writer_module, "_write_pdf_bytes", _fail_second_stage)

    with pytest.raises(IoError, match="Failed to write chapter output"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=[
                ChapterDefinition(title="Alpha", start_page=1, end_page=1),
                ChapterDefinition(title="Beta", start_page=2, end_page=2),
            ],
            page_offset=None,
            deadline=Deadline(settings.io.operation_timeout_seconds),
            token=CancellationToken(),
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    assert alpha_path.read_bytes() == b"ALPHA ORIGINAL"
    assert not (output_dir / "Beta.pdf").exists()
    assert {path.name for path in output_dir.iterdir()} == {"Alpha.pdf"}


def test_split_commit_failure_restores_all_overwritten_originals(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mid-commit rename failure must roll back earlier replacements and backups."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    alpha_path = output_dir / "Alpha.pdf"
    beta_path = output_dir / "Beta.pdf"
    alpha_path.write_bytes(b"ALPHA ORIGINAL")
    beta_path.write_bytes(b"BETA ORIGINAL")

    writer_module = cast(Any, sys.modules["chapter_splitter.pdf.splitting.engine.writer"])
    real_replace_path = writer_module._replace_path

    def _fail_beta_install(source: Path, destination: Path) -> None:
        if source.name.startswith(".Beta.stage-"):
            raise OSError("simulated later chapter commit failure")
        real_replace_path(source, destination)

    monkeypatch.setattr(writer_module, "_replace_path", _fail_beta_install)

    with pytest.raises(IoError, match="Failed to commit chapter output batch"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=[
                ChapterDefinition(title="Alpha", start_page=1, end_page=1),
                ChapterDefinition(title="Gamma", start_page=2, end_page=2),
                ChapterDefinition(title="Beta", start_page=3, end_page=3),
            ],
            page_offset=None,
            deadline=Deadline(settings.io.operation_timeout_seconds),
            token=CancellationToken(),
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    assert alpha_path.read_bytes() == b"ALPHA ORIGINAL"
    assert beta_path.read_bytes() == b"BETA ORIGINAL"
    assert not (output_dir / "Gamma.pdf").exists()
    assert {path.name for path in output_dir.iterdir()} == {"Alpha.pdf", "Beta.pdf"}


def test_split_non_overwrite_commit_does_not_clobber_racing_target(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target created after collision planning must survive the no-clobber commit."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "error"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    racing_path = output_dir / "Beta.pdf"

    writer_module = cast(Any, sys.modules["chapter_splitter.pdf.splitting.engine.writer"])
    real_link_path = writer_module._link_path

    def _create_target_before_link(source: Path, destination: Path) -> None:
        if destination == racing_path:
            destination.write_bytes(b"CONCURRENT OUTPUT")
        real_link_path(source, destination)

    monkeypatch.setattr(writer_module, "_link_path", _create_target_before_link)

    with pytest.raises(IoError, match="Failed to commit chapter output batch"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=[
                ChapterDefinition(title="Alpha", start_page=1, end_page=1),
                ChapterDefinition(title="Beta", start_page=2, end_page=2),
            ],
            page_offset=None,
            deadline=Deadline(settings.io.operation_timeout_seconds),
            token=CancellationToken(),
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    assert not (output_dir / "Alpha.pdf").exists()
    assert racing_path.read_bytes() == b"CONCURRENT OUTPUT"
    assert {path.name for path in output_dir.iterdir()} == {"Beta.pdf"}


def test_split_incomplete_rollback_preserves_recovery_backup(
    sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A backup must survive when restoring its original output path fails."""
    settings = load_settings(None, "tests.integration.test_splitter")
    settings.io.output_collision_policy = "overwrite"
    output_dir = sample_pdf.parent / f"{sample_pdf.stem}{settings.io.output_dir_suffix}"
    output_dir.mkdir(exist_ok=True)
    alpha_path = output_dir / "Alpha.pdf"
    beta_path = output_dir / "Beta.pdf"
    alpha_path.write_bytes(b"ALPHA ORIGINAL")
    beta_path.write_bytes(b"BETA ORIGINAL")

    writer_module = cast(Any, sys.modules["chapter_splitter.pdf.splitting.engine.writer"])
    real_replace_path = writer_module._replace_path

    def _fail_beta_install_and_restore(source: Path, destination: Path) -> None:
        if source.name.startswith((".Beta.stage-", ".Beta.backup-")):
            raise OSError("simulated Beta commit and rollback failure")
        real_replace_path(source, destination)

    monkeypatch.setattr(writer_module, "_replace_path", _fail_beta_install_and_restore)

    with pytest.raises(IoError, match="Failed to commit chapter output batch"):
        split_pdf_into_chapters(
            pdf_path=sample_pdf,
            chapters=[
                ChapterDefinition(title="Alpha", start_page=1, end_page=1),
                ChapterDefinition(title="Beta", start_page=2, end_page=2),
            ],
            page_offset=None,
            deadline=Deadline(settings.io.operation_timeout_seconds),
            token=CancellationToken(),
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=settings.io,
            location="tests.integration.test_splitter",
        )

    assert alpha_path.read_bytes() == b"ALPHA ORIGINAL"
    assert not beta_path.exists()
    recovery_backups = list(output_dir.glob(".Beta.backup-*.pdf"))
    assert len(recovery_backups) == 1
    assert recovery_backups[0].read_bytes() == b"BETA ORIGINAL"
    assert not list(output_dir.glob(".*.stage-*.pdf"))
