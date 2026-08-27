"""Interaction regression tests for the editable Qt chapters table."""

from __future__ import annotations

import os
from collections.abc import Iterator
from importlib import import_module
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from chapter_splitter.config.schema import ValidationConfig
from chapter_splitter.ui.qt.widgets.chapters_table import ChaptersTableWidget

QtTest = import_module("PySide6.QtTest")


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QtWidgets.QApplication]:
    """Provide the one QApplication permitted in a process."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def _chapters_table() -> ChaptersTableWidget:
    """Build a two-row table with the standard strict validation policy."""
    table = ChaptersTableWidget(
        total_pages=20,
        title_prefix="Chapter",
        validation_config=ValidationConfig(
            max_chapters=20,
            require_unique_titles=True,
            sort_chapters_by_start_page=True,
            reject_overlapping_ranges=True,
        ),
    )
    table.add_blank_chapter()
    table.add_blank_chapter()
    return table


@pytest.mark.parametrize("column", [0, 1, 2], ids=["title", "start", "end"])
def test_clicking_editor_selects_its_row_before_actions_run(
    qt_app: QtWidgets.QApplication,
    column: int,
) -> None:
    """A title or boundary editor click must retarget Set Start/End to that row."""
    chapters = _chapters_table()
    chapters.show()
    qt_app.processEvents()
    chapters.table().selectRow(1)

    editor = chapters.table().cellWidget(0, column)
    assert editor is not None
    mouse_button = cast(Any, QtCore.Qt).MouseButton.LeftButton
    QtTest.QTest.mouseClick(editor, mouse_button)
    qt_app.processEvents()

    assert chapters.selected_row_index() == 0
    chapters.close()


def test_keyboard_focus_selects_editor_row(qt_app: QtWidgets.QApplication) -> None:
    """Tab-style focus changes row targeting without altering editor key handling."""
    chapters = _chapters_table()
    chapters.show()
    qt_app.processEvents()
    chapters.table().selectRow(1)

    editor = chapters.table().cellWidget(0, 0)
    assert editor is not None
    focus_reason = cast(Any, QtCore.Qt).FocusReason.TabFocusReason
    editor.setFocus(focus_reason)
    qt_app.processEvents()

    assert chapters.selected_row_index() == 0
    chapters.close()
