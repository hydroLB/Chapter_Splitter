from __future__ import annotations

from typing import Any

from .QtCore import QObject, Signal
from .QtCore import Qt as Qt

class QFont:
    class Weight:
        DemiBold: int

    def pointSize(self) -> int: ...
    def setPointSize(self, point_size: int) -> None: ...
    def setWeight(self, weight: int) -> None: ...

class QFontMetrics:
    def __init__(self, font: QFont) -> None: ...
    def horizontalAdvance(self, text: str) -> int: ...

class QColor:
    def __init__(self, name: str) -> None: ...

class QPalette:
    class ColorRole:
        Window: int
        Base: int
        AlternateBase: int
        Text: int
        WindowText: int
        Button: int
        ButtonText: int
        Highlight: int
        HighlightedText: int

    def setColor(self, role: int, color: QColor) -> None: ...

class QPixmap:
    def __init__(self, *args: Any) -> None: ...

class QKeySequence:
    def __init__(self, sequence: str) -> None: ...

class QShowEvent: ...
class QResizeEvent: ...

class QStyleHints(QObject):
    colorSchemeChanged: Signal
    def colorScheme(self) -> int: ...

class QGuiApplication:
    @staticmethod
    def styleHints() -> QStyleHints: ...

__all__ = [
    "QColor",
    "QFont",
    "QFontMetrics",
    "QGuiApplication",
    "QKeySequence",
    "QPalette",
    "QPixmap",
    "QResizeEvent",
    "QShowEvent",
    "QStyleHints",
    "Qt",
]
