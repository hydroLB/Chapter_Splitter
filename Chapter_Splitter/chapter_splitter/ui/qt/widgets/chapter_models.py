"""Shared chapter table widget models."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtWidgets


@dataclass(frozen=True, slots=True)
class ChapterRowWidgets:
    """Per-row editor widget references."""

    title: QtWidgets.QLineEdit
    start: QtWidgets.QSpinBox
    end: QtWidgets.QSpinBox
    remove: QtWidgets.QToolButton


__all__ = ["ChapterRowWidgets"]
