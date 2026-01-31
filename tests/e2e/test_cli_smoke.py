"""End to end smoke tests for the CLI."""

from __future__ import annotations

from pathlib import Path

from tests.shared.pdf_factory import create_sample_pdf

from chapter_splitter.cli import main as cli_main


def test_cli_split_smoke(tmp_path: Path) -> None:
    """Verify the CLI split command completes successfully.

    Purpose:
        Ensure the CLI split workflow runs end to end.
    Ties To:
        Covers chapter_splitter.cli.main and split subcommand.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes output chapter PDFs to disk.
    Raises:
        - None.
    """
    pdf_path = create_sample_pdf(tmp_path / "sample.pdf", page_count=4, outline_titles=None)
    chapters_path = tmp_path / "chapters.toml"
    chapters_path.write_text(
        """
[[chapters]]
title = "One"
start_page = 1
end_page = 2

[[chapters]]
title = "Two"
start_page = 3
end_page = 4
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "override.toml"
    config_path.write_text(
        """
[logging]
console_enabled = false
file_enabled = false
file_path = "cli.log"
""",
        encoding="utf-8",
    )
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
