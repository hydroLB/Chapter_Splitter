"""Chapter review gallery for validating auto-detected chapter boundaries."""

from __future__ import annotations

import logging
import tkinter as tk
from collections import deque
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import ttk

from .....config.schema import UIConfig
from .....core.errors import UiError, format_error_message
from .....core.models import ChapterDefinition
from .....core.runtime import CancellationToken
from .....utils.timing import Deadline
from ..pdf_preview.renderer import PdfPreviewRenderer, is_preview_available

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChapterReviewActions:
    """Callback wiring for chapter review corrections.

    Summary:
        Provide a typed bundle of callbacks so the review gallery can apply quick corrections.
    Inputs:
        - jump_to_chapter: Focus the chapter row and navigate the main preview to the chapter start.
        - adjust_start: Adjust a chapter start by a delta in pages.
        - adjust_end: Adjust a chapter end by a delta in pages.
        - refresh_from_grid: Refresh the review gallery from the current grid values.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Stored and used by ChapterReviewFrame button handlers.
    Why this exists:
        Keeps the widget independent from workflow and grid internals.
    """

    jump_to_chapter: Callable[[int], None]
    adjust_start: Callable[[int, int], None]
    adjust_end: Callable[[int, int], None]
    refresh_from_grid: Callable[[], None]


class ChapterReviewFrame(tk.Frame):
    """Gallery view that previews chapters and enables quick boundary corrections.

    Summary:
        Render chapter start-page thumbnails in a scrollable grid so the user can spot bad splits
        after auto-detection and apply quick +/- adjustments.
    Inputs:
        - parent: Parent Tk widget.
        - pdf_path: PDF file path.
        - total_pages: Total pages in the document.
        - ui_config: UI configuration controlling thumbnail size and layout.
        - token: Cancellation token for graceful shutdown.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Creates Tk widgets and optionally opens a PDF renderer.
    Error handling:
        Degrades to a text-only view when PyMuPDF is unavailable.
    Ties to other methods:
        Constructed by the chapter window builder and wired by the workflow.
    Why this exists:
        A visual review step improves accuracy and reduces time spent correcting page numbers.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
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
        self._actions: ChapterReviewActions | None = None
        self._interaction_enabled = True
        self._chapters: tuple[ChapterDefinition, ...] = ()
        self._render_queue: deque[int] = deque()
        self._render_after_id: str | None = None
        self._thumbnails: dict[int, tk.PhotoImage] = {}
        self._thumb_labels: dict[int, ttk.Label] = {}
        self._range_labels: dict[int, ttk.Label] = {}
        self._card_buttons: list[ttk.Button] = []

        self._renderer = PdfPreviewRenderer()
        self._preview_ready = False

        self._build()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def set_actions(self, actions: ChapterReviewActions) -> None:
        """Wire callbacks for chapter review operations.

        Summary:
            Register callbacks that apply corrections to the grid/preview.
        Inputs:
            - actions: ChapterReviewActions bundle.
        Outputs:
            - None.
        Side effects:
            Enables review action buttons.
        Error handling:
            Raises UiError when actions are missing required callables.
        Ties to other methods:
            Used by the workflow after the window is built.
        Why this exists:
            The review widget should not depend on workflow internals.
        """
        error_location = f"{__name__}.ChapterReviewFrame.set_actions"
        if not callable(actions.jump_to_chapter):
            raise UiError(
                format_error_message(error_location, "jump_to_chapter callback must be callable.")
            )
        if not callable(actions.adjust_start):
            raise UiError(
                format_error_message(error_location, "adjust_start callback must be callable.")
            )
        if not callable(actions.adjust_end):
            raise UiError(
                format_error_message(error_location, "adjust_end callback must be callable.")
            )
        if not callable(actions.refresh_from_grid):
            raise UiError(
                format_error_message(error_location, "refresh_from_grid callback must be callable.")
            )
        self._actions = actions
        self._set_buttons_state()

    def set_interaction_enabled(self, enabled: bool) -> None:
        """Enable or disable interactions in the review panel.

        Summary:
            Prevent concurrent edits while long-running workflow actions run.
        Inputs:
            - enabled: True to allow interaction, False to disable.
        Outputs:
            - None.
        Side effects:
            Disables buttons.
        Error handling:
            Raises UiError when Tk state changes fail.
        Ties to other methods:
            Used by workflow busy-state helper.
        Why this exists:
            Export/detection should not compete with interactive corrections.
        """
        error_location = f"{__name__}.ChapterReviewFrame.set_interaction_enabled"
        try:
            self._interaction_enabled = enabled
            self._set_buttons_state()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(error_location, f"Unable to update review state: {exc}")
            ) from exc

    def set_chapters(self, chapters: Sequence[ChapterDefinition]) -> None:
        """Replace the gallery contents with the provided chapters.

        Summary:
            Rebuild the chapter cards and schedule thumbnail rendering.
        Inputs:
            - chapters: ChapterDefinition sequence.
        Outputs:
            - None.
        Side effects:
            Destroys and recreates card widgets; schedules renders.
        Error handling:
            Raises UiError for invalid chapter objects.
        Ties to other methods:
            Called by the workflow after auto-detection or when refreshing from grid.
        Why this exists:
            The gallery is derived state, so rebuilding is simpler than incremental patching.
        """
        error_location = f"{__name__}.ChapterReviewFrame.set_chapters"
        if not all(isinstance(item, ChapterDefinition) for item in chapters):
            raise UiError(
                format_error_message(
                    error_location, "chapters must contain ChapterDefinition items."
                )
            )
        self._chapters = tuple(chapters)
        self._rebuild_cards()
        self._schedule_thumbnail_renders()

    def update_chapter(self, index: int, chapter: ChapterDefinition) -> None:
        """Update a single chapter card in place.

        Summary:
            Apply a new ChapterDefinition to the given index and refresh labels/thumbnails without
            rebuilding the whole gallery.
        Inputs:
            - index: Chapter index in the current gallery.
            - chapter: Updated ChapterDefinition.
        Outputs:
            - None.
        Side effects:
            Updates widget text and schedules thumbnail re-render for that chapter.
        Error handling:
            Raises UiError when index is out of bounds or chapter is invalid.
        Ties to other methods:
            Used by workflow quick correction actions after updating the grid.
        Why this exists:
            Rebuilding dozens of cards after every +/- click feels sluggish; targeted updates keep
            the UI responsive.
        """
        error_location = f"{__name__}.ChapterReviewFrame.update_chapter"
        if not isinstance(chapter, ChapterDefinition):
            raise UiError(
                format_error_message(error_location, "chapter must be a ChapterDefinition.")
            )
        if index < 0 or index >= len(self._chapters):
            raise UiError(
                format_error_message(
                    error_location,
                    f"Chapter index out of range: {index}.",
                )
            )
        chapters = list(self._chapters)
        chapters[index] = chapter
        self._chapters = tuple(chapters)
        range_label = self._range_labels.get(index)
        if range_label is not None:
            range_label.configure(text=f"Pages {chapter.start_page}–{chapter.end_page}")
        if self._preview_ready and 1 <= chapter.start_page <= self._total_pages:
            self._render_queue.append(index)
            self._drain_render_queue()

    def _build(self) -> None:
        error_location = f"{__name__}.ChapterReviewFrame._build"
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
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Review", anchor="w").grid(row=0, column=0, sticky="w")
        self._refresh_button = ttk.Button(
            header,
            text="Refresh",
            command=self._on_refresh,
            state="disabled",
        )
        self._refresh_button.grid(row=0, column=1, sticky="e")

        container = ttk.Frame(self)
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(container, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=yscroll.set)

        self._inner = ttk.Frame(self._canvas)
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._message = ttk.Label(self._inner, text="No chapters to review yet.", anchor="w")
        self._message.grid(row=0, column=0, sticky="w", padx=4, pady=4)

        if not is_preview_available():
            self._preview_ready = False
            return
        try:
            self._renderer.open(self._pdf_path, self._token, self._location)
        except UiError as exc:
            logger.warning("review_preview_open_failed: %s", exc)
            self._preview_ready = False
            return
        self._preview_ready = True

    def _on_inner_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        with suppress(tk.TclError):
            self._canvas.itemconfigure(self._inner_id, width=event.width)

    def _set_buttons_state(self) -> None:
        if self._actions is None:
            state = "disabled"
        else:
            state = "normal" if self._interaction_enabled else "disabled"
        self._refresh_button.config(state=state)
        for btn in self._card_buttons:
            with suppress(tk.TclError):
                btn.config(state=state)

    def _rebuild_cards(self) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        self._card_buttons = []
        self._thumbnails.clear()
        self._thumb_labels.clear()
        self._range_labels.clear()
        if not self._chapters:
            self._message = ttk.Label(self._inner, text="No chapters to review yet.", anchor="w")
            self._message.grid(row=0, column=0, sticky="w", padx=4, pady=4)
            self._set_buttons_state()
            return

        cols = max(1, int(self._ui_config.chapter_review_columns))
        thumb_width = int(self._ui_config.chapter_review_thumbnail_width)
        for col in range(cols):
            self._inner.columnconfigure(col, weight=1)

        for idx, chapter in enumerate(self._chapters):
            row = idx // cols
            col = idx % cols
            card = ttk.Labelframe(self._inner, text=chapter.title)
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6, ipadx=4, ipady=4)
            card.columnconfigure(0, weight=1)

            thumb = ttk.Label(card, text="Preview unavailable" if not self._preview_ready else "")
            thumb.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
            thumb.configure(width=max(12, int(thumb_width / 12)))
            self._thumb_labels[idx] = thumb

            range_label = ttk.Label(
                card, text=f"Pages {chapter.start_page}–{chapter.end_page}", anchor="w"
            )
            range_label.grid(row=1, column=0, sticky="ew", padx=6)
            self._range_labels[idx] = range_label

            actions = ttk.Frame(card)
            actions.grid(row=2, column=0, sticky="ew", padx=6, pady=(6, 2))

            jump_btn = ttk.Button(actions, text="Jump", command=partial(self._on_jump, idx))
            jump_btn.pack(side="left")
            start_minus = ttk.Button(
                actions,
                text="Start −",
                command=partial(self._on_adjust_start, idx, -1),
                width=7,
            )
            start_minus.pack(side="left", padx=(8, 0))
            start_plus = ttk.Button(
                actions,
                text="Start +",
                command=partial(self._on_adjust_start, idx, 1),
                width=7,
            )
            start_plus.pack(side="left", padx=(4, 0))
            end_minus = ttk.Button(
                actions,
                text="End −",
                command=partial(self._on_adjust_end, idx, -1),
                width=6,
            )
            end_minus.pack(side="left", padx=(10, 0))
            end_plus = ttk.Button(
                actions,
                text="End +",
                command=partial(self._on_adjust_end, idx, 1),
                width=6,
            )
            end_plus.pack(side="left", padx=(4, 0))

            self._card_buttons.extend([jump_btn, start_minus, start_plus, end_minus, end_plus])

        self._set_buttons_state()

    def _schedule_thumbnail_renders(self) -> None:
        if not self._preview_ready or not self._chapters:
            return
        self._render_queue.clear()
        for idx, chapter in enumerate(self._chapters):
            if 1 <= chapter.start_page <= self._total_pages:
                self._render_queue.append(idx)
        self._drain_render_queue()

    def _drain_render_queue(self) -> None:
        if self._render_after_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._render_after_id)
        self._render_after_id = self.after(10, self._render_next_thumbnail)

    def _render_next_thumbnail(self) -> None:
        self._render_after_id = None
        if not self._render_queue:
            return
        idx = self._render_queue.popleft()
        try:
            chapter = self._chapters[idx]
            page_number = int(chapter.start_page)
            thumb_width = int(self._ui_config.chapter_review_thumbnail_width)
            supersample = max(1, int(self._ui_config.pdf_preview_supersample))
            deadline = Deadline(self._ui_config.pdf_preview_render_timeout_seconds)
            page_w, _page_h = self._renderer.get_page_size_points(
                page_number,
                deadline=deadline,
                token=self._token,
                location=self._location,
            )
            zoom = float(thumb_width / page_w)
            rendered = self._renderer.render_page_png_base64(
                page_number=page_number,
                zoom=zoom * supersample,
                deadline=deadline,
                token=self._token,
                location=self._location,
            )
            photo = tk.PhotoImage(data=rendered.png_base64, format="png")
            if supersample > 1:
                photo = photo.subsample(supersample, supersample)
            self._thumbnails[idx] = photo
            self._apply_thumbnail(idx, photo)
        except Exception as exc:
            logger.warning("thumbnail_render_failed idx=%s err=%s", idx, exc)
        finally:
            if self._render_queue:
                self._drain_render_queue()

    def _apply_thumbnail(self, index: int, photo: tk.PhotoImage) -> None:
        label = self._thumb_labels.get(index)
        if label is None:
            return
        label.configure(image=photo, text="")
        label.image = photo  # type: ignore[attr-defined]

    def _on_refresh(self) -> None:
        if self._actions is None:
            return
        self._actions.refresh_from_grid()

    def _on_jump(self, index: int) -> None:
        if self._actions is None:
            return
        self._actions.jump_to_chapter(index)

    def _on_adjust_start(self, index: int, delta: int) -> None:
        if self._actions is None:
            return
        self._actions.adjust_start(index, delta)

    def _on_adjust_end(self, index: int, delta: int) -> None:
        if self._actions is None:
            return
        self._actions.adjust_end(index, delta)

    def _on_destroy(self, _event: tk.Event[tk.Misc]) -> None:
        if self._render_after_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self._renderer.close()
