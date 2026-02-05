"""Tkinter workflow for PDF chapter splitting."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
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
from ...pdf.detection.detector import (
    DetectionRequest,
    detect_chapters_in_reader,
    format_detection_report,
)
from ...pdf.io.labels import extract_page_labels
from ...pdf.io.loader import get_total_pages, load_reader
from ...pdf.splitting.splitter import split_pdf_into_chapters
from ...utils.rate_limit import RateLimiter
from ...utils.retry import retry_with_backoff
from ...utils.timing import Deadline
from ...utils.viewer import open_in_default_viewer, open_path_in_default_viewer
from .dialogs import choose_pdf_file
from .widgets.chapter_grid import ChapterGridFrame
from .widgets.chapter_review import ChapterReviewActions
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
    _configure_ttk_style(root)

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


def _configure_ttk_style(root: tk.Tk) -> None:
    """Apply minimal ttk style tweaks for a cleaner, more native feel.

    Summary:
        Configure small padding adjustments without forcing colors so the UI stays compatible with
        system light/dark themes.
    Inputs:
        - root: Tk root window.
    Outputs:
        - None.
    Side effects:
        Updates global ttk styles for the process.
    Error handling:
        Suppresses Tk errors for platforms/themes that do not support specific options.
    Ties to other methods:
        Called by workflow after creating the root window.
    Why this exists:
        Default widget padding can feel cramped; subtle tweaks help the UI read closer to macOS
        conventions without adding third-party theme dependencies.
    """
    with suppress(tk.TclError):
        style = ttk.Style(root)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        style.configure("TButton", padding=(10, 6))
        style.configure("TNotebook.Tab", padding=(12, 6))


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
    is_busy = False

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

    def _set_primary_controls_state(
        controls: ChapterWindowComponents,
        *,
        state: str,
        include_close: bool,
        location: str,
    ) -> None:
        """Set enabled/disabled state for the primary action controls.

        Summary:
            Centralize button state toggling so long-running actions cannot drift over time.
        Inputs:
            - controls: ChapterWindowComponents bundle.
            - state: Tk state string (normal or disabled).
            - include_close: Whether to update the close button.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates Tk button state.
        Error handling:
            Raises UiError when Tk calls fail.
        Ties to other methods:
            Used by _busy_action context manager.
        Why this exists:
            The workflow disables a consistent set of controls during detection/export; centralizing
            the list prevents subtle inconsistencies between actions.
        """
        error_location = f"{__name__}._run_workflow._set_primary_controls_state"
        context = f" Context: {location}." if location else ""
        try:
            controls.auto_detect_button.config(state=state)
            controls.export_button.config(state=state)
            controls.open_pdf_button.config(state=state)
            controls.add_button.config(state=state)
            if include_close:
                controls.close_button.config(state=state)
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to set control state '{state}'.{context}",
                )
            ) from exc

    def _set_status_text(controls: ChapterWindowComponents, text: str) -> None:
        """Update the UI status message in a consistent place.

        Summary:
            Display status text in the configured status bar, or fall back to the window title.
        Inputs:
            - controls: ChapterWindowComponents bundle.
            - text: Status message to display.
        Outputs:
            - None.
        Side effects:
            Updates the status label text or window title.
        Error handling:
            Swallows Tk errors during teardown to avoid masking the primary failure.
        Ties to other methods:
            Used by _busy_action and open-PDF flow.
        Why this exists:
            Some users prefer a cleaner window without a footer; title fallback preserves feedback.
        """
        if controls.status_label is not None and controls.status_label.winfo_exists():
            with suppress(tk.TclError):
                controls.status_label.config(text=text)
            return
        with suppress(tk.TclError):
            controls.window.title(f"{settings.ui.chapter_window_title} - {text}")

    @contextmanager
    def _busy_action(
        controls: ChapterWindowComponents,
        grid_widget: ChapterGridFrame,
        *,
        status_text: str,
        disable_close: bool,
        location: str,
    ) -> Iterator[None]:
        """Apply a consistent busy/idle UI state around an action.

        Summary:
            Disable interactive UI while an action runs, then restore it reliably.
        Inputs:
            - controls: ChapterWindowComponents bundle.
            - grid_widget: ChapterGridFrame instance to disable during work.
            - status_text: Status message displayed while running.
            - disable_close: Whether to disable the close button during work.
            - location: Fully qualified module and method name.
        Outputs:
            - Context manager that runs the action.
        Side effects:
            Disables buttons, grid, and preview interactions; changes the cursor.
        Error handling:
            Restores UI state best-effort even if errors occur.
        Ties to other methods:
            Used by export/detection actions.
        Why this exists:
            Keeping busy-state behavior consistent prevents partial disable/enable bugs and reduces
            the chance of concurrent actions corrupting UI state.
        """
        nonlocal is_busy
        is_busy = True
        try:
            _set_status_text(controls, status_text)
            controls.window.config(cursor="watch")
            _set_primary_controls_state(
                controls,
                state="disabled",
                include_close=disable_close,
                location=location,
            )
            grid_widget.set_interaction_enabled(False, location)
            if controls.pdf_preview is not None:
                controls.pdf_preview.set_interaction_enabled(False)
            if controls.chapter_review is not None:
                controls.chapter_review.set_interaction_enabled(False)
            yield
        finally:
            is_busy = False
            if controls.window.winfo_exists():
                with suppress(tk.TclError):
                    controls.window.config(cursor="")
                    _set_primary_controls_state(
                        controls,
                        state="normal",
                        include_close=True,
                        location=location,
                    )
                    grid_widget.set_interaction_enabled(True, location)
                    if controls.pdf_preview is not None:
                        controls.pdf_preview.set_interaction_enabled(True)
                    if controls.chapter_review is not None:
                        controls.chapter_review.set_interaction_enabled(True)
                    if controls.status_label is not None:
                        controls.status_label.config(text=settings.ui.status_hint)
                    else:
                        controls.window.title(settings.ui.chapter_window_title)

    def _prepare_action(controls: ChapterWindowComponents) -> None:
        """Prepare action execution with correlation IDs and cancellation checks.

        Summary:
            Reset correlation IDs and fail fast when cancellation has been requested.
        Inputs:
            - controls: ChapterWindowComponents bundle.
        Outputs:
            - None.
        Side effects:
            Updates correlation ID for logging context.
        Error handling:
            Propagates CancellationError and ConfigurationError as ChapterSplitterError.
        Ties to other methods:
            Used by long-running UI actions.
        Why this exists:
            Keeping action setup consistent makes logs and cancellation behavior predictable.
        """
        set_correlation_id(
            new_correlation_id(settings.app.correlation_id_prefix, location),
            location,
        )
        token.check(location)

    def _confirm_overwrite_if_needed(
        controls: ChapterWindowComponents,
        grid_widget: ChapterGridFrame,
    ) -> bool:
        """Prompt before replacing existing grid content when configured.

        Summary:
            Guard destructive actions that replace the chapter list.
        Inputs:
            - controls: ChapterWindowComponents bundle.
            - grid_widget: ChapterGridFrame to inspect.
        Outputs:
            - True when the caller should proceed, False when cancelled.
        Side effects:
            Shows a modal dialog when the user has already typed ranges.
        Error handling:
            Propagates UiError/ValidationError from has_defined_ranges.
        Ties to other methods:
            Used by auto-detect and TOC detect actions.
        Why this exists:
            A consistent prompt reduces accidental data loss.
        """
        if not settings.ui.confirm_auto_detect_overwrite:
            return True
        if not grid_widget.has_defined_ranges():
            return True
        return bool(
            messagebox.askyesno(
                settings.ui.confirm_auto_detect_overwrite_title,
                settings.ui.confirm_auto_detect_overwrite_message,
                parent=controls.window,
            )
        )

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
        try:
            if not _confirm_overwrite_if_needed(controls, grid_widget):
                return
            with _busy_action(
                controls,
                grid_widget,
                status_text="Detecting chapters...",
                disable_close=False,
                location=location,
            ):
                _prepare_action(controls)
                toc_hint_page = (
                    controls.pdf_preview.get_current_page()
                    if controls.pdf_preview is not None
                    else None
                )
                detect_deadline = Deadline(settings.io.operation_timeout_seconds)
                report = detect_chapters_in_reader(
                    reader=reader,
                    total_pages=total_pages,
                    pdf_path=pdf_path,
                    deadline=detect_deadline,
                    token=token,
                    detection_config=settings.detection,
                    request=DetectionRequest(toc_hint_page=toc_hint_page, force_strategy=None),
                    location=location,
                )
                if not report.chapters:
                    messagebox.showinfo(
                        settings.ui.no_chapters_title,
                        format_detection_report(report),
                        parent=controls.window,
                    )
                    return
                prefill_rows = _chapters_to_prefill(report.chapters, page_labels)
                grid_widget.prefill(prefill_rows)
                _update_review(report.chapters)
                messagebox.showinfo(
                    "Detection Result",
                    format_detection_report(report),
                    parent=controls.window,
                )
        except CancellationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "ui_action_cancelled",
                format_error_message(location, str(exc)),
                {"action": "auto_detect", "reason": str(exc)},
            )
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "auto_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )

    def do_detect_from_toc_page(toc_page: int) -> None:
        """Fallback detect chapters from a TOC page selected by the user.

        Summary:
            Run unified detection forced to TOC strategy starting at the provided page.
        Inputs:
            - toc_page: 1-based page number where the TOC starts.
        Outputs:
            - None.
        Side effects:
            Updates the grid contents when detection succeeds.
        Error handling:
            Shows an error dialog and logs an event when detection fails.
        Ties to other methods:
            Uses detect_chapters_in_reader and _chapters_to_prefill.
        Why this exists:
            A visual TOC picker gives the user control when outlines are missing.
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
        try:
            if not _confirm_overwrite_if_needed(controls, grid_widget):
                return
            with _busy_action(
                controls,
                grid_widget,
                status_text=f"Detecting chapters from TOC page {toc_page}...",
                disable_close=False,
                location=location,
            ):
                _prepare_action(controls)
                detect_deadline = Deadline(settings.io.operation_timeout_seconds)
                report = detect_chapters_in_reader(
                    reader=reader,
                    total_pages=total_pages,
                    deadline=detect_deadline,
                    token=token,
                    detection_config=settings.detection,
                    request=DetectionRequest(toc_hint_page=toc_page, force_strategy="toc"),
                    pdf_path=pdf_path,
                    location=location,
                )
                if not report.chapters:
                    messagebox.showinfo(
                        settings.ui.no_chapters_title,
                        format_detection_report(report),
                        parent=controls.window,
                    )
                    return
                prefill_rows = _chapters_to_prefill(report.chapters, page_labels)
                grid_widget.prefill(prefill_rows)
                _update_review(report.chapters)
                messagebox.showinfo(
                    "Detection Result",
                    format_detection_report(report),
                    parent=controls.window,
                )
        except CancellationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "ui_action_cancelled",
                format_error_message(location, str(exc)),
                {"action": "toc_detect", "reason": str(exc), "toc_page": toc_page},
            )
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "toc_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc), "toc_page": toc_page},
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
        controls, _win_handle, grid_widget = _require_controls()
        try:
            with _busy_action(
                controls,
                grid_widget,
                status_text="Exporting chapters...",
                disable_close=True,
                location=location,
            ):
                _prepare_action(controls)
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
                        parent=controls.window,
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
                        parent=controls.window,
                    )
                root.destroy()
        except CancellationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "ui_action_cancelled",
                format_error_message(location, str(exc)),
                {"action": "export", "reason": str(exc)},
            )
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "export_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )

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
            _set_status_text(controls, "Opening PDF...")
            _prepare_action(controls)
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
        except CancellationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "ui_action_cancelled",
                format_error_message(location, str(exc)),
                {"action": "open_pdf", "reason": str(exc)},
            )
        finally:
            if controls.window.winfo_exists():
                if controls.status_label is not None:
                    controls.status_label.config(text=settings.ui.status_hint)
                else:
                    controls.window.title(settings.ui.chapter_window_title)

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
    review_state: list[ChapterDefinition] = []

    def _update_review(chapters: Sequence[ChapterDefinition]) -> None:
        """Update the review gallery from a validated chapter list.

        Summary:
            Populate the review tab with the provided chapters and optionally select the tab.
        Inputs:
            - chapters: ChapterDefinition sequence to display.
        Outputs:
            - None.
        Side effects:
            Updates the review widget and may switch the notebook tab.
        Error handling:
            Raises UiError when review updates fail.
        Ties to other methods:
            Called after successful chapter detection and during refresh actions.
        Why this exists:
            The review gallery is derived state that should stay in sync with the latest detection.
        """
        nonlocal review_state
        review_state = list(chapters)
        if ui_controls.chapter_review is not None:
            ui_controls.chapter_review.set_chapters(review_state)
            if (
                settings.ui.auto_show_review_after_detect
                and ui_controls.right_notebook is not None
                and ui_controls.review_tab is not None
            ):
                ui_controls.right_notebook.select(ui_controls.review_tab)

    def _safe_apply(action: str, fn: Callable[[], None]) -> None:
        try:
            if is_busy:
                return
            token.check(location)
            fn()
        except CancellationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "ui_action_cancelled",
                format_error_message(location, str(exc)),
                {"action": action, "reason": str(exc)},
            )
        except ChapterSplitterError as exc:
            messagebox.showerror(settings.ui.error_dialog_title, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "ui_action_failed",
                format_error_message(location, str(exc)),
                {"action": action, "reason": str(exc)},
            )

    if ui_controls.pdf_preview is not None:
        grid_widget = ui_controls.grid

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

    if ui_controls.chapter_review is not None:
        grid_widget = ui_controls.grid
        review_widget = ui_controls.chapter_review

        def _refresh_review_from_grid() -> None:
            chapters = grid_widget.get_chapters()
            _update_review(chapters)

        def _jump_to_chapter(index: int) -> None:
            if index < 0:
                return
            if index >= len(review_state):
                _refresh_review_from_grid()
            if index >= len(review_state):
                return
            chapter = review_state[index]
            grid_widget.set_active_row_index(index, location)
            if ui_controls.pdf_preview is not None:
                ui_controls.pdf_preview.go_to_page(chapter.start_page)

        def _adjust_start(index: int, delta: int) -> None:
            if index < 0:
                return
            if index >= len(review_state):
                _refresh_review_from_grid()
            if index >= len(review_state):
                return
            chapter = review_state[index]
            new_start = max(1, min(chapter.end_page, chapter.start_page + int(delta)))
            grid_widget.set_row_start_at_page(index, new_start, location)
            updated = ChapterDefinition(
                title=chapter.title,
                start_page=new_start,
                end_page=chapter.end_page,
            )
            review_state[index] = updated
            review_widget.update_chapter(index, updated)
            if ui_controls.pdf_preview is not None:
                ui_controls.pdf_preview.go_to_page(new_start)

        def _adjust_end(index: int, delta: int) -> None:
            if index < 0:
                return
            if index >= len(review_state):
                _refresh_review_from_grid()
            if index >= len(review_state):
                return
            chapter = review_state[index]
            new_end = max(chapter.start_page, min(total_pages, chapter.end_page + int(delta)))
            grid_widget.set_row_end_at_page(index, new_end, location)
            updated = ChapterDefinition(
                title=chapter.title,
                start_page=chapter.start_page,
                end_page=new_end,
            )
            review_state[index] = updated
            review_widget.update_chapter(index, updated)

        ui_controls.chapter_review.set_actions(
            ChapterReviewActions(
                jump_to_chapter=lambda idx: _safe_apply(
                    "review_jump", lambda: _jump_to_chapter(idx)
                ),
                adjust_start=lambda idx, delta: _safe_apply(
                    "review_adjust_start",
                    lambda: _adjust_start(idx, delta),
                ),
                adjust_end=lambda idx, delta: _safe_apply(
                    "review_adjust_end",
                    lambda: _adjust_end(idx, delta),
                ),
                refresh_from_grid=lambda: _safe_apply(
                    "review_refresh",
                    _refresh_review_from_grid,
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
