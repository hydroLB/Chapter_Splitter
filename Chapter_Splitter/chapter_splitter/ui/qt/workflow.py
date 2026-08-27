"""Qt workflow entrypoint for the Chapter Splitter GUI."""

from __future__ import annotations

import logging
from pathlib import Path

from ...config.schema import Settings
from ...core.error_mapping import map_error
from ...core.errors import UiError, format_error_message
from ...core.runtime import CancellationToken
from ...pdf.io.loader import get_total_pages, load_reader
from ...utils.rate_limit import RateLimiter
from ...utils.timing import Deadline
from .errors import show_error_dialog
from .main_window import MainWindow
from .theme import apply_theme, install_system_theme_listener
from .workflow_actions import build_workflow_actions

logger = logging.getLogger(__name__)


def workflow(settings: Settings, token: CancellationToken) -> None:
    """Run the Qt GUI flow for selecting and splitting a PDF."""
    location = "chapter_splitter.ui.qt.workflow.workflow"
    token.check(location)

    try:
        from PySide6 import QtCore, QtWidgets
    except Exception as exc:
        raise UiError(
            format_error_message(
                location,
                f"Qt GUI dependencies are missing: {exc}. Install with: "
                "pip install -e '.[desktop]'",
            )
        ) from exc

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    shutdown_timer = QtCore.QTimer(app)
    shutdown_timer.setInterval(100)
    shutdown_timer.timeout.connect(lambda: app.quit() if token.is_cancelled() else None)
    shutdown_timer.start()
    apply_theme(app=app, color_mode=settings.ui.color_mode)
    install_system_theme_listener(app=app, color_mode=settings.ui.color_mode)

    pdf_path = _choose_pdf_file(settings, location)
    if pdf_path is None:
        return

    read_deadline = Deadline(settings.io.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, settings.retry, location)
    total_pages = get_total_pages(reader, location)

    win = MainWindow(
        pdf_path=pdf_path,
        total_pages=total_pages,
        ui_config=settings.ui,
        validation_config=settings.validation,
    )
    if not win.viewer().load_pdf(pdf_path):
        show_error_dialog(title=settings.ui.error_dialog_title, message="Unable to open PDF.")
        return
    win.set_status(level="ready", text=f"Loaded {pdf_path.name}")

    action_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)
    win.set_undo_available(False)

    actions, auto_detect_callback = build_workflow_actions(
        settings=settings,
        token=token,
        location=location,
        pdf_path=pdf_path,
        total_pages=total_pages,
        reader=reader,
        win=win,
        action_limiter=action_limiter,
        logger=logger,
    )
    win.set_actions(actions)

    win.show()
    if settings.ui.auto_detect_on_open:
        QtCore.QTimer.singleShot(0, auto_detect_callback)
    app.exec()


def _choose_pdf_file(settings: Settings, location: str) -> Path | None:
    """Open a Qt file dialog and return a selected PDF path."""
    try:
        from PySide6 import QtWidgets

        filename, _filter = QtWidgets.QFileDialog.getOpenFileName(
            None,
            settings.ui.file_dialog_title,
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)",
        )
    except Exception as exc:
        payload = map_error(exc, channel="ui", location=location)
        from ...observability.logging import log_event

        log_event(
            logger,
            payload.log_level,
            "qt_file_dialog_failed",
            payload.message,
            payload.log_fields(location=location),
        )
        show_error_dialog(title=settings.ui.error_dialog_title, message=payload.user_message)
        return None
    if not filename:
        return None
    return Path(filename)
