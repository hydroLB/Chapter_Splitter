"""Public PDF splitting API facade."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from ...config.schema import IOConfig, RetryConfig, ValidationConfig
from ...core.models import ChapterDefinition, ChapterOutput
from ...core.runtime import CancellationToken
from ...utils.timing import Deadline
from ..io.dependencies import PdfWriter
from .engine import chapter_export as _chapter_export
from .engine import export as _export_engine
from .engine.models import ChapterExportProgress


def split_pdf_into_chapters(
    pdf_path: Path,
    chapters: list[ChapterDefinition],
    page_offset: int | None,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    validation_config: ValidationConfig,
    io_config: IOConfig,
    location: str,
    output_dir: Path | None = None,
    *,
    on_progress: Callable[[ChapterExportProgress], None] | None = None,
) -> list[ChapterOutput]:
    """Split a PDF into chapter files.

    Summary:
        Preserve the historical splitter module seam while delegating implementation to the
        internal engine package.
    Inputs:
        - pdf_path: Path to the source PDF.
        - chapters: List of ChapterDefinition objects.
        - page_offset: Optional offset applied when converting to zero-based indices.
        - deadline: Deadline tracker for timeout enforcement.
        - token: Cancellation token for graceful shutdown.
        - retry_config: Retry policy for PDF loading.
        - validation_config: Validation rules for chapters.
        - io_config: IO configuration for output behavior.
        - location: Fully qualified module and method name.
        - output_dir: Optional output directory override.
        - on_progress: Optional progress callback receiving per-chapter start and complete events.
    Outputs:
        - List of ChapterOutput objects with exported paths.
    Side effects:
        Delegates to the internal export engine and synchronizes monkeypatchable module state.
    Error handling:
        Propagates export validation, IO, and PDF processing errors from the internal engine.
    Ties to other methods:
        Delegates to chapter_splitter.pdf.splitting.engine.export.split_pdf_into_chapters.
    Why this exists:
        Existing callers and tests import and monkeypatch this module directly, so the facade must
        preserve that compatibility seam.
    """
    export_engine = cast(Any, _export_engine)
    export_engine.PdfWriter = PdfWriter
    chapter_export = cast(Any, _chapter_export)
    chapter_export.PdfWriter = PdfWriter
    return _export_engine.split_pdf_into_chapters(
        pdf_path=pdf_path,
        chapters=chapters,
        page_offset=page_offset,
        deadline=deadline,
        token=token,
        retry_config=retry_config,
        validation_config=validation_config,
        io_config=io_config,
        location=location,
        output_dir=output_dir,
        on_progress=on_progress,
    )


__all__ = ["ChapterExportProgress", "split_pdf_into_chapters"]
