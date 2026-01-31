"""Tkinter workflow for PDF chapter splitting."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Sequence
from pathlib import Path
from tkinter import messagebox, ttk

from ...config.schema import Settings
from ...core.errors import (
    CancellationError,
    ChapterSplitterError,
    IoError,
    UiError,
    format_error_message,
)
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...observability.logging import log_event, new_correlation_id, set_correlation_id
from ...pdf.detection.outlines import detect_chapters_from_outlines
from ...pdf.io.labels import extract_page_labels
from ...pdf.io.loader import load_reader
from ...pdf.splitting.splitter import split_pdf_into_chapters
from ...utils.rate_limit import RateLimiter
from ...utils.retry import retry_with_backoff
from ...utils.timing import Deadline
from ...utils.viewer import open_in_default_viewer
from .dialogs import choose_pdf_file
from .windows.chapter_window import build_chapter_window

logger = logging.getLogger(__name__)


def workflow(settings: Settings, token: CancellationToken) -> None:
    """Run the GUI flow for selecting and splitting a PDF.

    Purpose:
        Drive the user workflow from file selection to chapter export.
    Ties To:
        Called by the GUI entry point in chapter_splitter.app.
    Inputs:
        - settings: Application settings.
        - token: Cancellation token for graceful shutdown.
    Outputs:
        - None.
    Side Effects:
        Launches Tkinter windows and performs file IO.
    Raises:
        - UiError: When UI setup fails.
    """
    location = "chapter_splitter.ui.tk.workflow.workflow"
    root = tk.Tk()
    root.withdraw()

    def _on_close() -> None:
        """Handle window close events.

        Purpose:
            Convert a close request into a cancellation signal.
        Ties To:
            Registered with the Tk root window protocol handler.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Cancels the workflow and destroys the root window.
        Raises:
            - CancellationError: When cancellation reason is invalid.
        """
        token.cancel("UI close requested.", location)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    pdf_path = choose_pdf_file(settings.ui.file_dialog_title, location)
    if not pdf_path:
        return

    try:
        _run_workflow(settings, token, root, pdf_path, location)
    except CancellationError as exc:
        log_event(
            logger,
            logging.WARNING,
            "ui_cancelled",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
    except ChapterSplitterError as exc:
        messagebox.showerror(settings.ui.error_dialog_title, str(exc))
        log_event(
            logger,
            logging.ERROR,
            "ui_error",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
    finally:
        root.destroy()


def _run_workflow(
    settings: Settings,
    token: CancellationToken,
    root: tk.Tk,
    pdf_path: Path,
    location: str,
) -> None:
    """Execute the main UI workflow.

    Purpose:
        Load PDF metadata, build the chapter window, and handle actions.
    Ties To:
        Called by workflow after file selection.
    Inputs:
        - settings: Application settings.
        - token: Cancellation token for graceful shutdown.
        - root: Tk root instance.
        - pdf_path: Selected PDF path.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side Effects:
        Reads PDF metadata, opens viewer, and creates UI widgets.
    Raises:
        - ChapterSplitterError: When workflow operations fail.
    """
    token.check(location)
    read_deadline = Deadline(settings.io.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, settings.retry, location)
    page_labels = extract_page_labels(reader, location)

    viewer_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)
    action_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)

    if settings.ui.auto_open_viewer and settings.io.open_viewer:
        try:
            retry_with_backoff(
                lambda: open_in_default_viewer(
                    pdf_path,
                    settings.io.viewer_timeout_seconds,
                    viewer_limiter,
                    location,
                ),
                exceptions=(IoError,),
                max_attempts=settings.retry.max_attempts,
                initial_delay_seconds=settings.retry.initial_delay_seconds,
                max_delay_seconds=settings.retry.max_delay_seconds,
                jitter_ratio=settings.retry.jitter_ratio,
                location=location,
                token=token,
            )
        except IoError as exc:
            messagebox.showwarning(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.WARNING,
                "viewer_open_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )

    def do_auto_detect() -> None:
        """Auto detect chapters from PDF outlines.

        Purpose:
            Populate the grid using PDF outline data when available.
        Ties To:
            Triggered by the auto detect button.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Reads the PDF and updates the grid.
        Raises:
            - ChapterSplitterError: When detection fails.
        """
        if not action_limiter.allow():
            return
        try:
            set_correlation_id(
                new_correlation_id(settings.app.correlation_id_prefix, location),
                location,
            )
            token.check(location)
            detect_deadline = Deadline(settings.io.operation_timeout_seconds)
            chapters = detect_chapters_from_outlines(
                pdf_path,
                detect_deadline,
                token,
                settings.retry,
                settings.io,
                location,
            )
            if not chapters:
                messagebox.showinfo(
                    settings.ui.no_chapters_title,
                    settings.ui.no_chapters_message,
                )
                return
            prefill_rows = _chapters_to_prefill(chapters, page_labels)
            grid.prefill(prefill_rows)
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "auto_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )

    def do_export() -> None:
        """Export the defined chapters to PDF files.

        Purpose:
            Validate grid input and trigger PDF splitting.
        Ties To:
            Triggered by the export button.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Writes chapter PDF files to disk and closes the window.
        Raises:
            - ChapterSplitterError: When export fails.
        """
        if not action_limiter.allow():
            return
        try:
            set_correlation_id(
                new_correlation_id(settings.app.correlation_id_prefix, location),
                location,
            )
            token.check(location)
            export_deadline = Deadline(settings.io.operation_timeout_seconds)
            chapters = grid.get_chapters()
            outputs = split_pdf_into_chapters(
                pdf_path=pdf_path,
                chapters=chapters,
                page_offset=settings.io.page_offset,
                deadline=export_deadline,
                token=token,
                retry_config=settings.retry,
                validation_config=settings.validation,
                io_config=settings.io,
                location=location,
            )
            messagebox.showinfo(
                settings.ui.success_dialog_title,
                settings.ui.success_dialog_message_template.format(
                    count=len(outputs),
                    output_dir=str(pdf_path.parent),
                ),
            )
            win.destroy()
            root.destroy()
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "export_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )

    win, grid = build_chapter_window(
        root,
        page_labels,
        do_auto_detect,
        settings.ui,
        location,
    )
    ttk.Button(win, text=settings.ui.export_button_label, command=do_export).pack(
        pady=settings.ui.export_button_padding
    )
    root.mainloop()


def _chapters_to_prefill(
    chapters: Sequence[ChapterDefinition],
    page_labels: list[str] | None,
) -> list[tuple[str, str, str]]:
    """Convert chapter definitions into prefill string rows.

    Purpose:
        Convert chapters into displayable values for the grid.
    Ties To:
        Used by auto detect to populate the grid.
    Inputs:
        - chapters: Sequence of ChapterDefinition objects.
        - page_labels: Optional page label list from the PDF.
    Outputs:
        - List of (title, start, end) tuples as strings.
    Side Effects:
        None.
    Raises:
        - UiError: When page label mapping fails.
    """
    prefill: list[tuple[str, str, str]] = []
    for chapter in chapters:
        if page_labels:
            if chapter.start_page - 1 >= len(page_labels) or chapter.end_page - 1 >= len(
                page_labels
            ):
                raise UiError(
                    format_error_message(
                        "chapter_splitter.ui.tk.workflow._chapters_to_prefill",
                        "Page label mapping exceeded available labels.",
                    )
                )
            start_label = page_labels[chapter.start_page - 1]
            end_label = page_labels[chapter.end_page - 1]
            prefill.append((chapter.title, start_label, end_label))
        else:
            prefill.append((chapter.title, str(chapter.start_page), str(chapter.end_page)))
    return prefill
