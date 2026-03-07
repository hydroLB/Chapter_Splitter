"""Models used for chapter-file IO."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChapterFileSessionMetadata:
    """Optional session metadata stored alongside chapters.

    Summary:
        Capture lightweight session context so GUI exports can be reused safely across runs.
    Inputs:
        - pdf_path: Optional PDF path this chapter set applies to.
        - total_pages: Optional total page count observed at export time.
        - saved_at: Optional ISO-8601 timestamp string describing when the file was written.
        - source: Optional string describing the producing workflow.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Parsed by load_chapter_file_with_metadata and written by write_chapter_file.
    Why this exists:
        Session metadata helps chapter files round-trip cleanly between GUI and CLI workflows.
    """

    pdf_path: str | None
    total_pages: int | None
    saved_at: str | None
    source: str | None


__all__ = ["ChapterFileSessionMetadata"]
