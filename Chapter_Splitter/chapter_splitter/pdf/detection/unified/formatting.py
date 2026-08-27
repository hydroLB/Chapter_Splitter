"""Formatting helpers for unified chapter detection."""

from __future__ import annotations

from ..report import ChapterDetectionReport


def format_detection_report(report: ChapterDetectionReport) -> str:
    """Format a ChapterDetectionReport for display in a dialog."""
    percent = int(round(max(0.0, min(1.0, report.confidence)) * 100))
    base = (
        f"Detected {len(report.chapters)} chapters via {report.strategy} ({percent}% confidence)."
    )
    if report.strategy == "toc" and report.toc_start_page is not None:
        base = (
            f"Detected {len(report.chapters)} chapters via toc starting at page "
            f"{report.toc_start_page} ({percent}% confidence)."
        )
    if not report.warnings:
        return base
    return base + "\n\nWarnings:\n- " + "\n- ".join(report.warnings)


__all__ = ["format_detection_report"]
