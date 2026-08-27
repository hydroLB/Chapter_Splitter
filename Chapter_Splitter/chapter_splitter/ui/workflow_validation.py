"""Pure validation policies shared by desktop workflow widgets and actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config.schema import ValidationConfig
from ..core.errors import ValidationError, format_error_message
from ..core.models import ChapterDefinition
from ..core.validation import validate_chapters, validate_page_range
from ..io.chapters import ChapterFileSessionMetadata


@dataclass(frozen=True, slots=True)
class SessionImportPreflight:
    """Describe the user confirmation required after a safe session import preflight."""

    recorded_pdf_path: str | None
    pdf_path_mismatch: bool


def preflight_session_import(
    *,
    metadata: ChapterFileSessionMetadata | None,
    chapters: list[ChapterDefinition],
    current_pdf_path: Path,
    total_pages: int,
    location: str,
) -> SessionImportPreflight:
    """Validate imported ranges and identify session-to-document path mismatches.

    Page-count mismatches are unsafe because the chapter map cannot describe the currently loaded
    document reliably. A different recorded path is less definitive because a PDF may have been
    moved, so callers receive a confirmation requirement instead of a hard failure.
    """
    error_location = f"{__name__}.preflight_session_import"
    if (
        metadata is not None
        and metadata.total_pages is not None
        and metadata.total_pages != total_pages
    ):
        raise ValidationError(
            format_error_message(
                error_location,
                "Chapter session page count does not match the loaded PDF: "
                f"session has {metadata.total_pages}, loaded PDF has {total_pages} pages. "
                "Open the PDF used to create this session or import a matching chapter file.",
            )
        )

    validate_chapter_ranges_for_document(
        chapters=chapters,
        total_pages=total_pages,
        location=location,
    )

    recorded_pdf_path = metadata.pdf_path if metadata is not None else None
    has_recorded_path = bool(recorded_pdf_path and recorded_pdf_path.strip())
    path_mismatch = bool(
        has_recorded_path and not _paths_match(Path(recorded_pdf_path or ""), current_pdf_path)
    )
    return SessionImportPreflight(
        recorded_pdf_path=recorded_pdf_path,
        pdf_path_mismatch=path_mismatch,
    )


def validate_chapter_ranges_for_document(
    *,
    chapters: list[ChapterDefinition],
    total_pages: int,
    location: str,
) -> None:
    """Validate every chapter range against a document before replacing visible UI state."""
    for chapter in chapters:
        validate_page_range(
            start_page=chapter.start_page,
            end_page=chapter.end_page,
            total_pages=total_pages,
            location=location,
        )


def export_readiness_errors(
    *,
    chapters: list[ChapterDefinition],
    total_pages: int,
    validation_config: ValidationConfig,
    location: str,
) -> list[str]:
    """Return the first core validation failure that would block an export."""
    try:
        validate_chapters(
            chapters=chapters,
            total_pages=total_pages,
            max_chapters=validation_config.max_chapters,
            require_unique_titles=validation_config.require_unique_titles,
            sort_chapters_by_start_page=validation_config.sort_chapters_by_start_page,
            reject_overlapping_ranges=validation_config.reject_overlapping_ranges,
            location=location,
        )
    except ValidationError as exc:
        return [_user_facing_validation_detail(exc)]
    return []


def _paths_match(recorded_pdf_path: Path, current_pdf_path: Path) -> bool:
    """Return whether recorded and current PDF paths resolve to the same filesystem path."""
    try:
        return recorded_pdf_path.expanduser().resolve(
            strict=False
        ) == current_pdf_path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return recorded_pdf_path == current_pdf_path


def _user_facing_validation_detail(exc: ValidationError) -> str:
    """Remove internal location framing from a core validation error shown in the GUI."""
    message = str(exc)
    _prefix, separator, detail = message.partition(" failed. ")
    if separator:
        message = detail
    context_index = message.rfind(" Context: ")
    if context_index >= 0:
        message = message[:context_index]
    return message.strip()


__all__ = [
    "SessionImportPreflight",
    "export_readiness_errors",
    "preflight_session_import",
    "validate_chapter_ranges_for_document",
]
