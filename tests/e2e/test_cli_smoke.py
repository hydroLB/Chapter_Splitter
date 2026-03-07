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
    """Verify the CLI split command completes successfully.

    Summary:
        Ensure the CLI split workflow runs end to end.
    Ties to other methods:
        Covers chapter_splitter.cli.main and split subcommand.
    Inputs:
        - sample_pdf: Fixture providing a deterministic PDF path.
        - standard_chapters_file: Fixture providing a deterministic chapter TOML file.
        - quiet_logging_override_file: Fixture providing a deterministic logging override TOML.
    Outputs:
        - None.
    Side effects:
        Writes output chapter PDFs to disk.
    Error handling:
        - None.
    """
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
    """Verify the CLI split command can override the output directory.

    Summary:
        Allow one-off runs to direct exports without creating an override config TOML file.
    Ties to other methods:
        Covers chapter_splitter.cli.main split flags and output_dir override.
    Inputs:
        - sample_pdf: Fixture providing a deterministic PDF path.
        - standard_chapters_file: Fixture providing a deterministic chapter TOML file.
        - quiet_logging_override_file: Fixture providing a deterministic logging override TOML.
    Outputs:
        - None.
    Side effects:
        Writes output chapter PDFs to disk.
    Error handling:
        - None.
    """
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
    """Verify the CLI detect command writes a chapters TOML file.

    Summary:
        Ensure the CLI detect workflow runs end to end and produces a loadable output file.
    Ties to other methods:
        Covers chapter_splitter.cli.main detect subcommand.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
        - quiet_logging_override_file: Fixture providing a deterministic logging override TOML.
    Outputs:
        - None.
    Side effects:
        Writes a detection output TOML file to disk.
    Error handling:
        - None.
    """
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
