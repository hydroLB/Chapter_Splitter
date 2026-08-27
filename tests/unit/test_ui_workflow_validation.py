"""Unit tests for pure desktop workflow validation policies."""

from __future__ import annotations

from pathlib import Path

import pytest

from chapter_splitter.config.schema import ValidationConfig
from chapter_splitter.core import ChapterDefinition, ValidationError
from chapter_splitter.io import ChapterFileSessionMetadata
from chapter_splitter.ui import (
    export_readiness_errors,
    preflight_session_import,
)


def _validation_config(*, max_chapters: int = 10) -> ValidationConfig:
    """Return the strict export policy used by desktop workflow tests."""
    return ValidationConfig(
        max_chapters=max_chapters,
        require_unique_titles=True,
        sort_chapters_by_start_page=True,
        reject_overlapping_ranges=True,
    )


def _session(*, pdf_path: str, total_pages: int) -> ChapterFileSessionMetadata:
    """Return session metadata with only document identity fields populated."""
    return ChapterFileSessionMetadata(
        pdf_path=pdf_path,
        total_pages=total_pages,
        saved_at=None,
        source="test",
    )


def test_session_preflight_blocks_total_page_mismatch(tmp_path: Path) -> None:
    """Reject a chapter session created for a document with a different page count."""
    current_pdf = tmp_path / "current.pdf"
    with pytest.raises(ValidationError, match="session has 12, loaded PDF has 10"):
        preflight_session_import(
            metadata=_session(pdf_path=str(current_pdf), total_pages=12),
            chapters=[ChapterDefinition("One", 1, 2)],
            current_pdf_path=current_pdf,
            total_pages=10,
            location="tests.unit.test_ui_workflow_validation",
        )


def test_session_preflight_requires_confirmation_for_different_pdf_path(
    tmp_path: Path,
) -> None:
    """Flag a differing recorded path while allowing the GUI to request confirmation."""
    result = preflight_session_import(
        metadata=_session(pdf_path=str(tmp_path / "recorded.pdf"), total_pages=10),
        chapters=[ChapterDefinition("One", 1, 2)],
        current_pdf_path=tmp_path / "current.pdf",
        total_pages=10,
        location="tests.unit.test_ui_workflow_validation",
    )

    assert result.pdf_path_mismatch is True
    assert result.recorded_pdf_path == str(tmp_path / "recorded.pdf")


def test_session_preflight_accepts_equivalent_resolved_paths(tmp_path: Path) -> None:
    """Avoid prompting when syntactically different paths resolve to the same PDF."""
    current_pdf = tmp_path / "current.pdf"
    recorded_pdf = tmp_path / "nested" / ".." / "current.pdf"

    result = preflight_session_import(
        metadata=_session(pdf_path=str(recorded_pdf), total_pages=10),
        chapters=[ChapterDefinition("One", 1, 2)],
        current_pdf_path=current_pdf,
        total_pages=10,
        location="tests.unit.test_ui_workflow_validation",
    )

    assert result.pdf_path_mismatch is False


def test_session_preflight_rejects_out_of_document_range(tmp_path: Path) -> None:
    """Reject imported ranges before a widget can replace its existing chapter rows."""
    with pytest.raises(ValidationError, match="exceeds total pages 10"):
        preflight_session_import(
            metadata=None,
            chapters=[ChapterDefinition("One", 1, 11)],
            current_pdf_path=tmp_path / "current.pdf",
            total_pages=10,
            location="tests.unit.test_ui_workflow_validation",
        )


def test_export_readiness_uses_max_chapter_policy() -> None:
    """Keep the export button disabled when the configured chapter cap is exceeded."""
    errors = export_readiness_errors(
        chapters=[
            ChapterDefinition("One", 1, 1),
            ChapterDefinition("Two", 2, 2),
        ],
        total_pages=10,
        validation_config=_validation_config(max_chapters=1),
        location="tests.unit.test_ui_workflow_validation",
    )

    assert errors == ["Chapter count 2 exceeds max 1."]


def test_export_readiness_uses_unique_title_policy() -> None:
    """Surface duplicate titles in review state before the user starts an export."""
    errors = export_readiness_errors(
        chapters=[
            ChapterDefinition("Same", 1, 1),
            ChapterDefinition("Same", 2, 2),
        ],
        total_pages=10,
        validation_config=_validation_config(),
        location="tests.unit.test_ui_workflow_validation",
    )

    assert errors == ["Duplicate chapter title detected: Same."]


def test_export_readiness_uses_overlap_policy() -> None:
    """Surface overlapping ranges in review state before the user starts an export."""
    errors = export_readiness_errors(
        chapters=[
            ChapterDefinition("One", 1, 4),
            ChapterDefinition("Two", 4, 6),
        ],
        total_pages=10,
        validation_config=_validation_config(),
        location="tests.unit.test_ui_workflow_validation",
    )

    assert errors == [
        "Chapter page ranges must not overlap. 'One' ends at page 4 but 'Two' starts at page 4."
    ]


def test_export_readiness_accepts_valid_chapters() -> None:
    """Return no review errors when the same core policy would allow export."""
    errors = export_readiness_errors(
        chapters=[
            ChapterDefinition("One", 1, 3),
            ChapterDefinition("Two", 4, 6),
        ],
        total_pages=10,
        validation_config=_validation_config(),
        location="tests.unit.test_ui_workflow_validation",
    )

    assert errors == []
