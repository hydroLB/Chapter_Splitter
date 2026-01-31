"""PDF dependency imports with clear errors."""

from __future__ import annotations

from ...core.errors import ConfigurationError, format_error_message

try:
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:  # pragma: no cover
    raise ConfigurationError(
        format_error_message(
            "chapter_splitter.pdf.io.dependencies",
            "Missing required dependency 'pypdf'. Install with: pip install pypdf",
        )
    ) from exc

__all__ = ["PdfReader", "PdfWriter"]
