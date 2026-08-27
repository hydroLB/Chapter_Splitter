"""Qt GUI error helpers."""

from __future__ import annotations

from contextlib import suppress


def show_error_dialog(*, title: str, message: str) -> None:
    """Show a modal error dialog."""
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def show_warning_dialog(*, title: str, message: str) -> None:
    """Show a modal warning dialog."""
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def show_info_dialog(*, title: str, message: str) -> None:
    """Show a modal information dialog."""
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def ask_yes_no(*, title: str, message: str) -> bool:
    """Prompt the user with a yes or no question."""
    with suppress(Exception):
        from PySide6 import QtWidgets
        from PySide6.QtWidgets import QMessageBox

        parent = QtWidgets.QApplication.activeWindow()
        if parent is None:
            parent = QtWidgets.QWidget()

        response = QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes
    return False
