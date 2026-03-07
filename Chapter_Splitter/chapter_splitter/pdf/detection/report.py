"""Structured detection reports for chapter inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...core.models import ChapterDefinition

ChapterDetectionStrategy = Literal["outlines", "toc", "none"]


@dataclass(frozen=True, slots=True)
class ChapterDetectionReport:
    """Chapter detection outcome with confidence and warnings.

    Summary:
        Provide a structured, user-facing summary of detection output for UI and logs.
    Ties to other methods:
        Returned by chapter_splitter.pdf.detection.detector.detect_chapters.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    strategy: ChapterDetectionStrategy
    chapters: tuple[ChapterDefinition, ...]
    confidence: float
    warnings: tuple[str, ...]
    outline_entries: int
    toc_start_page: int | None
    toc_pages_scanned: int
