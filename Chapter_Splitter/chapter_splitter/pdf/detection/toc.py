"""Table-of-contents based chapter detection fallback."""

from __future__ import annotations

import math
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


@dataclass(frozen=True, slots=True)
class TocDetectionReport:
    """Structured TOC detection output and diagnostics.

    Purpose:
        Provide detection results with confidence and warnings for UI surfaces.
    Ties To:
        Returned by detect_best_toc_chapters and consumed by the unified detector.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    chapters: tuple[ChapterDefinition, ...]
    confidence: float
    warnings: tuple[str, ...]
    toc_start_page: int | None
    pages_scanned: int
    entries_found: int


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
    report = detect_best_toc_chapters(
        reader=reader,
        total_pages=total_pages,
        detection=detection,
        deadline=deadline,
        token=token,
        toc_hint_page=toc_start_page,
        location=location,
        force_hint_page=True,
    )
    return list(report.chapters)


def detect_best_toc_chapters(
    reader: TextExtractableReaderProtocol,
    total_pages: int,
    detection: DetectionConfig,
    deadline: Deadline,
    token: CancellationToken,
    toc_hint_page: int | None,
    location: str,
    force_hint_page: bool = False,
) -> TocDetectionReport:
    """Detect chapters from TOC text by scanning candidate pages and scoring results.

    Purpose:
        Provide a robust TOC fallback by trying multiple start pages and returning the best parse.
    Ties To:
        Used by the unified detector and GUI preview action.
    Inputs:
        - reader: Reader with page text extraction support.
        - total_pages: Total pages in the document.
        - detection: Detection configuration controlling parsing behavior.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - toc_hint_page: Optional 1-based hint page where TOC starts.
        - location: Fully qualified module and method name.
        - force_hint_page: When True, only scan starting from toc_hint_page.
    Outputs:
        - TocDetectionReport containing best-effort chapters and diagnostics.
    Side Effects:
        Extracts text from PDF pages in memory.
    Raises:
        - PdfProcessingError: When inputs are invalid.
    """
    token.check(location)
    deadline.check(location)
    error_location = f"{__name__}.detect_best_toc_chapters"
    context = f" Context: {location}." if location else ""
    if total_pages < 1:
        raise PdfProcessingError(
            format_error_message(
                error_location,
                f"total_pages must be >= 1 (got {total_pages}).{context}",
            )
        )

    detection.validate(location)
    entry_patterns = [re.compile(p) for p in detection.toc_entry_regexes]
    ignore_patterns = [re.compile(p) for p in detection.toc_ignore_title_regexes]

    candidates = _candidate_toc_start_pages(
        toc_hint_page=toc_hint_page,
        total_pages=total_pages,
        max_start_page=detection.toc_auto_scan_max_start_page,
        force_hint_page=force_hint_page,
    )
    best: tuple[float, TocDetectionReport] | None = None

    for start_page in candidates:
        token.check(location)
        deadline.check(location)
        report = _scan_toc_from_start(
            reader=reader,
            toc_start_page=start_page,
            total_pages=total_pages,
            entry_patterns=entry_patterns,
            ignore_patterns=ignore_patterns,
            detection=detection,
            deadline=deadline,
            token=token,
            location=location,
        )
        score = report.confidence
        if best is None or score > best[0]:
            best = (score, report)
        if best is not None and best[0] >= 0.9:
            break

    if best is None:
        return TocDetectionReport(
            chapters=(),
            confidence=0.0,
            warnings=("No TOC candidates were scanned.",),
            toc_start_page=toc_hint_page,
            pages_scanned=0,
            entries_found=0,
        )
    return best[1]


def _scan_toc_from_start(
    reader: TextExtractableReaderProtocol,
    toc_start_page: int,
    total_pages: int,
    entry_patterns: Sequence[re.Pattern[str]],
    ignore_patterns: Sequence[re.Pattern[str]],
    detection: DetectionConfig,
    deadline: Deadline,
    token: CancellationToken,
    location: str,
) -> TocDetectionReport:
    context = f" Context: {location}." if location else ""
    if toc_start_page < 1 or toc_start_page > total_pages:
        return TocDetectionReport(
            chapters=(),
            confidence=0.0,
            warnings=(f"TOC start page {toc_start_page} is out of range.{context}",),
            toc_start_page=toc_start_page,
            pages_scanned=0,
            entries_found=0,
        )

    max_scan = min(detection.toc_scan_max_pages, total_pages - toc_start_page + 1)
    entries: list[TocEntry] = []
    pages_scanned = 0
    for scan_offset in range(max_scan):
        token.check(location)
        deadline.check(location)
        page_index = toc_start_page - 1 + scan_offset
        if page_index < 0 or page_index >= len(reader.pages):
            break
        pages_scanned += 1
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
        return TocDetectionReport(
            chapters=(),
            confidence=0.0,
            warnings=(f"Found {len(normalized)} TOC entries, below minimum.",),
            toc_start_page=toc_start_page,
            pages_scanned=pages_scanned,
            entries_found=len(normalized),
        )
    chapters = _toc_entries_to_chapters(normalized, total_pages, location)
    confidence, warnings = _score_toc_entries(normalized, chapters, total_pages)
    return TocDetectionReport(
        chapters=tuple(chapters),
        confidence=confidence,
        warnings=tuple(warnings),
        toc_start_page=toc_start_page,
        pages_scanned=pages_scanned,
        entries_found=len(normalized),
    )


def _candidate_toc_start_pages(
    toc_hint_page: int | None,
    total_pages: int,
    max_start_page: int,
    force_hint_page: bool,
) -> list[int]:
    if force_hint_page:
        return [toc_hint_page] if toc_hint_page is not None else []
    candidates: list[int] = []
    if toc_hint_page is not None:
        for delta in range(0, 3):
            for sign in (1, -1):
                page = toc_hint_page + sign * delta
                if 1 <= page <= total_pages:
                    candidates.append(page)
    for page in range(1, min(total_pages, max_start_page) + 1):
        candidates.append(page)
    # De-dup while preserving order.
    seen: set[int] = set()
    ordered: list[int] = []
    for page in candidates:
        if page in seen:
            continue
        seen.add(page)
        ordered.append(page)
    return ordered


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


def _score_toc_entries(
    entries: Sequence[TocEntry],
    chapters: Sequence[ChapterDefinition],
    total_pages: int,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    if not chapters:
        return 0.0, ["No chapters could be constructed from TOC entries."]
    pages = [entry.page for entry in entries]
    increasing_pairs = sum(1 for a, b in zip(pages, pages[1:], strict=False) if b > a)
    monotonic_ratio = increasing_pairs / max(1, len(pages) - 1)
    if monotonic_ratio < 0.9:
        warnings.append("TOC page numbers are not strictly increasing.")
    span = max(pages) - min(pages) if pages else 0
    span_ratio = span / max(1, total_pages)
    if span_ratio < 0.25:
        warnings.append("TOC entries cover a small portion of the document.")

    count = len(entries)
    count_score = min(1.0, math.log10(count + 1) / math.log10(30))
    confidence = 0.25 + 0.55 * monotonic_ratio + 0.2 * count_score
    if count < 4:
        confidence *= 0.75
    confidence = max(0.0, min(0.99, confidence))
    return confidence, warnings
