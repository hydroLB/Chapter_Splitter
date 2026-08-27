"""Progress models for PDF chapter export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ....core.models import ChapterDefinition


@dataclass(frozen=True, slots=True)
class ChapterExportProgress:
    """Progress event emitted during chapter export."""

    phase: Literal["start", "complete"]
    chapter: ChapterDefinition
    index: int
    total: int
    output_path: Path


__all__ = ["ChapterExportProgress"]
