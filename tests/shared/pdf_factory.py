"""PDF factory helpers for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfWriter


def create_sample_pdf(
    path: Path,
    page_count: int,
    outline_titles: Sequence[str] | None,
) -> Path:
    """Create a sample PDF for tests.

    Purpose:
        Provide deterministic PDF fixtures for unit and integration tests.
    Ties To:
        Used by tests in unit, integration, and performance suites.
    Inputs:
        - path: Destination path for the PDF.
        - page_count: Number of pages to include.
        - outline_titles: Optional list of outline titles.
    Outputs:
        - Path to the created PDF file.
    Side Effects:
        Writes a PDF file to disk.
    Raises:
        - ValueError: When page_count is less than 1.
    """
    if page_count < 1:
        raise ValueError("tests.shared.pdf_factory.create_sample_pdf requires page_count >= 1")
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    if outline_titles:
        for index, title in enumerate(outline_titles):
            page_index = min(index, page_count - 1)
            writer.add_outline_item(title=title, page_number=page_index)
    try:
        with path.open("wb") as handle:
            writer.write(handle)
    except OSError as exc:
        raise RuntimeError(
            f"tests.shared.pdf_factory.create_sample_pdf failed to write PDF: {exc}"
        ) from exc
    return path
