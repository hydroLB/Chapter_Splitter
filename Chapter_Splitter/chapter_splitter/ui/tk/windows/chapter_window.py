"""Window builder for the chapter definition UI."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ....config.schema import UIConfig
from ....core.errors import UiError, format_error_message
from ..widgets.chapter_grid import ChapterGridFrame


def build_chapter_window(
    root: tk.Tk,
    page_labels: list[str] | None,
    do_auto_detect: Callable[[], None],
    ui_config: UIConfig,
    location: str,
) -> tuple[tk.Toplevel, ChapterGridFrame]:
    """Build the chapter definition window.

    Purpose:
        Create the main chapter entry window and grid widget.
    Ties To:
        Used by the Tkinter workflow when a PDF is selected.
    Inputs:
        - root: Tk root instance.
        - page_labels: Optional page labels from the PDF.
        - do_auto_detect: Callback for auto detect button.
        - ui_config: UI configuration.
        - location: Fully qualified module and method name.
    Outputs:
        - Tuple of the window and the chapter grid frame.
    Side Effects:
        Creates Tkinter widgets.
    Raises:
        - UiError: When window creation fails.
    """
    error_location = f"{__name__}.build_chapter_window"
    context = f" Context: {location}." if location else ""
    if not callable(do_auto_detect):
        raise UiError(
            format_error_message(error_location, f"Auto detect callback must be callable.{context}")
        )
    try:
        chapter_win = tk.Toplevel(root)
        chapter_win.title(ui_config.chapter_window_title)
        chapter_win.geometry(
            f"{ui_config.window_width}x{ui_config.window_height}+"
            f"{ui_config.window_offset_x}+{ui_config.window_offset_y}"
        )
        chapter_win.resizable(False, False)

        grid_frame = ChapterGridFrame(
            chapter_win,
            prefill_chapters=None,
            page_labels=page_labels,
            ui_config=ui_config,
        )
        grid_frame.pack(
            fill="both",
            expand=True,
            padx=ui_config.grid_frame_padding_x,
            pady=ui_config.grid_frame_padding_y,
        )

        btn_row = ttk.Frame(chapter_win)
        btn_row.pack(pady=ui_config.button_row_padding)
        ttk.Button(
            btn_row,
            text=ui_config.add_button_label,
            command=grid_frame.add_row,
        ).pack(side="left", padx=(0, ui_config.button_gap_padding))
        ttk.Button(
            btn_row,
            text=ui_config.auto_detect_button_label,
            command=do_auto_detect,
        ).pack(side="left")
    except tk.TclError as exc:
        raise UiError(
            format_error_message(error_location, f"Unable to build chapter window: {exc}.{context}")
        ) from exc

    return chapter_win, grid_frame
