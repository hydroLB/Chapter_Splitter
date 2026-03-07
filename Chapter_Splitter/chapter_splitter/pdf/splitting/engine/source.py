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
    """Load the source PDF and compute its page count.

    Summary:
        Open the PDF under the configured read timeout and return the loaded reader plus total
        page count.
    Inputs:
        - pdf_path: Path to the source PDF.
        - io_config: IO configuration containing read timeout values.
        - retry_config: Retry policy for PDF loading.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified caller location.
    Outputs:
        - Tuple of loaded PdfReader and total page count.
    Side effects:
        Reads PDF bytes from disk.
    Error handling:
        Propagates exceptions raised by load_reader and get_total_pages.
    Ties to other methods:
        Used by split_pdf_into_chapters before validation and export.
    Why this exists:
        Source-document loading is a distinct boundary from chapter iteration and file writing.
    """
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
    """Resolve the page offset used for chapter range conversion.

    Summary:
        Honor an explicit page offset when provided, otherwise apply configured defaults and
        optional label-based inference.
    Inputs:
        - reader: Loaded PDF reader.
        - page_offset: Optional explicit page offset override.
        - io_config: IO configuration controlling default and inferred offsets.
        - location: Fully qualified caller location.
    Outputs:
        - Effective page offset integer.
    Side effects:
        May extract PDF page labels when inference is enabled.
    Error handling:
        Ignores PdfProcessingError raised while extracting labels and keeps the configured offset.
    Ties to other methods:
        Used by split_pdf_into_chapters before validating export ranges.
    Why this exists:
        Offset resolution is independent from file-writing mechanics and benefits from isolation.
    """
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
    """Infer a page offset from PDF page labels.

    Summary:
        Inspect page labels and derive a user-facing page offset when the labels are sufficiently
        sequential.
    Inputs:
        - reader: Loaded PDF reader.
        - io_config: IO configuration controlling inference thresholds.
        - location: Fully qualified caller location.
    Outputs:
        - Inferred page offset integer or None when no reliable inference is available.
    Side effects:
        Reads page label metadata from the PDF.
    Error handling:
        Returns None when label extraction fails with PdfProcessingError.
    Ties to other methods:
        Used by resolve_effective_page_offset.
    Why this exists:
        Label-based inference is optional and should remain isolated from the main export flow.
    """
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
