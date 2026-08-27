"""Filename safety helpers."""

from __future__ import annotations

import unicodedata

from ..core.errors import ValidationError, format_error_message

_INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')
_INVALID_UNICODE_CATEGORIES = frozenset({"Cc", "Cs"})
_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "AUX",
        "CLOCK$",
        "CON",
        "CONIN$",
        "CONOUT$",
        "NUL",
        "PRN",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
        *(f"COM{index}" for index in "¹²³"),
        *(f"LPT{index}" for index in "¹²³"),
    }
)

# Leave room beneath the common 255-byte component limit for a " (250).pdf" suffix.
_MAX_SAFE_STEM_UTF8_BYTES = 240


def safe_filename(name: str) -> str:
    """Sanitize a string so it can be used as a filename."""
    if not isinstance(name, str):
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename must be a string.",
            )
        )
    cleaned = unicodedata.normalize("NFC", name).strip()
    if not cleaned:
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename must be non empty.",
            )
        )
    sanitized = (
        "".join(
            "_"
            if character in _INVALID_FILENAME_CHARACTERS
            or unicodedata.category(character) in _INVALID_UNICODE_CATEGORIES
            else character
            for character in cleaned
        )
        .strip()
        .rstrip(" .")
    )
    if not sanitized:
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename is empty after sanitization.",
            )
        )
    leading_dots = len(sanitized) - len(sanitized.lstrip("."))
    if leading_dots:
        sanitized = "_" * leading_dots + sanitized[leading_dots:]

    windows_basename = sanitized.partition(".")[0].rstrip(" .").upper()
    if windows_basename in _WINDOWS_RESERVED_BASENAMES:
        sanitized = f"_{sanitized}"

    sanitized = _truncate_utf8(sanitized, _MAX_SAFE_STEM_UTF8_BYTES).rstrip(" .")
    if not sanitized:
        raise ValidationError(
            format_error_message(
                "chapter_splitter.utils.filenames.safe_filename",
                "Filename is empty after length normalization.",
            )
        )
    return sanitized


def _truncate_utf8(value: str, max_bytes: int) -> str:
    """Truncate text without returning a partial UTF-8 code point."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")
