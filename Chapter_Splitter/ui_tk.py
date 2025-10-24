#!/usr/bin/env python
"""
ui_tk.py – current Tkinter GUI layer
====================================
Every GUI-specific line lives in this file.  When you migrate to Flet,
replace *only* this module; `main.py` will not need to change.

Changes (2025-07-03):
    • Replaced “from main import …” with “import main as backend” to eliminate
      the circular import detected by Python.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pypdf import PdfReader

# ── import the back-end module *once*; we reference its names at runtime ──────
import splitter_core as backend

logger = logging.getLogger(__name__)


# ───────────────────────────── chapter-grid widget ─────────────────────────────
class ChapterGridFrame(tk.Frame):
    """
    A grid where each row defines (title, start page, end page).
    Supports adding/removing rows, “Undo”, and auto-prefill from PDF outlines.
    """

    # ══════════════════════ static helpers ══════════════════════
    @staticmethod
    def _grid_position(idx: int) -> tuple[int, int]:
        """
        Map logical index → (column, row) for the 5-column Tk grid.

        * Up to 15 logical rows per column
        * Header rows occupy grid-rows 0 and 1
        """
        base_col = (idx // 15) * 5            # 0, 5, 10, 15 …
        grid_row = (idx % 15) + 2             # +2 for headers
        return base_col, grid_row

    # ══════════════════════ object lifecycle ════════════════════
    def __init__(
        self,
        parent,
        prefill_chapters: List[Tuple[int, int]] | None = None,
        page_labels: Optional[list] = None,
    ):
        super().__init__(parent)

        self.rows: list[Optional[tuple]] = []
        self.placeholders: dict[int, tuple] = {}
        self.max_row_count = 1
        self.page_labels = page_labels

        if hasattr(self.master, "resizable"):
            self.master.resizable(False, False)

        self.build_grid()
        if prefill_chapters:
            self.prefill(prefill_chapters)

    # ══════════════════════ high-level API ══════════════════════
    def add_row(self, insert_idx=None, title="", start_val="", end_val=""):
        """Append (or insert) a new editable row; max 60 rows."""
        if len(self.rows) >= 60:
            return
        widgets = self._make_row_widgets(title, start_val, end_val)
        if insert_idx is None:
            self.rows.append(widgets)
        else:
            self.rows.insert(min(insert_idx, len(self.rows)), widgets)
        self._maybe_resize()
        self.refresh_grid()
        return widgets

    def remove_row(self, idx):
        """Remove row at *idx* and leave an “Undo” placeholder."""
        row = self.rows[idx]
        values = [row[0].get(), row[1].get(), row[2].get()]  # title, start, end
        for w in row:
            w.grid_forget()
            w.destroy()
        self.placeholders[idx] = (values, idx)
        self.rows[idx] = None
        self._reindex_placeholders()
        self.refresh_grid()

    def undo_remove(self, values, idx):
        """Re-insert a row that was previously removed."""
        title, start_val, end_val = values
        widgets = self._make_row_widgets(title, start_val, end_val)
        self.rows[idx] = widgets
        self.placeholders.pop(idx, None)
        self._reindex_placeholders()
        self.refresh_grid()
        self._maybe_resize()

    def get_chapters(self) -> List[Tuple[str, int, int]]:
        """Collect (title, start, end) tuples from all valid rows."""
        chapters: List[Tuple[str, int, int]] = []
        for i, row in enumerate(self.rows):
            if row is None:
                continue
            e_title, e_start, e_end, _btn = row
            try:
                title = e_title.get().strip() or f"Chapter {i + 1}"
                if self.page_labels:                       # using label strings
                    start_label = e_start.get().strip()
                    end_label = e_end.get().strip()
                    start = (
                        self.page_labels.index(start_label) + 1
                        if start_label in self.page_labels
                        else None
                    )
                    end = (
                        self.page_labels.index(end_label) + 1
                        if end_label in self.page_labels
                        else None
                    )
                else:
                    start = int(e_start.get())
                    end = int(e_end.get())
                if start and end and start <= end:
                    chapters.append((title, start, end))
            except Exception:
                continue
        return chapters

    def prefill(
        self,
        chapters: List[Tuple[str, int, int]] | List[Tuple[int, int]] | None,
    ) -> None:
        """Replace entire grid contents with *chapters* (used by Auto-Detect)."""
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

        for item in (chapters or []):
            if len(item) == 3:
                title, start, end = item
            else:
                title = ""
                start, end = item
            self.add_row(title=title, start_val=str(start), end_val=str(end))

        self.refresh_grid()
        self._maybe_resize()

    # ══════════════════════ internal helpers ════════════════════
    def _reindex_placeholders(self):
        self.placeholders = {
            i: self.placeholders.get(i, (["", "", ""], i))
            for i, row in enumerate(self.rows)
            if row is None
        }

    def _maybe_resize(self):
        """Resize window in jumps for nicer UX."""
        if not hasattr(self.master, "geometry"):
            return

        base_height = 420
        visible_rows = len([r for r in self.rows if r is not None])
        self.max_row_count = max(self.max_row_count, visible_rows)

        per_row = 36
        height = (
            base_height
            if self.max_row_count <= 8
            else base_height + per_row * 2 + 4 * per_row
        )

        if self.max_row_count <= 15:
            width = 410
        elif self.max_row_count <= 30:
            width = 700
        elif self.max_row_count <= 45:
            width = 1025
        else:
            width = 1360

        self.master.geometry(f"{width}x{height}")

    def _make_row_widgets(self, title, start_val, end_val):
        e_title = ttk.Entry(self, width=8)
        e_start = ttk.Entry(self, width=8)
        e_end   = ttk.Entry(self, width=8)
        if title:
            e_title.insert(0, title)
        if start_val:
            e_start.insert(0, start_val)
        if end_val:
            e_end.insert(0, end_val)
        btn_remove = ttk.Button(self, text="–", width=2)
        return e_title, e_start, e_end, btn_remove

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

        # Normal editable row
        e_title, e_start, e_end, btn_remove = row
        if not e_title.get().strip():
            e_title.insert(0, f"Chapter {idx + 1}")

        e_title.grid(row=grid_row, column=base_col, sticky="w", padx=2, pady=2)
        e_start.grid(row=grid_row, column=base_col + 1, padx=2, pady=2)
        e_end.grid(row=grid_row, column=base_col + 2, padx=2, pady=2)
        ttk.Label(self, text="").grid(row=grid_row, column=base_col + 3)

        btn_remove.config(command=lambda remove_idx=idx: self.remove_row(remove_idx))
        btn_remove.grid(row=grid_row, column=base_col + 4, padx=2, pady=2)

    def _clear_undo_buttons(self):
        for widget in self.grid_slaves():
            gi = widget.grid_info()
            if (
                int(gi.get("row", -1)) >= 2
                and int(gi.get("column", -1)) % 5 == 0
                and isinstance(widget, ttk.Button)
                and widget.cget("text") == "Undo"
            ):
                widget.destroy()

    def refresh_grid(self):
        self._clear_undo_buttons()
        for i, row in enumerate(self.rows):
            self._render_row(i, row)


# ───────────────────────────── helper functions ────────────────────────────────
def choose_pdf_file() -> Optional[Path]:
    pdf_path_str = filedialog.askopenfilename(
        title="Select PDF to Split",
        filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
    )
    return Path(pdf_path_str) if pdf_path_str else None


def extract_page_labels(reader: PdfReader):
    try:
        return reader.page_labels or None
    except Exception:
        return None


def build_chapter_window(
    root: tk.Tk,
    page_labels,
    do_auto_detect,
) -> Tuple[tk.Toplevel, ChapterGridFrame]:
    chapter_win = tk.Toplevel(root)
    chapter_win.title("Define Chapters")
    chapter_win.geometry("420x504+900+100")
    chapter_win.resizable(False, False)

    grid_frame = ChapterGridFrame(
        chapter_win, prefill_chapters=None, page_labels=page_labels
    )
    grid_frame.pack(fill="both", expand=True, padx=10, pady=10)

    btn_row = ttk.Frame(chapter_win)
    btn_row.pack(pady=2)
    ttk.Button(btn_row, text="+ Add Chapter", command=grid_frame.add_row).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(btn_row, text="Auto Detect Chapters", command=do_auto_detect).pack(
        side="left"
    )

    return chapter_win, grid_frame


# ───────────────────────────── top-level workflow ───────────────────────────────
def workflow() -> None:
    """GUI flow: pick PDF → define chapters → export."""
    root = tk.Tk()
    root.withdraw()

    pdf_path = choose_pdf_file()
    if not pdf_path:
        return

    reader = PdfReader(str(pdf_path))
    page_labels = extract_page_labels(reader)

    backend.open_in_default_viewer(pdf_path)

    # ----- nested helpers ------------------------------------------------------
    def do_auto_detect():
        try:
            auto = backend.detect_chapters_from_outlines(pdf_path)
        except Exception as err:
            logger.exception("Auto detect failed: %s", err)
            messagebox.showerror("Error", str(err))
            return

        if page_labels:
            mapped = []
            for title, start, end in auto:
                try:
                    start_lbl = page_labels[start - 1]
                    end_lbl   = page_labels[end   - 1]
                except IndexError:
                    start_lbl, end_lbl = str(start), str(end)
                mapped.append((title, start_lbl, end_lbl))
            auto = mapped

        if not auto:
            messagebox.showinfo(
                "No Chapters Found",
                "This PDF does not contain usable outline/bookmark metadata.",
            )
            return

        grid.prefill(auto)

    def do_export():
        chapters = grid.get_chapters()
        if not chapters:
            messagebox.showerror(
                "No Chapters", "Define at least one valid chapter range."
            )
            return
        try:
            outputs = backend.split_pdf_into_chapters(pdf_path, chapters, 0)
        except Exception as err:
            logger.exception("Splitting failed: %s", err)
            messagebox.showerror("Error", str(err))
            return
        messagebox.showinfo(
            "Success", f"Created {len(outputs)} chapter file(s) in:\n{pdf_path.parent}"
        )
        win.destroy()
        root.destroy()

    # ----- build window --------------------------------------------------------
    win, grid = build_chapter_window(root, page_labels, do_auto_detect)
    ttk.Button(win, text="Export Chapters", command=do_export).pack(pady=10)
    root.mainloop()