# pdf_chapter_splitter.py
"""
PDF Chapter Splitter
====================
A small GUI tool that splits a single PDF into chapter-level PDFs.

Table of Contents
-----------------
1. Imports & Constants
2. Configuration & Unified Logging
3. Utility Functions
4. Core PDF Logic
5. GUI Helpers / Workflow
6. Main Entrypoint
"""

# --- 1. START IMPORTS & CONSTANTS ----------------------------------------------- #
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple, Optional
import os
import sys

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing required dependency 'pypdf'. Install with: pip install pypdf"
    ) from exc

APP_TITLE: str = "PDF Chapter Splitter"
DEFAULT_LOG_FILE: Path = Path(__file__).with_suffix(".log")


#
# --- 1. END IMPORTS & CONSTANTS ----------------------------------------------- #
#


#
# --- 2. START CONFIGURATION & UNIFIED LOGGING ----------------------------------- #
#
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


#
# --- 2. END CONFIGURATION & UNIFIED LOGGING ----------------------------------- #
#

#
# --- 3. START UTILITY FUNCTIONS -------------------------------------------------- #
#
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


#
# --- 3. END UTILITY FUNCTIONS -------------------------------------------------- #
#


#
# --- 4. START CORE PDF LOGIC ----------------------------------------------------- #
#

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


# --- Auto-detect chapters from PDF outline/bookmarks
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


class ChapterGridFrame(tk.Frame):
    def _update_row(self, idx):
        """Remove any widgets in the row idx and redraw it using _render_row."""
        base_col, grid_row = self._grid_position(idx)
        # Remove all widgets in this grid row (across this column group)
        for widget in self.grid_slaves(row=grid_row):
            widget.grid_forget()
            widget.destroy()
        self._render_row(idx, self.rows[idx])
    def _reindex_placeholders(self):
        """Ensure placeholders exist for all None rows, and only for those."""
        new_ph = {}
        for i, row in enumerate(self.rows):
            if row is None:
                # If placeholder already had values, keep them; else make blank
                old = self.placeholders.get(i, (["", "", ""], i))
                new_ph[i] = old
        self.placeholders = new_ph

    def __init__(self, parent, prefill_chapters: List[Tuple[int, int]] | None = None,
                 page_labels: Optional[list] = None):
        super().__init__(parent)
        self.rows = []
        self.placeholders = {}  # {idx: (values, idx)} for undo placeholders
        self.max_row_count = 1  # Track the highest visible row ever
        self.page_labels = page_labels
        # Make window never resizable
        if hasattr(self.master, "resizable"):
            self.master.resizable(False, False)
        self.build_grid()
        # Make all logical grid columns stretch evenly so that placeholder
        # buttons and normal rows always occupy the full available width.
        if prefill_chapters:
            self.prefill(prefill_chapters)

    def prefill(
            self,
            chapters: List[Tuple[str, int, int]] | List[Tuple[int, int]] | None,
    ) -> None:
        """Replace the grid contents with *chapters*.

        Accepts either:
        - [(title, start, end), ...]  from auto‑detection
        - [(start, end), ...]         legacy manual lists
        """
        # Clear existing rows and widgets
        for idx in range(len(self.rows) - 1, -1, -1):
            if len(self.rows) <= 1:
                break
            self.remove_row(idx)

        self.placeholders.clear()
        for row in self.rows:
            if row is not None:
                for w in row:
                    w.grid_forget()
                    w.destroy()
        self.rows.clear()

        # Re‑populate
        for item in (chapters or []):
            if len(item) == 3:
                title, start, end = item
            else:
                title = ""
                start, end = item
            self.add_row(title=title, start_val=str(start), end_val=str(end))

        self.refresh_grid()
        self._maybe_resize()

    def _maybe_resize(self) -> None:
        """Jump the window height all at once after 9 chapters;\
         after 15, 30, and 45, expand only horizontally (not vertically)."""
        if hasattr(self.master, "geometry"):
            base_height = 420  # for up to 9 chapters in one column
            visible_rows = len([row for row in self.rows if row is not None])
            self.max_row_count = max(getattr(self, "max_row_count", 1), visible_rows)
            col1_rows = min(self.max_row_count, 15)
            per_row = 36
            # Height jumps once when the 10th chapter is added, stays fixed through 15
            if col1_rows <= 8:
                height = base_height
            else:
                height = base_height + per_row * 2 + 4 * per_row
            if self.max_row_count <= 15:
                width = 410  # 1 column
            elif self.max_row_count <= 30:
                width = 700  # 2 columns
            elif self.max_row_count <= 45:
                width = 1025  # 3 columns
            else:
                width = 1360  # 4 columns
            self.master.geometry(f"{width}x{height}")

    def add_row(self, insert_idx=None, title="", start_val="", end_val=""):
        """Always adds at the end unless insert_idx is specified (only for undo)."""
        # Enforce maximum of 60 rows (including placeholders)
        if len(self.rows) >= 60:
            return  # Max 60 chapters
        widgets = self._make_row_widgets(title, start_val, end_val)
        if insert_idx is None:
            self.rows.append(widgets)
        else:
            idx = min(insert_idx, len(self.rows))
            self.rows.insert(idx, widgets)
        self._maybe_resize()
        self.refresh_grid()
        return widgets

    def remove_row(self, idx):
        row = self.rows[idx]
        values = [row[0].get(), row[1].get(), row[2].get()]  # title, start, end
        for w in row:
            w.grid_forget()
            w.destroy()
        # Store undo info as placeholder and replace row with None
        self.placeholders[idx] = (values, idx)
        self.rows[idx] = None
        self._reindex_placeholders()
        self.refresh_grid()

    def undo_remove(self, values, idx):
        title, start_val, end_val = values
        widgets = self._make_row_widgets(title, start_val, end_val)
        # Replace placeholder with widgets
        self.rows[idx] = widgets
        # Remove placeholder
        if idx in self.placeholders:
            del self.placeholders[idx]
        self._reindex_placeholders()
        self.refresh_grid()
        self._maybe_resize()

    def _make_row_widgets(self, title, start_val, end_val):
        e_title = ttk.Entry(self, width=8)
        e_start = ttk.Entry(self, width=8)
        e_end = ttk.Entry(self, width=8)
        if title:
            e_title.insert(0, title)
        if start_val:
            e_start.insert(0, start_val)
        if end_val:
            e_end.insert(0, end_val)
        btn_remove = ttk.Button(self, text="–", width=2)
        return e_title, e_start, e_end, btn_remove

    def build_grid(self):
        if self.page_labels:
            label_text = (
                "Use the page numbers shown on each PDF page \n(Also seen in your viewer's sidebar)."
            )
        else:
            label_text = (
                "Use the overall PDF file's page numbers \n(As shown at the top, e.g., Page 12 of 200)."
            )
        label = ttk.Label(self, text=label_text, font=("Arial", 10, "italic"))
        label.grid(row=0, column=0, columnspan=5, padx=4, pady=(4, 2), sticky="w")
        headers = ["Chapter Title", "Start Page", "End Page", "", ""]
        for c, h in enumerate(headers):
            ttk.Label(self, text=h, font=("Arial", 10, "bold")).grid(row=1, column=c, padx=4, pady=2)
        self.add_row()

    @staticmethod
    def _grid_position(idx: int) -> tuple[int, int]:
        # Each column displays up to 15 chapter rows.
        base_col = (idx // 15) * 5  # 0, 5, 10, 15 for columns 1‑4
        grid_row = (idx % 15) + 2  # rows start at grid row 2
        return base_col, grid_row

    def _clear_undo_buttons(self) -> None:
        """Remove any Undo buttons currently present in the grid."""
        for widget in self.grid_slaves():
            info = widget.grid_info()
            r = int(info.get("row", -1))
            c = int(info.get("column", -1))
            if (
                    r >= 2
                    and c % 5 == 0  # first column of each 5‑column chapter group
                    and isinstance(widget, ttk.Button)
                    and widget.cget("text") == "Undo"
            ):
                widget.destroy()

    def refresh_grid(self):
        """Render all chapter rows (or placeholders) and align them in a two-column grid."""
        self._clear_undo_buttons()
        for outer_i, row in enumerate(self.rows):
            self._render_row(outer_i, row)

    def _render_row(self, idx, row):
        base_col, grid_row = self._grid_position(idx)

        # Placeholder → Undo button
        if row is None and idx in self.placeholders:
            values, placeholder_idx = self.placeholders[idx]

            def do_undo(vals=values, undo_idx=placeholder_idx):
                self.undo_remove(vals, undo_idx)

            ttk.Button(self, text="Undo", command=do_undo).grid(
                row=grid_row,
                column=base_col,
                columnspan=5,
                padx=2,
                pady=2,
                sticky="ew",
            )
            self.grid_columnconfigure(base_col, weight=1)
            return

        # Normal row
        e_title, e_start, e_end, btn_remove = row
        if not e_title.get().strip():
            e_title.insert(0, f"Chapter {idx + 1}")

        e_title.grid(row=grid_row, column=base_col, sticky="w", padx=2, pady=2)
        e_start.grid(row=grid_row, column=base_col + 1, padx=2, pady=2)
        e_end.grid(row=grid_row, column=base_col + 2, padx=2, pady=2)
        ttk.Label(self, text="").grid(row=grid_row, column=base_col + 3)
        btn_remove.config(command=lambda remove_idx=idx: self.remove_row(remove_idx))
        btn_remove.grid(row=grid_row, column=base_col + 4, padx=2, pady=2)

    def get_chapters(self):
        chapters = []
        for i, row in enumerate(self.rows):
            if row is None:
                continue
            e_title, e_start, e_end, _btn = row
            try:
                title = e_title.get().strip()
                if not title:
                    title = f"Chapter {i + 1}"
                if self.page_labels:
                    start_label = e_start.get().strip()
                    end_label = e_end.get().strip()
                    start = self.page_labels.index(start_label) + 1 if start_label in self.page_labels else None
                    end = self.page_labels.index(end_label) + 1 if end_label in self.page_labels else None
                else:
                    start = int(e_start.get())
                    end = int(e_end.get())
                if start and end and start > 0 and end > 0 and start <= end:
                    chapters.append((title, start, end))
            except Exception:
                continue
        return chapters


#
# --- 4. END CORE PDF LOGIC ----------------------------------------------------- #
#

#
# --- 5. GUI HELPERS / WORKFLOW ------------------------------------------- #
#
def choose_pdf_file() -> Optional[Path]:
    """Prompt the user to select a PDF and return its Path, or *None* if cancelled."""
    pdf_path_str = filedialog.askopenfilename(
        title="Select PDF to Split",
        filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
    )
    return Path(pdf_path_str) if pdf_path_str else None


def extract_page_labels(reader: PdfReader):
    """Return the PDFs page labels if they exist, else *None*."""
    try:
        labels = reader.page_labels
        return labels if labels else None
    except Exception:
        return None


def build_chapter_window(
        root: tk.Tk, page_labels, do_auto_detect
) -> Tuple[tk.Toplevel, "ChapterGridFrame"]:
    """Create and configure the chapter-definition window and return it plus its grid frame."""
    chapter_win = tk.Toplevel(root)
    chapter_win.title("Define Chapters")
    chapter_win.geometry("420x504+900+100")
    chapter_win.resizable(False, False)

    grid_frame = ChapterGridFrame(
        chapter_win, prefill_chapters=None, page_labels=page_labels
    )
    grid_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # --- Place Add Chapter and Auto Detect side by side ---
    btn_row = ttk.Frame(chapter_win)
    btn_row.pack(pady=2)
    ttk.Button(btn_row, text="+ Add Chapter", command=grid_frame.add_row).pack(side="left", padx=(0, 8))
    ttk.Button(btn_row, text="Auto Detect Chapters", command=do_auto_detect).pack(side="left")
    return chapter_win, grid_frame


def workflow() -> None:
    """Main GUI workflow orchestrating PDF selection, chapter definition, and export."""
    root = tk.Tk()
    root.withdraw()

    pdf_path = choose_pdf_file()
    if not pdf_path:
        return

    reader = PdfReader(str(pdf_path))
    page_labels = extract_page_labels(reader)

    open_in_default_viewer(pdf_path)

    def do_auto_detect():
        """Use PDF outline metadata to populate chapter ranges automatically."""
        try:
            auto_chapters = detect_chapters_from_outlines(pdf_path)
        except Exception as err:
            logger.exception("Auto detect failed: %s", err)
            messagebox.showerror("Error", str(err))
            return

        # If the PDF has page‑label metadata, convert raw page numbers to the
        # sidebar labels so the grid reflects what users actually see.
        if page_labels:
            mapped = []
            for title, start, end in auto_chapters:
                try:
                    start_label = page_labels[start - 1]
                    end_label = page_labels[end - 1]
                except IndexError:
                    # Fall back to numeric strings if something is off
                    start_label, end_label = str(start), str(end)
                mapped.append((title, start_label, end_label))
            auto_chapters = mapped

        if not auto_chapters:
            messagebox.showinfo(
                "No Chapters Found",
                "This PDF does not appear to contain outline/bookmark metadata "
                "that can be used to detect chapters automatically.",
            )
            return

        grid_frame.prefill(auto_chapters)

    chapter_win, grid_frame = build_chapter_window(root, page_labels, do_auto_detect)

    def do_export():
        chapters = grid_frame.get_chapters()
        if not chapters:
            messagebox.showerror(
                "No Chapters", "Define at least one valid chapter range."
            )
            return
        try:
            outputs = split_pdf_into_chapters(pdf_path, chapters, 0)
        except Exception as err:
            logger.exception("Splitting failed: %s", err)
            messagebox.showerror("Error", str(err))
            return
        messagebox.showinfo(
            "Success",
            f"Created {len(outputs)} chapter file(s) in:\n{pdf_path.parent}",
        )
        chapter_win.destroy()
        root.destroy()

    ttk.Button(chapter_win, text="Export Chapters", command=do_export).pack(pady=10)

    root.mainloop()


#
# --- 5. END GUI HELPERS / WORKFLOW ------------------------------------------- #
#

#
# --- 6. START MAIN ENTRYPOINT ---------------------------------------------------- #
#
def main() -> None:
    """Initialize logging and start GUI workflow."""
    setup_logging()
    logger.info("%s started", APP_TITLE)

    try:
        workflow()
    except Exception as err:  # pragma: no cover
        logger.exception("Unhandled exception: %s", err)
        messagebox.showerror("Fatal Error", str(err))
    finally:
        logger.info("%s terminated", APP_TITLE)


if __name__ == "__main__":
    main()
#
# --- 6. END MAIN ENTRYPOINT ---------------------------------------------------- #
#
