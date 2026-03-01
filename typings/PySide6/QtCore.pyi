from __future__ import annotations

from collections.abc import Callable
from typing import Any

class QObject:
    def __init__(self, parent: QObject | None = ...) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

class Signal:
    def __init__(self, *types: object) -> None: ...
    def connect(self, slot: Callable[..., object]) -> None: ...
    def emit(self, *args: object) -> None: ...

class QModelIndex:
    def row(self) -> int: ...

class QItemSelection: ...

class QItemSelectionModel(QObject):
    selectionChanged: Signal
    def selectedRows(self) -> list[QModelIndex]: ...

class QTimer(QObject):
    timeout: Signal
    def setInterval(self, msec: int) -> None: ...
    def setSingleShot(self, single: bool) -> None: ...
    def start(self, msec: int | None = ...) -> None: ...
    def stop(self) -> None: ...
    @staticmethod
    def singleShot(msec: int, callback: Callable[[], object]) -> None: ...

class QMargins:
    def __init__(self, left: int, top: int, right: int, bottom: int) -> None: ...

class QPointF:
    def __init__(self, x: float, y: float) -> None: ...

class QSignalBlocker:
    def __init__(self, obj: object) -> None: ...
    def __enter__(self) -> QSignalBlocker: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool | None: ...

class Qt:
    class AlignmentFlag:
        AlignCenter: int

    class Orientation:
        Horizontal: int
        Vertical: int

    class WindowModality:
        WindowModal: int

    class WidgetAttribute:
        WA_TransparentForMouseEvents: int
        WA_OpaquePaintEvent: int
        WA_NoSystemBackground: int

    class ColorScheme:
        Dark: int
        Light: int

    class ItemFlag:
        NoItemFlags: int
