"""Qt workflow action wiring helpers."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ...config.schema import Settings
from ...core.error_mapping import map_error
from ...core.errors import CancellationError, ChapterSplitterError
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
    UnifiedReaderProtocol,
    detect_chapters_in_reader,
    format_detection_report,
)
from ...pdf.detection.report import ChapterDetectionReport, ChapterDetectionStrategy
from ...pdf.splitting.splitter import ChapterExportProgress, split_pdf_into_chapters
from ...utils.rate_limit import RateLimiter
from ...utils.timing import Deadline
from ...utils.viewer import open_path_in_default_viewer
from ..workflow_validation import preflight_session_import
from .errors import ask_yes_no, show_error_dialog, show_info_dialog, show_warning_dialog
from .main_window import MainWindow, MainWindowActions
from .workers import QtWorkerTask


def build_workflow_actions(
    *,
    settings: Settings,
    token: CancellationToken,
    location: str,
    pdf_path: Path,
    total_pages: int,
    reader: UnifiedReaderProtocol,
    win: MainWindow,
    action_limiter: RateLimiter,
    logger: logging.Logger,
) -> tuple[MainWindowActions, Callable[[], None]]:
    """Build and return all main-window actions for the Qt workflow."""
    from PySide6 import QtCore, QtWidgets

    undo_snapshot: list[ChapterDefinition] | None = None
    active_task: QtWorkerTask | None = None

    def _operation_is_running() -> bool:
        return active_task is not None and active_task.is_running

    def _track_task(task: QtWorkerTask) -> None:
        nonlocal active_task
        active_task = task

        def _release_task() -> None:
            nonlocal active_task
            if active_task is task:
                active_task = None

        task.finished.connect(_release_task)
        task.start()

    def _cancel_active_task() -> None:
        if active_task is not None:
            active_task.request_cancel()

    def _shutdown_active_task() -> None:
        if active_task is not None:
            active_task.shutdown()

    def _show_busy_dialog(*, title: str, message: str) -> QtWidgets.QProgressDialog:
        dialog = QtWidgets.QProgressDialog(message, "Cancel", 0, 0, win)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        return dialog

    def _confirm_replace_if_needed(*, interactive: bool) -> bool:
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
        nonlocal undo_snapshot
        previous_chapters = win.chapters()
        win.set_chapters(chapters)
        undo_snapshot = previous_chapters
        win.set_undo_available(True)
        if settings.ui.auto_show_review_after_detect:
            win.show_export_tab()
        if interactive:
            show_info_dialog(title="Detection Result", message=report_text)

    def _run_auto_detect(
        *,
        interactive: bool,
        toc_hint_page: int | None,
        force_strategy: ChapterDetectionStrategy | None,
    ) -> None:
        if _operation_is_running():
            return
        if interactive and not action_limiter.allow():
            return
        if not _confirm_replace_if_needed(interactive=interactive):
            return
        win.set_status(level="working", text="Auto Detect in progress")
        action_token = CancellationToken()
        dialog = _show_busy_dialog(
            title=settings.ui.auto_detect_button_label,
            message="Auto detecting chapters...",
        )
        dialog.canceled.connect(lambda: action_token.cancel("Detection cancelled.", location))

        def _detect(_progress: Callable[[object], None]) -> object:
            detect_deadline = Deadline(settings.io.operation_timeout_seconds)
            return detect_chapters_in_reader(
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

        task = QtWorkerTask(
            _detect,
            cancel=lambda: action_token.cancel("Detection cancelled.", location),
        )
        result_box: list[ChapterDetectionReport] = []
        error_box: list[BaseException] = []

        def _detection_result(value: object) -> None:
            result_box.append(cast(ChapterDetectionReport, value))

        def _detection_error(value: object) -> None:
            error_box.append(cast(BaseException, value))

        def _finalize_detection() -> None:
            if error_box:
                exc = error_box[0]
                if isinstance(exc, CancellationError):
                    win.set_status(level="ready", text="Detection cancelled")
                    if interactive:
                        show_warning_dialog(
                            title=settings.ui.error_dialog_title,
                            message="Detection cancelled.",
                        )
                    dialog.close()
                    return
                payload = map_error(exc, channel="ui", location=location)
                win.set_status(level="error", text="Detection failed")
                show_error_dialog(
                    title=settings.ui.error_dialog_title,
                    message=payload.user_message,
                )
                log_event(
                    logger,
                    payload.log_level,
                    "qt_auto_detect_failed",
                    payload.message,
                    payload.log_fields(location=location),
                )
                dialog.close()
                return
            if not result_box:
                dialog.close()
                return
            report = result_box[0]
            chapters = list(report.chapters)
            report_text = format_detection_report(report)
            if not chapters:
                win.set_status(level="ready", text="No chapters detected")
                if interactive:
                    show_info_dialog(
                        title=settings.ui.no_chapters_title,
                        message=report_text,
                    )
                dialog.close()
                return
            _apply_detected_chapters(
                chapters=chapters,
                interactive=interactive,
                report_text=report_text,
            )
            win.set_status(level="success", text=f"Detected {len(chapters)} chapter(s)")
            dialog.close()

        task.result.connect(_detection_result)
        task.error.connect(_detection_error)
        task.finished.connect(_finalize_detection)
        _track_task(task)

    def _detect_all() -> None:
        _run_auto_detect(interactive=True, toc_hint_page=None, force_strategy=None)

    def _undo_auto_detect() -> None:
        nonlocal undo_snapshot
        if undo_snapshot is None:
            return
        try:
            win.set_chapters(undo_snapshot)
            undo_snapshot = None
            win.set_undo_available(False)
            win.show_chapters_tab()
            win.set_status(level="ready", text="Reverted Auto Detect changes")
        except Exception:
            return

    def _export_chapters(*, close_after_success: bool) -> bool:
        if _operation_is_running():
            return False
        if not action_limiter.allow():
            return False
        win.set_status(level="working", text="Export in progress")
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
            win.set_status(level="error", text="Export blocked by validation")
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

        def _on_progress(value: object) -> None:
            event = cast(ChapterExportProgress, value)
            completed = event.index - 1 if event.phase == "start" else event.index
            label = (
                f"Exporting {event.index}/{event.total}: {event.chapter.title}"
                if event.phase == "start"
                else f"Exported {event.index}/{event.total}: {event.chapter.title}"
            )
            dialog.setLabelText(label)
            dialog.setValue(completed)

        def _export(progress: Callable[[object], None]) -> object:
            export_deadline = Deadline(settings.io.operation_timeout_seconds)
            return split_pdf_into_chapters(
                pdf_path=pdf_path,
                chapters=chapters,
                page_offset=None,
                deadline=export_deadline,
                token=action_token,
                retry_config=settings.retry,
                validation_config=settings.validation,
                io_config=settings.io,
                location=location,
                on_progress=progress,
            )

        task = QtWorkerTask(
            _export,
            cancel=lambda: action_token.cancel("Export cancelled.", location),
        )
        result_box: list[list[object]] = []
        error_box: list[BaseException] = []

        def _export_result(value: object) -> None:
            result_box.append(cast(list[object], value))

        def _export_error(value: object) -> None:
            error_box.append(cast(BaseException, value))

        def _finalize_export() -> None:
            if error_box:
                exc = error_box[0]
                if isinstance(exc, CancellationError):
                    win.set_status(level="ready", text="Export cancelled")
                    show_warning_dialog(
                        title=settings.ui.error_dialog_title,
                        message="Export cancelled.",
                    )
                    dialog.close()
                    return
                payload = map_error(exc, channel="ui", location=location)
                win.set_status(level="error", text="Export failed")
                show_error_dialog(
                    title=settings.ui.error_dialog_title,
                    message=payload.user_message,
                )
                log_event(
                    logger,
                    payload.log_level,
                    "qt_export_failed",
                    payload.message,
                    payload.log_fields(location=location),
                )
                dialog.close()
                return
            if not result_box:
                dialog.close()
                return
            outputs = result_box[0]
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
            win.set_status(level="success", text=f"Exported {len(outputs)} chapter file(s)")
            if close_after_success:
                win.close()
            dialog.close()

        task.progress.connect(_on_progress)
        task.result.connect(_export_result)
        task.error.connect(_export_error)
        task.finished.connect(_finalize_export)
        _track_task(task)
        return True

    def _export_menu_action() -> None:
        _export_chapters(close_after_success=False)

    def _done() -> None:
        win.show_export_tab()
        if not win.is_ready_for_export():
            win.set_status(level="error", text="Fix chapter list before exporting")
            show_warning_dialog(
                title=settings.ui.error_dialog_title,
                message="Fix the chapter list before exporting.",
            )
            return
        _export_chapters(close_after_success=True)

    def _default_session_metadata() -> ChapterFileSessionMetadata:
        try:
            saved_at = datetime.datetime.now(datetime.UTC).isoformat()
        except Exception:
            saved_at = None
        return ChapterFileSessionMetadata(
            pdf_path=pdf_path.name,
            total_pages=int(total_pages),
            saved_at=saved_at,
            source="gui-qt",
        )

    def _export_toml() -> None:
        if not action_limiter.allow():
            return
        win.set_status(level="working", text="Exporting chapter TOML")
        default_path = pdf_path.with_suffix(".chapters.toml")
        filename, _filter = QtWidgets.QFileDialog.getSaveFileName(
            win,
            "Export TOML",
            str(default_path),
            "TOML Files (*.toml);;All Files (*)",
        )
        if not filename:
            win.set_status(level="ready", text="TOML export cancelled")
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
            win.set_status(level="success", text="Exported TOML")
        except ChapterSplitterError as exc:
            win.set_status(level="error", text="TOML export failed")
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))

    def _save_session() -> None:
        _export_toml()

    def _import_toml() -> None:
        if not action_limiter.allow():
            return
        win.set_status(level="working", text="Importing chapter TOML")
        filename, _filter = QtWidgets.QFileDialog.getOpenFileName(
            win,
            "Import Chapters (TOML)",
            str(pdf_path.parent),
            "TOML Files (*.toml);;All Files (*)",
        )
        if not filename:
            win.set_status(level="ready", text="Import cancelled")
            return
        try:
            import_deadline = Deadline(settings.io.operation_timeout_seconds)
            metadata, chapters = load_chapter_file_with_metadata(
                Path(filename),
                deadline=import_deadline,
                token=token,
                location=location,
            )
            preflight = preflight_session_import(
                metadata=metadata,
                chapters=chapters,
                current_pdf_path=pdf_path,
                total_pages=total_pages,
                location=location,
            )
            if preflight.pdf_path_mismatch:
                should_import = ask_yes_no(
                    title="Chapter File PDF Differs",
                    message=(
                        "This chapter file was saved for a different PDF path.\n\n"
                        f"Saved PDF: {preflight.recorded_pdf_path}\n"
                        f"Loaded PDF: {pdf_path}\n\n"
                        "Import these chapters into the loaded PDF anyway?"
                    ),
                )
                if not should_import:
                    win.set_status(level="ready", text="Import cancelled")
                    return
            win.set_chapters(chapters)
            show_info_dialog(
                title="Imported Chapters",
                message=f"Imported {len(chapters)} chapters.",
            )
            win.set_status(level="success", text=f"Imported {len(chapters)} chapter(s)")
        except ChapterSplitterError as exc:
            win.set_status(level="error", text="TOML import failed")
            show_error_dialog(title=settings.ui.error_dialog_title, message=str(exc))

    win.destroyed.connect(_cancel_active_task)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(_shutdown_active_task)

    actions = MainWindowActions(
        on_detect=_detect_all,
        on_export_chapters=_export_menu_action,
        on_export_toml=_export_toml,
        on_import_toml=_import_toml,
        on_save_session=_save_session,
        on_undo_auto_detect=_undo_auto_detect,
        on_done=_done,
    )

    return actions, (
        lambda: _run_auto_detect(interactive=False, toc_hint_page=None, force_strategy=None)
    )
