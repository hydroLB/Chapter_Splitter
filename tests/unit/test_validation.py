"""Unit tests for validation helpers."""

from __future__ import annotations

import pytest

from chapter_splitter.core.errors import ValidationError
from chapter_splitter.core.models import ChapterDefinition
from chapter_splitter.core.validation import validate_chapters, validate_page_range


def test_validate_page_range_accepts_valid_range() -> None:
    """Verify valid ranges pass validation.

    Purpose:
        Ensure validate_page_range returns the expected range.
    Ties To:
        Covers chapter_splitter.core.validation.validate_page_range.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert validate_page_range(1, 3, 10, "tests.unit.test_validation") == (1, 3)


def test_validate_page_range_rejects_invalid_range() -> None:
    """Verify invalid ranges raise validation errors.

    Purpose:
        Ensure validate_page_range rejects invalid inputs.
    Ties To:
        Covers chapter_splitter.core.validation.validate_page_range.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ValidationError):
        validate_page_range(5, 2, 10, "tests.unit.test_validation")


def test_validate_chapters_enforces_limits() -> None:
    """Verify chapter validation enforces title uniqueness.

    Purpose:
        Ensure validate_chapters enforces unique titles when required.
    Ties To:
        Covers chapter_splitter.core.validation.validate_chapters.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
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
            location="tests.unit.test_validation",
        )
