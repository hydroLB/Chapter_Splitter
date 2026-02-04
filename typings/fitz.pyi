from __future__ import annotations

from typing import Any

class Matrix:
    def __init__(self, a: float, b: float) -> None: ...

class Pixmap:
    width: int
    height: int
    def tobytes(self, output: str = ...) -> bytes: ...

class Page:
    def get_pixmap(self, matrix: Matrix | None = ..., alpha: bool = ...) -> Pixmap: ...

class Document:
    def load_page(self, pno: int) -> Page: ...
    def close(self) -> None: ...

def open(file: str, *args: Any, **kwargs: Any) -> Document: ...
