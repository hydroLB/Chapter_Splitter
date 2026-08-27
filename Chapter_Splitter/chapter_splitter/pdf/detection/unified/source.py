"""Source-loading entrypoint for unified chapter detection."""

from __future__ import annotations

from pathlib import Path

from ....config.schema import DetectionConfig, IOConfig, RetryConfig
from ....core.runtime import CancellationToken
from ....utils.timing import Deadline
from ...io.loader import get_total_pages, load_reader
from ..report import ChapterDetectionReport
from .request import DetectionRequest
from .service import detect_chapters_in_reader


def detect_chapters(
    pdf_path: Path,
    deadline: Deadline,
    token: CancellationToken,
    retry_config: RetryConfig,
    io_config: IOConfig,
    detection_config: DetectionConfig,
    request: DetectionRequest,
    location: str,
) -> ChapterDetectionReport:
    """Detect chapters using outlines first and TOC fallback when configured."""
    token.check(location)
    read_deadline = Deadline(io_config.pdf_read_timeout_seconds)
    reader = load_reader(pdf_path, read_deadline, token, retry_config, location)
    total_pages = get_total_pages(reader, location)
    deadline.check(location)
    return detect_chapters_in_reader(
        reader=reader,
        total_pages=total_pages,
        pdf_path=pdf_path,
        deadline=deadline,
        token=token,
        detection_config=detection_config,
        request=request,
        location=location,
    )


__all__ = ["detect_chapters"]
