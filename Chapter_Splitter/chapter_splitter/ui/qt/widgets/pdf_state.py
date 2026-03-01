"""Shared PDF viewer widget state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfViewerState:
    """Small immutable snapshot of viewer state."""

    page_index: int
    page_count: int


__all__ = ["PdfViewerState"]
