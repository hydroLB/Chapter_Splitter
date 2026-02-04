"""Unit tests for filename utilities."""

from __future__ import annotations

import pytest

from chapter_splitter.core.errors import ValidationError
from chapter_splitter.utils.filenames import safe_filename


def test_safe_filename_sanitizes_invalid_chars() -> None:
    """Verify that invalid characters are replaced.

    Purpose:
        Ensure filename sanitization replaces OS invalid characters.
    Ties To:
        Covers chapter_splitter.utils.filenames.safe_filename.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert safe_filename("Chap:1/2") == "Chap_1_2"


def test_safe_filename_rejects_empty_input() -> None:
    """Verify that empty input is rejected.

    Purpose:
        Ensure validation errors are raised for empty filenames.
    Ties To:
        Covers chapter_splitter.utils.filenames.safe_filename.
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
        safe_filename(" ")


def test_safe_filename_strips_windows_trailing_chars() -> None:
    """Verify that Windows-incompatible trailing characters are removed.

    Purpose:
        Ensure sanitized filenames do not end with a trailing space or period, which are invalid on
        Windows filesystems.
    Ties To:
        Covers chapter_splitter.utils.filenames.safe_filename.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert safe_filename("Chapter.") == "Chapter"
    assert safe_filename("Chapter . ") == "Chapter"

    with pytest.raises(ValidationError):
        safe_filename("...")
