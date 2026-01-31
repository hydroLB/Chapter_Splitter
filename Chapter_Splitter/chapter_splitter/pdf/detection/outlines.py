"""PDF outline detection logic for chapter inference."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...config.schema import IOConfig, RetryConfig
from ...core.errors import PdfProcessingError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline
from ..io.loader import get_total_pages, load_reader


def detect_chapters_from_outlines(
    pdf_path: Path,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    io_config: IOConfig,
    location: str,
) -> list[ChapterDefinition]:
    """Inspect PDF outlines and return inferred chapter ranges.

    Purpose:
        Use top level PDF outlines to infer chapter boundaries.
    Ties To:
        Used by the UI auto detect feature and CLI workflows.
    Inputs:
        - pdf_path: Path to the PDF file.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - retry_config: Retry policy for PDF loading.
        - io_config: IO configuration for timeouts.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects.
    Side Effects:
        Reads the PDF file from disk.
    Raises:
        - PdfProcessingError: When outlines are malformed or unavailable.
    """
    token.check(location)
    read_deadline = Deadline(io_config.pdf_read_timeout_seconds)
    error_location = f"{__name__}.detect_chapters_from_outlines"
    context = f" Context: {location}." if location else ""
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    deadline.check(location)

    outlines = reader.outline
    if outlines is None:
        return []
    if not isinstance(outlines, Sequence):
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF outlines must be a sequence.{context}")
        )

    entries: list[tuple[str, int]] = []

    def _walk(items: Sequence[object], depth: int) -> None:
        """Walk outline items and collect top level chapters.

        Purpose:
            Traverse nested outline items and collect depth zero entries.
        Ties To:
            Used by detect_chapters_from_outlines.
        Inputs:
            - items: Sequence of outline items.
            - depth: Depth of the current outline traversal.
        Outputs:
            - None.
        Side Effects:
            Appends to the enclosing entries list.
        Raises:
            - PdfProcessingError: When outline entries are invalid.
        """
        for item in items:
            token.check(location)
            deadline.check(location)
            if isinstance(item, list):
                _walk(item, depth + 1)
                continue
            if depth != 0:
                continue
            try:
                page_num = reader.get_destination_page_number(item) + 1
            except (ValueError, TypeError, AttributeError) as exc:
                raise PdfProcessingError(
                    format_error_message(
                        error_location, f"Outline destination is invalid.{context}"
                    )
                ) from exc
            title = getattr(item, "title", "").strip()
            if not title:
                title = f"Chapter {len(entries) + 1}"
            entries.append((title, page_num))

    _walk(outlines, 0)
    if not entries:
        return []
    entries.sort(key=lambda item: item[1])

    chapters: list[ChapterDefinition] = []
    for idx, (title, start_page) in enumerate(entries):
        end_page = entries[idx + 1][1] - 1 if idx + 1 < len(entries) else total_pages
        chapters.append(ChapterDefinition(title=title, start_page=start_page, end_page=end_page))
    return chapters
