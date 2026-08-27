"""Source-document preparation helpers for PDF splitting."""

from __future__ import annotations

from pathlib import Path

from ....config.schema import IOConfig, RetryConfig
from ....core.errors import PdfProcessingError
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ...io.dependencies import PdfReader
from ...io.labels import extract_page_labels, infer_page_offset_from_labels
from ...io.loader import get_total_pages, load_reader


def load_source_document(
    *,
    pdf_path: Path,
    io_config: IOConfig,
    retry_config: RetryConfig,
    token: CancellationToken,
    location: str,
) -> tuple[PdfReader, int]:
    """Load the source PDF and compute its page count."""
    read_deadline = Deadline(io_config.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    return reader, total_pages


def resolve_effective_page_offset(
    *,
    reader: PdfReader,
    page_offset: int | None,
    io_config: IOConfig,
    location: str,
) -> int:
    """Resolve the page offset used for chapter range conversion."""
    if page_offset is not None:
        return page_offset
    effective_page_offset = io_config.page_offset
    if io_config.page_offset != 0 or not io_config.infer_page_offset_from_labels:
        return effective_page_offset
    inferred_offset = _infer_page_offset_from_labels(
        reader=reader,
        io_config=io_config,
        location=location,
    )
    if inferred_offset is None:
        return effective_page_offset
    return inferred_offset


def _infer_page_offset_from_labels(
    *,
    reader: PdfReader,
    io_config: IOConfig,
    location: str,
) -> int | None:
    """Infer a page offset from PDF page labels."""
    try:
        labels = extract_page_labels(reader, location)
    except PdfProcessingError:
        return None
    if not labels:
        return None
    return infer_page_offset_from_labels(
        labels,
        min_sequential_numeric_labels=(io_config.infer_page_offset_min_sequential_numeric_labels),
        location=location,
    )


__all__ = ["load_source_document", "resolve_effective_page_offset"]
