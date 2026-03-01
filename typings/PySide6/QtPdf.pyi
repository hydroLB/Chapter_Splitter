from __future__ import annotations

from typing import Any

from .QtCore import QObject

class QPdfDocument(QObject):
    class Error:
        None_: int

    def __init__(self, parent: QObject | None = ...) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def load(self, file_name: str) -> int: ...
    def pageCount(self) -> int: ...
