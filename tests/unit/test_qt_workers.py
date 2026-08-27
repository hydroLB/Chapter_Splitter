"""Offscreen event-loop tests for the repo-native Qt worker abstraction."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from chapter_splitter.ui.qt.workers import QtWorkerTask


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QtWidgets.QApplication]:
    """Provide the single QApplication allowed in this test process."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


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


def test_blocking_operation_keeps_event_loop_responsive_and_queues_result(
    qt_app: QtWidgets.QApplication,
) -> None:
    """A blocked worker must not stop GUI timers or run UI callbacks off-thread."""
    worker_started = threading.Event()
    release_worker = threading.Event()
    main_thread = threading.get_ident()
    operation_threads: list[int] = []
    callback_threads: list[int] = []
    results: list[object] = []
    heartbeats: list[int] = []

    def _operation(progress: Callable[[object], None]) -> object:
        operation_threads.append(threading.get_ident())
        progress("halfway")
        worker_started.set()
        assert release_worker.wait(timeout=2.0)
        return "complete"

    def _record_result(value: object) -> None:
        callback_threads.append(threading.get_ident())
        results.append(value)

    task = QtWorkerTask(_operation)
    task.result.connect(_record_result)
    task.progress.connect(lambda _value: callback_threads.append(threading.get_ident()))

    timer = QtCore.QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: heartbeats.append(1))
    timer.start()
    task.start()

    _wait_until(qt_app, worker_started.is_set)
    _wait_until(qt_app, lambda: len(heartbeats) >= 3)
    assert operation_threads == [operation_threads[0]]
    assert operation_threads[0] != main_thread

    release_worker.set()
    _wait_until(qt_app, lambda: not task.is_running)
    timer.stop()

    assert results == ["complete"]
    assert callback_threads
    assert set(callback_threads) == {main_thread}


def test_error_is_delivered_on_gui_thread(qt_app: QtWidgets.QApplication) -> None:
    """Worker exceptions become queued error values without escaping QThread.run."""
    main_thread = threading.get_ident()
    errors: list[object] = []
    callback_threads: list[int] = []

    def _operation(_progress: Callable[[object], None]) -> object:
        raise ValueError("deterministic failure")

    def _record_error(value: object) -> None:
        errors.append(value)
        callback_threads.append(threading.get_ident())

    task = QtWorkerTask(_operation)
    task.error.connect(_record_error)
    task.start()
    _wait_until(qt_app, lambda: not task.is_running)

    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert str(errors[0]) == "deterministic failure"
    assert callback_threads == [main_thread]


def test_cancel_request_reaches_blocked_cooperative_operation(
    qt_app: QtWidgets.QApplication,
) -> None:
    """Cancellation is delivered immediately but completion remains cooperative."""
    started = threading.Event()
    cancelled = threading.Event()

    def _operation(_progress: Callable[[object], None]) -> object:
        started.set()
        assert cancelled.wait(timeout=2.0)
        return None

    task = QtWorkerTask(_operation, cancel=cancelled.set)
    task.start()
    _wait_until(qt_app, started.is_set)

    task.request_cancel()

    assert cancelled.is_set()
    _wait_until(qt_app, lambda: not task.is_running)


def test_application_quit_joins_running_worker_without_qthread_warning() -> None:
    """Application shutdown waits for a non-interruptible call to return cleanly."""
    script = """
import time
from PySide6 import QtCore, QtWidgets
from chapter_splitter.ui.qt.workers import QtWorkerTask

app = QtWidgets.QApplication([])

def operation(_progress):
    time.sleep(0.15)
    return None

task = QtWorkerTask(operation)
app.aboutToQuit.connect(task.shutdown)
task.start()
QtCore.QTimer.singleShot(10, app.quit)
raise SystemExit(app.exec())
"""
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert "QThread: Destroyed" not in completed.stderr
