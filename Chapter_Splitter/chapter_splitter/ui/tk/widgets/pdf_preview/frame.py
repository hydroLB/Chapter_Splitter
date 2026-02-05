"""Embedded PDF preview panel with chapter marking controls."""

from __future__ import annotations

import logging
import tkinter as tk
from collections import OrderedDict
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Literal

from .....config.schema import UIConfig
from .....core.errors import UiError, format_error_message
from .....core.runtime import CancellationToken
from .....utils.timing import Deadline
from .renderer import PdfPreviewRenderer, RenderedImage, is_preview_available

logger = logging.getLogger(__name__)

ZoomMode = Literal["fit_page", "fit_width", "manual"]


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
        self._interaction_enabled = True

        self._renderer = PdfPreviewRenderer()
        self._current_page = 1
        self._preview_ready = False
        self._zoom_mode: ZoomMode = self._initial_zoom_mode()
        self._manual_zoom = self._clamp_manual_zoom(float(self._ui_config.pdf_preview_zoom))
        self._last_fit_zoom: float | None = None
        self._resize_after_id: str | None = None
        self._photo: tk.PhotoImage | None = None
        self._image_item: int | None = None

        # Cache by (page_number, display_zoom, supersample) -> PhotoImage.
        self._cache: OrderedDict[tuple[int, float, int], tk.PhotoImage] = OrderedDict()

        self._build()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _initial_zoom_mode(self) -> ZoomMode:
        """Determine the initial zoom mode from configuration.

        Summary:
            Map the config-driven fit mode to the internal zoom mode representation.
        Inputs:
            - None.
        Outputs:
            - ZoomMode value.
        Side effects:
            None.
        Error handling:
            Defaults to fit_page for unknown values to keep preview usable.
        Ties to other methods:
            Used by __init__.
        Why this exists:
            Keeping the mapping in one place prevents config parsing drift.
        """
        fit_mode = getattr(self._ui_config, "pdf_preview_fit_mode", "page")
        if fit_mode == "width":
            return "fit_width"
        if fit_mode == "none":
            return "manual"
        return "fit_page"

    def _clamp_manual_zoom(self, zoom: float) -> float:
        """Clamp a manual zoom value within configured bounds.

        Summary:
            Normalize manual zoom inputs so the renderer is not asked to render extreme values.
        Inputs:
            - zoom: Proposed zoom value.
        Outputs:
            - Clamped zoom value.
        Side effects:
            None.
        Error handling:
            Returns a safe fallback when zoom is invalid.
        Ties to other methods:
            Used by __init__ and zoom button handlers.
        Why this exists:
            Guard rails keep rendering predictable and prevent large memory spikes.
        """
        try:
            min_zoom = float(self._ui_config.pdf_preview_min_zoom)
            max_zoom = float(self._ui_config.pdf_preview_max_zoom)
        except Exception:
            min_zoom = 0.25
            max_zoom = 4.0
        if zoom <= 0:
            return max(min_zoom, 1.0)
        return max(min_zoom, min(max_zoom, zoom))

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
        self._refresh_action_button_states()

    def set_interaction_enabled(self, enabled: bool) -> None:
        """Enable or disable interactions in the preview panel.

        Summary:
            Prevent concurrent preview navigation and labeling while the workflow runs long actions.
        Inputs:
            - enabled: True to allow interaction, False to disable it.
        Outputs:
            - None.
        Side effects:
            Disables navigation widgets and action buttons.
        Error handling:
            Raises UiError when Tk state changes fail.
        Ties to other methods:
            Used by the Tk workflow busy-state helper.
        Why this exists:
            Export, detection, and viewer-open actions should not compete with additional UI
            actions.
        """
        error_location = f"{__name__}.PdfPreviewFrame.set_interaction_enabled"
        try:
            self._interaction_enabled = enabled
            nav_state = "normal" if enabled else "disabled"
            self._prev_button.config(state=nav_state)
            self._next_button.config(state=nav_state)
            self._page_entry.config(state=nav_state)
            self._go_button.config(state=nav_state)
            self._refresh_action_button_states()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to update preview widget states: {exc}",
                )
            ) from exc

    def _refresh_action_button_states(self) -> None:
        error_location = f"{__name__}.PdfPreviewFrame._refresh_action_button_states"
        try:
            enabled = self._interaction_enabled and self._actions is not None
            state = "normal" if enabled else "disabled"
            self._new_chapter_button.config(state=state)
            self._set_start_button.config(state=state)
            self._set_end_button.config(state=state)
            self._detect_chapters_button.config(state=state)
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to update preview action button states: {exc}",
                )
            ) from exc

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

        self._prev_button = ttk.Button(nav, text="◀", width=3, command=self.prev_page)
        self._prev_button.grid(row=0, column=0)
        self._next_button = ttk.Button(nav, text="▶", width=3, command=self.next_page)
        self._next_button.grid(row=0, column=1, padx=(4, 0))

        ttk.Label(nav, text="Page").grid(row=0, column=2, padx=(10, 4))
        self._page_var = tk.StringVar(value=str(self._current_page))
        self._page_entry = ttk.Entry(nav, width=6, textvariable=self._page_var)
        self._page_entry.grid(row=0, column=3)
        self._page_entry.bind("<Return>", lambda _event: self._on_page_entry())
        self._page_count_label = ttk.Label(nav, text=f"/ {self._total_pages}")
        self._page_count_label.grid(row=0, column=4, padx=(4, 0))

        self._go_button = ttk.Button(nav, text="Go", command=self._on_page_entry)
        self._go_button.grid(row=0, column=5, padx=(6, 0))

        self._zoom_mode_var = tk.StringVar(value=self._zoom_mode_label(self._zoom_mode))
        self._zoom_mode_combo = ttk.Combobox(
            nav,
            width=10,
            state="readonly",
            textvariable=self._zoom_mode_var,
            values=("Fit Page", "Fit Width", "Manual"),
        )
        self._zoom_mode_combo.grid(row=0, column=7, padx=(10, 0))
        self._zoom_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_zoom_mode())

        self._zoom_out_button = ttk.Button(
            nav, text="−", width=3, command=lambda: self._bump_zoom(-1)
        )
        self._zoom_out_button.grid(row=0, column=8, padx=(6, 0))
        self._zoom_in_button = ttk.Button(
            nav, text="+", width=3, command=lambda: self._bump_zoom(1)
        )
        self._zoom_in_button.grid(row=0, column=9, padx=(4, 0))
        self._zoom_label = ttk.Label(nav, text="")
        self._zoom_label.grid(row=0, column=10, padx=(6, 0))

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
        self._detect_chapters_button.pack(side="right")

        # Canvas with scrollbars.
        container = ttk.Frame(self)
        container.grid(row=2, column=0, sticky="nsew", padx=8)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(container, highlightthickness=0, background="white")
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", self._on_canvas_resize)

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
        self._preview_ready = True

        self.go_to_page(1)

    def _zoom_mode_label(self, mode: ZoomMode) -> str:
        """Convert an internal zoom mode into a user-facing label."""
        return {"fit_page": "Fit Page", "fit_width": "Fit Width", "manual": "Manual"}[mode]

    def _on_zoom_mode(self) -> None:
        """Handle zoom mode changes from the combobox.

        Summary:
            Update zoom mode state and rerender the current page using the new mode.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Changes zoom mode and triggers a rerender.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Bound to the zoom mode combobox selection event.
        Why this exists:
            Fit modes should be discoverable and not require config edits during labeling.
        """
        raw = self._zoom_mode_var.get().strip().lower()
        if raw.startswith("fit width"):
            self._zoom_mode = "fit_width"
        elif raw.startswith("manual"):
            self._zoom_mode = "manual"
        else:
            self._zoom_mode = "fit_page"
        self._last_fit_zoom = None
        self._render_current_page(force=True)

    def _bump_zoom(self, direction: int) -> None:
        """Adjust manual zoom and rerender.

        Summary:
            Increase or decrease the manual zoom value by the configured step.
        Inputs:
            - direction: -1 for zoom out, +1 for zoom in.
        Outputs:
            - None.
        Side effects:
            Switches to manual zoom mode and triggers a rerender.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Used by the zoom +/- buttons.
        Why this exists:
            Users need quick adjustments when pages are unusually sized or dense.
        """
        step = float(self._ui_config.pdf_preview_zoom_step)
        self._zoom_mode = "manual"
        self._zoom_mode_var.set(self._zoom_mode_label(self._zoom_mode))
        self._manual_zoom = self._clamp_manual_zoom(self._manual_zoom + (step * direction))
        self._render_current_page(force=True)

    def _on_canvas_resize(self, _event: tk.Event[tk.Misc]) -> None:
        """Debounce rerenders when the canvas resizes under fit modes.

        Summary:
            Fit zoom depends on available canvas size, so resizing should trigger recomputation.
        Inputs:
            - _event: Tkinter configure event.
        Outputs:
            - None.
        Side effects:
            Schedules a rerender via after().
        Error handling:
            Suppresses Tk errors during teardown.
        Ties to other methods:
            Called by the canvas <Configure> binding.
        Why this exists:
            Without debouncing, fast window resizes can trigger expensive rerenders.
        """
        if self._zoom_mode == "manual":
            return
        if self._resize_after_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(80, lambda: self._render_current_page(force=True))

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

    def _render_current_page(self, *, force: bool = False) -> None:
        """Render and display the current page using current zoom settings.

        Summary:
            Compute an effective zoom value (fit or manual), render via PyMuPDF, and display it.
        Inputs:
            - force: When True, bypasses cache and rerenders.
        Outputs:
            - None.
        Side effects:
            Updates the canvas image and cache.
        Error handling:
            Raises UiError when rendering fails.
        Ties to other methods:
            Called by navigation, zoom controls, and resize handling.
        Why this exists:
            Centralizing zoom logic ensures consistent quality and fit behavior across UI actions.
        """
        if not self._ui_config.enable_pdf_preview:
            return
        if not self._preview_ready:
            return
        display_zoom = self._current_display_zoom()
        supersample = int(self._ui_config.pdf_preview_supersample)
        key = (self._current_page, round(display_zoom, 4), supersample)
        if not force:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                self._set_image(cached, cached.width(), cached.height())
                self._update_zoom_label(display_zoom)
                return

        deadline = Deadline(self._ui_config.pdf_preview_render_timeout_seconds)
        rendered: RenderedImage = self._renderer.render_page_png_base64(
            page_number=self._current_page,
            zoom=float(display_zoom) * float(max(1, supersample)),
            deadline=deadline,
            token=self._token,
            location=self._location,
        )
        photo = tk.PhotoImage(data=rendered.png_base64, format="png")
        width = rendered.width
        height = rendered.height
        if supersample > 1:
            photo = photo.subsample(supersample, supersample)
            width = max(1, int(width / supersample))
            height = max(1, int(height / supersample))
        self._cache[key] = photo
        self._cache.move_to_end(key)
        while len(self._cache) > self._ui_config.pdf_preview_cache_entries:
            self._cache.popitem(last=False)
        self._set_image(photo, width, height)
        self._update_zoom_label(display_zoom)

    def _current_display_zoom(self) -> float:
        """Return the effective zoom used for the next render."""
        if self._zoom_mode == "manual":
            return self._manual_zoom
        fit = self._compute_fit_zoom()
        if fit is None:
            return self._manual_zoom
        self._last_fit_zoom = fit
        return fit

    def _compute_fit_zoom(self) -> float | None:
        """Compute a fit zoom based on canvas size and PDF page size.

        Summary:
            Calculate a zoom factor that fits the current page to the available canvas space.
        Inputs:
            - None.
        Outputs:
            - Zoom factor or None when sizing information is not yet available.
        Side effects:
            Reads page size via the renderer.
        Error handling:
            Returns None on transient sizing issues; raises UiError for renderer failures.
        Ties to other methods:
            Used by _current_display_zoom when in fit modes.
        Why this exists:
            Fit-to-view behavior is required to make chapter labeling comfortable on varied screens.
        """
        canvas_width = int(self._canvas.winfo_width())
        canvas_height = int(self._canvas.winfo_height())
        if canvas_width <= 2 or canvas_height <= 2:
            return None
        padding = int(self._ui_config.pdf_preview_fit_padding_px)
        available_w = max(10, canvas_width - (padding * 2))
        available_h = max(10, canvas_height - (padding * 2))
        deadline = Deadline(self._ui_config.pdf_preview_render_timeout_seconds)
        page_w, page_h = self._renderer.get_page_size_points(
            self._current_page,
            deadline=deadline,
            token=self._token,
            location=self._location,
        )
        if self._zoom_mode == "fit_width":
            zoom = available_w / page_w
        else:
            zoom = min(available_w / page_w, available_h / page_h)
        return self._clamp_manual_zoom(float(zoom))

    def _update_zoom_label(self, display_zoom: float) -> None:
        """Update the zoom label text."""
        percent = int(round(display_zoom * 100))
        self._zoom_label.config(text=f"{percent}%")

    def _set_image(self, photo: tk.PhotoImage, width: int, height: int) -> None:
        self._photo = photo
        self._canvas.delete("all")
        canvas_w = int(self._canvas.winfo_width())
        canvas_h = int(self._canvas.winfo_height())
        x = max(0, int((canvas_w - width) / 2)) if canvas_w > width else 0
        y = max(0, int((canvas_h - height) / 2)) if canvas_h > height else 0
        self._image_item = self._canvas.create_image(x, y, anchor="nw", image=photo)
        scroll_w = max(1, width, canvas_w)
        scroll_h = max(1, height, canvas_h)
        self._canvas.configure(scrollregion=(0, 0, scroll_w, scroll_h))

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
