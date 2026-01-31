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

        self._validate_ui_config()
        if hasattr(self.master, "resizable"):
            self.master.resizable(False, False)
        self._build_grid()
        if prefill_chapters:
            self.prefill(prefill_chapters)

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
                ttk.Label(self, text=text).grid(
                    row=0,
                    column=col,
                    padx=self._ui_config.grid_padding_x,
                    pady=self._ui_config.grid_padding_y,
                )
            for spacer_row in range(1, self._ui_config.header_rows):
                ttk.Label(self, text="").grid(
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
            title_entry = ttk.Entry(self, width=self._ui_config.grid_entry_width)
            start_entry = ttk.Entry(self, width=self._ui_config.grid_entry_width)
            end_entry = ttk.Entry(self, width=self._ui_config.grid_entry_width)
            if title:
                title_entry.insert(0, title)
            if start_val:
                start_entry.insert(0, start_val)
            if end_val:
                end_entry.insert(0, end_val)
            remove_button = ttk.Button(
                self,
                text=self._ui_config.remove_button_label,
                width=self._ui_config.grid_remove_button_width,
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
                rows_per_column=self._ui_config.rows_per_column,
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

                ttk.Button(self, text=self._ui_config.undo_button_label, command=do_undo).grid(
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
                sticky="w",
                padx=self._ui_config.grid_padding_x,
                pady=self._ui_config.grid_padding_y,
            )
            start_entry.grid(
                row=grid_row,
                column=base_col + 1,
                padx=self._ui_config.grid_padding_x,
                pady=self._ui_config.grid_padding_y,
            )
            end_entry.grid(
                row=grid_row,
                column=base_col + 2,
                padx=self._ui_config.grid_padding_x,
                pady=self._ui_config.grid_padding_y,
            )
            remove_col = base_col + self._ui_config.grid_columns - 1

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
            )
        except tk.TclError as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to render grid row: {exc}",
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
            for widget in self.grid_slaves():
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
