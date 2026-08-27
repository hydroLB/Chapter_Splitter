"""Small Qt worker abstraction for blocking GUI operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6 import QtCore

ProgressCallback = Callable[[object], None]
WorkerOperation = Callable[[ProgressCallback], object]

# A task can outlive its window while a cooperative operation reaches its next
# cancellation check. Keeping a module-level reference prevents Python from
# destroying the backing QThread prematurely during that interval.
_ACTIVE_TASKS: set[QtWorkerTask] = set()


class _OperationWorker(QtCore.QObject):
    """Execute one operation in a worker thread and report its outcome."""

    result = QtCore.Signal(object)
    error = QtCore.Signal(object)
    progress = QtCore.Signal(object)
    finished = QtCore.Signal()

    def __init__(self, operation: WorkerOperation) -> None:
        super().__init__()
        self._operation = operation

    def run(self) -> None:
        """Run the operation once in the object's current thread."""
        try:
            result = self._operation(self.progress.emit)
        except Exception as exc:
            self.error.emit(exc)
        else:
            self.result.emit(result)
        finally:
            self.finished.emit()


class QtWorkerTask(QtCore.QObject):
    """Own a worker and QThread while relaying queued signals to the GUI."""

    result = QtCore.Signal(object)
    error = QtCore.Signal(object)
    progress = QtCore.Signal(object)
    finished = QtCore.Signal()

    def __init__(
        self,
        operation: WorkerOperation,
        *,
        cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._cancel = cancel
        self._started = False
        self._running = False
        self._thread: Any = QtCore.QThread()  # type: ignore[attr-defined]
        self._worker: _OperationWorker | None = _OperationWorker(operation)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._relay_result)
        self._worker.error.connect(self._relay_error)
        self._worker.progress.connect(self._relay_progress)
        self._worker.finished.connect(self._worker.deleteLater)
        direct_connection = QtCore.Qt.ConnectionType.DirectConnection  # type: ignore[attr-defined]
        self._worker.finished.connect(  # type: ignore[call-arg]
            self._thread.quit,
            direct_connection,
        )
        self._thread.finished.connect(self._thread_finished)

    @property
    def is_running(self) -> bool:
        """Return whether the backing thread is still active."""
        return self._running

    def start(self) -> None:
        """Start the task exactly once."""
        if self._started:
            raise RuntimeError("A QtWorkerTask can only be started once.")
        self._started = True
        self._running = True
        _ACTIVE_TASKS.add(self)
        self._thread.start()

    def request_cancel(self) -> None:
        """Deliver cooperative cancellation without terminating the thread."""
        if self._running and self._cancel is not None:
            self._cancel()

    def shutdown(self) -> None:
        """Cancel cooperatively and wait for the worker thread to stop.

        This intentionally does not terminate the thread. If the operation is
        inside a blocking library call, shutdown waits until that call returns
        and the operation reaches completion or a cancellation check.
        """
        self.request_cancel()
        if self._running:
            self._thread.wait()

    def _relay_result(self, value: object) -> None:
        self.result.emit(value)

    def _relay_error(self, exc: object) -> None:
        self.error.emit(exc)

    def _relay_progress(self, value: object) -> None:
        self.progress.emit(value)

    def _thread_finished(self) -> None:
        self._running = False
        self._worker = None
        self._thread.deleteLater()
        _ACTIVE_TASKS.discard(self)
        self.finished.emit()
