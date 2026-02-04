"""Embedded PDF preview panel with chapter marking controls."""

from __future__ import annotations

import logging
import tkinter as tk
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from .....config.schema import UIConfig
from .....core.errors import UiError, format_error_message
from .....core.runtime import CancellationToken
from .....utils.timing import Deadline
from .renderer import PdfPreviewRenderer, RenderedImage, is_preview_available

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PdfPreviewActions:
    """Callback wiring for chapter labeling actions.

    Summary:
        Provide a typed bundle of callbacks so the preview widget can trigger labeling operations.
    Inputs:
        - new_chapter_at_page: Start a new chapter at the given page.
        - set_start_at_page: Set the active chapter start to the given page.
        - set_end_at_page: Set the active chapter end to the given page.
        - detect_chapters_at_page: Run fallback chapter detection starting at the given page.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Stored and used by PdfPreviewFrame button handlers.
    Why this exists:
        Keeps the UI builder decoupled from workflow and grid internals.
    """

    new_chapter_at_page: Callable[[int], None]
    set_start_at_page: Callable[[int], None]
    set_end_at_page: Callable[[int], None]
    detect_chapters_at_page: Callable[[int], None]


class PdfPreviewFrame(tk.Frame):
    """Side panel that renders PDF pages and lets the user mark chapter boundaries.

    Summary:
        Display a navigable PDF page preview and expose buttons for chapter labeling actions.
    Inputs:
        - parent: Parent Tk widget.
        - pdf_path: PDF file path.
        - total_pages: Total pages in the document.
        - ui_config: UI configuration controlling preview behavior.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Creates Tk widgets and optionally opens a PDF renderer.
    Error handling:
        Degrades to an install message when PyMuPDF is unavailable.
    Ties to other methods:
        Wired by the workflow to apply edits to ChapterGridFrame.
    Why this exists:
        A visual labeling workflow reduces errors compared to typing page numbers.
    """

    def __init__(
        self,
        parent: tk.Misc,
        pdf_path: Path,
        total_pages: int,
        ui_config: UIConfig,
        token: CancellationToken,
        location: str,
    ) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._total_pages = total_pages
        self._ui_config = ui_config
        self._token = token
        self._location = location
        self._actions: PdfPreviewActions | None = None

        self._renderer = PdfPreviewRenderer()
        self._current_page = 1
        self._photo: tk.PhotoImage | None = None
        self._image_item: int | None = None

        # Cache by (page_number, zoom) -> PhotoImage.
        self._cache: OrderedDict[tuple[int, float], tk.PhotoImage] = OrderedDict()

        self._build()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def set_actions(self, actions: PdfPreviewActions) -> None:
        """Wire callbacks for chapter labeling operations.

        Summary:
            Register callbacks that apply page marks to the chapter grid.
        Inputs:
            - actions: PdfPreviewActions bundle.
        Outputs:
            - None.
        Side effects:
            Enables action buttons.
        Error handling:
            Raises UiError when actions are missing required callables.
        Ties to other methods:
            Used by the workflow after the window is built.
        Why this exists:
            The preview widget should not depend on grid internals.
        """
        error_location = f"{__name__}.PdfPreviewFrame.set_actions"
        if not callable(actions.new_chapter_at_page):
            raise UiError(
                format_error_message(
                    error_location, "new_chapter_at_page callback must be callable."
                )
            )
        if not callable(actions.set_start_at_page):
            raise UiError(
                format_error_message(error_location, "set_start_at_page callback must be callable.")
            )
        if not callable(actions.set_end_at_page):
            raise UiError(
                format_error_message(error_location, "set_end_at_page callback must be callable.")
            )
        if not callable(actions.detect_chapters_at_page):
            raise UiError(
                format_error_message(
                    error_location,
                    "detect_chapters_at_page callback must be callable.",
                )
            )
        self._actions = actions
        self._new_chapter_button.config(state="normal")
        self._set_start_button.config(state="normal")
        self._set_end_button.config(state="normal")
        self._detect_chapters_button.config(state="normal")

    def get_current_page(self) -> int:
        """Return the currently displayed page number.

        Summary:
            Provide page access for keyboard shortcut wiring and status messages.
        Inputs:
            - None.
        Outputs:
            - Current 1-based page number.
        Side effects:
            None.
        Error handling:
            None.
        Ties to other methods:
            Used by workflow keyboard bindings.
        Why this exists:
            Centralizes navigation state within the preview widget.
        """
        return self._current_page

    def go_to_page(self, page_number: int) -> None:
        """Navigate to a specific 1-based page number and render it.

        Summary:
            Update the preview display to the requested page, clamping to valid bounds.
        Inputs:
            - page_number: 1-based page number.
        Outputs:
            - None.
        Side effects:
            Renders and displays a new image.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Called by nav buttons and the page entry handler.
        Why this exists:
            The labeling workflow depends on reliable page navigation.
        """
        target = max(1, min(self._total_pages, int(page_number)))
        if target == self._current_page and self._photo is not None:
            return
        self._current_page = target
        self._page_var.set(str(target))
        self._page_count_label.config(text=f"/ {self._total_pages}")
        self._render_current_page()

    def next_page(self) -> None:
        """Navigate to the next page.

        Summary:
            Advance the preview by one page, clamped to the end of the document.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Renders a new page when applicable.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Called by the Next button and keyboard bindings.
        Why this exists:
            Fast navigation is essential for manual chapter labeling.
        """
        self.go_to_page(self._current_page + 1)

    def prev_page(self) -> None:
        """Navigate to the previous page.

        Summary:
            Move the preview back by one page, clamped to page 1.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Renders a new page when applicable.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Called by the Prev button and keyboard bindings.
        Why this exists:
            Manual labeling frequently requires stepping back to confirm boundaries.
        """
        self.go_to_page(self._current_page - 1)

    def _build(self) -> None:
        error_location = f"{__name__}.PdfPreviewFrame._build"
        context = f" Context: {self._location}." if self._location else ""
        if not isinstance(self._pdf_path, Path):
            raise UiError(
                format_error_message(error_location, f"pdf_path must be a Path.{context}")
            )
        if self._total_pages <= 0:
            raise UiError(
                format_error_message(error_location, f"total_pages must be positive.{context}")
            )

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Label(self, text="PDF Preview", anchor="w")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))

        nav = ttk.Frame(self)
        nav.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        nav.columnconfigure(6, weight=1)

        prev_btn = ttk.Button(nav, text="◀", width=3, command=self.prev_page)
        prev_btn.grid(row=0, column=0)
        next_btn = ttk.Button(nav, text="▶", width=3, command=self.next_page)
        next_btn.grid(row=0, column=1, padx=(4, 0))

        ttk.Label(nav, text="Page").grid(row=0, column=2, padx=(10, 4))
        self._page_var = tk.StringVar(value=str(self._current_page))
        self._page_entry = ttk.Entry(nav, width=6, textvariable=self._page_var)
        self._page_entry.grid(row=0, column=3)
        self._page_entry.bind("<Return>", lambda _event: self._on_page_entry())
        self._page_count_label = ttk.Label(nav, text=f"/ {self._total_pages}")
        self._page_count_label.grid(row=0, column=4, padx=(4, 0))

        go_btn = ttk.Button(nav, text="Go", command=self._on_page_entry)
        go_btn.grid(row=0, column=5, padx=(6, 0))

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", padx=8, pady=(6, 8))

        self._new_chapter_button = ttk.Button(
            actions,
            text="New Chapter Here",
            state="disabled",
            command=self._on_new_chapter_here,
        )
        self._new_chapter_button.pack(side="left")

        self._set_start_button = ttk.Button(
            actions,
            text="Set Start",
            state="disabled",
            command=self._on_set_start,
        )
        self._set_start_button.pack(side="left", padx=(8, 0))

        self._set_end_button = ttk.Button(
            actions,
            text="Set End",
            state="disabled",
            command=self._on_set_end,
        )
        self._set_end_button.pack(side="left", padx=(8, 0))

        self._detect_chapters_button = ttk.Button(
            actions,
            text="Detect Chapters Here",
            state="disabled",
            command=self._on_detect_chapters_here,
        )
        self._detect_chapters_button.pack(side="left", padx=(14, 0))

        # Canvas with scrollbars.
        container = ttk.Frame(self)
        container.grid(row=2, column=0, sticky="nsew", padx=8)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(container, highlightthickness=0, background="white")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=self._canvas.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self._canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        if not self._ui_config.enable_pdf_preview:
            self._show_message(
                "PDF preview disabled in config. Set ui.enable_pdf_preview = true to enable."
            )
            return

        if not is_preview_available():
            self._show_message("PDF preview requires PyMuPDF. Install with: pip install pymupdf")
            return

        try:
            self._renderer.open(self._pdf_path, self._token, self._location)
        except UiError as exc:
            self._show_message(str(exc))
            return

        self.go_to_page(1)

    def _show_message(self, message: str) -> None:
        self._canvas.delete("all")
        self._photo = None
        self._image_item = None
        self._canvas.configure(scrollregion=(0, 0, 1, 1))
        self._canvas.create_text(
            10,
            10,
            anchor="nw",
            text=message,
            width=max(220, self._canvas.winfo_width() - 20),
            fill="#444",
        )

    def _on_page_entry(self) -> None:
        error_location = f"{__name__}.PdfPreviewFrame._on_page_entry"
        context = f" Context: {self._location}." if self._location else ""
        raw = self._page_var.get().strip()
        if not raw:
            return
        try:
            page = int(raw)
        except ValueError as exc:
            raise UiError(
                format_error_message(error_location, f"Page must be an integer.{context}")
            ) from exc
        self.go_to_page(page)

    def _render_current_page(self) -> None:
        if not self._ui_config.enable_pdf_preview:
            return
        key = (self._current_page, float(self._ui_config.pdf_preview_zoom))
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            self._set_image(cached, cached.width(), cached.height())
            return

        deadline = Deadline(self._ui_config.pdf_preview_render_timeout_seconds)
        rendered: RenderedImage = self._renderer.render_page_png_base64(
            page_number=self._current_page,
            zoom=float(self._ui_config.pdf_preview_zoom),
            deadline=deadline,
            token=self._token,
            location=self._location,
        )
        photo = tk.PhotoImage(data=rendered.png_base64, format="png")
        self._cache[key] = photo
        self._cache.move_to_end(key)
        while len(self._cache) > self._ui_config.pdf_preview_cache_entries:
            self._cache.popitem(last=False)
        self._set_image(photo, rendered.width, rendered.height)

    def _set_image(self, photo: tk.PhotoImage, width: int, height: int) -> None:
        self._photo = photo
        self._canvas.delete("all")
        self._image_item = self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._canvas.configure(scrollregion=(0, 0, max(1, width), max(1, height)))

    def _on_new_chapter_here(self) -> None:
        if self._actions is None:
            return
        self._actions.new_chapter_at_page(self._current_page)

    def _on_set_start(self) -> None:
        if self._actions is None:
            return
        self._actions.set_start_at_page(self._current_page)

    def _on_set_end(self) -> None:
        if self._actions is None:
            return
        self._actions.set_end_at_page(self._current_page)

    def _on_detect_chapters_here(self) -> None:
        if self._actions is None:
            return
        self._actions.detect_chapters_at_page(self._current_page)

    def _on_destroy(self, _event: tk.Event[tk.Misc]) -> None:
        self._renderer.close()
