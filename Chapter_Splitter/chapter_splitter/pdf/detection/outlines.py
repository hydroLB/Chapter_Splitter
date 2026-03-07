"""PDF outline detection logic for chapter inference."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from ...config.schema import DetectionConfig, IOConfig, RetryConfig
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
    detection_config: DetectionConfig | None = None,
) -> list[ChapterDefinition]:
    """Inspect PDF outlines and return inferred chapter ranges.

    Summary:
        Use top level PDF outlines to infer chapter boundaries.
    Ties to other methods:
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
    Side effects:
        Reads the PDF file from disk.
    Error handling:
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
        outline_min_depth=detection_config.outline_min_depth if detection_config else 0,
        outline_ignore_title_regexes=(
            detection_config.outline_ignore_title_regexes if detection_config else ()
        ),
        outline_merge_tiny_max_pages=(
            detection_config.outline_merge_tiny_max_pages if detection_config else 0
        ),
        outline_merge_tiny_title_joiner=(
            detection_config.outline_merge_tiny_title_joiner if detection_config else " + "
        ),
    )


def detect_chapters_from_outlines_reader(
    reader: OutlineReaderProtocol,
    total_pages: int,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
    entries: list[tuple[str, int]] | None = None,
    outline_min_depth: int = 0,
    outline_ignore_title_regexes: Sequence[str] = (),
    outline_merge_tiny_max_pages: int = 0,
    outline_merge_tiny_title_joiner: str = " + ",
) -> list[ChapterDefinition]:
    """Inspect outlines on an already-loaded reader and infer chapter ranges.

    Summary:
        Provide a reusable outlines implementation when the caller already has a reader.
    Ties to other methods:
        Used by unified detection and GUI workflows.
    Inputs:
        - reader: Reader exposing outlines and destination page lookup.
        - total_pages: Total page count for end-range calculations.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects inferred from outlines.
    Side effects:
        None.
    Error handling:
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
    extracted = entries or extract_outline_entries(
        reader,
        deadline,
        token,
        location,
        outline_min_depth=outline_min_depth,
        outline_ignore_title_regexes=outline_ignore_title_regexes,
    )
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
    if outline_merge_tiny_max_pages > 0:
        chapters = _merge_tiny_chapters(
            chapters,
            outline_merge_tiny_max_pages,
            outline_merge_tiny_title_joiner,
        )
    return chapters


def extract_outline_entries(
    reader: OutlineReaderProtocol,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
    outline_min_depth: int = 0,
    outline_ignore_title_regexes: Sequence[str] = (),
) -> list[tuple[str, int]]:
    """Extract top-level outline entries as (title, 1-based page) pairs.

    Summary:
        Provide a lightweight outline extraction API for unified detection and reporting.
    Ties to other methods:
        Used by detect_chapters_from_outlines_reader and the unified detector.
    Inputs:
        - reader: Reader exposing outline and destination page lookup.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of (title, page) tuples.
    Side effects:
        None.
    Error handling:
        - PdfProcessingError: When outlines are malformed or destinations are invalid.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.extract_outline_entries"
    context = f" Context: {location}." if location else ""
    if outline_min_depth < 0:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"outline_min_depth must be >= 0 (got {outline_min_depth}).{context}",
            )
        )
    outlines = reader.outline
    if outlines is None:
        return []
    if not isinstance(outlines, Sequence):
        raise PdfProcessingError(
            format_error_message(error_location, f"PDF outlines must be a sequence.{context}")
        )

    compiled_ignores: list[re.Pattern[str]] = []
    for pattern in outline_ignore_title_regexes:
        try:
            compiled_ignores.append(re.compile(pattern))
        except re.error as exc:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"Invalid outline ignore pattern: {pattern}.{context}",
                )
            ) from exc

    candidates: list[tuple[int, str, int]] = []

    def _walk(items: Sequence[object], depth: int) -> None:
        """Walk outline items and collect top level entries.

        Summary:
            Traverse nested outlines and collect depth zero items as chapter candidates.
        Ties to other methods:
            Used by extract_outline_entries.
        Inputs:
            - items: Outline items.
            - depth: Current nesting depth.
        Outputs:
            - None.
        Side effects:
            Appends to the entries list.
        Error handling:
            - PdfProcessingError: When an outline destination is invalid.
        """
        for item in items:
            token.check(location)
            deadline.check(location)
            if isinstance(item, list):
                _walk(item, depth + 1)
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
                title = f"Chapter {len(candidates) + 1}"
            if any(pattern.search(title) for pattern in compiled_ignores):
                continue
            candidates.append((depth, title, page_num))

    _walk(outlines, 0)
    eligible = [item for item in candidates if item[0] >= outline_min_depth]
    if not eligible:
        return []
    selected_depth = min(item[0] for item in eligible)
    return [(title, page) for depth, title, page in eligible if depth == selected_depth]


def _merge_tiny_chapters(
    chapters: list[ChapterDefinition],
    max_pages: int,
    title_joiner: str,
) -> list[ChapterDefinition]:
    """Merge small outline-derived chapters into adjacent ranges.

    Summary:
        Reduce noisy outline outputs such as one-page entries that fragment the chapter list.
    Ties to other methods:
        Used by detect_chapters_from_outlines_reader after chapter ranges are derived.
    Inputs:
        - chapters: Outline-derived chapters to post-process.
        - max_pages: Maximum page count considered "tiny" (<= max_pages).
        - title_joiner: Joiner used when combining titles.
    Outputs:
        - New list of ChapterDefinition objects with merged ranges.
    Side effects:
        None.
    Error handling:
        - None.
    """
    if max_pages <= 0:
        return chapters
    if not title_joiner.strip():
        title_joiner = " + "

    merged: list[ChapterDefinition] = []
    work = list(chapters)
    idx = 0
    while idx < len(work):
        current = work[idx]
        page_count = current.end_page - current.start_page + 1
        if page_count <= max_pages and idx + 1 < len(work):
            nxt = work[idx + 1]
            work[idx + 1] = ChapterDefinition(
                title=f"{current.title}{title_joiner}{nxt.title}",
                start_page=current.start_page,
                end_page=nxt.end_page,
            )
            idx += 1
            continue
        if page_count <= max_pages and merged:
            prev = merged.pop()
            merged.append(
                ChapterDefinition(
                    title=f"{prev.title}{title_joiner}{current.title}",
                    start_page=prev.start_page,
                    end_page=current.end_page,
                )
            )
            idx += 1
            continue
        merged.append(current)
        idx += 1
    return merged
