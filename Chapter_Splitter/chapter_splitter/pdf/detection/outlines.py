"""PDF outline detection logic for chapter inference."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from ...config.schema import IOConfig, RetryConfig
from ...core.errors import PdfProcessingError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline
from ..io.loader import get_total_pages, load_reader


class OutlineReaderProtocol(Protocol):
    @property
    def outline(self) -> Sequence[object] | None: ...

    def get_destination_page_number(self, dest: object) -> int: ...


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
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    deadline.check(location)
    return detect_chapters_from_outlines_reader(
        reader=reader,
        total_pages=total_pages,
        deadline=deadline,
        token=token,
        location=location,
    )


def detect_chapters_from_outlines_reader(
    reader: OutlineReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
    entries: list[tuple[str, int]] | None = None,
) -> list[ChapterDefinition]:
    """Inspect outlines on an already-loaded reader and infer chapter ranges.

    Purpose:
        Provide a reusable outlines implementation when the caller already has a reader.
    Ties To:
        Used by unified detection and GUI workflows.
    Inputs:
        - reader: Reader exposing outlines and destination page lookup.
        - total_pages: Total page count for end-range calculations.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects inferred from outlines.
    Side Effects:
        None.
    Raises:
        - PdfProcessingError: When outlines are malformed or destinations are invalid.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.detect_chapters_from_outlines_reader"
    context = f" Context: {location}." if location else ""
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"total_pages must be >= 1 (got {total_pages}).{context}",
            )
        )
    extracted = entries or extract_outline_entries(reader, deadline, token, location)
    if not extracted:
        return []
    extracted.sort(key=lambda item: item[1])
    chapters: list[ChapterDefinition] = []
    for idx, (title, start_page) in enumerate(extracted):
        end_page = extracted[idx + 1][1] - 1 if idx + 1 < len(extracted) else total_pages
        if start_page < 1 or start_page > total_pages:
            continue
        if end_page < start_page:
            continue
        chapters.append(ChapterDefinition(title=title, start_page=start_page, end_page=end_page))
    return chapters


def extract_outline_entries(
    reader: OutlineReaderProtocol,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> list[tuple[str, int]]:
    """Extract top-level outline entries as (title, 1-based page) pairs.

    Purpose:
        Provide a lightweight outline extraction API for unified detection and reporting.
    Ties To:
        Used by detect_chapters_from_outlines_reader and the unified detector.
    Inputs:
        - reader: Reader exposing outline and destination page lookup.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of (title, page) tuples.
    Side Effects:
        None.
    Raises:
        - PdfProcessingError: When outlines are malformed or destinations are invalid.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.extract_outline_entries"
    context = f" Context: {location}." if location else ""
    outlines = reader.outline
    if outlines is None:
        return []
    if not isinstance(outlines, Sequence):
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF outlines must be a sequence.{context}")
        )

    entries: list[tuple[str, int]] = []

    def _walk(items: Sequence[object], depth: int) -> None:
        """Walk outline items and collect top level entries.

        Purpose:
            Traverse nested outlines and collect depth zero items as chapter candidates.
        Ties To:
            Used by extract_outline_entries.
        Inputs:
            - items: Outline items.
            - depth: Current nesting depth.
        Outputs:
            - None.
        Side Effects:
            Appends to the entries list.
        Raises:
            - PdfProcessingError: When an outline destination is invalid.
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
    return entries
