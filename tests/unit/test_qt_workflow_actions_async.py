"""Offscreen regression tests for asynchronous Qt workflow actions."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core.models import ChapterDefinition
from chapter_splitter.core.runtime import CancellationToken
from chapter_splitter.pdf.detection.report import ChapterDetectionReport
from chapter_splitter.ui.qt import workflow_actions
from chapter_splitter.ui.qt.main_window import MainWindow
from chapter_splitter.utils.rate_limit import RateLimiter


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QtWidgets.QApplication]:
    """Provide the single QApplication allowed in this test process."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


class _FakeWindow(QtWidgets.QWidget):
    """Minimal QWidget-backed window surface consumed by workflow actions."""

    def __init__(self) -> None:
        super().__init__()
        self.items = [ChapterDefinition("Existing", 1, 2)]
        self.statuses: list[tuple[str, str, int]] = []
        self.close_calls = 0

    def chapters(self) -> list[ChapterDefinition]:
        return list(self.items)

    def set_chapters(self, chapters: list[ChapterDefinition]) -> None:
        self.items = list(chapters)

    def set_status(self, *, level: str, text: str) -> None:
        self.statuses.append((level, text, threading.get_ident()))

    def set_undo_available(self, _available: bool) -> None:
        return

    def show_export_tab(self) -> None:
        return

    def show_chapters_tab(self) -> None:
        return

    def is_ready_for_export(self) -> bool:
        return True

    def close(self) -> None:
        self.close_calls += 1


def _wait_until(
    app: QtWidgets.QApplication,
    predicate: Callable[[], bool],
    *,
    timeout: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    app.processEvents()
    assert predicate()


def _build_actions(win: _FakeWindow) -> Any:
    settings = load_settings(None, "tests.unit.test_qt_workflow_actions_async")
    settings.ui.confirm_auto_detect_overwrite = False
    settings.ui.auto_show_review_after_detect = False
    settings.ui.prompt_open_output_dir_after_export = False
    settings.io.open_viewer = False
    actions, _auto_detect = workflow_actions.build_workflow_actions(
        settings=settings,
        token=CancellationToken(),
        location="tests.unit.test_qt_workflow_actions_async",
        pdf_path=Path("sample.pdf"),
        total_pages=10,
        reader=cast(Any, object()),
        win=cast(MainWindow, win),
        action_limiter=RateLimiter(0),
        logger=logging.getLogger(__name__),
    )
    return actions


def test_detection_runs_off_gui_thread_and_finalizes_on_gui_thread(
    qt_app: QtWidgets.QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detection must leave timers live and apply its result on the GUI thread."""
    started = threading.Event()
    release = threading.Event()
    operation_threads: list[int] = []
    heartbeats: list[int] = []
    main_thread = threading.get_ident()

    def _detect(**_kwargs: object) -> ChapterDetectionReport:
        operation_threads.append(threading.get_ident())
        started.set()
        assert release.wait(timeout=2.0)
        return ChapterDetectionReport(
            strategy="outlines",
            chapters=(ChapterDefinition("Detected", 1, 10),),
            confidence=1.0,
            warnings=(),
            outline_entries=1,
            toc_start_page=None,
            toc_pages_scanned=0,
        )

    monkeypatch.setattr(workflow_actions, "detect_chapters_in_reader", _detect)
    monkeypatch.setattr(workflow_actions, "show_info_dialog", lambda **_kwargs: None)
    win = _FakeWindow()
    actions = _build_actions(win)
    timer = QtCore.QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: heartbeats.append(1))
    timer.start()

    actions.on_detect()
    actions.on_detect()  # A repeated action is ignored while the first is active.
    _wait_until(qt_app, started.is_set)
    _wait_until(qt_app, lambda: len(heartbeats) >= 3)
    assert operation_threads == [operation_threads[0]]
    assert operation_threads[0] != main_thread

    release.set()
    _wait_until(qt_app, lambda: any(level == "success" for level, _text, _tid in win.statuses))
    timer.stop()

    assert [chapter.title for chapter in win.items] == ["Detected"]
    assert {thread_id for _level, _text, thread_id in win.statuses} == {main_thread}
    win.close()


def test_export_cancel_reaches_token_while_worker_is_blocked(
    qt_app: QtWidgets.QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Cancel signal must set the export token before the worker returns."""
    started = threading.Event()
    cancellation_seen = threading.Event()
    main_thread = threading.get_ident()

    def _split(**kwargs: object) -> list[object]:
        action_token = cast(CancellationToken, kwargs["token"])
        started.set()
        while not action_token.is_cancelled():
            time.sleep(0.001)
        cancellation_seen.set()
        action_token.check("test export")
        return []

    monkeypatch.setattr(workflow_actions, "split_pdf_into_chapters", _split)
    monkeypatch.setattr(workflow_actions, "show_warning_dialog", lambda **_kwargs: None)
    win = _FakeWindow()
    actions = _build_actions(win)

    actions.on_export_chapters()
    _wait_until(qt_app, started.is_set)
    dialogs = win.findChildren(QtWidgets.QProgressDialog)
    assert len(dialogs) == 1
    dialogs[0].canceled.emit()

    _wait_until(qt_app, cancellation_seen.is_set)
    _wait_until(qt_app, lambda: any(text == "Export cancelled" for _, text, _ in win.statuses))

    assert {thread_id for _level, _text, thread_id in win.statuses} == {main_thread}
    win.close()


def test_export_and_close_waits_for_thread_finished_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A result alone cannot close the window before its QThread has stopped."""
    instances: list[_DeferredTask] = []

    class _DeferredTask(QtCore.QObject):
        result = QtCore.Signal(object)
        error = QtCore.Signal(object)
        progress = QtCore.Signal(object)
        finished = QtCore.Signal()

        def __init__(
            self,
            _operation: Callable[[Callable[[object], None]], object],
            *,
            cancel: Callable[[], None] | None = None,
        ) -> None:
            super().__init__()
            self.is_running = False
            self._cancel = cancel
            instances.append(self)

        def start(self) -> None:
            self.is_running = True
            self.result.emit([])

        def request_cancel(self) -> None:
            if self._cancel is not None:
                self._cancel()

        def shutdown(self) -> None:
            self.request_cancel()

        def complete(self) -> None:
            self.is_running = False
            self.finished.emit()

    monkeypatch.setattr(workflow_actions, "QtWorkerTask", _DeferredTask)
    monkeypatch.setattr(workflow_actions, "show_info_dialog", lambda **_kwargs: None)
    win = _FakeWindow()
    actions = _build_actions(win)

    actions.on_done()

    assert len(instances) == 1
    assert win.close_calls == 0
    instances[0].complete()
    assert win.close_calls == 1
