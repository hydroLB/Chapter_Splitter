"""Window builder for the chapter definition UI."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from tkinter.font import Font

from ....config.schema import UIConfig
from ....core.errors import UiError, format_error_message
from ....core.runtime import CancellationToken
from ..widgets.chapter_grid import ChapterGridFrame
from ..widgets.chapter_review import ChapterReviewFrame
from ..widgets.pdf_preview.frame import PdfPreviewFrame


@dataclass(frozen=True, slots=True)
class ChapterWindowComponents:
    """References to the main chapter window widgets.

    Purpose:
        Provide structured access to the chapter window and its primary controls.
    Ties To:
        Returned by build_chapter_window and used by the Tk workflow to wire callbacks.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    window: tk.Toplevel
    grid: ChapterGridFrame
    open_pdf_button: ttk.Button
    add_button: ttk.Button
    auto_detect_button: ttk.Button
    export_button: ttk.Button
    close_button: ttk.Button
    status_label: ttk.Label | None
    pdf_preview: PdfPreviewFrame | None
    chapter_review: ChapterReviewFrame | None
    right_notebook: ttk.Notebook | None
    review_tab: ttk.Frame | None


def build_chapter_window(
    root: tk.Tk,
    pdf_path: Path,
    total_pages: int,
    page_labels: list[str] | None,
    do_auto_detect: Callable[[], None],
    token: CancellationToken,
    ui_config: UIConfig,
    location: str,
) -> ChapterWindowComponents:
    """Build the chapter definition window.

    Purpose:
        Create the main chapter entry window, grid widget, and primary action buttons.
    Ties To:
        Used by the Tkinter workflow when a PDF is selected.
    Inputs:
        - root: Tk root instance.
        - pdf_path: Selected PDF path displayed in the header.
        - total_pages: Total page count displayed in the header.
        - page_labels: Optional page labels from the PDF.
        - do_auto_detect: Callback for auto detect button.
        - ui_config: UI configuration.
        - location: Fully qualified module and method name.
    Outputs:
        - ChapterWindowComponents containing widget references.
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
    if not isinstance(pdf_path, Path):
        raise UiError(format_error_message(error_location, f"pdf_path must be a Path.{context}"))
    if total_pages <= 0:
        raise UiError(
            format_error_message(error_location, f"total_pages must be positive.{context}")
        )
    try:
        chapter_win = tk.Toplevel(root)
        chapter_win.title(ui_config.chapter_window_title)
        chapter_win.geometry(
            f"{ui_config.window_width}x{ui_config.window_height}+"
            f"{ui_config.window_offset_x}+{ui_config.window_offset_y}"
        )
        chapter_win.minsize(900 if ui_config.enable_pdf_preview else 520, 520)
        chapter_win.resizable(True, True)
        chapter_win.columnconfigure(0, weight=1)
        chapter_win.rowconfigure(1, weight=1)

        info_frame = ttk.Frame(chapter_win)
        info_frame.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=ui_config.grid_frame_padding_x,
            pady=(ui_config.grid_frame_padding_y, 0),
        )
        info_frame.columnconfigure(0, weight=1)

        title_font = Font(info_frame)
        title_font.configure(weight="bold")

        pdf_name_label = ttk.Label(
            info_frame,
            text=pdf_path.name,
            justify="left",
            font=title_font,
        )
        pdf_name_label.grid(row=0, column=0, sticky="w")

        pages_label = ttk.Label(info_frame, text=f"{total_pages} pages", justify="left")
        pages_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        path_label = ttk.Label(
            info_frame,
            text=str(pdf_path),
            justify="left",
            wraplength=ui_config.pdf_info_wraplength,
        )
        path_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        def _update_wrap(_event: tk.Event[tk.Misc]) -> None:
            """Update the wrap length of the path label when the window resizes.

            Purpose:
                Keep the PDF path readable by wrapping to the available width.
            Ties To:
                Bound to the header frame <Configure> event.
            Inputs:
                - _event: Tkinter configure event.
            Outputs:
                - None.
            Side Effects:
                Updates the label wrap length.
            Raises:
                - None.
            """
            available = max(200, info_frame.winfo_width() - 140)
            path_label.configure(wraplength=available)

        info_frame.bind("<Configure>", _update_wrap)

        open_pdf_button = ttk.Button(info_frame, text=ui_config.open_pdf_button_label)
        open_pdf_button.grid(row=0, column=1, rowspan=3, sticky="ne", padx=(12, 0))

        pdf_preview: PdfPreviewFrame | None = None
        chapter_review: ChapterReviewFrame | None = None
        right_notebook: ttk.Notebook | None = None
        review_tab: ttk.Frame | None = None

        main_container: tk.Misc = chapter_win
        if ui_config.enable_pdf_preview:
            main_pane = ttk.PanedWindow(chapter_win, orient="horizontal")
            main_pane.grid(
                row=1,
                column=0,
                sticky="nsew",
                padx=ui_config.grid_frame_padding_x,
                pady=ui_config.grid_frame_padding_y,
            )
            pdf_preview = PdfPreviewFrame(
                main_pane,
                pdf_path=pdf_path,
                total_pages=total_pages,
                ui_config=ui_config,
                token=token,
                location=location,
            )
            main_container = main_pane
            main_pane.add(pdf_preview, weight=1)

        right_container = ttk.Frame(main_container)
        right_container.columnconfigure(0, weight=1)
        right_container.rowconfigure(0, weight=1)

        right_notebook = ttk.Notebook(right_container)
        chapters_tab = ttk.Frame(right_notebook)
        review_tab = ttk.Frame(right_notebook)
        right_notebook.add(chapters_tab, text="Chapters")
        right_notebook.add(review_tab, text="Review")
        right_notebook.grid(row=0, column=0, sticky="nsew")

        grid_frame = ChapterGridFrame(
            chapters_tab,
            prefill_chapters=None,
            page_labels=page_labels,
            ui_config=ui_config,
        )
        grid_frame.pack(fill="both", expand=True)

        chapter_review = ChapterReviewFrame(
            review_tab,
            pdf_path=pdf_path,
            total_pages=total_pages,
            ui_config=ui_config,
            token=token,
            location=location,
        )
        chapter_review.pack(fill="both", expand=True)

        if isinstance(main_container, ttk.PanedWindow):
            main_container.add(right_container, weight=2)
        else:
            right_container.grid(
                row=1,
                column=0,
                sticky="nsew",
                padx=ui_config.grid_frame_padding_x,
                pady=ui_config.grid_frame_padding_y,
            )

        btn_row = ttk.Frame(chapter_win)
        btn_row.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=ui_config.grid_frame_padding_x,
            pady=(ui_config.button_row_padding, ui_config.export_button_padding),
        )

        left_actions = ttk.Frame(btn_row)
        left_actions.pack(side="left")
        right_actions = ttk.Frame(btn_row)
        right_actions.pack(side="right")

        add_button = ttk.Button(
            left_actions,
            text=ui_config.add_button_label,
            command=grid_frame.add_row,
        )
        add_button.pack(side="left", padx=(0, ui_config.button_gap_padding))

        auto_detect_button = ttk.Button(
            left_actions,
            text=ui_config.auto_detect_button_label,
            command=do_auto_detect,
        )
        auto_detect_button.pack(side="left")

        export_button = ttk.Button(right_actions, text=ui_config.export_button_label)
        export_button.pack(side="left", padx=(0, ui_config.button_gap_padding))

        close_button = ttk.Button(right_actions, text=ui_config.close_button_label)
        close_button.pack(side="left")

        status_label: ttk.Label | None = None
        if ui_config.show_status_bar:
            status_label = ttk.Label(
                chapter_win,
                text=ui_config.status_hint,
                anchor="w",
            )
            status_label.grid(
                row=3,
                column=0,
                sticky="ew",
                padx=ui_config.grid_frame_padding_x,
                pady=(0, ui_config.grid_frame_padding_y),
            )
    except tk.TclError as exc:
        raise UiError(
            format_error_message(error_location, f"Unable to build chapter window: {exc}.{context}")
        ) from exc

    return ChapterWindowComponents(
        window=chapter_win,
        grid=grid_frame,
        open_pdf_button=open_pdf_button,
        add_button=add_button,
        auto_detect_button=auto_detect_button,
        export_button=export_button,
        close_button=close_button,
        status_label=status_label,
        pdf_preview=pdf_preview,
        chapter_review=chapter_review,
        right_notebook=right_notebook,
        review_tab=review_tab,
    )
