"""Domain validation for chapters and page ranges."""

from __future__ import annotations

from collections.abc import Sequence

from .errors import ValidationError, format_error_message
from .models import ChapterDefinition


def validate_page_range(
    start_page: int,
    end_page: int,
    total_pages: int,
    location: str,
) -> tuple[int, int]:
    """Validate and normalize a one based page range.

    Summary:
        Ensure page ranges are within document bounds and correctly ordered.
    Ties to other methods:
        Used by PDF splitting and chapter validation.
    Inputs:
        - start_page: Start page number, one based.
        - end_page: End page number, one based.
        - total_pages: Total number of pages in the PDF.
        - location: Fully qualified module and method name.
    Outputs:
        - Tuple of validated (start_page, end_page).
    Side effects:
        None.
    Error handling:
        - ValidationError: When page ranges are invalid.
    """
    error_location = f"{__name__}.validate_page_range"
    context = f" Context: {location}." if location else ""
    if total_pages < 1:
        raise ValidationError(
            format_error_message(error_location, f"Total pages must be at least 1.{context}")
        )
    if start_page < 1 or end_page < 1:
        raise ValidationError(
            format_error_message(error_location, f"Page numbers must be at least 1.{context}")
        )
    if start_page > end_page:
        raise ValidationError(
            format_error_message(error_location, f"Start page must not exceed end page.{context}")
        )
    if end_page > total_pages:
        raise ValidationError(
            format_error_message(
                error_location,
                f"End page {end_page} exceeds total pages {total_pages}.{context}",
            )
        )
    return start_page, end_page


def validate_chapters(
    chapters: Sequence[ChapterDefinition],
    total_pages: int,
    max_chapters: int,
    require_unique_titles: bool,
    sort_chapters_by_start_page: bool,
    reject_overlapping_ranges: bool,
    location: str,
) -> list[ChapterDefinition]:
    """Validate a list of chapter definitions.

    Summary:
        Ensure chapter definitions are valid and within document bounds.
    Ties to other methods:
        Used by the UI and CLI before invoking the splitter.
    Inputs:
        - chapters: Sequence of ChapterDefinition instances.
        - total_pages: Total number of pages in the PDF.
        - max_chapters: Maximum allowed number of chapters.
        - require_unique_titles: Whether titles must be unique.
        - sort_chapters_by_start_page: Whether to sort validated chapters by start page.
        - reject_overlapping_ranges: Whether validated ranges must not overlap.
        - location: Fully qualified module and method name.
    Outputs:
        - List of validated ChapterDefinition objects.
    Side effects:
        None.
    Error handling:
        - ValidationError: When chapter definitions are invalid.
    """
    error_location = f"{__name__}.validate_chapters"
    context = f" Context: {location}." if location else ""
    if not chapters:
        raise ValidationError(
            format_error_message(error_location, f"At least one chapter is required.{context}")
        )
    if len(chapters) > max_chapters:
        raise ValidationError(
            format_error_message(
                error_location,
                f"Chapter count {len(chapters)} exceeds max {max_chapters}.{context}",
            )
        )
    seen_titles: set[str] = set()
    validated: list[ChapterDefinition] = []
    for chapter in chapters:
        chapter.validate(location)
        validate_page_range(chapter.start_page, chapter.end_page, total_pages, location)
        if require_unique_titles:
            if chapter.title in seen_titles:
                raise ValidationError(
                    format_error_message(
                        error_location,
                        f"Duplicate chapter title detected: {chapter.title}.{context}",
                    )
                )
            seen_titles.add(chapter.title)
        validated.append(chapter)
    if sort_chapters_by_start_page:
        validated = sorted(
            validated,
            key=lambda item: (item.start_page, item.end_page, item.title),
        )

    if reject_overlapping_ranges:
        ordered = sorted(
            validated,
            key=lambda item: (item.start_page, item.end_page, item.title),
        )
        for prev, curr in zip(ordered, ordered[1:], strict=False):
            if curr.start_page <= prev.end_page:
                raise ValidationError(
                    format_error_message(
                        error_location,
                        "Chapter page ranges must not overlap. "
                        f"'{prev.title}' ends at page {prev.end_page} but '{curr.title}' "
                        f"starts at page {curr.start_page}.{context}",
                    )
                )

    return validated
