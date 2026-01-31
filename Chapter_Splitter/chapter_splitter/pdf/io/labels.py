"""Extract page labels from a PDF reader."""

from __future__ import annotations

from ...core.errors import PdfProcessingError, format_error_message
from .dependencies import PdfReader


def extract_page_labels(reader: PdfReader, location: str) -> list[str] | None:
    """Return page labels when available.

    Purpose:
        Map visible page labels to numeric pages for UI display.
    Ties To:
        Used by the Tkinter workflow to prefill labels.
    Inputs:
        - reader: PdfReader instance.
        - location: Fully qualified module and method name.
    Outputs:
        - List of labels or None when labels are not present.
    Side Effects:
        None.
    Raises:
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
