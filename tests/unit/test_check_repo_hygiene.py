"""Tests for the repository-hygiene enforcement script."""

import subprocess
from pathlib import Path

from scripts import check_repo_hygiene


def test_git_ignored_tracked_files_detects_tracked_ignore_matches(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], check=True, cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")

    ignored = check_repo_hygiene._git_ignored_tracked_files(tmp_path, ["source.py", "tracked.log"])

    assert ignored == ["tracked.log"]


def test_validate_tracked_ignore_rules_returns_actionable_errors() -> None:
    assert check_repo_hygiene._validate_tracked_ignore_rules([".githooks/pre-commit"]) == [
        "tracked file matches an ignore rule; narrow or remove the rule: .githooks/pre-commit"
    ]
