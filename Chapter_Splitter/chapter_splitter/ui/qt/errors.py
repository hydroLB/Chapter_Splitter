"""Qt GUI error helpers.

Summary:
    Provide small helpers to convert common runtime exceptions into user-facing dialogs.
Inputs:
    - None.
Outputs:
    - None.
Side effects:
    Imports Qt modules when called.
Error handling:
    All helpers are best-effort and never raise from dialog display.
Ties to other methods:
    Used by ui.qt.workflow and window controllers to surface errors consistently.
Why this exists:
    Centralized error dialogs keep the UI consistent and reduce duplicated try/except blocks.
"""

from __future__ import annotations

from contextlib import suppress


def show_error_dialog(*, title: str, message: str) -> None:
    """Show a modal error dialog.

    Summary:
        Display a user-facing error message in a consistent Qt dialog.
    Inputs:
        - title: Dialog title string.
        - message: Dialog message body.
    Outputs:
        - None.
    Side effects:
        Shows a modal QMessageBox.
    Error handling:
        Suppresses any Qt errors so failures do not crash the process.
    Ties to other methods:
        Called by the workflow boundary exception handlers.
    Why this exists:
        Error messaging should not rely on stack traces or logging for basic user recovery.
    """
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def show_warning_dialog(*, title: str, message: str) -> None:
    """Show a modal warning dialog.

    Summary:
        Display a user-facing warning message in a consistent Qt dialog.
    Inputs:
        - title: Dialog title string.
        - message: Dialog message body.
    Outputs:
        - None.
    Side effects:
        Shows a modal QMessageBox.
    Error handling:
        Suppresses any Qt errors so failures do not crash the process.
    Ties to other methods:
        Called by UI actions that can be safely retried by the user.
    Why this exists:
        Warnings should be visible but non-fatal.
    """
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def show_info_dialog(*, title: str, message: str) -> None:
    """Show a modal information dialog.

    Summary:
        Display a user-facing informational message in a consistent Qt dialog.
    Inputs:
        - title: Dialog title string.
        - message: Dialog message body.
    Outputs:
        - None.
    Side effects:
        Shows a modal QMessageBox.
    Error handling:
        Suppresses any Qt errors so failures do not crash the process.
    Ties to other methods:
        Used by workflows for success and detection result messages.
    Why this exists:
        Success and status dialogs should not be styled differently from warnings and errors.
    """
    with suppress(Exception):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()


def ask_yes_no(*, title: str, message: str) -> bool:
    """Prompt the user with a yes or no question.

    Summary:
        Display a modal yes or no prompt and return the selected response.
    Inputs:
        - title: Dialog title string.
        - message: Dialog message body.
    Outputs:
        - True when the user selects Yes, otherwise False.
    Side effects:
        Shows a modal QMessageBox.
    Error handling:
        Returns False when dialog display fails.
    Ties to other methods:
        Used by export flows to ask whether to open the output folder.
    Why this exists:
        A consistent prompt avoids platform-specific messagebox APIs across UI layers.
    """
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
