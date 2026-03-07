"""Unit tests for validation helpers."""

from __future__ import annotations

import pytest

from chapter_splitter.core import (
    ChapterDefinition,
    ValidationError,
    validate_chapters,
    validate_page_range,
)


def test_validate_page_range_accepts_valid_range() -> None:
    """Verify valid ranges pass validation.

    Summary:
        Ensure validate_page_range returns the expected range.
    Ties to other methods:
        Covers chapter_splitter.core.validation.validate_page_range.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    assert validate_page_range(1, 3, 10, "tests.unit.test_validation") == (1, 3)


def test_validate_page_range_rejects_invalid_range() -> None:
    """Verify invalid ranges raise validation errors.

    Summary:
        Ensure validate_page_range rejects invalid inputs.
    Ties to other methods:
        Covers chapter_splitter.core.validation.validate_page_range.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    with pytest.raises(ValidationError):
        validate_page_range(5, 2, 10, "tests.unit.test_validation")


def test_validate_chapters_enforces_limits() -> None:
    """Verify chapter validation enforces title uniqueness.

    Summary:
        Ensure validate_chapters enforces unique titles when required.
    Ties to other methods:
        Covers chapter_splitter.core.validation.validate_chapters.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=1),
        ChapterDefinition(title="One", start_page=2, end_page=2),
    ]
    with pytest.raises(ValidationError):
        validate_chapters(
            chapters=chapters,
            total_pages=3,
            max_chapters=5,
            require_unique_titles=True,
            sort_chapters_by_start_page=False,
            reject_overlapping_ranges=False,
            location="tests.unit.test_validation",
        )


def test_validate_chapters_rejects_overlapping_ranges() -> None:
    """Verify chapter validation rejects overlapping page ranges.

    Summary:
        Ensure exports cannot silently produce duplicate pages across chapters.
    Ties to other methods:
        Covers overlap enforcement in chapter_splitter.core.validation.validate_chapters.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=3),
        ChapterDefinition(title="Two", start_page=3, end_page=4),
    ]
    with pytest.raises(ValidationError):
        validate_chapters(
            chapters=chapters,
            total_pages=10,
            max_chapters=10,
            require_unique_titles=False,
            sort_chapters_by_start_page=False,
            reject_overlapping_ranges=True,
            location="tests.unit.test_validation",
        )
