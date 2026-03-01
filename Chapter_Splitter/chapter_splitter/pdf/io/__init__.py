"""Public PDF IO API."""

from __future__ import annotations

from .dependencies import PdfReader, PdfWriter
from .labels import extract_page_labels, infer_page_offset_from_labels
from .loader import get_total_pages, load_reader

__all__ = [
    "PdfReader",
    "PdfWriter",
    "extract_page_labels",
    "get_total_pages",
    "infer_page_offset_from_labels",
    "load_reader",
]
