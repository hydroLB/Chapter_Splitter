"""Data models that represent validated chapter splitting inputs and outputs."""

from __future__ import annotations

from pathlib import Path

from .errors import ValidationError, format_error_message


class PageRange:
    """Inclusive zero based page range for a PDF.

    Summary:
        Represent a validated, inclusive range of PDF page indices.
    Ties to other methods:
        Created by ChapterDefinition and consumed by PDF splitting logic.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    start_index: int
    end_index: int

    def __init__(self, start_index: int, end_index: int) -> None:
        """Initialize an inclusive zero based page range.

        Summary:
            Store zero based page indices for downstream PDF slicing.
        Ties to other methods:
            Created by ChapterDefinition.to_page_range and consumed by split logic.
        Inputs:
            - start_index: First page index, zero based.
            - end_index: Last page index, zero based.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.start_index = start_index
        self.end_index = end_index

    def validate(self, location: str) -> None:
        """Validate the page range values.

        Summary:
            Ensure the calculated PDF indices are valid before use.
        Ties to other methods:
            Used by ChapterDefinition.to_page_range and the splitting pipeline.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ValidationError: When the range is invalid.
        """
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
    """User facing chapter definition using one based page numbers.

    Summary:
        Capture chapter titles and page boundaries from user input.
    Ties to other methods:
        Used by UI, CLI parsing, validation, and chapter splitting.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    title: str
    start_page: int
    end_page: int

    def __init__(self, title: str, start_page: int, end_page: int) -> None:
        """Initialize a chapter definition.

        Summary:
            Capture a chapter title and its one based page boundaries.
        Ties to other methods:
            Used by validation, UI grid extraction, and CLI parsing.
        Inputs:
            - title: Chapter label shown in filenames and logs.
            - start_page: First page number, one based.
            - end_page: Last page number, one based.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.title = title
        self.start_page = start_page
        self.end_page = end_page

    def validate(self, location: str) -> None:
        """Validate the chapter definition values.

        Summary:
            Ensure chapter title and page boundaries are sane before processing.
        Ties to other methods:
            Used by validation routines and split execution.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ValidationError: When title or page numbers are invalid.
        """
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
        """Convert to a zero based page range for PDF indexing.

        Summary:
            Translate human page numbers into zero based PDF indices.
        Ties to other methods:
            Consumed by the PDF splitter when iterating pages.
        Inputs:
            - page_offset: Offset used to align labeled pages to PDF indices.
            - location: Fully qualified module and method name.
        Outputs:
            - PageRange with inclusive zero based indices.
        Side effects:
            None.
        Error handling:
            - ValidationError: When the calculated range is invalid.
        """
        error_location = f"{__name__}.ChapterDefinition.to_page_range"
        start_index = self.start_page + page_offset - 1
        end_index = self.end_page + page_offset - 1
        page_range = PageRange(start_index=start_index, end_index=end_index)
        page_range.validate(error_location)
        return page_range


class ChapterOutput:
    """Result metadata for a single chapter export.

    Summary:
        Bundle a chapter definition with the exported output path.
    Ties to other methods:
        Returned by the splitter for UI and CLI output.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    chapter: ChapterDefinition
    output_path: Path

    def __init__(self, chapter: ChapterDefinition, output_path: Path) -> None:
        """Initialize a chapter output record.

        Summary:
            Bundle the chapter metadata with its exported file path.
        Ties to other methods:
            Returned by the splitter to the UI and CLI layers.
        Inputs:
            - chapter: Chapter definition that was exported.
            - output_path: Path to the exported PDF file.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.chapter = chapter
        self.output_path = output_path
