"""PDF detection helpers."""

from __future__ import annotations

from .outlines import detect_chapters_from_outlines
from .toc import detect_chapters_from_toc_page

__all__ = [
    "detect_chapters_from_outlines",
    "detect_chapters_from_toc_page",
]
