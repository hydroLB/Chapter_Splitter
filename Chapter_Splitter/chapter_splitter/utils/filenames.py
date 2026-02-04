"""Filename safety helpers."""

from __future__ import annotations

from ..core.errors import ValidationError, format_error_message


def safe_filename(name: str) -> str:
    """Sanitize a string so it can be used as a filename.

    Purpose:
        Ensure chapter titles produce safe filenames across operating systems.
    Ties To:
        Used by PDF splitting when naming chapter files.
    Inputs:
        - name: Raw filename candidate.
    Outputs:
        - Sanitized filename string.
    Side Effects:
        None.
    Raises:
        - ValidationError: When name is empty or not a string.
    """
    if not isinstance(name, str):
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename must be a string.",
            )
        )
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename must be non empty.",
            )
        )
    invalid_chars = r"<>:\"/|?*"
    sanitized = "".join("_" if c in invalid_chars else c for c in cleaned).strip().rstrip(" .")
    if not sanitized:
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename is empty after sanitization.",
            )
        )
    return sanitized
