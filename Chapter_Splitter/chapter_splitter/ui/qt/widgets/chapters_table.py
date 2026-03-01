"""Chapter table widget for the Qt GUI.

Summary:
    Provide an editable table for chapter titles and page boundaries.
Inputs:
    - total_pages: Total page count for bounds validation.
    - title_prefix: Default chapter title prefix for new rows.
Outputs:
    - ChaptersTableWidget instance.
Side effects:
    Creates Qt widgets and manages per-row editors.
Error handling:
    Guards invalid indices and returns safe defaults for missing state.
Ties to other methods:
    Used by MainWindow to store chapter definitions for detect/export flows.
Why this exists:
    Keeping the chapter table logic in one place prevents MainWindow from becoming a blob.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ....core.errors import UiError, format_error_message
from ....core.models import ChapterDefinition
from .chapter_models import ChapterRowWidgets


class ChaptersTableWidget(QtWidgets.QWidget):
    """Editable chapter table.

    Summary:
        Provide a compact table UI with add/remove and start/end edits.
    Inputs:
        - total_pages: Total pages of the document.
        - title_prefix: Default title prefix.
        - parent: Optional Qt parent widget.
    Outputs:
        - QWidget that exposes chapter mutation and extraction helpers.
    Side effects:
        Creates a QTableWidget and editor widgets.
    Error handling:
        Raises UiError for invalid constructor inputs.
    Ties to other methods:
        Used by MainWindow and wired to PDF viewer start/end actions.
    Why this exists:
        The chapter grid is a core surface area; it should be reusable and testable.
    """

    active_row_changed = QtCore.Signal(int)
    chapters_changed = QtCore.Signal()

    def __init__(
        self,
        *,
        total_pages: int,
        title_prefix: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        error_location = f"{__name__}.ChaptersTableWidget.__init__"
        if total_pages <= 0:
            raise UiError(format_error_message(error_location, "total_pages must be positive."))
        if not title_prefix.strip():
            raise UiError(format_error_message(error_location, "title_prefix must be non empty."))

        self._total_pages = int(total_pages)
        self._title_prefix = title_prefix
        self._rows: list[ChapterRowWidgets] = []
        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.setInterval(140)
        self._pulse_active_row: int | None = None
        self._pulse_on = False
        self._pulse_ticks_left = 0
        self._compact_mode = False

        self._table = QtWidgets.QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Chapter", "Start", "End", ""])
        self._table.verticalHeader().setVisible(False)
        scrollbar_as_needed = int(getattr(QtCore.Qt, "ScrollBarAsNeeded", 0))
        self._table.setHorizontalScrollBarPolicy(scrollbar_as_needed)
        self._table.setVerticalScrollBarPolicy(scrollbar_as_needed)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setCornerButtonEnabled(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._apply_row_and_header_metrics()
        spin_width = self._compute_page_spin_width()
        # Add a little column padding so the spinbox does not touch the cell edges.
        self._table.setColumnWidth(1, int(spin_width + 16))
        self._table.setColumnWidth(2, int(spin_width + 16))
        self._table.setColumnWidth(3, 44)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._table, 1)

        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)

    def table(self) -> QtWidgets.QTableWidget:
        """Return the underlying QTableWidget.

        Summary:
            Expose the raw table widget for rare UI-level customization.
        Inputs:
            - None.
        Outputs:
            - QTableWidget instance.
        Side effects:
            None.
        Error handling:
            None.
        Ties to other methods:
            Used by MainWindow for layout and potential styling.
        Why this exists:
            Some Qt APIs require access to the native widget rather than a wrapper.
        """
        return self._table

    def set_compact_mode(self, compact: bool) -> None:
        """Apply compact row and header sizing.

        Summary:
            Reduce row and header heights in constrained layouts.
        Inputs:
            - compact: True for compact mode, otherwise False.
        Outputs:
            - None.
        Side effects:
            Updates table header height, row heights, and editor control heights.
        Error handling:
            Best-effort only; ignores per-widget sizing failures.
        Ties to other methods:
            Called by MainWindow density tuning.
        Why this exists:
            Smaller windows need tighter table density to preserve visible rows.
        """
        self._compact_mode = bool(compact)
        self._apply_row_and_header_metrics()

    def _apply_row_and_header_metrics(self) -> None:
        """Apply table header and row geometry for current density.

        Summary:
            Keep header typography and row heights synchronized to prevent clipped headings.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates header size, default row height, and editor minimum heights.
        Error handling:
            Best-effort only; no-ops when metrics cannot be applied.
        Ties to other methods:
            Called by __init__ and set_compact_mode.
        Why this exists:
            Header text clipping occurs when font and section heights drift apart.
        """
        header_height = 28 if self._compact_mode else 32
        row_height = 34 if self._compact_mode else 38
        try:
            header_view = self._table.horizontalHeader()
            header_view.setMinimumHeight(header_height)
            header_view.setDefaultSectionSize(header_height)
            font = header_view.font()
            font.setPointSize(11 if self._compact_mode else 12)
            header_view.setFont(font)
            self._table.verticalHeader().setDefaultSectionSize(row_height)
            for row_index in range(self._table.rowCount()):
                self._table.setRowHeight(row_index, row_height)
            control_height = 28 if self._compact_mode else 32
            for widgets in self._rows:
                widgets.title.setMinimumHeight(control_height)
                widgets.start.setMinimumHeight(control_height)
                widgets.end.setMinimumHeight(control_height)
                widgets.remove.setMinimumHeight(control_height)
        except Exception:
            return

    def _compute_page_spin_width(self) -> int:
        """Compute a compact width for page spinboxes.

        Summary:
            Size the start and end editors based on the total page count digit length so the
            controls remain tight and the remove button has room.
        Inputs:
            - None.
        Outputs:
            - Pixel width integer for the QSpinBox widget.
        Side effects:
            None.
        Error handling:
            Returns a conservative width when font metrics are unavailable.
        Ties to other methods:
            Used during __init__ and row insertion to size spinboxes consistently.
        Why this exists:
            Oversized numeric inputs waste space and make the remove button feel cramped.
        """
        try:
            digits = max(1, len(str(max(1, int(self._total_pages)))))
            sample = "9" * digits
            metrics = self.fontMetrics()
            text_width = int(metrics.horizontalAdvance(sample))
            # Include internal padding and the spinbox frame and arrows.
            return max(54, min(74, text_width + 34))
        except Exception:
            return 64

    def selected_row_index(self) -> int | None:
        """Return the selected row index, if any.

        Summary:
            Determine which chapter row is currently selected.
        Inputs:
            - None.
        Outputs:
            - Row index integer or None.
        Side effects:
            None.
        Error handling:
            Returns None when selection cannot be resolved.
        Ties to other methods:
            Used by MainWindow to decide which row to mutate for Set Start/End.
        Why this exists:
            Chapter editing is row-based and selection state drives most actions.
        """
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return int(indexes[0].row())

    def row_display_title(self, row_index: int) -> str:
        """Return a user-facing title for a row.

        Summary:
            Provide a stable display string for UI labels and tooltips.
        Inputs:
            - row_index: Row index to query.
        Outputs:
            - Non-empty title string when possible, otherwise a fallback label.
        Side effects:
            None.
        Error handling:
            Returns a fallback string when row widgets are unavailable.
        Ties to other methods:
            Used by MainWindow to surface the active chapter context for Set Start/End.
        Why this exists:
            Embedded editor widgets can make row selection subtle; a top-level label reduces
            ambiguity.
        """
        widgets = self._row_widgets(int(row_index))
        if widgets is None:
            return f"Chapter {int(row_index) + 1}"
        title = widgets.title.text().strip()
        return title if title else f"Chapter {int(row_index) + 1}"

    def active_row_summary(self) -> tuple[int, str] | None:
        """Return the active row index and a concise summary string.

        Summary:
            Provide a compact string like "Chapter 1 (1 to 3)" for header callouts.
        Inputs:
            - None.
        Outputs:
            - Tuple of (row_index, summary) or None when no row is selected.
        Side effects:
            None.
        Error handling:
            Returns None when state cannot be computed.
        Ties to other methods:
            Used by MainWindow to show which chapter Set Start/End will edit.
        Why this exists:
            Users need immediate context for boundary actions without hunting through the table.
        """
        row = self.selected_row_index()
        if row is None:
            return None
        widgets = self._row_widgets(int(row))
        if widgets is None:
            return int(row), self.row_display_title(int(row))
        title = self.row_display_title(int(row))
        start = int(widgets.start.value())
        end = int(widgets.end.value())
        return int(row), f"{title} ({start} to {end})"

    def row_count(self) -> int:
        """Return the current row count.

        Summary:
            Provide a small helper to query whether any chapters exist.
        Inputs:
            - None.
        Outputs:
            - Row count integer.
        Side effects:
            None.
        Error handling:
            Returns 0 when table state cannot be queried.
        Ties to other methods:
            Used by MainWindow to decide whether export should be shown or enabled.
        Why this exists:
            The export step should remain hidden until at least one chapter exists.
        """
        try:
            return int(self._table.rowCount())
        except Exception:
            return 0

    def export_readiness_errors(self) -> list[str]:
        """Return a best-effort list of validation errors for export readiness.

        Summary:
            Perform lightweight UI validation without invoking the full core validation pipeline.
        Inputs:
            - None.
        Outputs:
            - List of human-readable error strings.
        Side effects:
            None.
        Error handling:
            Returns an empty list when errors cannot be computed.
        Ties to other methods:
            Used by MainWindow to disable Export until the user fixes obvious issues.
        Why this exists:
            Disabling export for obviously invalid input improves UX before running the pipeline.
        """
        errors: list[str] = []
        if self.row_count() <= 0:
            errors.append("Add at least one chapter.")
            return errors
        for idx, widgets in enumerate(self._rows, start=1):
            title = widgets.title.text().strip()
            if not title:
                errors.append(f"Chapter {idx} title is empty.")
            start = int(widgets.start.value())
            end = int(widgets.end.value())
            if start < 1 or end < 1:
                errors.append(f"Chapter {idx} pages must be >= 1.")
            if start > self._total_pages or end > self._total_pages:
                errors.append(f"Chapter {idx} pages must be <= {self._total_pages}.")
            if end < start:
                errors.append(f"Chapter {idx} end page must be >= start page.")
        return errors

    def is_ready_for_export(self) -> bool:
        """Return True when chapters are ready for export.

        Summary:
            Provide a fast boolean check for enabling the Export action.
        Inputs:
            - None.
        Outputs:
            - True when export readiness has no errors, otherwise False.
        Side effects:
            None.
        Error handling:
            Returns False on unexpected failures.
        Ties to other methods:
            Used by MainWindow to set Export enabled state.
        Why this exists:
            The main export pipeline should not be invoked when the UI state is obviously invalid.
        """
        try:
            return not self.export_readiness_errors()
        except Exception:
            return False

    def add_blank_chapter(self) -> int:
        """Append a new blank chapter row.

        Summary:
            Add a new row with a default title and unset page boundaries.
        Inputs:
            - None.
        Outputs:
            - Row index of the created row.
        Side effects:
            Mutates the table model and creates editor widgets.
        Error handling:
            Raises UiError when widget creation fails.
        Ties to other methods:
            Called by MainWindow Add menu actions.
        Why this exists:
            Users frequently need to insert chapters manually.
        """
        index = self._table.rowCount()
        title = f"{self._title_prefix} {index + 1}"
        return self._insert_row(index, title=title, start_page=1, end_page=1)

    def add_chapter_at_page(self, page_1based: int) -> int:
        """Append a new chapter row at the provided page.

        Summary:
            Create a new chapter with start/end set to the given page.
        Inputs:
            - page_1based: 1-based page number.
        Outputs:
            - Row index of the created row.
        Side effects:
            Mutates the table model.
        Error handling:
            Clamps invalid page values to valid bounds.
        Ties to other methods:
            Called by MainWindow Add Chapter at Current Page action.
        Why this exists:
            Preview-driven chapter creation is faster than typing page numbers.
        """
        page = max(1, min(int(page_1based), self._total_pages))
        index = self._table.rowCount()
        title = f"{self._title_prefix} {index + 1}"
        return self._insert_row(index, title=title, start_page=page, end_page=page)

    def remove_row(self, row_index: int) -> None:
        """Remove a row by index.

        Summary:
            Delete a chapter row and update internal row widget registry.
        Inputs:
            - row_index: Row index to remove.
        Outputs:
            - None.
        Side effects:
            Mutates the table and internal row list.
        Error handling:
            No-ops when index is out of bounds.
        Ties to other methods:
            Called by the remove button handler.
        Why this exists:
            Removing chapters is a common edit operation during review.
        """
        if row_index < 0 or row_index >= self._table.rowCount():
            return
        self._table.removeRow(int(row_index))
        self._rows.pop(int(row_index))
        self.chapters_changed.emit()

    def set_row_start(self, row_index: int, page_1based: int) -> None:
        """Set the start page for a row.

        Summary:
            Update start page and keep end page >= start page.
        Inputs:
            - row_index: Row index.
            - page_1based: 1-based page number.
        Outputs:
            - None.
        Side effects:
            Mutates spinbox values.
        Error handling:
            No-ops when row cannot be resolved.
        Ties to other methods:
            Used by MainWindow Set Start action.
        Why this exists:
            Start and end boundaries should remain consistent without extra user steps.
        """
        widgets = self._row_widgets(row_index)
        if widgets is None:
            return
        widgets.start.setValue(max(1, min(int(page_1based), self._total_pages)))
        if widgets.end.value() < widgets.start.value():
            widgets.end.setValue(widgets.start.value())
        self.chapters_changed.emit()

    def set_row_end(self, row_index: int, page_1based: int) -> None:
        """Set the end page for a row.

        Summary:
            Update end page and keep start page <= end page.
        Inputs:
            - row_index: Row index.
            - page_1based: 1-based page number.
        Outputs:
            - None.
        Side effects:
            Mutates spinbox values.
        Error handling:
            No-ops when row cannot be resolved.
        Ties to other methods:
            Used by MainWindow Set End action.
        Why this exists:
            Start and end boundaries should remain consistent without extra user steps.
        """
        widgets = self._row_widgets(row_index)
        if widgets is None:
            return
        widgets.end.setValue(max(1, min(int(page_1based), self._total_pages)))
        if widgets.end.value() < widgets.start.value():
            widgets.start.setValue(widgets.end.value())
        self.chapters_changed.emit()

    def set_chapters(self, chapters: list[ChapterDefinition]) -> None:
        """Replace table contents with provided chapters.

        Summary:
            Clear all rows and insert chapters in order.
        Inputs:
            - chapters: ChapterDefinition list.
        Outputs:
            - None.
        Side effects:
            Clears and repopulates the table widget.
        Error handling:
            Clamps start/end pages to valid bounds.
        Ties to other methods:
            Used by detection and TOML import workflows.
        Why this exists:
            The table must be populated from multiple sources deterministically.
        """
        self._table.setRowCount(0)
        self._rows.clear()
        for chapter in chapters:
            start = max(1, min(int(chapter.start_page), self._total_pages))
            end = max(1, min(int(chapter.end_page), self._total_pages))
            self._insert_row(
                self._table.rowCount(),
                title=chapter.title,
                start_page=start,
                end_page=end,
            )
        self.chapters_changed.emit()

    def get_chapters(self) -> list[ChapterDefinition]:
        """Extract chapters from the table.

        Summary:
            Convert row editor values into a list of ChapterDefinition objects.
        Inputs:
            - None.
        Outputs:
            - List of ChapterDefinition objects.
        Side effects:
            None.
        Error handling:
            Uses best-effort defaults for missing titles and page values.
        Ties to other methods:
            Used by export and TOML write workflows.
        Why this exists:
            The workflow needs typed chapter data, not UI widgets.
        """
        chapters: list[ChapterDefinition] = []
        for widgets in self._rows:
            title = widgets.title.text().strip()
            chapters.append(
                ChapterDefinition(
                    title=title,
                    start_page=int(widgets.start.value()),
                    end_page=int(widgets.end.value()),
                )
            )
        return chapters

    def _insert_row(self, row_index: int, *, title: str, start_page: int, end_page: int) -> int:
        error_location = f"{__name__}.ChaptersTableWidget._insert_row"
        if row_index < 0 or row_index > self._table.rowCount():
            raise UiError(format_error_message(error_location, "row_index out of bounds."))

        self._table.insertRow(int(row_index))
        title_edit = QtWidgets.QLineEdit(self._table)
        title_edit.setText(title)
        title_edit.setClearButtonEnabled(True)
        title_edit.setPlaceholderText("Chapter title")
        title_edit.setMinimumHeight(28 if self._compact_mode else 32)

        start_spin = QtWidgets.QSpinBox(self._table)
        start_spin.setRange(1, self._total_pages)
        start_spin.setValue(max(1, min(int(start_page), self._total_pages)))
        start_spin.setFixedWidth(self._compute_page_spin_width())
        start_spin.setMinimumHeight(28 if self._compact_mode else 32)
        start_spin.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        end_spin = QtWidgets.QSpinBox(self._table)
        end_spin.setRange(1, self._total_pages)
        end_spin.setValue(max(1, min(int(end_page), self._total_pages)))
        end_spin.setFixedWidth(self._compute_page_spin_width())
        end_spin.setMinimumHeight(28 if self._compact_mode else 32)
        end_spin.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        remove_btn = QtWidgets.QToolButton(self._table)
        remove_btn.setText("✕")
        remove_btn.setAutoRaise(True)
        remove_btn.setProperty("button_role", "toolbar")
        remove_btn.setProperty("destructive", "true")
        remove_btn.setMinimumHeight(28 if self._compact_mode else 32)
        remove_btn.clicked.connect(self._on_remove_clicked)
        title_edit.textChanged.connect(self._on_editor_changed)
        start_spin.valueChanged.connect(self._on_editor_changed)
        end_spin.valueChanged.connect(self._on_editor_changed)

        self._table.setCellWidget(int(row_index), 0, title_edit)
        self._table.setCellWidget(int(row_index), 1, start_spin)
        self._table.setCellWidget(int(row_index), 2, end_spin)
        self._table.setCellWidget(int(row_index), 3, remove_btn)

        row_widgets = ChapterRowWidgets(
            title=title_edit,
            start=start_spin,
            end=end_spin,
            remove=remove_btn,
        )
        self._rows.insert(int(row_index), row_widgets)
        self._table.setRowHeight(int(row_index), 34 if self._compact_mode else 38)
        self._table.selectRow(int(row_index))
        self._apply_active_row_visuals(int(row_index))
        self._start_row_pulse(int(row_index))
        self.active_row_changed.emit(int(row_index))
        self.chapters_changed.emit()
        return int(row_index)

    def _row_widgets(self, row_index: int) -> ChapterRowWidgets | None:
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[int(row_index)]

    def _on_selection_changed(
        self,
        _selected: QtCore.QItemSelection,
        _deselected: QtCore.QItemSelection,
    ) -> None:
        """Handle table selection changes.

        Summary:
            Emit the active row index when the user selects a different chapter row.
        Inputs:
            - _selected: Qt selection payload (unused).
            - _deselected: Qt deselection payload (unused).
        Outputs:
            - None.
        Side effects:
            Emits active_row_changed.
        Error handling:
            No-ops when there is no selected row.
        Ties to other methods:
            Connected to QItemSelectionModel.selectionChanged in __init__.
        Why this exists:
            Set Start and Set End should operate on the user-selected chapter row.
        """
        row = self.selected_row_index()
        if row is None:
            return
        self._apply_active_row_visuals(int(row))
        self._start_row_pulse(int(row))
        self.active_row_changed.emit(int(row))

    def _start_row_pulse(self, row_index: int) -> None:
        """Start a short pulse highlight on the active row.

        Summary:
            Toggle a dynamic property on the active row widgets for a brief period so it is
            immediately obvious which chapter is selected.
        Inputs:
            - row_index: Active row index.
        Outputs:
            - None.
        Side effects:
            Starts a QTimer and changes dynamic properties on row editor widgets.
        Error handling:
            Best-effort only; ignores update failures.
        Ties to other methods:
            Called when selection changes or when rows are inserted.
        Why this exists:
            A short visual pulse draws attention to the selected chapter without persistent UI
            chrome.
        """
        try:
            self._pulse_timer.stop()
            self._pulse_active_row = int(row_index)
            self._pulse_on = False
            self._pulse_ticks_left = 8
            self._apply_pulse_state()
            self._pulse_timer.start()
        except Exception:
            return

    def _on_pulse_tick(self) -> None:
        """Advance the pulse animation state.

        Summary:
            Flip the pulse highlight on and off a fixed number of times, then clear it.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Updates dynamic properties for the active row widgets.
        Error handling:
            Best-effort only; stops the timer on failures.
        Ties to other methods:
            Triggered by _pulse_timer while a pulse is active.
        Why this exists:
            Timed pulses are cheaper and more consistent than per-frame animations in QSS.
        """
        if self._pulse_active_row is None:
            self._pulse_timer.stop()
            return
        self._pulse_ticks_left -= 1
        self._pulse_on = not self._pulse_on
        self._apply_pulse_state()
        if self._pulse_ticks_left <= 0:
            self._pulse_timer.stop()
            self._pulse_on = False
            self._apply_pulse_state()

    def _apply_pulse_state(self) -> None:
        """Apply the current pulse state to row widgets.

        Summary:
            Set the `pulse` dynamic property on the active row editors and refresh their style so
            the theme stylesheet can tint their background.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates dynamic properties and repolishes widgets.
        Error handling:
            Best-effort only; ignores per-widget polish failures.
        Ties to other methods:
            Called by _start_row_pulse and _on_pulse_tick.
        Why this exists:
            QTableWidget selection painting does not reach embedded editors; properties do.
        """
        active = self._pulse_active_row
        for idx, widgets in enumerate(self._rows):
            enabled = idx == active and self._pulse_on
            value = "true" if enabled else "false"
            widgets.title.setProperty("pulse", value)
            widgets.start.setProperty("pulse", value)
            widgets.end.setProperty("pulse", value)
            widgets.remove.setProperty("pulse", value)
            for widget in (widgets.title, widgets.start, widgets.end, widgets.remove):
                try:
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                except RuntimeError:
                    self._pulse_timer.stop()
                    self._pulse_active_row = None
                    self._pulse_on = False

    def _apply_active_row_visuals(self, row_index: int) -> None:
        """Apply visual emphasis to the active row editors.

        Summary:
            Mark editors in the active row with a dynamic property used by the global stylesheet so
            the selected chapter remains obvious even when cell widgets cover selection painting.
        Inputs:
            - row_index: Active row index.
        Outputs:
            - None.
        Side effects:
            Mutates Qt dynamic properties on row editor widgets.
        Error handling:
            Best-effort only; ignores per-widget update failures.
        Ties to other methods:
            Called from _on_selection_changed and _insert_row.
        Why this exists:
            QTableWidget selection highlighting can be obscured by embedded QLineEdit/QSpinBox cell
            widgets, making it unclear which chapter Set Start/End will target.
        """
        for idx, widgets in enumerate(self._rows):
            is_active = idx == int(row_index)
            value = "true" if is_active else "false"
            with QtCore.QSignalBlocker(widgets.title):
                widgets.title.setProperty("active_row", value)
            with QtCore.QSignalBlocker(widgets.start):
                widgets.start.setProperty("active_row", value)
            with QtCore.QSignalBlocker(widgets.end):
                widgets.end.setProperty("active_row", value)
            with QtCore.QSignalBlocker(widgets.remove):
                widgets.remove.setProperty("active_row", value)
            widgets.title.style().unpolish(widgets.title)
            widgets.title.style().polish(widgets.title)
            widgets.start.style().unpolish(widgets.start)
            widgets.start.style().polish(widgets.start)
            widgets.end.style().unpolish(widgets.end)
            widgets.end.style().polish(widgets.end)
            widgets.remove.style().unpolish(widgets.remove)
            widgets.remove.style().polish(widgets.remove)

    def _on_editor_changed(self, *_args: object) -> None:
        """Handle any editor widget change.

        Summary:
            Emit a single chapters_changed signal whenever any row editor changes.
        Inputs:
            - _args: Ignored Qt signal payload.
        Outputs:
            - None.
        Side effects:
            Emits chapters_changed.
        Error handling:
            None.
        Ties to other methods:
            Connected to line edit and spinbox signals during _insert_row.
        Why this exists:
            Export readiness and review UI should react to edits without polling.
        """
        self.chapters_changed.emit()

    def _on_remove_clicked(self) -> None:
        """Handle a remove button click for the associated row.

        Summary:
            Determine which row's remove button was clicked and delete that row.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Removes a table row and its editor widgets.
        Error handling:
            No-ops when the sender cannot be resolved to a row.
        Ties to other methods:
            Connected to each row's remove button clicked signal.
        Why this exists:
            Row indices can change after insertions and deletions; the sender is stable.
        """
        sender = self.sender()
        if not isinstance(sender, QtWidgets.QToolButton):
            return
        for index, widgets in enumerate(self._rows):
            if widgets.remove is sender:
                self.remove_row(index)
                return
