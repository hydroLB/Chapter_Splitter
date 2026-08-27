"""Unit tests for filename utilities."""

from __future__ import annotations

import pytest

from chapter_splitter.core import ValidationError
from chapter_splitter.utils import safe_filename


def test_safe_filename_sanitizes_invalid_chars() -> None:
    """Verify that invalid characters are replaced."""
    assert safe_filename("Chap:1/2") == "Chap_1_2"


def test_safe_filename_rejects_empty_input() -> None:
    """Verify that empty input is rejected."""
    with pytest.raises(ValidationError):
        safe_filename(" ")


def test_safe_filename_strips_windows_trailing_chars() -> None:
    """Verify that Windows-incompatible trailing characters are removed."""
    assert safe_filename("Chapter.") == "Chapter"
    assert safe_filename("Chapter . ") == "Chapter"

    with pytest.raises(ValidationError):
        safe_filename("...")


def test_safe_filename_replaces_controls_and_prevents_hidden_names() -> None:
    """Control characters and leading dots must not survive into an output component."""
    assert safe_filename(".Chapter\nOne\x7f") == "_Chapter_One_"
    assert safe_filename(f"A{chr(0xD800)}B") == "A_B"
    assert not safe_filename("..appendix").startswith(".")


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("LPT9", "_LPT9"),
        ("COM¹.notes", "_COM¹.notes"),
    ],
)
def test_safe_filename_escapes_windows_reserved_device_names(
    raw_name: str,
    expected: str,
) -> None:
    """Windows device basenames remain reserved regardless of case or extension."""
    assert safe_filename(raw_name) == expected


def test_safe_filename_normalizes_unicode_and_bounds_utf8_length() -> None:
    """Filename components are NFC-stable and leave room below filesystem byte limits."""
    assert safe_filename("Cafe\u0301") == "Café"

    sanitized = safe_filename("章" * 200)

    assert len(sanitized.encode("utf-8")) == 240
    assert sanitized.encode("utf-8").decode("utf-8") == sanitized
