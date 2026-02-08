"""Qt workflow entrypoint for the Chapter Splitter GUI.

Summary:
    Provide the end-to-end GUI flow using Qt and a true PDF renderer (QtPdf).
Inputs:
    - settings: Settings registry.
    - token: Cancellation token for graceful shutdown.
Outputs:
    - None.
Side effects:
    Creates a QApplication, shows windows, and performs PDF IO.
Error handling:
    Converts known application errors into modal dialogs and structured logs.
Ties to other methods:
    Called by chapter_splitter.app.main.
Why this exists:
    Tk cannot provide a vector-accurate PDF view; Qt is the long-term GUI platform.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

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
from ...core.validation import validate_chapters
from ...io.chapters import (
    ChapterFileSessionMetadata,
    load_chapter_file_with_metadata,
    write_chapter_file,
)
from ...observability.logging import log_event
from ...pdf.detection.detector import (
    DetectionRequest,
    detect_chapters_in_reader,
    format_detection_report,
)
from ...pdf.detection.report import ChapterDetectionStrategy
from ...pdf.io.loader import get_total_pages, load_reader
from ...pdf.splitting.splitter import ChapterExportProgress, split_pdf_into_chapters
from ...utils.rate_limit import RateLimiter
from ...utils.timing import Deadline
from ...utils.viewer import open_path_in_default_viewer
from .errors import ask_yes_no, show_error_dialog, show_info_dialog, show_warning_dialog
from .main_window import MainWindow, MainWindowActions
from .theme import apply_theme, install_system_theme_listener

logger = logging.getLogger(__name__)


def workflow(settings: Settings, token: CancellationToken) -> None:
    """Run the Qt GUI flow for selecting and splitting a PDF.

    Summary:
        Ask the user for a PDF file, load PDF metadata, and show the main chapter window.
    Inputs:
        - settings: Application settings.
        - token: Cancellation token for graceful shutdown.
    Outputs:
        - None.
    Side effects:
        Launches Qt windows and reads PDF metadata.
    Error handling:
        Shows dialogs for user-facing failures and re-raises unexpected exceptions.
    Ties to other methods:
        Called by chapter_splitter.app.main.
    Why this exists:
        Centralize the GUI workflow so the app entrypoint remains stable.
    """
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
    apply_theme(app=app)
    install_system_theme_listener(app=app)

    pdf_path = _choose_pdf_file(settings, location)
    if pdf_path is None:
        return

    read_deadline = Deadline(settings.io.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, settings.retry, location)
    total_pages = get_total_pages(reader, location)

    win = MainWindow(pdf_path=pdf_path, total_pages=total_pages, ui_config=settings.ui)
    if not win.viewer().load_pdf(pdf_path):
        show_error_dialog(title=settings.ui.error_dialog_title, message="Unable to open PDF.")
        return

    action_limiter = RateLimiter(settings.ui.action_rate_limit_seconds)
    undo_snapshot: list[ChapterDefinition] | None = None
    win.set_undo_available(False)

    def _show_busy_dialog(*, title: str, message: str) -> QtWidgets.QProgressDialog:
        """Show a cancellable busy dialog.

        Summary:
            Display a modal indeterminate progress dialog for long operations.
        Inputs:
            - title: Dialog title.
            - message: Dialog text.
        Outputs:
            - QProgressDialog instance.
        Side effects:
            Creates and shows a QProgressDialog.
        Error handling:
            Uses conservative defaults when platform styles vary.
        Ties to other methods:
            Used by detect and export actions.
        Why this exists:
            Long operations need explicit feedback and a cancellation path.
        """
        dialog = QtWidgets.QProgressDialog(message, "Cancel", 0, 0, win)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        return dialog

    def _confirm_replace_if_needed(*, interactive: bool) -> bool:
        """Confirm replacing current chapters when configured.

        Summary:
            Ask the user before overwriting existing chapter rows when
            ui.confirm_auto_detect_overwrite is enabled.
        Inputs:
            - interactive: True when triggered by a user action, otherwise False.
        Outputs:
            - True when replacement is allowed, otherwise False.
        Side effects:
            May show a modal yes or no dialog.
        Error handling:
            Returns False when the dialog cannot be shown.
        Ties to other methods:
            Used by _run_auto_detect before applying detected chapters.
        Why this exists:
            Auto Detect should be safe to try without accidentally erasing manual edits.
        """
        if win.chapters() and settings.ui.confirm_auto_detect_overwrite:
            if not interactive:
                return False
            return ask_yes_no(
                title=settings.ui.confirm_auto_detect_overwrite_title,
                message=settings.ui.confirm_auto_detect_overwrite_message,
            )
        return True

    def _apply_detected_chapters(
        *,
        chapters: list[ChapterDefinition],
        interactive: bool,
        report_text: str,
    ) -> None:
        """Apply detected chapters to the UI and set up undo state.

        Summary:
            Snapshot current chapters for undo, replace the table, and optionally show the result.
        Inputs:
            - chapters: Detected chapters to apply.
            - interactive: True when triggered by a user action.
            - report_text: Formatted detection report text.
        Outputs:
            - None.
        Side effects:
            Mutates the chapter table and enables the Undo button.
        Error handling:
            No-ops when applying chapters fails.
        Ties to other methods:
            Called by _run_auto_detect after detect_chapters_in_reader succeeds.
        Why this exists:
            Auto Detect should apply immediately, but it must be reversible.
        """
        nonlocal undo_snapshot
        try:
            undo_snapshot = win.chapters()
            win.set_chapters(chapters)
            win.set_undo_available(True)
            if settings.ui.auto_show_review_after_detect:
                win.show_export_tab()
            if interactive:
                show_info_dialog(title="Detection Result", message=report_text)
        except Exception:
            return

    def _run_auto_detect(
        *,
        interactive: bool,
        toc_hint_page: int | None,
        force_strategy: ChapterDetectionStrategy | None,
    ) -> None:
        """Run auto-detection and apply results.

        Summary:
            Execute unified detection and apply detected chapters to the grid on success.
        Inputs:
            - interactive: True when triggered by a user action.
            - toc_hint_page: Optional 1-based TOC hint page.
            - force_strategy: Optional strategy override.
        Outputs:
            - None.
        Side effects:
            Reads PDF metadata, shows progress UI, and mutates the chapter table.
        Error handling:
            Shows dialogs for cancellation and errors; logs structured events.
        Ties to other methods:
            Calls detect_chapters_in_reader and _apply_detected_chapters.
        Why this exists:
            Auto Detect is the primary workflow and should apply immediately when it succeeds.
        """
        if interactive and not action_limiter.allow():
            return
        if not _confirm_replace_if_needed(interactive=interactive):
            return
        action_token = CancellationToken()
        dialog = _show_busy_dialog(
            title=settings.ui.auto_detect_button_label,
            message="Auto detecting chapters...",
        )
        dialog.canceled.connect(lambda: action_token.cancel("Detection cancelled.", location))
        try:
            detect_deadline = Deadline(settings.io.operation_timeout_seconds)
            report = detect_chapters_in_reader(
                reader=reader,
                total_pages=total_pages,
                pdf_path=pdf_path,
                deadline=detect_deadline,
                token=action_token,
                detection_config=settings.detection,
                request=DetectionRequest(
                    toc_hint_page=toc_hint_page,
                    force_strategy=force_strategy,
                ),
                location=location,
            )
            chapters = list(report.chapters)
            report_text = format_detection_report(report)
            if not chapters:
                if interactive:
                    show_info_dialog(
                        title=settings.ui.no_chapters_title,
                        message=report_text,
                    )
                return
            _apply_detected_chapters(
                chapters=chapters,
                interactive=interactive,
                report_text=report_text,
            )
        except CancellationError:
            if interactive:
                show_warning_dialog(
                    title=settings.ui.error_dialog_title,
                    message="Detection cancelled.",
                )
        except ChapterSplitterError as exc:
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))
            log_event(
                logger,
                logging.ERROR,
                "qt_auto_detect_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )
        finally:
            dialog.close()

    def _detect_all() -> None:
        """Auto detect chapters using outlines and TOC fallback.

        Summary:
            Run auto-detect and apply chapters immediately.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Reads PDF metadata, updates the chapter table, and may show dialogs.
        Error handling:
            Shows a dialog on failure and logs structured events.
        Ties to other methods:
            Calls _run_auto_detect.
        Why this exists:
            Detection is the primary productivity feature of the app.
        """
        _run_auto_detect(interactive=True, toc_hint_page=None, force_strategy=None)

    def _detect_from_current_page(page_1based: int) -> None:
        """Run TOC detection using the current page as a hint.

        Summary:
            Use a user-selected TOC hint page to improve TOC scan results when outlines are missing.
        Inputs:
            - page_1based: 1-based page number to use as TOC hint.
        Outputs:
            - None.
        Side effects:
            Reads PDF text and updates chapter table when chapters are found.
        Error handling:
            Shows dialogs on failure or when TOC fallback is disabled.
        Ties to other methods:
            Calls detect_chapters_in_reader with a DetectionRequest.
        Why this exists:
            Many PDFs omit outlines, so giving the detector a TOC starting point improves accuracy.
        """
        if not action_limiter.allow():
            return
        if not settings.detection.enable_toc_fallback:
            show_warning_dialog(
                title=settings.ui.error_dialog_title,
                message="TOC fallback detection is disabled (detection.enable_toc_fallback=false).",
            )
            return
        _run_auto_detect(
            interactive=True,
            toc_hint_page=int(page_1based),
            force_strategy="toc",
        )

    def _undo_auto_detect() -> None:
        """Undo the last Auto Detect apply.

        Summary:
            Restore the previous chapter list snapshot captured before Auto Detect replaced it.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the chapter table and disables the Undo button.
        Error handling:
            No-ops when no snapshot exists.
        Ties to other methods:
            Wired to the Undo button by MainWindowActions.
        Why this exists:
            Auto Detect should be low-risk so users can recover from incorrect detection quickly.
        """
        nonlocal undo_snapshot
        if undo_snapshot is None:
            return
        try:
            win.set_chapters(undo_snapshot)
            undo_snapshot = None
            win.set_undo_available(False)
            win.show_chapters_tab()
        except Exception:
            return

    def _export_chapters(*, close_after_success: bool) -> bool:
        """Export chapter PDFs using the current chapter table.

        Summary:
            Validate chapter definitions and run the split pipeline with a cancellable progress UI.
        Inputs:
            - close_after_success: Whether to close the window after a successful export.
        Outputs:
            - True when export completed successfully, otherwise False.
        Side effects:
            Writes PDF files to disk and may open the output directory.
        Error handling:
            Shows dialogs for validation, IO, or PDF processing failures.
        Ties to other methods:
            Calls validate_chapters and split_pdf_into_chapters.
        Why this exists:
            Export is the core output of the application and must be safe and cancellable.
        """
        if not action_limiter.allow():
            return False
        try:
            chapters = validate_chapters(
                chapters=win.chapters(),
                total_pages=total_pages,
                max_chapters=settings.validation.max_chapters,
                require_unique_titles=settings.validation.require_unique_titles,
                sort_chapters_by_start_page=settings.validation.sort_chapters_by_start_page,
                reject_overlapping_ranges=settings.validation.reject_overlapping_ranges,
                location=location,
            )
        except ChapterSplitterError as exc:
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))
            return False

        action_token = CancellationToken()
        dialog = QtWidgets.QProgressDialog("Exporting chapters...", "Cancel", 0, len(chapters), win)
        dialog.setWindowTitle("Export Chapters")
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(lambda: action_token.cancel("Export cancelled.", location))
        dialog.show()

        def _on_progress(event: ChapterExportProgress) -> None:
            """Update export progress UI.

            Summary:
                Map split pipeline progress events to the progress dialog.
            Inputs:
                - event: ChapterExportProgress emitted by the splitter.
            Outputs:
                - None.
            Side effects:
                Updates the progress dialog and processes UI events.
            Error handling:
                Best-effort updates; ignores dialog errors.
            Ties to other methods:
                Passed to split_pdf_into_chapters via on_progress.
            Why this exists:
                Long exports need explicit user feedback and cancellation responsiveness.
            """
            completed = event.index - 1 if event.phase == "start" else event.index
            label = (
                f"Exporting {event.index}/{event.total}: {event.chapter.title}"
                if event.phase == "start"
                else f"Exported {event.index}/{event.total}: {event.chapter.title}"
            )
            dialog.setLabelText(label)
            dialog.setValue(completed)
            QtWidgets.QApplication.processEvents()

        try:
            export_deadline = Deadline(settings.io.operation_timeout_seconds)
            outputs = split_pdf_into_chapters(
                pdf_path=pdf_path,
                chapters=chapters,
                page_offset=None,
                deadline=export_deadline,
                token=action_token,
                retry_config=settings.retry,
                validation_config=settings.validation,
                io_config=settings.io,
                location=location,
                on_progress=_on_progress,
            )
            dialog.setValue(len(chapters))
            output_dir = pdf_path.parent / f"{pdf_path.stem}{settings.io.output_dir_suffix}"
            if settings.ui.prompt_open_output_dir_after_export and settings.io.open_viewer:
                should_open = ask_yes_no(
                    title=settings.ui.open_output_dir_prompt_title,
                    message=settings.ui.open_output_dir_prompt_message_template.format(
                        count=len(outputs),
                        output_dir=str(output_dir),
                    ),
                )
                if should_open:
                    open_path_in_default_viewer(
                        output_dir,
                        settings.io.viewer_timeout_seconds,
                        None,
                        location,
                    )
            show_info_dialog(
                title=settings.ui.success_dialog_title,
                message=settings.ui.success_dialog_message_template.format(
                    count=len(outputs),
                    output_dir=str(output_dir),
                ),
            )
            if close_after_success:
                win.close()
                return True
            return True
        except CancellationError:
            show_warning_dialog(title=settings.ui.error_dialog_title, message="Export cancelled.")
            return False
        except (ChapterSplitterError, IoError) as exc:
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))
            log_event(
                logger,
                logging.ERROR,
                "qt_export_failed",
                format_error_message(location, str(exc)),
                {"reason": str(exc)},
            )
            return False
        finally:
            dialog.close()

    def _export_menu_action() -> None:
        """Handle the Export Chapters menu action.

        Summary:
            Export chapters without closing the app.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Writes chapter PDFs to disk.
        Error handling:
            Delegates to _export_chapters for dialogs and logging.
        Ties to other methods:
            Wired to MainWindowActions.on_export_chapters.
        Why this exists:
            The menu Export should not exit the app; Done is the exit path.
        """
        _export_chapters(close_after_success=False)

    def _done() -> None:
        """Complete the workflow: export then close.

        Summary:
            Navigate to Export implicitly and run export automatically when chapters are ready.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Switches tabs, may write outputs, and closes the window on success.
        Error handling:
            Shows a warning when chapters are not ready, otherwise delegates to export handler.
        Ties to other methods:
            Uses ChaptersTableWidget export readiness checks and _export_chapters.
        Why this exists:
            The primary user goal is "export and done"; one button should finish the job.
        """
        win.show_export_tab()
        if not win.is_ready_for_export():
            show_warning_dialog(
                title=settings.ui.error_dialog_title,
                message="Fix the chapter list before exporting.",
            )
            return
        _export_chapters(close_after_success=True)

    def _default_session_metadata() -> ChapterFileSessionMetadata:
        """Build session metadata for TOML outputs.

        Summary:
            Capture a small amount of context so the TOML can be re-used later.
        Inputs:
            - None.
        Outputs:
            - ChapterFileSessionMetadata object.
        Side effects:
            Reads the current time.
        Error handling:
            Uses safe defaults when timestamps cannot be created.
        Ties to other methods:
            Used by export TOML and save session actions.
        Why this exists:
            Session metadata makes it easier to verify a chapter file matches the intended PDF.
        """
        try:
            saved_at = datetime.datetime.now(datetime.UTC).isoformat()
        except Exception:
            saved_at = None
        return ChapterFileSessionMetadata(
            pdf_path=str(pdf_path),
            total_pages=int(total_pages),
            saved_at=saved_at,
            source="gui-qt",
        )

    def _export_toml() -> None:
        """Export chapters as a TOML file.

        Summary:
            Serialize the current chapter table to TOML for reuse in CLI or later GUI sessions.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Writes a TOML file to disk.
        Error handling:
            Shows dialogs for IO or validation failures.
        Ties to other methods:
            Calls write_chapter_file.
        Why this exists:
            A chapter TOML file is the main portability format of the application.
        """
        if not action_limiter.allow():
            return
        default_path = pdf_path.with_suffix(".chapters.toml")
        filename, _filter = QtWidgets.QFileDialog.getSaveFileName(
            win,
            "Export TOML",
            str(default_path),
            "TOML Files (*.toml);;All Files (*)",
        )
        if not filename:
            return
        try:
            export_deadline = Deadline(settings.io.operation_timeout_seconds)
            write_chapter_file(
                Path(filename),
                win.chapters(),
                report=None,
                session=_default_session_metadata(),
                overwrite=True,
                deadline=export_deadline,
                token=token,
                location=location,
            )
            show_info_dialog(
                title=settings.ui.success_dialog_title,
                message=f"Exported chapters to TOML:\n{filename}",
            )
        except ChapterSplitterError as exc:
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))

    def _save_session() -> None:
        """Save a session TOML file that can be re-opened later.

        Summary:
            Write chapters and minimal session metadata to TOML.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Writes a TOML file to disk.
        Error handling:
            Shows an error dialog for write failures.
        Ties to other methods:
            Calls write_chapter_file with session metadata.
        Why this exists:
            Session files reduce friction when revisiting large PDFs.
        """
        _export_toml()

    def _import_toml() -> None:
        """Import chapters from a TOML file.

        Summary:
            Load chapter definitions from TOML and populate the chapter table.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Reads a TOML file from disk and mutates the chapter table UI.
        Error handling:
            Shows dialogs for IO or validation failures.
        Ties to other methods:
            Calls load_chapter_file_with_metadata and MainWindow.set_chapters.
        Why this exists:
            TOML import enables collaboration and reproducibility across runs.
        """
        if not action_limiter.allow():
            return
        filename, _filter = QtWidgets.QFileDialog.getOpenFileName(
            win,
            "Import Chapters (TOML)",
            str(pdf_path.parent),
            "TOML Files (*.toml);;All Files (*)",
        )
        if not filename:
            return
        try:
            import_deadline = Deadline(settings.io.operation_timeout_seconds)
            _meta, chapters = load_chapter_file_with_metadata(
                Path(filename),
                deadline=import_deadline,
                token=token,
                location=location,
            )
            win.set_chapters(chapters)
            show_info_dialog(
                title="Imported Chapters",
                message=f"Imported {len(chapters)} chapters.",
            )
        except ChapterSplitterError as exc:
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))

    def _close() -> None:
        """Close the window and cancel the workflow token.

        Summary:
            Treat a close request as a workflow cancellation.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Cancels the token and closes the main window.
        Error handling:
            Allows cancellation errors to bubble to the app boundary.
        Ties to other methods:
            Wired to the Close button.
        Why this exists:
            Closing the main window should reliably stop background work.
        """
        token.cancel("UI close requested.", location)
        win.close()

    win.set_actions(
        MainWindowActions(
            on_detect=_detect_all,
            on_detect_from_current_page=_detect_from_current_page,
            on_export_chapters=_export_menu_action,
            on_export_toml=_export_toml,
            on_import_toml=_import_toml,
            on_save_session=_save_session,
            on_undo_auto_detect=_undo_auto_detect,
            on_done=_done,
            on_close=_close,
        )
    )

    win.show()
    if settings.ui.auto_detect_on_open:
        QtCore.QTimer.singleShot(
            0,
            lambda: _run_auto_detect(interactive=False, toc_hint_page=None, force_strategy=None),
        )
    app.exec()


def _choose_pdf_file(settings: Settings, location: str) -> Path | None:
    """Open a Qt file dialog and return a selected PDF path.

    Summary:
        Prompt the user to choose a PDF file to split.
    Inputs:
        - settings: Settings registry providing UI labels.
        - location: Fully qualified module and method name.
    Outputs:
        - Selected Path or None when cancelled.
    Side effects:
        Opens a modal Qt file dialog.
    Error handling:
        Returns None for dialog errors and logs them.
    Ties to other methods:
        Used by workflow() before loading the PDF.
    Why this exists:
        The GUI workflow starts with selecting a PDF.
    """
    try:
        from PySide6 import QtWidgets

        filename, _filter = QtWidgets.QFileDialog.getOpenFileName(
            None,
            settings.ui.file_dialog_title,
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)",
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "qt_file_dialog_failed",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
        show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))
        return None
    if not filename:
        return None
    return Path(filename)
