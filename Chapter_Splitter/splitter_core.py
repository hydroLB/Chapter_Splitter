"""
splitter_core.py
================
Core logic for **PDF Chapter Splitter**.

This module is *completely GUI-agnostic*.  It provides:
    • unified logging setup
    • utility helpers (file-safe names, page-range validation, etc.)
    • pure functions to split a PDF into chapter files
    • outline/bookmark introspection to auto-detect chapters
    • a thin `main()` that boots whichever GUI layer is imported
      (Tkinter today, Flet tomorrow).

Replace the GUI front-end and the rest of this module keeps on ticking.
"""

# --- 1. START IMPORTS & CONSTANTS ----------------------------------------------- #
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple
import os
import sys

# --- UI LAYER IMPORT (Tkinter today, Flet tomorrow) ---

try:
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing required dependency 'pypdf'. Install with: pip install pypdf"
    ) from exc

APP_TITLE: str = "PDF Chapter Splitter"
DEFAULT_LOG_FILE: Path = Path(__file__).with_suffix(".log")


def setup_logging(log_path: Path = DEFAULT_LOG_FILE) -> None:
    """Configure and enable unified logging for the entire application.

    Args:
        log_path: Destination file for DEBUG-level logs.
    """
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Silence overly noisy libraries
    for noisy in ("pypdf", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


def open_in_default_viewer(pdf_path: Path):
    """Open the PDF in the system's default PDF viewer."""
    try:
        if sys.platform.startswith("darwin"):
            os.system(f'open "{pdf_path}"')
        elif os.name == "nt":
            os.startfile(str(pdf_path))
        else:
            # Assume Linux/Unix
            os.system(f'xdg-open "{pdf_path}"')
    except Exception as e:
        logger.error("Could not open PDF in default viewer: %s", e)


def validate_page_range(
        start: int, end: int, total_pages: int
) -> Tuple[int, int]:  # noqa: D401
    """Validate and normalize a [start, end] page range.

    Raises:
        ValueError: If the range is invalid.
    """
    logger.debug("Validating page range: %s-%s (total=%s)", start, end, total_pages)

    if start < 1 or end < 1:
        raise ValueError("Page numbers must be positive integers (starting at 1)")
    if start > end:
        raise ValueError("Start page cannot exceed end page")
    if end > total_pages:
        raise ValueError(
            f"End page {end} exceeds PDF length ({total_pages} pages)"
        )
    return start, end


def safe_filename(name: str) -> str:  # noqa: D401
    """Sanitize *name* so it can be used as a filename on all major OS."""
    invalid_chars = r"<>:\"/|?*"
    sanitized = "".join("_" if c in invalid_chars else c for c in name).strip()
    return sanitized or "untitled"


def split_pdf_into_chapters(
        pdf_path: Path,
        chapters: List[Tuple[str, int, int]],
        page_offset: int = 0,
) -> List[Path]:
    """Split *pdf_path* into PDF files described in *chapters*.

    Args:
        pdf_path: Source PDF to split.
        chapters: List of tuples (chapter_title, start_page, end_page) using PDF page numbers.
        page_offset: Offset to convert page numbering to zero-based PDF indices such that
                      pdf_index = (page + page_offset) - 1.

    Returns:
        List of paths to newly created chapter PDFs.
    """
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    logger.info("Loaded '%s' (%s pages)", pdf_path.name, total_pages)

    output_paths: List[Path] = []

    output_dir = pdf_path.parent / f"{pdf_path.stem}_chapters"
    output_dir.mkdir(exist_ok=True)

    for title, start, end in chapters:
        try:
            start, end = validate_page_range(start, end, total_pages)
        except ValueError as err:
            logger.error("Skipping chapter '%s': %s", title, err)
            continue

        # Convert pages to zero-based PDF indices.
        pdf_start_idx = start + page_offset - 1
        pdf_end_idx = end + page_offset - 1

        writer = PdfWriter()
        for page_idx in range(pdf_start_idx, pdf_end_idx + 1):
            writer.add_page(reader.pages[page_idx])

        out_path = output_dir / f"{safe_filename(title)}.pdf"
        with out_path.open("wb") as fp:
            writer.write(fp)

        logger.info(
            "Created chapter '%s' (pages %s-%s) → %s",
            title,
            start,
            end,
            out_path.name,
        )
        output_paths.append(out_path)

    return output_paths


def detect_chapters_from_outlines(pdf_path: Path) -> List[Tuple[str, int, int]]:
    """
    Inspect the PDF’s outline/bookmarks and return logical chapter ranges.

    Each top‑level outline item is treated as a chapter start.  The chapter’s
    end page is one page before the next outline item begins, or the final page
    of the document for the last entry.

    Returns
    -------
    list[(title, start_page, end_page)]
        Page numbers are 1‑based.  An empty list means no suitable outline was
        found.
    """
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    # `pypdf` exposes outlines slightly differently across versions
    try:
        outlines = reader.outline if hasattr(reader, "outline") else reader.outlines
    except Exception:
        try:
            outlines = reader.get_outlines()
        except Exception:
            outlines = []

    if not outlines:
        return []

    chapters: List[Tuple[str, int]] = []

    def _walk(items, depth: int = 0):
        for item in items:
            # Nested sub‑lists represent lower‑level headings
            if isinstance(item, list):
                _walk(item, depth + 1)
                continue
            # Only consider depth‑0 items as chapters
            if depth != 0:
                continue
            try:
                page_num = reader.get_destination_page_number(item) + 1  # to 1‑based
                title_walk = getattr(item, "title", f"Chapter {len(chapters) + 1}")
                chapters.append((title_walk, page_num))
            except Exception:
                continue

    _walk(outlines)

    if not chapters:
        return []

    chapters.sort(key=lambda t: t[1])

    ranges: List[Tuple[str, int, int]] = []
    for idx, (title, start) in enumerate(chapters):
        end = chapters[idx + 1][1] - 1 if idx + 1 < len(chapters) else total_pages
        ranges.append((title, start, end))

    return ranges


def main() -> None:
    """Initialize logging and start GUI workflow."""
    setup_logging()
    logger.info("%s started", APP_TITLE)
    try:
        from ui_tk import main as gui_workflow
        gui_workflow()
    except Exception as err:  # pragma: no cover
        logger.exception("Unhandled exception: %s", err)
    finally:
        logger.info("%s terminated", APP_TITLE)


if __name__ == "__main__":
    import ui_tk
    ui_tk.run()  # Or whatever starts the GUI
