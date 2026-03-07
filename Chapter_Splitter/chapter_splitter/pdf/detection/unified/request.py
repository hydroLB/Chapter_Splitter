"""Request models for unified chapter detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..outlines import OutlineReaderProtocol
from ..report import ChapterDetectionStrategy
from ..toc import TextExtractableReaderProtocol


class UnifiedReaderProtocol(OutlineReaderProtocol, TextExtractableReaderProtocol, Protocol):
    """Reader protocol supporting both outlines and text extraction."""


@dataclass(frozen=True, slots=True)
class DetectionRequest:
    """Detection request options for unified detection."""

    toc_hint_page: int | None
    force_strategy: ChapterDetectionStrategy | None


__all__ = ["DetectionRequest", "UnifiedReaderProtocol"]
