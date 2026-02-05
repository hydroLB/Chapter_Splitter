"""Chapter grid widget frame for entering chapter definitions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from contextlib import suppress
from tkinter import ttk
from typing import Literal

from chapter_splitter.config.schema import UIConfig
from chapter_splitter.core.errors import UiError, ValidationError, format_error_message
from chapter_splitter.core.models import ChapterDefinition

from ..grid_placeholders import first_none_index, shift_indices
from .layout import grid_position
from .types import ChapterRowValues, GridRow

AddMode = Literal["append", "replace", "insert"]
AddAction = tuple[AddMode, int]


def _set_entry_state(
    widget: tk.Entry,
    *,
    enabled: bool,
    readonly_when_enabled: bool = False,
) -> None:
    """Set the enabled/disabled state for an entry-like widget.

    Summary:
        Normalize state transitions across ttk.Entry, ttk.Combobox, and tk.Entry.
    Inputs:
        - widget: Entry widget to update.
        - enabled: True for interactive, False for disabled.
        - readonly_when_enabled: When True and widget is a Combobox, uses readonly mode.
    Outputs:
        - None.
    Side effects:
        Updates the widget state.
    Error handling:
        Lets Tk exceptions bubble to the caller, which should wrap them as UiError.
    Ties to other methods:
        Used by ChapterGridFrame.set_interaction_enabled.
    Why this exists:
        Tk widgets use slightly different state semantics; centralizing them prevents drift.
    """
    if isinstance(widget, ttk.Combobox):
        widget.config(
            state="readonly"
            if enabled and readonly_when_enabled
            else ("normal" if enabled else "disabled")
        )
        return
    widget.config(state="normal" if enabled else "disabled")


class ChapterGridFrame(tk.Frame):
    """A grid where each row defines a chapter title and page range.

    Purpose:
        Provide a reusable grid widget for chapter entry and editing.
    Ties To:
        Constructed by build_chapter_window and used in the UI workflow.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(
        self,
        parent: tk.Misc,
        prefill_chapters: Sequence[ChapterRowValues] | None,
        page_labels: list[str] | None,
        ui_config: UIConfig,
    ) -> None:
        """Initialize the chapter grid widget.

        Purpose:
            Build the grid layout and apply optional prefilled values.
        Ties To:
            Created by build_chapter_window and used by the UI workflow.
        Inputs:
            - parent: Parent Tk widget.
            - prefill_chapters: Optional chapter rows to prefill.
            - page_labels: Optional list of page labels from the PDF.
            - ui_config: UI configuration for layout and limits.
        Outputs:
            - None.
        Side Effects:
            Creates Tk widgets and initializes internal state.
        Raises:
            - ValidationError: When the UI configuration is invalid.
        """
        super().__init__(parent)
        self._ui_config = ui_config
        self._page_labels = page_labels
        self._rows: list[GridRow | None] = []
        self._placeholders: dict[int, ChapterRowValues] = {}
        self._max_row_count = 1
        self._active_row_index: int | None = None
        self._int_validate_cmd = (self.register(self._is_valid_int_input), "%P")
        self._effective_rows_per_column = max(
            self._ui_config.rows_per_column,
            self._ui_config.row_limit,
        )

        self._validate_ui_config()
        self._build_scroll_container()
        self._build_grid()
        if prefill_chapters:
            self.prefill(prefill_chapters)

    def _build_scroll_container(self) -> None:
        """Create a scrollable container for the grid contents.

        Purpose:
            Ensure the chapter grid expands with the window and remains usable for many rows.
        Ties To:
            Used by __init__ before building headers and rows.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Creates a canvas, scrollbar, and inner frame for gridded widgets.
        Raises:
            - UiError: When the scroll container cannot be created.
        """
        error_location = f"{__name__}.ChapterGridFrame._build_scroll_container"
        try:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)

            container = ttk.Frame(self)
            container.grid(row=0, column=0, sticky="nsew")
            container.columnconfigure(0, weight=1)
            container.rowconfigure(0, weight=1)

            self._canvas = tk.Canvas(container, highlightthickness=0)
            self._canvas.grid(row=0, column=0, sticky="nsew")

            scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            self._canvas.configure(yscrollcommand=scrollbar.set)

            self._grid = ttk.Frame(self._canvas)
            self._grid_window_id = self._canvas.create_window(
                (0, 0),
                window=self._grid,
                anchor="nw",
            )
            self._grid.bind("<Configure>", self._on_grid_configure)
            self._canvas.bind("<Configure>", self._on_canvas_configure)

            self._grid.columnconfigure(0, weight=1)
            for col in range(1, self._ui_config.grid_columns):
                self._grid.columnconfigure(col, weight=0)

            self._bind_mousewheel(self._canvas)
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to create scroll container: {exc}",
                )
            ) from exc

    def _on_grid_configure(self, _event: tk.Event[tk.Misc]) -> None:
        """Update canvas scroll region after grid content changes.

        Purpose:
            Keep the scrollbar accurate when rows are added, removed, or resized.
        Ties To:
            Bound to the inner grid frame <Configure> event.
        Inputs:
            - _event: Tkinter configure event.
        Outputs:
            - None.
        Side Effects:
            Updates the canvas scrollregion.
        Raises:
            - None.
        """
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """Keep the inner grid frame width in sync with the canvas width.

        Purpose:
            Allow the Chapter column to expand and shrink with the window.
        Ties To:
            Bound to the canvas <Configure> event.
        Inputs:
            - event: Tkinter configure event.
        Outputs:
            - None.
        Side Effects:
            Updates the canvas window item width.
        Raises:
            - None.
        """
        self._canvas.itemconfigure(self._grid_window_id, width=event.width)

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        """Bind mouse wheel scrolling to the canvas.

        Purpose:
            Provide expected scrolling behavior across platforms.
        Ties To:
            Used by _build_scroll_container.
        Inputs:
            - widget: Widget to bind events on.
        Outputs:
            - None.
        Side Effects:
            Adds event bindings to the widget.
        Raises:
            - None.
        """

        def _on_mousewheel(event: tk.Event[tk.Misc]) -> str:
            delta = 0
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            elif getattr(event, "delta", None):
                raw_delta = int(event.delta)
                delta = -1 * int(raw_delta / 120) if abs(raw_delta) >= 120 else -1 * raw_delta
            if delta:
                self._canvas.yview_scroll(delta, "units")
            return "break"

        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    def has_defined_ranges(self) -> bool:
        """Check whether the grid contains any user-defined start or end values.

        Summary:
            Determine whether the user has started defining ranges so destructive actions can warn.
        Inputs:
            - None.
        Outputs:
            - True when any row has a non-empty start or end field, otherwise False.
        Side effects:
            None.
        Error handling:
            Raises UiError when Tk field access fails.
        Ties to other methods:
            Used by the workflow before auto-detect prefill replaces the grid contents.
        Why this exists:
            Auto-detection overwrites the current grid; prompting when the user has input reduces
            accidental data loss.
        """
        error_location = f"{__name__}.ChapterGridFrame.has_defined_ranges"
        try:
            for row in self._rows:
                if row is None:
                    continue
                _title_field, start_field, end_field, _button = row
                if start_field.get().strip() or end_field.get().strip():
                    return True
            return False
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to inspect grid values: {exc}",
                )
            ) from exc

    def _is_valid_int_input(self, proposed: str) -> bool:
        """Validate integer-only entry input for page number fields.

        Summary:
            Reject non-digit characters while allowing the field to be temporarily empty.
        Inputs:
            - proposed: Proposed entry value after the edit.
        Outputs:
            - True when the input is empty or all digits, otherwise False.
        Side effects:
            None.
        Error handling:
            Returns False for invalid values; Tk validate callbacks should not raise.
        Ties to other methods:
            Used by _make_row_widgets to validate page number entry fields.
        Why this exists:
            Preventing invalid characters makes errors less likely and reduces frustrating export
            failures.
        """
        return proposed == "" or proposed.isdigit()

    def add_row(
        self,
        insert_idx: int | None = None,
        title: str = "",
        start_val: str = "",
        end_val: str = "",
    ) -> GridRow | None:
        """Append or insert a new editable row.

        Purpose:
            Add a new chapter entry row to the grid.
        Ties To:
            Invoked by the UI add chapter button and prefill logic.
        Inputs:
            - insert_idx: Optional insertion index.
            - title: Optional chapter title.
            - start_val: Optional start page value.
            - end_val: Optional end page value.
        Outputs:
            - The created row widgets or None when limit reached.
        Side Effects:
            Modifies internal row list and refreshes layout.
        Raises:
            - ValidationError: When row limit is exceeded.
        """
        error_location = f"{__name__}.ChapterGridFrame.add_row"
        try:
            mode, target = self._plan_add_action(insert_idx, error_location)
            widgets = self._make_row_widgets(title, start_val, end_val)
            self._apply_add_action(mode, target, widgets, error_location)
            self._maybe_resize()
            self.refresh_grid()
            return widgets
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to add grid row: {exc}",
                )
            ) from exc

    def set_interaction_enabled(self, enabled: bool, location: str) -> None:
        """Enable or disable interactive widgets in the grid.

        Summary:
            Prevent edits while long-running workflow actions are running.
        Inputs:
            - enabled: True to enable interaction, False to disable it.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the `state` of entry widgets, comboboxes, and per-row buttons.
        Error handling:
            Raises UiError when Tk state changes fail.
        Ties to other methods:
            Used by the Tk workflow busy-state helper to avoid concurrent edits.
        Why this exists:
            Disabling inputs during export and detection avoids inconsistent reads and reduces the
            chance of Tk widgets being destroyed while the user is typing.
        """
        error_location = f"{__name__}.ChapterGridFrame.set_interaction_enabled"
        context = f" Context: {location}." if location else ""
        try:
            for row in self._rows:
                if row is None:
                    continue
                title_entry, start_entry, end_entry, remove_button = row
                _set_entry_state(title_entry, enabled=enabled)
                _set_entry_state(start_entry, enabled=enabled, readonly_when_enabled=True)
                _set_entry_state(end_entry, enabled=enabled, readonly_when_enabled=True)
                remove_button.config(state="normal" if enabled else "disabled")
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to update grid widget states.{context}",
                )
            ) from exc

    def _plan_add_action(self, insert_idx: int | None, error_location: str) -> AddAction:
        """Determine how a row should be added to the internal list.

        Purpose:
            Centralize add-row decision logic so add_row stays simple.
        Ties To:
            Used by add_row and prefill when inserting rows.
        Inputs:
            - insert_idx: Optional insertion index from the caller.
            - error_location: Location string used for error messages.
        Outputs:
            - Tuple of add mode and target index.
        Side Effects:
            None.
        Raises:
            - ValidationError: When row limit is exceeded and no placeholder is available.
        """
        if insert_idx is None:
            if len(self._rows) < self._ui_config.row_limit:
                return "append", len(self._rows)
            reuse_idx = self._first_placeholder_index()
            if reuse_idx is None:
                raise ValidationError(
                    format_error_message(
                        error_location, f"Row limit {self._ui_config.row_limit} reached."
                    )
                )
            return "replace", reuse_idx

        target_idx = min(insert_idx, len(self._rows))
        if target_idx < len(self._rows) and self._rows[target_idx] is None:
            return "replace", target_idx
        if len(self._rows) >= self._ui_config.row_limit:
            raise ValidationError(
                format_error_message(
                    error_location, f"Row limit {self._ui_config.row_limit} reached."
                )
            )
        return "insert", target_idx

    def _apply_add_action(
        self,
        mode: AddMode,
        target: int,
        widgets: GridRow,
        error_location: str,
    ) -> None:
        """Apply an add-row action to the internal state.

        Purpose:
            Encapsulate list and placeholder mutations for add_row.
        Ties To:
            Used by add_row after widgets are created.
        Inputs:
            - mode: Add action mode.
            - target: Target row index.
            - widgets: Newly created row widgets.
            - error_location: Location string used for error messages.
        Outputs:
            - None.
        Side Effects:
            Mutates self._rows and self._placeholders.
        Raises:
            - UiError: When an unexpected mode is provided.
        """
        if mode == "append":
            self._rows.append(widgets)
            return
        if mode == "replace":
            self._rows[target] = widgets
            self._placeholders.pop(target, None)
            return
        if mode == "insert":
            self._rows.insert(target, widgets)
            self._shift_placeholders(start=target, delta=1)
            return
        raise UiError(format_error_message(error_location, f"Unexpected add row mode: {mode}"))

    def remove_row(self, idx: int) -> None:
        """Remove a row and create an undo placeholder.

        Purpose:
            Allow removal of chapters while offering an undo action.
        Ties To:
            Invoked by remove buttons on each row.
        Inputs:
            - idx: Row index to remove.
        Outputs:
            - None.
        Side Effects:
            Updates internal row and placeholder collections.
        Raises:
            - ValidationError: When the row index is invalid.
        """
        error_location = f"{__name__}.ChapterGridFrame.remove_row"
        if idx < 0 or idx >= len(self._rows):
            raise ValidationError(
                format_error_message(error_location, f"Row index out of range: {idx}")
            )
        row = self._rows[idx]
        if row is None:
            return
        try:
            values = (row[0].get(), row[1].get(), row[2].get())
            for widget in row:
                widget.grid_forget()
                widget.destroy()
            self._placeholders[idx] = values
            self._rows[idx] = None
            self.refresh_grid()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to remove grid row: {exc}",
                )
            ) from exc

    def undo_remove(self, values: ChapterRowValues, idx: int) -> None:
        """Reinsert a previously removed row.

        Purpose:
            Restore removed row data on demand.
        Ties To:
            Triggered by the undo button placeholder.
        Inputs:
            - values: Tuple of title, start, and end values.
            - idx: Row index to restore.
        Outputs:
            - None.
        Side Effects:
            Modifies row lists and UI layout.
        Raises:
            - ValidationError: When the row index is invalid.
        """
        error_location = f"{__name__}.ChapterGridFrame.undo_remove"
        if idx < 0 or idx >= max(len(self._rows), self._ui_config.row_limit):
            raise ValidationError(
                format_error_message(error_location, f"Row index out of range: {idx}")
            )
        title, start_val, end_val = values
        try:
            if idx < len(self._rows) and self._rows[idx] is not None:
                raise ValidationError(
                    format_error_message(
                        error_location, f"Cannot restore row {idx}: slot already occupied."
                    )
                )
            widgets = self._make_row_widgets(title, start_val, end_val)
            if idx >= len(self._rows):
                self._rows.extend([None] * (idx - len(self._rows) + 1))
            self._rows[idx] = widgets
            self._placeholders.pop(idx, None)
            self.refresh_grid()
            self._maybe_resize()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to restore grid row: {exc}",
                )
            ) from exc

    def get_chapters(self) -> list[ChapterDefinition]:
        """Collect chapter definitions from valid rows.

        Purpose:
            Convert UI input into ChapterDefinition objects.
        Ties To:
            Used by the UI workflow before exporting chapters.
        Inputs:
            - None.
        Outputs:
            - List of ChapterDefinition objects.
        Side Effects:
            None.
        Raises:
            - ValidationError: When any row contains invalid data.
        """
        error_location = f"{__name__}.ChapterGridFrame.get_chapters"
        chapters: list[ChapterDefinition] = []
        for index, row in enumerate(self._rows):
            if row is None:
                continue
            title_field, start_field, end_field, _button = row
            title = (
                title_field.get().strip() or f"{self._ui_config.chapter_title_prefix} {index + 1}"
            )
            if self._page_labels is not None:
                start_label = start_field.get().strip()
                end_label = end_field.get().strip()
                if start_label not in self._page_labels or end_label not in self._page_labels:
                    raise ValidationError(
                        format_error_message(
                            error_location,
                            f"Row {index + 1} has unknown page labels.",
                        )
                    )
                start_page = self._page_labels.index(start_label) + 1
                end_page = self._page_labels.index(end_label) + 1
            else:
                try:
                    start_page = int(start_field.get())
                    end_page = int(end_field.get())
                except ValueError as exc:
                    raise ValidationError(
                        format_error_message(
                            error_location,
                            f"Row {index + 1} must contain integer page numbers.",
                        )
                    ) from exc
            chapters.append(
                ChapterDefinition(title=title, start_page=start_page, end_page=end_page)
            )
        if not chapters:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "At least one chapter is required.",
                )
            )
        return chapters

    def set_active_row_start_at_page(self, page_number: int, location: str) -> None:
        """Set the active row start value based on a 1-based page number.

        Summary:
            Allow external UI controls (like the PDF preview panel) to set the active chapter start.
        Inputs:
            - page_number: 1-based page number.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the active row start widget value.
        Error handling:
            Raises UiError or ValidationError for invalid page numbers or missing rows.
        Ties to other methods:
            Used by the embedded PDF preview actions in the workflow.
        Why this exists:
            Clicking a page is faster and less error-prone than typing start pages manually.
        """
        row_idx = self._ensure_active_row(location)
        value = self._page_value_for_number(page_number, location)
        row = self._require_row(row_idx, location)
        _title, start_field, _end_field, _remove = row
        self._set_field_value(start_field, value, location)

    def set_active_row_index(self, row_index: int, location: str) -> None:
        """Set the active row index for subsequent external actions.

        Summary:
            Allow helper panels (preview/review) to target a specific chapter row for edits.
        Inputs:
            - row_index: Zero-based row index.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the internal active row pointer and focuses the row title widget.
        Error handling:
            Raises UiError when the row index is invalid or the row does not exist.
        Ties to other methods:
            Used by the chapter review gallery to apply corrections to a specific row.
        Why this exists:
            Quick correction workflows need deterministic row targeting, not implicit "last active"
            behavior.
        """
        error_location = f"{__name__}.ChapterGridFrame.set_active_row_index"
        context = f" Context: {location}." if location else ""
        if row_index < 0 or row_index >= len(self._rows):
            raise UiError(
                format_error_message(
                    error_location,
                    f"Row index out of range: {row_index}.{context}",
                )
            )
        row = self._rows[row_index]
        if row is None:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Row {row_index} is empty.{context}",
                )
            )
        self._active_row_index = row_index
        with suppress(tk.TclError):
            row[0].focus_set()

    def set_active_row_end_at_page(self, page_number: int, location: str) -> None:
        """Set the active row end value based on a 1-based page number.

        Summary:
            Allow external UI controls (like the PDF preview panel) to set the active chapter end.
        Inputs:
            - page_number: 1-based page number.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the active row end widget value.
        Error handling:
            Raises UiError or ValidationError for invalid page numbers or missing rows.
        Ties to other methods:
            Used by the embedded PDF preview actions in the workflow.
        Why this exists:
            A visual end-marking action reduces off-by-one errors during exports.
        """
        row_idx = self._ensure_active_row(location)
        value = self._page_value_for_number(page_number, location)
        row = self._require_row(row_idx, location)
        _title, _start_field, end_field, _remove = row
        self._set_field_value(end_field, value, location)

    def get_row_page_numbers(self, row_index: int, location: str) -> tuple[int, int]:
        """Return the start/end page numbers for a row.

        Summary:
            Parse the row's start and end fields into 1-based page numbers, honoring page labels
            when present.
        Inputs:
            - row_index: Zero-based row index.
            - location: Fully qualified module and method name.
        Outputs:
            - (start_page, end_page) tuple.
        Side effects:
            None.
        Error handling:
            Raises UiError for missing rows and ValidationError for missing/invalid page values.
        Ties to other methods:
            Used by the chapter review gallery to compute +/- adjustments.
        Why this exists:
            Corrections should operate on validated numeric page values, not raw widget strings.
        """
        error_location = f"{__name__}.ChapterGridFrame.get_row_page_numbers"
        context = f" Context: {location}." if location else ""
        row = self._require_row(row_index, location)
        _title, start_field, end_field, _remove = row
        start_raw = start_field.get().strip()
        end_raw = end_field.get().strip()
        start_page = self._parse_page_value(start_raw)
        end_page = self._parse_page_value(end_raw)
        if start_page is None or end_page is None:
            raise ValidationError(
                format_error_message(
                    error_location,
                    f"Row {row_index + 1} must have both start and end values set.{context}",
                )
            )
        return start_page, end_page

    def set_row_start_at_page(self, row_index: int, page_number: int, location: str) -> None:
        """Set the start page for a specific row.

        Summary:
            Apply a 1-based page number to a specific row start field.
        Inputs:
            - row_index: Zero-based row index.
            - page_number: 1-based page number.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the row start widget value.
        Error handling:
            Raises UiError or ValidationError for invalid indices or page numbers.
        Ties to other methods:
            Used by the chapter review gallery quick correction buttons.
        Why this exists:
            Row-targeted updates avoid implicit "active row" behavior when correcting many chapters.
        """
        value = self._page_value_for_number(page_number, location)
        row = self._require_row(row_index, location)
        _title, start_field, _end_field, _remove = row
        self._set_field_value(start_field, value, location)

    def set_row_end_at_page(self, row_index: int, page_number: int, location: str) -> None:
        """Set the end page for a specific row.

        Summary:
            Apply a 1-based page number to a specific row end field.
        Inputs:
            - row_index: Zero-based row index.
            - page_number: 1-based page number.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Updates the row end widget value.
        Error handling:
            Raises UiError or ValidationError for invalid indices or page numbers.
        Ties to other methods:
            Used by the chapter review gallery quick correction buttons.
        Why this exists:
            Corrections should be quick and deterministic across many chapters.
        """
        value = self._page_value_for_number(page_number, location)
        row = self._require_row(row_index, location)
        _title, _start_field, end_field, _remove = row
        self._set_field_value(end_field, value, location)

    def start_new_chapter_at_page(self, page_number: int, location: str) -> None:
        """Create a new chapter row starting at the given page.

        Summary:
            Add a new chapter row with start set to the current page and optionally close the prior
            chapter by setting its end to the previous page when empty.
        Inputs:
            - page_number: 1-based page number.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Adds a new row to the grid and may update the previous row end field.
        Error handling:
            Raises UiError or ValidationError when page values cannot be applied.
        Ties to other methods:
            Used by the embedded PDF preview "New Chapter Here" action.
        Why this exists:
            A single button supports fast labeling workflows where the user clicks through pages and
            marks chapter boundaries as they go.
        """
        error_location = f"{__name__}.ChapterGridFrame.start_new_chapter_at_page"
        if page_number < 1:
            raise ValidationError(
                format_error_message(
                    error_location, f"page_number must be >= 1 (got {page_number})"
                )
            )
        start_value = self._page_value_for_number(page_number, location)

        previous_end_page = page_number - 1
        if previous_end_page >= 1:
            previous_row_idx = self._last_defined_row_index()
            if previous_row_idx is not None:
                previous_row = self._require_row(previous_row_idx, location)
                _title_field, start_field, end_field, _remove = previous_row
                if not end_field.get().strip():
                    try:
                        previous_start_page = self._parse_page_value(start_field.get().strip())
                    except ValidationError:
                        previous_start_page = None
                    if previous_start_page is None or previous_start_page <= previous_end_page:
                        end_value = self._page_value_for_number(previous_end_page, location)
                        self._set_field_value(end_field, end_value, location)

        new_row = self.add_row(start_val=start_value)
        if new_row is None:
            raise ValidationError(
                format_error_message(
                    error_location, f"Unable to add a new row at page {page_number}."
                )
            )
        new_index = self._find_row_index(new_row)
        self._active_row_index = new_index
        new_row[0].focus_set()

    def prefill(self, chapters: Sequence[ChapterRowValues]) -> None:
        """Replace the grid contents with prefilled chapters.

        Purpose:
            Populate the grid with auto detected or loaded chapters.
        Ties To:
            Used by auto detect and UI workflow initialization.
        Inputs:
            - chapters: Sequence of (title, start, end) string tuples.
        Outputs:
            - None.
        Side Effects:
            Resets and rebuilds the grid rows.
        Raises:
            - ValidationError: When the input exceeds the row limit.
        """
        error_location = f"{__name__}.ChapterGridFrame.prefill"
        if len(chapters) > self._ui_config.row_limit:
            raise ValidationError(
                format_error_message(
                    error_location,
                    f"Prefill exceeds row limit {self._ui_config.row_limit}.",
                )
            )
        new_rows: list[GridRow | None] = []
        try:
            if chapters:
                for title, start_val, end_val in chapters:
                    new_rows.append(self._make_row_widgets(title, start_val, end_val))
            else:
                new_rows.append(self._make_row_widgets("", "", ""))

            self._clear_transient_widgets()
            for row in self._rows:
                if row is None:
                    continue
                for widget in row:
                    widget.grid_forget()
                    widget.destroy()

            self._rows = new_rows
            self._placeholders.clear()
            self.refresh_grid()
            self._maybe_resize()
        except tk.TclError as exc:
            for row in new_rows:
                if row is None:
                    continue
                for widget in row:
                    with suppress(tk.TclError):
                        widget.destroy()
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to prefill grid rows: {exc}",
                )
            ) from exc

    def refresh_grid(self) -> None:
        """Refresh the grid rendering.

        Purpose:
            Re-render all rows and placeholders in the grid.
        Ties To:
            Used after row modifications.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Updates Tk layout.
        Raises:
            - None.
        """
        self._clear_transient_widgets()
        for index, row in enumerate(self._rows):
            self._render_row(index, row)

    def _validate_ui_config(self) -> None:
        """Validate required UI configuration for the grid.

        Purpose:
            Ensure layout values are present before rendering.
        Ties To:
            Called during initialization.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - ValidationError: When UI config is invalid.
        """
        error_location = f"{__name__}.ChapterGridFrame._validate_ui_config"
        if self._ui_config.row_limit < 1:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Row limit must be at least 1.",
                )
            )
        if not self._ui_config.column_widths:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Column widths must not be empty.",
                )
            )
        if self._ui_config.grid_columns < 4:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Grid columns must be at least 4.",
                )
            )
        if len(self._ui_config.grid_header_labels) != self._ui_config.grid_columns:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Grid header labels must match grid column count.",
                )
            )

    def _build_grid(self) -> None:
        """Construct the grid header and the initial row.

        Purpose:
            Initialize the grid structure with headers and one row.
        Ties To:
            Called during initialization.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Creates Tk widgets.
        Raises:
            - None.
        """
        error_location = f"{__name__}.ChapterGridFrame._build_grid"
        try:
            for col, text in enumerate(self._ui_config.grid_header_labels):
                ttk.Label(
                    self._grid,
                    text=text,
                    anchor="w" if col == 0 else "center",
                ).grid(
                    row=0,
                    column=col,
                    padx=self._ui_config.grid_padding_x,
                    pady=self._ui_config.grid_padding_y,
                    sticky="ew",
                )
            for spacer_row in range(1, self._ui_config.header_rows):
                ttk.Label(self._grid, text="").grid(
                    row=spacer_row,
                    column=0,
                    columnspan=self._ui_config.grid_columns,
                )
            self.add_row()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to build grid header: {exc}",
                )
            ) from exc

    def _shift_placeholders(self, start: int, delta: int) -> None:
        """Shift placeholder indices when rows are inserted.

        Purpose:
            Keep placeholder indices aligned with row list positions.
        Ties To:
            Used by add_row when inserting into the row list.
        Inputs:
            - start: Index where the insertion happens.
            - delta: Amount to shift indices by (positive for inserts).
        Outputs:
            - None.
        Side Effects:
            Updates the placeholder dictionary keys.
        Raises:
            - None.
        """
        if delta == 0 or not self._placeholders:
            return
        self._placeholders = shift_indices(self._placeholders, start=start, delta=delta)

    def _first_placeholder_index(self) -> int | None:
        """Return the first placeholder row index if any.

        Purpose:
            Allow reusing deleted row slots when the grid reaches its row limit.
        Ties To:
            Used by add_row.
        Inputs:
            - None.
        Outputs:
            - Index of the first placeholder row, or None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        return first_none_index(self._rows)

    def _maybe_resize(self) -> None:
        """Resize the window based on visible rows.

        Purpose:
            Adjust the window size to fit the current grid rows.
        Ties To:
            Called after row modifications.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Updates the window geometry.
        Raises:
            - None.
        """
        if not hasattr(self.master, "geometry"):
            return

        if hasattr(self.master, "resizable"):
            try:
                if self.master.resizable() != (False, False):
                    return
            except tk.TclError:
                return

        error_location = f"{__name__}.ChapterGridFrame._maybe_resize"
        try:
            visible_rows = len([row for row in self._rows if row is not None])
            self._max_row_count = max(self._max_row_count, visible_rows)

            height = self._ui_config.base_height
            extra_rows = max(0, self._max_row_count - self._ui_config.height_threshold_rows)
            height += extra_rows * self._ui_config.row_height

            columns = (max(self._max_row_count, 1) - 1) // self._ui_config.rows_per_column + 1
            width_index = min(columns - 1, len(self._ui_config.column_widths) - 1)
            width = self._ui_config.column_widths[width_index]

            self.master.geometry(f"{width}x{height}")
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to resize grid window: {exc}",
                )
            ) from exc

    def _make_row_widgets(self, title: str, start_val: str, end_val: str) -> GridRow:
        """Create the widgets for a single row.

        Purpose:
            Build entry fields and buttons for a row.
        Ties To:
            Used by add_row and undo_remove.
        Inputs:
            - title: Chapter title value.
            - start_val: Start page value.
            - end_val: End page value.
        Outputs:
            - Tuple of entry widgets and the remove button.
        Side Effects:
            Creates Tk widgets.
        Raises:
            - None.
        """
        error_location = f"{__name__}.ChapterGridFrame._make_row_widgets"
        try:
            title_entry = ttk.Entry(self._grid)
            start_entry: tk.Entry
            end_entry: tk.Entry
            if self._page_labels:
                start_entry = ttk.Combobox(
                    self._grid,
                    width=self._ui_config.grid_entry_width,
                    values=tuple(self._page_labels),
                    state="readonly",
                )
                end_entry = ttk.Combobox(
                    self._grid,
                    width=self._ui_config.grid_entry_width,
                    values=tuple(self._page_labels),
                    state="readonly",
                )
            else:
                start_entry = ttk.Entry(
                    self._grid,
                    width=self._ui_config.grid_entry_width,
                    validate="key",
                    validatecommand=self._int_validate_cmd,
                )
                end_entry = ttk.Entry(
                    self._grid,
                    width=self._ui_config.grid_entry_width,
                    validate="key",
                    validatecommand=self._int_validate_cmd,
                )
            if title:
                title_entry.insert(0, title)
            if start_val:
                if isinstance(start_entry, ttk.Combobox):
                    start_entry.set(start_val)
                else:
                    start_entry.insert(0, start_val)
            if end_val:
                if isinstance(end_entry, ttk.Combobox):
                    end_entry.set(end_val)
                else:
                    end_entry.insert(0, end_val)
            remove_button = ttk.Button(
                self._grid,
                text=self._ui_config.remove_button_label,
                width=self._ui_config.grid_remove_button_width,
                takefocus=False,
            )
            return title_entry, start_entry, end_entry, remove_button
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to create row widgets: {exc}",
                )
            ) from exc

    def _render_row(self, idx: int, row: GridRow | None) -> None:
        """Render a row or placeholder in the grid.

        Purpose:
            Position widgets for a row or an undo placeholder.
        Ties To:
            Called by refresh_grid after state changes.
        Inputs:
            - idx: Row index.
            - row: Row widgets or None for placeholders.
        Outputs:
            - None.
        Side Effects:
            Updates Tk widget layout.
        Raises:
            - None.
        """
        error_location = f"{__name__}.ChapterGridFrame._render_row"
        try:
            base_col, grid_row = grid_position(
                idx,
                rows_per_column=self._effective_rows_per_column,
                header_rows=self._ui_config.header_rows,
                grid_columns=self._ui_config.grid_columns,
            )

            if row is None and idx in self._placeholders:
                values = self._placeholders[idx]

                def do_undo(vals: ChapterRowValues = values, undo_idx: int = idx) -> None:
                    """Restore a removed row when undo is clicked.

                    Purpose:
                        Provide a local callback for the undo button.
                    Ties To:
                        Used by the undo placeholder rendering.
                    Inputs:
                        - vals: Stored row values.
                        - undo_idx: Row index to restore.
                    Outputs:
                        - None.
                    Side Effects:
                        Restores the row in the grid.
                    Raises:
                        - ValidationError: When undo fails.
                    """
                    self.undo_remove(vals, undo_idx)

                ttk.Button(
                    self._grid,
                    text=self._ui_config.undo_button_label,
                    command=do_undo,
                ).grid(
                    row=grid_row,
                    column=base_col,
                    columnspan=self._ui_config.grid_columns,
                    padx=self._ui_config.grid_padding_x,
                    pady=self._ui_config.grid_padding_y,
                    sticky="ew",
                )
                return

            if row is None:
                return

            title_entry, start_entry, end_entry, remove_button = row
            if not title_entry.get().strip():
                title_entry.insert(0, f"{self._ui_config.chapter_title_prefix} {idx + 1}")

            title_entry.grid(
                row=grid_row,
                column=base_col,
                sticky="ew",
                padx=(self._ui_config.grid_padding_x, self._ui_config.grid_padding_x + 2),
                pady=self._ui_config.grid_padding_y,
            )
            start_entry.grid(
                row=grid_row,
                column=base_col + 1,
                padx=(0, self._ui_config.grid_padding_x),
                pady=self._ui_config.grid_padding_y,
            )
            end_entry.grid(
                row=grid_row,
                column=base_col + 2,
                padx=(0, self._ui_config.grid_padding_x),
                pady=self._ui_config.grid_padding_y,
            )
            remove_col = base_col + self._ui_config.grid_columns - 1

            def _focus(target: tk.Entry) -> str:
                target.focus_set()
                return "break"

            def _advance_from_end(row_idx: int = idx) -> str:
                next_idx = row_idx + 1
                if next_idx < len(self._rows):
                    next_row = self._rows[next_idx]
                    if next_row is not None:
                        next_row[0].focus_set()
                    return "break"
                new_row = self.add_row(insert_idx=next_idx)
                if new_row is not None:
                    new_row[0].focus_set()
                return "break"

            title_entry.bind("<Return>", lambda _event: _focus(start_entry))
            start_entry.bind("<Return>", lambda _event: _focus(end_entry))
            end_entry.bind("<Return>", lambda _event: _advance_from_end())

            def _mark_active(_event: tk.Event[tk.Misc], row_idx: int = idx) -> None:
                self._active_row_index = row_idx

            title_entry.bind("<FocusIn>", _mark_active, add="+")
            start_entry.bind("<FocusIn>", _mark_active, add="+")
            end_entry.bind("<FocusIn>", _mark_active, add="+")

            def do_remove(remove_idx: int = idx) -> None:
                """Remove the current row when the remove button is clicked.

                Purpose:
                    Provide a typed callback for Tkinter command wiring.
                Ties To:
                    Used by _render_row to bind remove_row to the per-row button.
                Inputs:
                    - remove_idx: Row index captured at render time.
                Outputs:
                    - None.
                Side Effects:
                    Removes the row from the UI grid.
                Raises:
                    - ValidationError: When the row index is invalid.
                """
                self.remove_row(remove_idx)

            remove_button.config(
                text=self._ui_config.remove_button_label,
                command=do_remove,
            )
            remove_button.grid(
                row=grid_row,
                column=remove_col,
                padx=self._ui_config.grid_padding_x,
                pady=self._ui_config.grid_padding_y,
                sticky="e",
            )
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to render grid row: {exc}",
                )
            ) from exc

    def _require_row(self, idx: int, location: str) -> GridRow:
        error_location = f"{__name__}.ChapterGridFrame._require_row"
        context = f" Context: {location}." if location else ""
        if idx < 0 or idx >= len(self._rows):
            raise UiError(
                format_error_message(error_location, f"Row index out of range: {idx}.{context}")
            )
        row = self._rows[idx]
        if row is None:
            raise UiError(format_error_message(error_location, f"Row {idx} is empty.{context}"))
        return row

    def _ensure_active_row(self, location: str) -> int:
        error_location = f"{__name__}.ChapterGridFrame._ensure_active_row"
        context = f" Context: {location}." if location else ""
        if (
            self._active_row_index is not None
            and 0 <= self._active_row_index < len(self._rows)
            and self._rows[self._active_row_index] is not None
        ):
            return self._active_row_index
        for idx, row in enumerate(self._rows):
            if row is not None:
                self._active_row_index = idx
                return idx
        new_row = self.add_row()
        if new_row is None:
            raise UiError(format_error_message(error_location, f"Unable to create a row.{context}"))
        idx = self._find_row_index(new_row)
        self._active_row_index = idx
        return idx

    def _last_defined_row_index(self) -> int | None:
        for idx in range(len(self._rows) - 1, -1, -1):
            if self._rows[idx] is not None:
                return idx
        return None

    def _find_row_index(self, widgets: GridRow) -> int:
        for idx, row in enumerate(self._rows):
            if row is widgets:
                return idx
        # Fallback for cases where identity matching fails (should not happen in practice).
        for idx, row in enumerate(self._rows):
            if row is None:
                continue
            if all(a is b for a, b in zip(row, widgets, strict=False)):
                return idx
        return max(0, len(self._rows) - 1)

    def _page_value_for_number(self, page_number: int, location: str) -> str:
        error_location = f"{__name__}.ChapterGridFrame._page_value_for_number"
        context = f" Context: {location}." if location else ""
        if page_number < 1:
            raise ValidationError(
                format_error_message(error_location, f"Page numbers must be >= 1.{context}")
            )
        if self._page_labels is not None:
            if page_number > len(self._page_labels):
                raise ValidationError(
                    format_error_message(
                        error_location,
                        f"Page number {page_number} exceeds available page labels.{context}",
                    )
                )
            return self._page_labels[page_number - 1]
        return str(page_number)

    def _set_field_value(self, field: tk.Entry, value: str, location: str) -> None:
        error_location = f"{__name__}.ChapterGridFrame._set_field_value"
        context = f" Context: {location}." if location else ""
        try:
            if isinstance(field, ttk.Combobox):
                field.set(value)
                return
            field.delete(0, "end")
            field.insert(0, value)
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to set field value.{context}",
                )
            ) from exc

    def _parse_page_value(self, value: str) -> int | None:
        error_location = f"{__name__}.ChapterGridFrame._parse_page_value"
        if not value.strip():
            return None
        if self._page_labels is not None:
            if value not in self._page_labels:
                raise ValidationError(
                    format_error_message(
                        error_location,
                        f"Unknown page label: {value}",
                    )
                )
            return self._page_labels.index(value) + 1
        try:
            return int(value)
        except ValueError as exc:
            raise ValidationError(
                format_error_message(
                    error_location,
                    f"Page value must be an integer: {value}",
                )
            ) from exc

    def _clear_transient_widgets(self) -> None:
        """Remove transient widgets created during rendering.

        Purpose:
            Prevent duplicates and visual artifacts after rerendering.
        Ties To:
            Called by refresh_grid and prefill before re-rendering rows.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Destroys Tk widgets.
        Raises:
            - None.
        """
        error_location = f"{__name__}.ChapterGridFrame._clear_transient_widgets"
        try:
            for widget in self._grid.grid_slaves():
                grid_info = widget.grid_info()
                row_index = int(grid_info.get("row", -1))
                col_index = int(grid_info.get("column", -1))
                if row_index < self._ui_config.header_rows:
                    continue
                if (
                    isinstance(widget, ttk.Button)
                    and col_index % self._ui_config.grid_columns == 0
                    and widget.cget("text") == self._ui_config.undo_button_label
                ):
                    widget.destroy()
                    continue
                spacer_mod = self._ui_config.grid_columns - 2
                if spacer_mod >= 0 and isinstance(widget, ttk.Label):
                    try:
                        label_text = widget.cget("text")
                    except tk.TclError:
                        label_text = ""
                    if (
                        col_index % self._ui_config.grid_columns == spacer_mod
                        and not str(label_text).strip()
                    ):
                        widget.destroy()
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to clear transient widgets: {exc}",
                )
            ) from exc

    def _clear_undo_buttons(self) -> None:
        """Backward-compatible wrapper for clearing transient widgets."""
        self._clear_transient_widgets()
