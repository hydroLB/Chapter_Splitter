"""Performance benchmarks for chapter splitter hot paths."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from tests.shared.pdf_factory import create_sample_pdf

from chapter_splitter.config.loader import load_settings
from chapter_splitter.config.schema import IOConfig
from chapter_splitter.core import CancellationToken, ChapterDefinition
from chapter_splitter.pdf.detection import detect_chapters_from_outlines
from chapter_splitter.pdf.splitting import split_pdf_into_chapters
from chapter_splitter.utils import Deadline

BASELINE_PATH = Path("benchmarks/baseline.json")


def test_split_performance_budget(tmp_path: Path) -> None:
    """Verify split performance stays within the baseline budget.

    Purpose:
        Guard against performance regressions in chapter splitting.
    Ties To:
        Covers chapter_splitter.pdf.splitting.splitter.split_pdf_into_chapters.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes output files during benchmark execution.
    Raises:
        - AssertionError: When the benchmark exceeds the baseline.
    """
    settings = load_settings(None, "tests.performance.test_benchmarks")
    pdf_path = create_sample_pdf(tmp_path / "bench.pdf", page_count=12, outline_titles=None)
    chapters = [
        ChapterDefinition(title="One", start_page=1, end_page=4),
        ChapterDefinition(title="Two", start_page=5, end_page=8),
        ChapterDefinition(title="Three", start_page=9, end_page=12),
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

    def _run_once() -> None:
        """Run a single split benchmark iteration.

        Purpose:
            Execute the split operation once and record elapsed time.
        Ties To:
            Used by test_split_performance_budget.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Writes and deletes output files.
        Raises:
            - None.
        """
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
            location="tests.performance.test_benchmarks",
        )
        end = time.perf_counter()
        for output in outputs:
            output.output_path.unlink(missing_ok=True)
        output_dir = pdf_path.parent / f"{pdf_path.stem}{io_config.output_dir_suffix}"
        if output_dir.exists():
            for item in output_dir.iterdir():
                item.unlink(missing_ok=True)
            output_dir.rmdir()
        _record_timing(end - start)

    timings: list[float] = []

    def _record_timing(value: float) -> None:
        """Record a timing measurement.

        Purpose:
            Append a timing value to the local timings list.
        Ties To:
            Used by test_split_performance_budget.
        Inputs:
            - value: Timing value in seconds.
        Outputs:
            - None.
        Side Effects:
            Appends to the timings list.
        Raises:
            - None.
        """
        timings.append(value)

    for _ in range(settings.performance.benchmark_iterations):
        _run_once()

    median_time = statistics.median(timings)
    baseline = _load_baseline(BASELINE_PATH)
    budget = baseline["split_chapters_seconds"]
    assert median_time <= budget * 2
    assert median_time <= settings.performance.benchmark_budget_seconds


def test_outline_detection_performance_budget(tmp_path: Path) -> None:
    """Verify outline detection performance stays within baseline budget.

    Purpose:
        Guard against regressions in outline detection.
    Ties To:
        Covers chapter_splitter.pdf.detection.outlines.detect_chapters_from_outlines.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - None.
    Side Effects:
        Reads the PDF file during benchmark execution.
    Raises:
        - AssertionError: When the benchmark exceeds the baseline.
    """
    settings = load_settings(None, "tests.performance.test_benchmarks")
    pdf_path = create_sample_pdf(
        tmp_path / "outlined.pdf",
        page_count=10,
        outline_titles=["One", "Two", "Three"],
    )
    token = CancellationToken()
    timings: list[float] = []

    for _ in range(settings.performance.benchmark_iterations):
        deadline = Deadline(settings.io.operation_timeout_seconds)
        start = time.perf_counter()
        detect_chapters_from_outlines(
            pdf_path,
            deadline,
            token,
            settings.retry,
            settings.io,
            "tests.performance.test_benchmarks",
            detection_config=settings.detection,
        )
        end = time.perf_counter()
        timings.append(end - start)

    median_time = statistics.median(timings)
    baseline = _load_baseline(BASELINE_PATH)
    budget = baseline["outline_detection_seconds"]
    assert median_time <= budget * 2
    assert median_time <= settings.performance.benchmark_budget_seconds


def _load_baseline(path: Path) -> dict[str, float]:
    """Load benchmark baseline values from disk.

    Purpose:
        Provide benchmark baselines for performance tests.
    Ties To:
        Used by performance tests in this module.
    Inputs:
        - path: Path to the baseline JSON file.
    Outputs:
        - Mapping of baseline metrics to float values.
    Side Effects:
        Reads the baseline JSON file from disk.
    Raises:
        - RuntimeError: When the baseline file cannot be read.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"tests.performance.test_benchmarks._load_baseline failed: {exc}"
        ) from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(
            "tests.performance.test_benchmarks._load_baseline requires a JSON object"
        )
    return {key: float(value) for key, value in data.items()}
