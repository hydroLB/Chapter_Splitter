"""Data models that represent validated chapter splitting inputs and outputs."""

from __future__ import annotations

from pathlib import Path

from .errors import ValidationError, format_error_message


class PageRange:
    """Inclusive zero based page range for a PDF."""

    start_index: int
    end_index: int

    def __init__(self, start_index: int, end_index: int) -> None:
        """Initialize an inclusive zero based page range."""
        self.start_index = start_index
        self.end_index = end_index

    def validate(self, location: str) -> None:
        """Validate the page range values."""
        error_location = f"{__name__}.PageRange.validate"
        context = f" Context: {location}." if location else ""
        if self.start_index < 0 or self.end_index < 0:
            raise ValidationError(
                format_error_message(error_location, f"Page indices must be non negative.{context}")
            )
        if self.start_index > self.end_index:
            raise ValidationError(
                format_error_message(
                    error_location, f"Start index must not exceed end index.{context}"
                )
            )


class ChapterDefinition:
    """User facing chapter definition using one based page numbers."""

    title: str
    start_page: int
    end_page: int

    def __init__(self, title: str, start_page: int, end_page: int) -> None:
        """Initialize a chapter definition."""
        self.title = title
        self.start_page = start_page
        self.end_page = end_page

    def validate(self, location: str) -> None:
        """Validate the chapter definition values."""
        error_location = f"{__name__}.ChapterDefinition.validate"
        context = f" Context: {location}." if location else ""
        if not self.title.strip():
            raise ValidationError(
                format_error_message(error_location, f"Chapter title must be non empty.{context}")
            )
        if self.start_page < 1 or self.end_page < 1:
            raise ValidationError(
                format_error_message(
                    error_location,
                    f"Page numbers must start at 1 or higher.{context}",
                )
            )
        if self.start_page > self.end_page:
            raise ValidationError(
                format_error_message(
                    error_location, f"Start page must not exceed end page.{context}"
                )
            )

    def to_page_range(self, page_offset: int, location: str) -> PageRange:
        """Convert to a zero based page range for PDF indexing."""
        error_location = f"{__name__}.ChapterDefinition.to_page_range"
        start_index = self.start_page + page_offset - 1
        end_index = self.end_page + page_offset - 1
        page_range = PageRange(start_index=start_index, end_index=end_index)
        page_range.validate(error_location)
        return page_range


class ChapterOutput:
    """Result metadata for a single chapter export."""

    chapter: ChapterDefinition
    output_path: Path

    def __init__(self, chapter: ChapterDefinition, output_path: Path) -> None:
        """Initialize a chapter output record."""
        self.chapter = chapter
        self.output_path = output_path
