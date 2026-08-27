"""Models used for chapter-file IO."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChapterFileSessionMetadata:
    """Optional session metadata stored alongside chapters."""

    pdf_path: str | None
    total_pages: int | None
    saved_at: str | None
    source: str | None


__all__ = ["ChapterFileSessionMetadata"]
