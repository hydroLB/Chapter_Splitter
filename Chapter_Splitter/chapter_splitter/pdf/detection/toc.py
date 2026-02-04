"""Table-of-contents based chapter detection fallback."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ...config.schema import DetectionConfig
from ...core.errors import PdfProcessingError, format_error_message
from ...core.models import ChapterDefinition
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline


class TextExtractablePageProtocol(Protocol):
    """Minimal protocol for a PDF page that can provide extracted text."""

    def extract_text(self) -> str | None: ...


class TextExtractableReaderProtocol(Protocol):
    """Minimal protocol for a PDF reader exposing pages with extract_text support."""

    @property
    def pages(self) -> Sequence[TextExtractablePageProtocol]: ...


@dataclass(frozen=True, slots=True)
class TocEntry:
    """Parsed TOC entry.

    Purpose:
        Provide an intermediate representation while converting TOC lines to chapter ranges.
    Ties To:
        Used by detect_chapters_from_toc_page.
    Inputs:
        - title: Parsed chapter title.
        - page: Parsed 1-based page number.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    title: str
    page: int


def detect_chapters_from_toc_page(
    reader: TextExtractableReaderProtocol,
    toc_start_page: int,
    total_pages: int,
    detection: DetectionConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> list[ChapterDefinition]:
    """Detect chapter ranges from a Table of Contents page.

    Purpose:
        Provide a fallback chapter inference path when PDF outline metadata is missing.
    Ties To:
        Used by the GUI when the user navigates to a TOC page and requests detection.
    Inputs:
        - reader: Reader with page text extraction support.
        - toc_start_page: 1-based page number where the TOC starts.
        - total_pages: Total pages in the document.
        - detection: Detection configuration controlling parsing behavior.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - List of ChapterDefinition objects inferred from TOC entries.
    Side Effects:
        Extracts text from PDF pages in memory.
    Raises:
        - PdfProcessingError: When parsing fails or the TOC cannot be interpreted.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.detect_chapters_from_toc_page"
    context = f" Context: {location}." if location else ""
    if toc_start_page < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"toc_start_page must be >= 1 (got {toc_start_page}).{context}",
            )
        )
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"total_pages must be >= 1 (got {total_pages}).{context}",
            )
        )
    if toc_start_page > total_pages:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"toc_start_page {toc_start_page} exceeds total pages {total_pages}.{context}",
            )
        )

    detection.validate(location)
    entry_patterns = [re.compile(p) for p in detection.toc_entry_regexes]
    ignore_patterns = [re.compile(p) for p in detection.toc_ignore_title_regexes]

    max_scan = min(
        detection.toc_scan_max_pages,
        total_pages - toc_start_page + 1,
    )
    entries: list[TocEntry] = []

    for scan_offset in range(max_scan):
        token.check(location)
        deadline.check(location)
        page_index = toc_start_page - 1 + scan_offset
        if page_index < 0 or page_index >= len(reader.pages):
            break
        page = reader.pages[page_index]
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for raw_line in lines:
            token.check(location)
            deadline.check(location)
            parsed = _parse_toc_line(raw_line, entry_patterns, ignore_patterns, location)
            if parsed is None:
                continue
            if not 1 <= parsed.page <= total_pages:
                continue
            entries.append(parsed)
            if len(entries) >= detection.toc_max_entries:
                break
        if len(entries) >= detection.toc_max_entries:
            break

    normalized = _normalize_toc_entries(entries, detection.toc_max_entries)
    if len(normalized) < detection.toc_min_entries:
        return []
    return _toc_entries_to_chapters(normalized, total_pages, location)


def _parse_toc_line(
    line: str,
    entry_patterns: Sequence[re.Pattern[str]],
    ignore_patterns: Sequence[re.Pattern[str]],
    location: str,
) -> TocEntry | None:
    """Parse a single TOC line into a TocEntry when it matches expected patterns.

    Purpose:
        Isolate TOC line parsing so detection stays readable and easy to tune.
    Ties To:
        Used by detect_chapters_from_toc_page.
    Inputs:
        - line: Candidate TOC line.
        - entry_patterns: Compiled patterns exposing groups named 'title' and 'page'.
        - ignore_patterns: Patterns identifying ignorable titles.
        - location: Fully qualified module and method name.
    Outputs:
        - TocEntry when parsed, otherwise None.
    Side Effects:
        None.
    Raises:
        - PdfProcessingError: When a match yields an invalid page number.
    """
    error_location = f"{__name__}._parse_toc_line"
    context = f" Context: {location}." if location else ""
    if not line.strip():
        return None
    for pattern in entry_patterns:
        match = pattern.match(line)
        if match is None:
            continue
        title = (match.group("title") or "").strip()
        page_raw = (match.group("page") or "").strip()
        title = _clean_title(title)
        if not title:
            return None
        if any(pat.match(title) for pat in ignore_patterns):
            return None
        try:
            page = int(page_raw)
        except ValueError as exc:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"TOC line contains an invalid page number: {line}.{context}",
                )
            ) from exc
        return TocEntry(title=title, page=page)
    return None


def _clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip(" .\t")


def _normalize_toc_entries(entries: Sequence[TocEntry], max_entries: int) -> list[TocEntry]:
    by_page: dict[int, TocEntry] = {}
    for entry in entries:
        if entry.page not in by_page:
            by_page[entry.page] = entry
    ordered = sorted(by_page.values(), key=lambda item: item.page)
    return ordered[:max_entries]


def _toc_entries_to_chapters(
    entries: Sequence[TocEntry],
    total_pages: int,
    location: str,
) -> list[ChapterDefinition]:
    error_location = f"{__name__}._toc_entries_to_chapters"
    context = f" Context: {location}." if location else ""
    chapters: list[ChapterDefinition] = []
    for idx, entry in enumerate(entries):
        start_page = entry.page
        next_start = entries[idx + 1].page if idx + 1 < len(entries) else total_pages + 1
        end_page = min(total_pages, next_start - 1)
        if start_page < 1 or start_page > total_pages:
            continue
        if end_page < start_page:
            continue
        title = entry.title.strip() or f"Chapter {len(chapters) + 1}"
        chapters.append(ChapterDefinition(title=title, start_page=start_page, end_page=end_page))
    if not chapters:
        return []
    for chapter in chapters:
        if chapter.start_page < 1 or chapter.end_page > total_pages:
            raise PdfProcessingError(
                format_error_message(
                    error_location,
                    f"TOC detection produced an out of range chapter: {chapter}.{context}",
                )
            )
    return chapters
