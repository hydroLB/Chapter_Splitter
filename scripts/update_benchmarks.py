"""Update benchmark baseline values."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from pypdf import PdfWriter

from chapter_splitter.config.loader import load_settings
from chapter_splitter.config.schema import IOConfig
from chapter_splitter.core import CancellationToken, ChapterDefinition
from chapter_splitter.pdf.detection import detect_chapters_from_outlines
from chapter_splitter.pdf.splitting import split_pdf_into_chapters
from chapter_splitter.utils import Deadline


def main() -> int:
    """Measure performance and write the baseline JSON file."""
    parser = argparse.ArgumentParser(description="Update benchmark baselines.")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/baseline.json"))
    parser.add_argument("--pages", type=int, default=12)
    args = parser.parse_args()

    settings = load_settings(None, "scripts.update_benchmarks")
    pdf_path = _create_benchmark_pdf(Path("benchmarks/bench.pdf"), args.pages)
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=4),
        ChapterDefinition(title="Two", start_page=5, end_page=8),
        ChapterDefinition(title="Three", start_page=9, end_page=args.pages),
    ]
    io_config = IOConfig(
        open_viewer=settings.io.open_viewer,
        viewer_timeout_seconds=settings.io.viewer_timeout_seconds,
        pdf_read_timeout_seconds=settings.io.pdf_read_timeout_seconds,
        pdf_write_timeout_seconds=settings.io.pdf_write_timeout_seconds,
        operation_timeout_seconds=settings.io.operation_timeout_seconds,
        output_dir_suffix=settings.io.output_dir_suffix,
        output_collision_policy="overwrite",
        output_collision_max_suffix=settings.io.output_collision_max_suffix,
        fsync_writes=settings.io.fsync_writes,
        page_offset=settings.io.page_offset,
        infer_page_offset_from_labels=settings.io.infer_page_offset_from_labels,
        infer_page_offset_min_sequential_numeric_labels=(
            settings.io.infer_page_offset_min_sequential_numeric_labels
        ),
    )
    token = CancellationToken()

    split_timings: list[float] = []
    detect_timings: list[float] = []

    for _ in range(settings.performance.benchmark_iterations):
        deadline = Deadline(settings.io.operation_timeout_seconds)
        start = time.perf_counter()
        outputs = split_pdf_into_chapters(
            pdf_path=pdf_path,
            chapters=chapters,
            page_offset=None,
            deadline=deadline,
            token=token,
            retry_config=settings.retry,
            validation_config=settings.validation,
            io_config=io_config,
            location="scripts.update_benchmarks",
        )
        end = time.perf_counter()
        split_timings.append(end - start)
        for output in outputs:
            output.output_path.unlink(missing_ok=True)
        output_dir = pdf_path.parent / f"{pdf_path.stem}{io_config.output_dir_suffix}"
        if output_dir.exists():
            for item in output_dir.iterdir():
                item.unlink(missing_ok=True)
            output_dir.rmdir()

        deadline = Deadline(settings.io.operation_timeout_seconds)
        start = time.perf_counter()
        detect_chapters_from_outlines(
            pdf_path,
            deadline,
            token,
            settings.retry,
            settings.io,
            "scripts.update_benchmarks",
            detection_config=settings.detection,
        )
        end = time.perf_counter()
        detect_timings.append(end - start)

    baseline = {
        "split_chapters_seconds": statistics.median(split_timings),
        "outline_detection_seconds": statistics.median(detect_timings),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        args.output.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"scripts.update_benchmarks.main failed to write baseline: {exc}"
        ) from exc
    return 0


def _create_benchmark_pdf(path: Path, page_count: int) -> Path:
    """Create a PDF for benchmark runs."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    for index, title in enumerate(["One", "Two", "Three"]):
        page_index = min(index * 3, page_count - 1)
        writer.add_outline_item(title=title, page_number=page_index)
    try:
        with path.open("wb") as handle:
            writer.write(handle)
    except OSError as exc:
        raise RuntimeError(
            f"scripts.update_benchmarks._create_benchmark_pdf failed: {exc}"
        ) from exc
    return path


if __name__ == "__main__":
    raise SystemExit(main())
