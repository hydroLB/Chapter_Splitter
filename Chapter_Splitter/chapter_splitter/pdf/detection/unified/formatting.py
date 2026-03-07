"""Formatting helpers for unified chapter detection."""

from __future__ import annotations

from ..report import ChapterDetectionReport


def format_detection_report(report: ChapterDetectionReport) -> str:
    """Format a ChapterDetectionReport for display in a dialog.

    Summary:
        Produce a concise, human-readable description of strategy, chapter count, confidence, and
        warnings.
    Inputs:
        - report: Detection report to format.
    Outputs:
        - Multi-line string suitable for message boxes.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by GUI and CLI boundaries after detect_chapters_in_reader completes.
    Why this exists:
        Keeping formatting centralized avoids UI-specific string logic scattered across callbacks.
    """
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
