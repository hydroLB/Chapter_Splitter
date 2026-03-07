"""Session metadata parsing helpers for chapter files."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.errors import ValidationError, format_error_message
from .models import ChapterFileSessionMetadata


def parse_session_metadata(
    raw: object,
    *,
    location: str,
) -> ChapterFileSessionMetadata | None:
    """Parse the optional [session] table from a chapter file.

    Summary:
        Preserve forward-compatible session metadata without making it required.
    Inputs:
        - raw: Raw TOML value for the "session" key.
        - location: Fully qualified module and method name.
    Outputs:
        - ChapterFileSessionMetadata when present, otherwise None.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when the session table exists but is malformed.
    Ties to other methods:
        Used by load_chapter_file_with_metadata.
    Why this exists:
        Session metadata should stay optional while still being validated rigorously.
    """
    error_location = "chapter_splitter.io.chapter_files.session.parse_session_metadata"
    context = f" Context: {location}." if location else ""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session must be a table when present.{context}",
            )
        )
    pdf_path = _optional_str(raw, key="pdf_path", error_location=error_location, context=context)
    total_pages = _optional_int(
        raw,
        key="total_pages",
        error_location=error_location,
        context=context,
    )
    saved_at = _optional_str(raw, key="saved_at", error_location=error_location, context=context)
    source = _optional_str(raw, key="source", error_location=error_location, context=context)
    return ChapterFileSessionMetadata(
        pdf_path=pdf_path,
        total_pages=total_pages,
        saved_at=saved_at,
        source=source,
    )


def _optional_str(
    raw: Mapping[str, object],
    *,
    key: str,
    error_location: str,
    context: str,
) -> str | None:
    """Validate an optional string field inside session metadata.

    Summary:
        Return an optional string value while enforcing its type when present.
    Inputs:
        - raw: Session metadata mapping.
        - key: Field name to validate.
        - error_location: Fully qualified helper location for error messages.
        - context: Formatted context suffix for error messages.
    Outputs:
        - Optional string value.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when the field exists with a non-string value.
    Ties to other methods:
        Used by parse_session_metadata.
    Why this exists:
        Small typed field helpers keep the session parser linear and easy to audit.
    """
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.{key} must be a string when present.{context}",
            )
        )
    return value


def _optional_int(
    raw: Mapping[str, object],
    *,
    key: str,
    error_location: str,
    context: str,
) -> int | None:
    """Validate an optional integer field inside session metadata.

    Summary:
        Return an optional integer value while enforcing its type when present.
    Inputs:
        - raw: Session metadata mapping.
        - key: Field name to validate.
        - error_location: Fully qualified helper location for error messages.
        - context: Formatted context suffix for error messages.
    Outputs:
        - Optional integer value.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when the field exists with a non-integer value.
    Ties to other methods:
        Used by parse_session_metadata.
    Why this exists:
        Numeric field validation should stay explicit and consistent across metadata keys.
    """
    value = raw.get(key)
    if value is not None and not isinstance(value, int):
        raise ValidationError(
            format_error_message(
                error_location,
                f"session.{key} must be an integer when present.{context}",
            )
        )
    return value


__all__ = ["parse_session_metadata"]
