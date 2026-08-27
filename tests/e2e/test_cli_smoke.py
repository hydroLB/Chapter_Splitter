"""End to end smoke tests for the CLI."""

from __future__ import annotations

from pathlib import Path

from tests.shared.pdf_factory import create_sample_pdf

from chapter_splitter.cli import main as cli_main


def test_cli_split_smoke(
    sample_pdf: Path,
    standard_chapters_file: Path,
    quiet_logging_override_file: Path,
) -> None:
    """Verify the CLI split command completes successfully."""
    pdf_path = sample_pdf
    chapters_path = standard_chapters_file
    config_path = quiet_logging_override_file
    exit_code = cli_main(
        [
            "--config",
            str(config_path),
            "split",
            "--pdf",
            str(pdf_path),
            "--chapters",
            str(chapters_path),
        ]
    )
    assert exit_code == 0


def test_cli_split_respects_output_dir(
    sample_pdf: Path,
    standard_chapters_file: Path,
    quiet_logging_override_file: Path,
) -> None:
    """Verify the CLI split command can override the output directory."""
    pdf_path = sample_pdf
    chapters_path = standard_chapters_file
    config_path = quiet_logging_override_file
    out_dir = pdf_path.parent / "custom-output"
    exit_code = cli_main(
        [
            "--config",
            str(config_path),
            "split",
            "--pdf",
            str(pdf_path),
            "--chapters",
            str(chapters_path),
            "--output-dir",
            str(out_dir),
        ]
    )
    assert exit_code == 0
    assert (out_dir / "One.pdf").exists()
    assert (out_dir / "Two.pdf").exists()


def test_cli_detect_smoke(tmp_path: Path, quiet_logging_override_file: Path) -> None:
    """Verify the CLI detect command writes a chapters TOML file."""
    pdf_path = create_sample_pdf(
        tmp_path / "outlined.pdf",
        page_count=4,
        outline_titles=["One", "Two"],
    )
    out_path = tmp_path / "chapters.detected.toml"
    config_path = quiet_logging_override_file
    exit_code = cli_main(
        [
            "--config",
            str(config_path),
            "detect",
            "--pdf",
            str(pdf_path),
            "--strategy",
            "outlines",
            "--out",
            str(out_path),
        ]
    )
    assert exit_code == 0
    text = out_path.read_text(encoding="utf-8")
    assert "[detection]" in text
    assert 'strategy = "outlines"' in text
    assert "[[chapters]]" in text
