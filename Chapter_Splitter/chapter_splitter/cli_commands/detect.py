"""Detect command execution logic."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from ..config.schema import Settings
from ..core.errors import CancellationError, ChapterSplitterError, format_error_message
from ..core.models import ChapterDefinition
from ..core.runtime import CancellationToken
from ..io.chapters import write_chapter_file
from ..pdf.detection.detector import DetectionRequest, detect_chapters
from ..pdf.detection.report import ChapterDetectionStrategy
from ..utils.timing import Deadline


class _DetectionReport(Protocol):
    strategy: str
    confidence: float
    chapters: list[ChapterDefinition]
    warnings: list[str]


def run_detect(
    *,
    pdf_path: Path,
    out_path: Path | None,
    strategy: str | None,
    toc_hint_page: int | None,
    overwrite: bool,
    settings: Settings,
    token: CancellationToken,
    location: str,
    logger: logging.Logger,
    detect_chapters_fn: Callable[..., object] = detect_chapters,
    write_chapter_file_fn: Callable[..., None] = write_chapter_file,
    log_event_fn: Callable[..., None] | None = None,
) -> int:
    """Execute the detect command workflow."""
    error_location = "chapter_splitter.cli._run_detect"
    context = f" Context: {location}." if location else ""
    if token.is_cancelled():
        raise CancellationError(
            format_error_message(error_location, f"Detect cancelled before start.{context}")
        )
    if strategy is None:
        raise ChapterSplitterError(
            format_error_message(error_location, f"Detect requires a strategy.{context}")
        )
    if strategy not in ("auto", "outlines", "toc"):
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"Unsupported detect strategy: {strategy}.{context}",
            )
        )
    if strategy == "toc" and toc_hint_page is None:
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"--toc-hint-page is required when --strategy toc.{context}",
            )
        )

    effective_out = out_path or pdf_path.with_suffix(".chapters.toml")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    force_strategy: ChapterDetectionStrategy | None = None
    if strategy != "auto":
        force_strategy = cast(ChapterDetectionStrategy, strategy)
    request = DetectionRequest(
        toc_hint_page=toc_hint_page,
        force_strategy=force_strategy,
    )
    report = cast(
        _DetectionReport,
        detect_chapters_fn(
            pdf_path=pdf_path,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            io_config=settings.io,
            detection_config=settings.detection,
            request=request,
            location=location,
        ),
    )
    write_chapter_file_fn(
        effective_out,
        report.chapters,
        report=report,
        overwrite=overwrite,
        deadline=deadline,
        token=token,
        location=location,
    )
    if log_event_fn is not None:
        log_event_fn(
            logger,
            logging.INFO,
            "detect_complete",
            "Chapter detection complete.",
            {
                "strategy": report.strategy,
                "confidence": report.confidence,
                "chapter_count": len(report.chapters),
                "output_path": str(effective_out),
                "warnings": list(report.warnings),
            },
        )
    return 0
