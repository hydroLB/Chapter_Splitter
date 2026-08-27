"""Tests for standalone bundle construction and verification helpers."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import bundle_pyinstaller


def test_gui_bundle_declares_lazy_workflow_as_hidden_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The GUI bundle must include the workflow loaded dynamically by app.py."""
    entry = tmp_path / "entry.py"
    entry.write_text("", encoding="utf-8")
    captured: list[str] = []

    def _run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)

    bundle_pyinstaller._run_pyinstaller(
        entry=entry,
        name="ChapterSplitter",
        windowed=True,
        onefile=False,
        dist_dir=tmp_path / "dist",
        work_dir=tmp_path / "work",
        hidden_imports=(bundle_pyinstaller.GUI_WORKFLOW_MODULE,),
    )

    hidden_index = captured.index("--hidden-import")
    assert captured[hidden_index + 1] == bundle_pyinstaller.GUI_WORKFLOW_MODULE


def test_log_contains_event_ignores_unrelated_and_malformed_lines(tmp_path: Path) -> None:
    """Startup verification should use the structured event instead of brittle text matching."""
    log_path = tmp_path / "startup.jsonl"
    log_path.write_text(
        'not-json\n{"event": "other"}\n{"event": "app_started"}\n',
        encoding="utf-8",
    )

    assert bundle_pyinstaller._log_contains_event(log_path, "app_started")
    assert not bundle_pyinstaller._log_contains_event(log_path, "missing")
    assert not bundle_pyinstaller._log_contains_event(tmp_path / "absent.jsonl", "app_started")


def test_finalize_macos_bundle_uses_project_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """macOS artifacts should not ship with PyInstaller's 0.0.0 placeholder metadata."""
    app_bundle = tmp_path / "ChapterSplitter.app"
    contents = app_bundle / "Contents"
    executable = contents / "MacOS" / "ChapterSplitter"
    executable.parent.mkdir(parents=True)
    executable.touch()
    info_path = contents / "Info.plist"
    with info_path.open("wb") as write_stream:
        plistlib.dump({"CFBundleShortVersionString": "0.0.0"}, write_stream)
    captured: list[str] = []

    def _run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", _run)

    bundle_pyinstaller._finalize_macos_bundle(executable, project_version="0.1.0")

    with info_path.open("rb") as read_stream:
        info = plistlib.load(read_stream)
    assert info["CFBundleDisplayName"] == "PDF Chapter Splitter"
    assert info["CFBundleIdentifier"] == bundle_pyinstaller.MACOS_BUNDLE_IDENTIFIER
    assert info["CFBundleShortVersionString"] == "0.1.0"
    assert info["CFBundleVersion"] == "0.1.0"
    assert captured[:6] == ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)]
