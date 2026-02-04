"""Tkinter workflow for PDF chapter splitting."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import messagebox, simpledialog

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
from ...pdf.detection.toc import detect_chapters_from_toc_page
from ...pdf.io.labels import extract_page_labels
from ...pdf.io.loader import get_total_pages, load_reader
from ...pdf.splitting.splitter import split_pdf_into_chapters
from ...utils.rate_limit import RateLimiter
from ...utils.retry import retry_with_backoff
from ...utils.timing import Deadline
from ...utils.viewer import open_in_default_viewer, open_path_in_default_viewer
from .dialogs import choose_pdf_file
from .widgets.chapter_grid import ChapterGridFrame
from .widgets.pdf_preview.frame import PdfPreviewActions
from .windows.chapter_window import ChapterWindowComponents, build_chapter_window

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
    total_pages = get_total_pages(reader, location)
    page_labels = extract_page_labels(reader, location)

    viewer_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)
    action_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)

    ui_controls: ChapterWindowComponents | None = None
    win: tk.Toplevel | None = None
    grid: ChapterGridFrame | None = None

    def _require_controls() -> tuple[ChapterWindowComponents, tk.Toplevel, ChapterGridFrame]:
        """Resolve UI widget references after the window is built.

        Summary:
            Provide a single guard to prevent using uninitialized UI widget references.
        Inputs:
            - None.
        Outputs:
            - Tuple of (ChapterWindowComponents, window, grid).
        Side effects:
            None.
        Error handling:
            Raises UiError if the workflow is called before the window is constructed.
        Ties to other methods:
            Used by action handlers (auto detect, export, open PDF).
        Why this exists:
            Tkinter callback wiring requires defining handlers before the window is created; this
            guard keeps the callbacks safe and the error messages explicit.
        """
        error_location = f"{__name__}._run_workflow._require_controls"
        if ui_controls is None or win is None or grid is None:
            raise UiError(
                format_error_message(
                    error_location,
                    "UI controls are not initialized yet.",
                )
            )
        return ui_controls, win, grid

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
        controls, _win_handle, grid_widget = _require_controls()
        if settings.ui.confirm_auto_detect_overwrite and grid_widget.has_defined_ranges():
            should_replace = messagebox.askyesno(
                settings.ui.confirm_auto_detect_overwrite_title,
                settings.ui.confirm_auto_detect_overwrite_message,
            )
            if not should_replace:
                return

        def _prompt_for_toc_page(default_page: int) -> int | None:
            """Prompt the user for a TOC start page.

            Purpose:
                Provide a fallback when embedded PDF preview is disabled or unavailable.
            Ties To:
                Used when outlines are missing and TOC fallback detection is enabled.
            Inputs:
                - default_page: Initial value for the dialog.
            Outputs:
                - Selected page number, or None when cancelled.
            Side Effects:
                Shows a modal dialog.
            Raises:
                - None.
            """
            return simpledialog.askinteger(
                "TOC Page",
                "Enter the page number where the Table of Contents starts:",
                minvalue=1,
                maxvalue=total_pages,
                initialvalue=default_page,
                parent=controls.window,
            )

        def _run_toc_fallback(toc_page: int) -> bool:
            """Run TOC-based detection starting at the provided page.

            Purpose:
                Populate the grid by parsing a table-of-contents page when outlines are unavailable.
            Ties To:
                Called by auto-detect fallback and the embedded preview action.
            Inputs:
                - toc_page: 1-based page number where the TOC starts.
            Outputs:
                - True when chapters were detected and applied, otherwise False.
            Side Effects:
                Updates the grid and status label.
            Raises:
                - ChapterSplitterError: When detection fails.
            """
            detect_deadline = Deadline(settings.io.operation_timeout_seconds)
            chapters = detect_chapters_from_toc_page(
                reader=reader,
                toc_start_page=toc_page,
                total_pages=total_pages,
                detection=settings.detection,
                deadline=detect_deadline,
                token=token,
                location=location,
            )
            if not chapters:
                return False
            prefill_rows = _chapters_to_prefill(chapters, page_labels)
            grid_widget.prefill(prefill_rows)
            controls.status_label.config(text=settings.ui.status_hint)
            return True

        try:
            controls.status_label.config(text="Detecting chapters from PDF outlines...")
            controls.window.config(cursor="watch")
            controls.auto_detect_button.config(state="disabled")
            controls.export_button.config(state="disabled")
            controls.open_pdf_button.config(state="disabled")
            controls.add_button.config(state="disabled")
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
                if settings.detection.enable_toc_fallback:
                    default_toc_page = 1
                    if controls.pdf_preview is not None:
                        default_toc_page = controls.pdf_preview.get_current_page()
                    should_try = messagebox.askyesno(
                        "No PDF Outlines Found",
                        "This PDF does not contain usable outline metadata.\n\n"
                        "Try TOC-based detection as a fallback?",
                        parent=controls.window,
                    )
                    if should_try:
                        toc_page = default_toc_page
                        if controls.pdf_preview is None:
                            selected = _prompt_for_toc_page(default_toc_page)
                            if selected is None:
                                return
                            toc_page = selected
                        controls.status_label.config(
                            text=f"Detecting chapters from TOC page {toc_page}..."
                        )
                        if _run_toc_fallback(toc_page):
                            return
                        messagebox.showinfo(
                            settings.ui.no_chapters_title,
                            "No chapters were detected from the selected TOC page.\n\n"
                            "Navigate to the Table of Contents and try again.",
                            parent=controls.window,
                        )
                        return
                messagebox.showinfo(
                    settings.ui.no_chapters_title,
                    settings.ui.no_chapters_message,
                    parent=controls.window,
                )
                return
            prefill_rows = _chapters_to_prefill(chapters, page_labels)
            grid_widget.prefill(prefill_rows)
            controls.status_label.config(text=settings.ui.status_hint)
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "auto_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )
        finally:
            if controls.window.winfo_exists():
                controls.window.config(cursor="")
                controls.auto_detect_button.config(state="normal")
                controls.export_button.config(state="normal")
                controls.open_pdf_button.config(state="normal")
                controls.add_button.config(state="normal")

    def do_detect_from_toc_page(toc_page: int) -> None:
        """Fallback detect chapters from a TOC page selected by the user.

        Summary:
            Parse TOC text from the specified page and prefill the grid when outlines are missing.
        Inputs:
            - toc_page: 1-based page number where the TOC starts.
        Outputs:
            - None.
        Side effects:
            Updates the grid contents when detection succeeds.
        Error handling:
            Shows an error dialog and logs an event when detection fails.
        Ties to other methods:
            Uses detect_chapters_from_toc_page and _chapters_to_prefill.
        Why this exists:
            Some PDFs lack outlines; TOC parsing offers a manual, visual fallback for detection.
        """
        if not action_limiter.allow():
            return
        controls, _win_handle, grid_widget = _require_controls()
        if not settings.detection.enable_toc_fallback:
            messagebox.showinfo(
                settings.ui.error_dialog_title,
                "TOC fallback detection is disabled by configuration "
                "(detection.enable_toc_fallback=false).",
                parent=controls.window,
            )
            return
        if settings.ui.confirm_auto_detect_overwrite and grid_widget.has_defined_ranges():
            should_replace = messagebox.askyesno(
                settings.ui.confirm_auto_detect_overwrite_title,
                settings.ui.confirm_auto_detect_overwrite_message,
                parent=controls.window,
            )
            if not should_replace:
                return
        try:
            controls.status_label.config(text=f"Detecting chapters from TOC page {toc_page}...")
            controls.window.config(cursor="watch")
            controls.auto_detect_button.config(state="disabled")
            controls.export_button.config(state="disabled")
            controls.open_pdf_button.config(state="disabled")
            controls.add_button.config(state="disabled")
            set_correlation_id(
                new_correlation_id(settings.app.correlation_id_prefix, location),
                location,
            )
            token.check(location)
            detect_deadline = Deadline(settings.io.operation_timeout_seconds)
            chapters = detect_chapters_from_toc_page(
                reader=reader,
                toc_start_page=toc_page,
                total_pages=total_pages,
                detection=settings.detection,
                deadline=detect_deadline,
                token=token,
                location=location,
            )
            if not chapters:
                messagebox.showinfo(
                    settings.ui.no_chapters_title,
                    "No chapters were detected from the selected TOC page.\n\n"
                    "Navigate to the Table of Contents and try again.",
                    parent=controls.window,
                )
                return
            prefill_rows = _chapters_to_prefill(chapters, page_labels)
            grid_widget.prefill(prefill_rows)
            controls.status_label.config(text=settings.ui.status_hint)
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "toc_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc), "toc_page": toc_page},
            )
        finally:
            if controls.window.winfo_exists():
                controls.window.config(cursor="")
                controls.auto_detect_button.config(state="normal")
                controls.export_button.config(state="normal")
                controls.open_pdf_button.config(state="normal")
                controls.add_button.config(state="normal")

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
        controls, _win_handle, grid_widget = _require_controls()
        try:
            controls.status_label.config(text="Exporting chapters...")
            controls.window.config(cursor="watch")
            controls.auto_detect_button.config(state="disabled")
            controls.export_button.config(state="disabled")
            controls.open_pdf_button.config(state="disabled")
            controls.add_button.config(state="disabled")
            controls.close_button.config(state="disabled")
            set_correlation_id(
                new_correlation_id(settings.app.correlation_id_prefix, location),
                location,
            )
            token.check(location)
            export_deadline = Deadline(settings.io.operation_timeout_seconds)
            chapters = grid_widget.get_chapters()
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
            output_dir = pdf_path.parent / f"{pdf_path.stem}{settings.io.output_dir_suffix}"
            if settings.ui.prompt_open_output_dir_after_export and settings.io.open_viewer:
                should_open = messagebox.askyesno(
                    settings.ui.open_output_dir_prompt_title,
                    settings.ui.open_output_dir_prompt_message_template.format(
                        count=len(outputs),
                        output_dir=str(output_dir),
                    ),
                )
                if should_open:
                    retry_with_backoff(
                        lambda: open_path_in_default_viewer(
                            output_dir,
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
            else:
                messagebox.showinfo(
                    settings.ui.success_dialog_title,
                    settings.ui.success_dialog_message_template.format(
                        count=len(outputs),
                        output_dir=str(output_dir),
                    ),
                )
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
        finally:
            if controls.window.winfo_exists():
                controls.window.config(cursor="")
                controls.auto_detect_button.config(state="normal")
                controls.export_button.config(state="normal")
                controls.open_pdf_button.config(state="normal")
                controls.add_button.config(state="normal")
                controls.close_button.config(state="normal")

    def do_open_pdf() -> None:
        """Open the selected PDF in the system viewer.

        Summary:
            Open the PDF being edited from the GUI.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Launches the system viewer when enabled by configuration.
        Error handling:
            Shows a warning dialog and logs an event when the viewer fails to open.
        Ties to other methods:
            Uses open_in_default_viewer and the shared retry/backoff policy.
        Why this exists:
            Users often want to cross-check pages while editing chapter ranges.
        """
        if not settings.io.open_viewer:
            messagebox.showinfo(
                settings.ui.error_dialog_title,
                "Opening the system viewer is disabled by configuration (io.open_viewer=false).",
            )
            return
        if not viewer_limiter.allow():
            return
        controls, _win_handle, _grid_widget = _require_controls()
        try:
            controls.status_label.config(text="Opening PDF...")
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
        finally:
            if controls.window.winfo_exists():
                controls.status_label.config(text=settings.ui.status_hint)

    ui_controls = build_chapter_window(
        root,
        pdf_path,
        total_pages,
        page_labels,
        do_auto_detect,
        token,
        settings.ui,
        location,
    )
    win = ui_controls.window
    grid = ui_controls.grid
    ui_controls.export_button.config(command=do_export)
    ui_controls.open_pdf_button.config(command=do_open_pdf)
    if ui_controls.pdf_preview is not None:
        grid_widget = ui_controls.grid

        def _safe_apply(action: str, fn: Callable[[], None]) -> None:
            try:
                fn()
            except ChapterSplitterError as exc:
                messagebox.showerror(settings.ui.error_dialog_title, str(exc))
                log_event(
                    logger,
                    logging.ERROR,
                    "pdf_preview_action_failed",
                    format_error_message(location, str(exc)),
                    {"action": action, "reason": str(exc)},
                )

        ui_controls.pdf_preview.set_actions(
            PdfPreviewActions(
                new_chapter_at_page=lambda page: _safe_apply(
                    "new_chapter_at_page",
                    lambda: grid_widget.start_new_chapter_at_page(page, location),
                ),
                set_start_at_page=lambda page: _safe_apply(
                    "set_start_at_page",
                    lambda: grid_widget.set_active_row_start_at_page(page, location),
                ),
                set_end_at_page=lambda page: _safe_apply(
                    "set_end_at_page",
                    lambda: grid_widget.set_active_row_end_at_page(page, location),
                ),
                detect_chapters_at_page=lambda page: _safe_apply(
                    "detect_chapters_at_page",
                    lambda: do_detect_from_toc_page(page),
                ),
            )
        )

    def _on_close_window() -> None:
        """Close the chapter window and cancel the workflow.

        Summary:
            Convert a UI close action into a cancellation signal and clean shutdown.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Cancels the token and destroys the root Tk instance.
        Error handling:
            Relies on CancellationToken.cancel validation and lets Tk handle destroy errors.
        Ties to other methods:
            Shared by the close button and the window manager close handler.
        Why this exists:
            Without explicit shutdown wiring, closing the toplevel can leave the hidden root
            mainloop running and make the app appear hung.
        """
        token.cancel("UI close requested.", location)
        root.destroy()

    ui_controls.close_button.config(command=_on_close_window)
    win.protocol("WM_DELETE_WINDOW", _on_close_window)

    if settings.ui.enable_keyboard_shortcuts:
        win.bind("<Escape>", lambda _event: _on_close_window())
        win.bind("<Control-n>", lambda _event: grid.add_row())
        win.bind("<Command-n>", lambda _event: grid.add_row())
        win.bind("<Control-d>", lambda _event: do_auto_detect())
        win.bind("<Command-d>", lambda _event: do_auto_detect())
        win.bind("<Control-e>", lambda _event: do_export())
        win.bind("<Command-e>", lambda _event: do_export())
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
