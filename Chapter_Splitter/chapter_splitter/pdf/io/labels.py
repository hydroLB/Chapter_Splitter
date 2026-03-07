"""Extract page labels from a PDF reader."""

from __future__ import annotations

from collections.abc import Sequence

from ...core.errors import PdfProcessingError, format_error_message
from .dependencies import PdfReader


def extract_page_labels(reader: PdfReader, location: str) -> list[str] | None:
    """Return page labels when available.

    Summary:
        Map visible page labels to numeric pages for UI display.
    Ties to other methods:
        Used by the Qt GUI workflow to prefill labels.
    Inputs:
        - reader: PdfReader instance.
        - location: Fully qualified module and method name.
    Outputs:
        - List of labels or None when labels are not present.
    Side effects:
        None.
    Error handling:
        - PdfProcessingError: When labels are malformed or unavailable.
    """
    error_location = f"{__name__}.extract_page_labels"
    context = f" Context: {location}." if location else ""
    try:
        labels = reader.page_labels
    except AttributeError as exc:
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF page labels are unavailable.{context}")
        ) from exc
    if labels is None:
        return None
    if not all(isinstance(label, str) for label in labels):
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF page labels must be strings.{context}")
        )
    return list(labels)


def infer_page_offset_from_labels(
    labels: Sequence[str],
    *,
    min_sequential_numeric_labels: int,
    location: str,
) -> int | None:
    """Infer a page offset from PDF page labels when they contain a numeric run.

    Summary:
        Help map user-facing page numbers to PDF page indices without manual configuration when a
        PDF exposes page label metadata.
    Ties to other methods:
        Used by the split pipeline when io.infer_page_offset_from_labels is enabled.
    Inputs:
        - labels: Page labels indexed by the PDF's physical page order.
        - min_sequential_numeric_labels: Minimum sequential labels required to accept a match.
        - location: Fully qualified module and method name.
    Outputs:
        - Inferred non-negative page_offset value, or None when inference is not possible.
    Side effects:
        None.
    Error handling:
        Raises PdfProcessingError when min_sequential_numeric_labels is invalid.
    Ties to other methods:
        Consumed by chapter_splitter.pdf.splitting.splitter.split_pdf_into_chapters.
    Why this exists:
        Many PDFs include front matter with Roman numerals and start numeric labeling later. When
        labels are available, an inferred offset reduces user friction.
    """
    error_location = f"{__name__}.infer_page_offset_from_labels"
    context = f" Context: {location}." if location else ""
    if min_sequential_numeric_labels < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"min_sequential_numeric_labels must be at least 1.{context}",
            )
        )
    if not labels:
        return None

    required = min_sequential_numeric_labels
    for start_index, raw_label in enumerate(labels):
        if raw_label.strip() != "1":
            continue
        matches = 0
        for offset in range(required):
            idx = start_index + offset
            if idx >= len(labels):
                break
            if labels[idx].strip() != str(1 + offset):
                break
            matches += 1
        if matches >= required:
            return start_index
    return None
