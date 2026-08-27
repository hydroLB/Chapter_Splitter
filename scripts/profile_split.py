"""Profile PDF splitting and outline detection."""

from __future__ import annotations

import argparse
import cProfile
import pstats
from pathlib import Path

from pypdf import PdfWriter

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import CancellationToken, ChapterDefinition
from chapter_splitter.pdf.detection import detect_chapters_from_outlines
from chapter_splitter.pdf.splitting import split_pdf_into_chapters
from chapter_splitter.utils import Deadline


def main() -> int:
    """Run profiler for core PDF workflows."""
    parser = argparse.ArgumentParser(description="Profile chapter splitter hot paths.")
    parser.add_argument("--output", type=Path, default=Path("profiles/profile.pstats"))
    parser.add_argument("--pages", type=int, default=12)
    args = parser.parse_args()

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    settings = load_settings(None, "scripts.profile_split")
    pdf_path = _create_profile_pdf(Path("profiles/profile.pdf"), args.pages, ["One", "Two"])
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=4),
        ChapterDefinition(title="Two", start_page=5, end_page=8),
        ChapterDefinition(title="Three", start_page=9, end_page=args.pages),
    ]
    token = CancellationToken()

    profiler = cProfile.Profile()
    profiler.enable()

    deadline = Deadline(settings.io.operation_timeout_seconds)
    detect_chapters_from_outlines(
        pdf_path,
        deadline,
        token,
        settings.retry,
        settings.io,
        "scripts.profile_split",
        detection_config=settings.detection,
    )
    split_pdf_into_chapters(
        pdf_path=pdf_path,
        chapters=chapters,
        page_offset=None,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location="scripts.profile_split",
    )

    profiler.disable()
    profiler.dump_stats(str(output_path))
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative").print_stats(20)
    return 0


def _create_profile_pdf(path: Path, page_count: int, outline_titles: list[str]) -> Path:
    """Create a PDF file for profiling runs."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    for index, title in enumerate(outline_titles):
        page_index = min(index, page_count - 1)
        writer.add_outline_item(title=title, page_number=page_index)
    try:
        with path.open("wb") as handle:
            writer.write(handle)
    except OSError as exc:
        raise RuntimeError(f"scripts.profile_split._create_profile_pdf failed: {exc}") from exc
    return path


if __name__ == "__main__":
    raise SystemExit(main())
