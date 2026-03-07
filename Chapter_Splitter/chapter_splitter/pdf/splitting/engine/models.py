"""Progress models for PDF chapter export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ....core.models import ChapterDefinition


@dataclass(frozen=True, slots=True)
class ChapterExportProgress:
    """Progress event emitted during chapter export.

    Summary:
        Provide structured per-chapter progress so UI layers can display progress without parsing
        log text.
    Inputs:
        - phase: Progress phase ("start" or "complete").
        - chapter: Chapter definition being exported.
        - index: 1-based chapter index.
        - total: Total chapter count.
        - output_path: Output PDF path for the chapter.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Emitted by split_pdf_into_chapters when on_progress is provided.
    Why this exists:
        UI progress should be deterministic and testable without coupling to internal loops.
    """

    phase: Literal["start", "complete"]
    chapter: ChapterDefinition
    index: int
    total: int
    output_path: Path


__all__ = ["ChapterExportProgress"]
