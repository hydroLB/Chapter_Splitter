"""Headless smoke coverage for the Qt desktop entrypoint."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from chapter_splitter.app import main as app_main
from chapter_splitter.config.loader import load_settings

pytest.importorskip("PySide6")

workflow_module = importlib.import_module("chapter_splitter.ui.qt.workflow")


def test_app_main_qt_smoke(
    monkeypatch: pytest.MonkeyPatch,
    sample_pdf: Path,
) -> None:
    """Verify the desktop entrypoint can complete a minimal headless startup path."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    settings = load_settings(None, "tests.e2e.test_gui_smoke")
    settings.ui.auto_detect_on_open = False
    settings.io.open_viewer = False
    settings.logging.console_enabled = False
    settings.logging.file_enabled = False

    monkeypatch.setattr(workflow_module, "_choose_pdf_file", lambda *_args: sample_pdf)
    monkeypatch.setattr(workflow_module, "apply_theme", lambda **_kwargs: None)
    monkeypatch.setattr(workflow_module, "install_system_theme_listener", lambda **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.ui.qt.widgets.pdf_viewer.PdfViewerWidget.load_pdf",
        lambda self, _path: True,
    )
    monkeypatch.setattr(workflow_module.MainWindow, "show", lambda self: None)
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: 0)

    assert app_main(settings=settings) == 0
