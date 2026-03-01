"""Split command execution logic."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

from ..config.schema import IOConfig, Settings
from ..config.schema.sections.io import OutputCollisionPolicy
from ..core.errors import CancellationError, ChapterSplitterError, format_error_message
from ..core.models import ChapterDefinition
from ..core.runtime import CancellationToken
from ..utils.timing import Deadline


class _SplitOutput(Protocol):
    output_path: Path


def run_split(
    *,
    pdf_path: Path,
    chapters_path: Path,
    output_dir: Path | None,
    collision_policy: str | None,
    page_offset: int | None,
    settings: Settings,
    token: CancellationToken,
    location: str,
    logger: logging.Logger,
    load_chapter_file_fn: Callable[
        [Path, Deadline, CancellationToken, str],
        list[ChapterDefinition],
    ],
    split_pdf_into_chapters_fn: Callable[..., Sequence[_SplitOutput]],
    log_event_fn: Callable[..., None],
) -> int:
    """Execute the split command workflow."""
    if token.is_cancelled():
        error_location = "chapter_splitter.cli._run_split"
        context = f" Context: {location}." if location else ""
        raise CancellationError(
            format_error_message(error_location, f"Split cancelled before start.{context}")
        )

    error_location = "chapter_splitter.cli._run_split"
    context = f" Context: {location}." if location else ""
    effective_page_offset = page_offset
    if effective_page_offset is not None and effective_page_offset < 0:
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"--page-offset must be non-negative (got {effective_page_offset}).{context}",
            )
        )
    effective_io = settings.io
    if collision_policy is not None:
        policy = cast(OutputCollisionPolicy, collision_policy)
        effective_io = IOConfig(
            open_viewer=settings.io.open_viewer,
            viewer_timeout_seconds=settings.io.viewer_timeout_seconds,
            pdf_read_timeout_seconds=settings.io.pdf_read_timeout_seconds,
            pdf_write_timeout_seconds=settings.io.pdf_write_timeout_seconds,
            operation_timeout_seconds=settings.io.operation_timeout_seconds,
            output_dir_suffix=settings.io.output_dir_suffix,
            output_collision_policy=policy,
            output_collision_max_suffix=settings.io.output_collision_max_suffix,
            fsync_writes=settings.io.fsync_writes,
            page_offset=settings.io.page_offset,
            infer_page_offset_from_labels=settings.io.infer_page_offset_from_labels,
            infer_page_offset_min_sequential_numeric_labels=(
                settings.io.infer_page_offset_min_sequential_numeric_labels
            ),
        )

    chapter_deadline = Deadline(settings.io.operation_timeout_seconds)
    chapter_defs: list[ChapterDefinition] = load_chapter_file_fn(
        chapters_path,
        chapter_deadline,
        token,
        location,
    )
    split_deadline = Deadline(settings.io.operation_timeout_seconds)
    outputs = split_pdf_into_chapters_fn(
        pdf_path=pdf_path,
        chapters=chapter_defs,
        page_offset=effective_page_offset,
        deadline=split_deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=effective_io,
        location=location,
        output_dir=output_dir,
    )
    output_dir_str = str(outputs[0].output_path.parent) if outputs else str(pdf_path.parent)
    log_event_fn(
        logger,
        logging.INFO,
        "split_complete",
        "Chapter export complete.",
        {"output_count": len(outputs), "output_dir": output_dir_str},
    )
    return 0
