"""Chapter table widget for the Qt GUI."""

from __future__ import annotations

from typing import Any, cast

from PySide6 import QtCore, QtWidgets

from ....config.schema import ValidationConfig
from ....core.errors import UiError, format_error_message
from ....core.models import ChapterDefinition
from ...workflow_validation import (
    export_readiness_errors,
    validate_chapter_ranges_for_document,
)
from .chapter_models import ChapterRowWidgets


class ChaptersTableWidget(QtWidgets.QWidget):
    """Editable chapter table."""

    active_row_changed = QtCore.Signal(int)
    chapters_changed = QtCore.Signal()

    def __init__(
        self,
        *,
        total_pages: int,
        title_prefix: str,
        validation_config: ValidationConfig,
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
        self._validation_config = validation_config
        self._rows: list[ChapterRowWidgets] = []
        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.setInterval(140)
        self._pulse_active_row: int | None = None
        self._pulse_on = False
        self._pulse_ticks_left = 0
        self._compact_mode = False

        self._table = QtWidgets.QTableWidget(0, 4, self)
        self._table.setAccessibleName("Chapter definitions")
        self._table.setHorizontalHeaderLabels(["Chapter", "Start", "End", ""])
        self._table.verticalHeader().setVisible(False)
        scrollbar_as_needed = getattr(
            QtCore.Qt,
            "ScrollBarAsNeeded",
            cast(Any, QtCore.Qt).ScrollBarPolicy.ScrollBarAsNeeded,
        )
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
        """Return the underlying QTableWidget."""
        return self._table

    def set_compact_mode(self, compact: bool) -> None:
        """Apply compact row and header sizing."""
        self._compact_mode = bool(compact)
        self._apply_row_and_header_metrics()

    def _apply_row_and_header_metrics(self) -> None:
        """Apply table header and row geometry for current density."""
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
        """Compute a compact width for page spinboxes."""
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
        """Return the selected row index, if any."""
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return int(indexes[0].row())

    def row_display_title(self, row_index: int) -> str:
        """Return a user-facing title for a row."""
        widgets = self._row_widgets(int(row_index))
        if widgets is None:
            return f"Chapter {int(row_index) + 1}"
        title = widgets.title.text().strip()
        return title if title else f"Chapter {int(row_index) + 1}"

    def active_row_summary(self) -> tuple[int, str] | None:
        """Return the active row index and a concise summary string."""
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
        """Return the current row count."""
        try:
            return int(self._table.rowCount())
        except Exception:
            return 0

    def export_readiness_errors(self) -> list[str]:
        """Return the core validation error that currently blocks export."""
        return export_readiness_errors(
            chapters=self.get_chapters(),
            total_pages=self._total_pages,
            validation_config=self._validation_config,
            location=f"{__name__}.ChaptersTableWidget.export_readiness_errors",
        )

    def is_ready_for_export(self) -> bool:
        """Return True when chapters are ready for export."""
        try:
            return not self.export_readiness_errors()
        except Exception:
            return False

    def add_blank_chapter(self) -> int:
        """Append a new blank chapter row."""
        index = self._table.rowCount()
        title = f"{self._title_prefix} {index + 1}"
        return self._insert_row(index, title=title, start_page=1, end_page=1)

    def add_chapter_at_page(self, page_1based: int) -> int:
        """Append a new chapter row at the provided page."""
        page = max(1, min(int(page_1based), self._total_pages))
        index = self._table.rowCount()
        title = f"{self._title_prefix} {index + 1}"
        return self._insert_row(index, title=title, start_page=page, end_page=page)

    def remove_row(self, row_index: int) -> None:
        """Remove a row by index."""
        if row_index < 0 or row_index >= self._table.rowCount():
            return
        self._table.removeRow(int(row_index))
        self._rows.pop(int(row_index))
        self._refresh_row_accessibility()
        self.chapters_changed.emit()

    def set_row_start(self, row_index: int, page_1based: int) -> None:
        """Set the start page for a row."""
        widgets = self._row_widgets(row_index)
        if widgets is None:
            return
        widgets.start.setValue(max(1, min(int(page_1based), self._total_pages)))
        if widgets.end.value() < widgets.start.value():
            widgets.end.setValue(widgets.start.value())
        self.chapters_changed.emit()

    def set_row_end(self, row_index: int, page_1based: int) -> None:
        """Set the end page for a row."""
        widgets = self._row_widgets(row_index)
        if widgets is None:
            return
        widgets.end.setValue(max(1, min(int(page_1based), self._total_pages)))
        if widgets.end.value() < widgets.start.value():
            widgets.start.setValue(widgets.end.value())
        self.chapters_changed.emit()

    def set_chapters(self, chapters: list[ChapterDefinition]) -> None:
        """Replace table contents with provided chapters."""
        replacement = list(chapters)
        validate_chapter_ranges_for_document(
            chapters=replacement,
            total_pages=self._total_pages,
            location=f"{__name__}.ChaptersTableWidget.set_chapters",
        )

        with QtCore.QSignalBlocker(self):
            self._table.setRowCount(0)
            self._rows.clear()
            for chapter in replacement:
                self._insert_row(
                    self._table.rowCount(),
                    title=chapter.title,
                    start_page=chapter.start_page,
                    end_page=chapter.end_page,
                )
        self.chapters_changed.emit()

    def get_chapters(self) -> list[ChapterDefinition]:
        """Extract chapters from the table."""
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

        # QTableWidget does not receive cell clicks when an embedded editor consumes the event.
        # Watch both the editors and their child widgets (notably a spinbox's line edit) so mouse
        # and keyboard focus always make the edited chapter the active row first.
        for editor in (title_edit, start_spin, end_spin):
            editor.installEventFilter(self)
            for child in editor.findChildren(QtWidgets.QWidget):
                child.installEventFilter(self)

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
        self._refresh_row_accessibility()
        self._table.setRowHeight(int(row_index), 34 if self._compact_mode else 38)
        self._table.selectRow(int(row_index))
        self._apply_active_row_visuals(int(row_index))
        self._start_row_pulse(int(row_index))
        self.active_row_changed.emit(int(row_index))
        self.chapters_changed.emit()
        return int(row_index)

    def _refresh_row_accessibility(self) -> None:
        """Keep accessible editor names aligned after insertions and removals."""
        for row_number, widgets in enumerate(self._rows, start=1):
            widgets.title.setAccessibleName(f"Chapter {row_number} title")
            widgets.start.setAccessibleName(f"Chapter {row_number} start page")
            widgets.end.setAccessibleName(f"Chapter {row_number} end page")
            widgets.remove.setAccessibleName(f"Remove chapter {row_number}")
            widgets.remove.setToolTip(f"Remove chapter {row_number}")

    def _row_widgets(self, row_index: int) -> ChapterRowWidgets | None:
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[int(row_index)]

    def eventFilter(self, watched: QtCore.QObject, event: Any) -> bool:
        """Select the row belonging to an editor before it handles focus or a click.

        Embedded cell widgets consume input events before QTableWidget can update its selection.
        Resolving the row from the live widget registry also remains correct after rows are removed.
        """
        event_types = cast(Any, QtCore).QEvent.Type
        if event.type() in (event_types.FocusIn, event_types.MouseButtonPress):
            row_index = self._row_index_for_editor(watched)
            if row_index is not None and self.selected_row_index() != row_index:
                self._table.selectRow(row_index)
        return bool(cast(Any, super()).eventFilter(watched, event))

    def _row_index_for_editor(self, watched: QtCore.QObject) -> int | None:
        """Return the row containing an editor or one of its child widgets."""
        if not isinstance(watched, QtWidgets.QWidget):
            return None
        for row_index, widgets in enumerate(self._rows):
            for editor in (widgets.title, widgets.start, widgets.end):
                if watched is editor or editor.isAncestorOf(watched):
                    return row_index
        return None

    def _on_selection_changed(
        self,
        _selected: QtCore.QItemSelection,
        _deselected: QtCore.QItemSelection,
    ) -> None:
        """Handle table selection changes."""
        row = self.selected_row_index()
        if row is None:
            return
        self._apply_active_row_visuals(int(row))
        self._start_row_pulse(int(row))
        self.active_row_changed.emit(int(row))

    def _start_row_pulse(self, row_index: int) -> None:
        """Start a short pulse highlight on the active row."""
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
        """Advance the pulse animation state."""
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
        """Apply the current pulse state to row widgets."""
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
        """Apply visual emphasis to the active row editors."""
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
        """Handle any editor widget change."""
        self.chapters_changed.emit()

    def _on_remove_clicked(self) -> None:
        """Handle a remove button click for the associated row."""
        sender = self.sender()
        if not isinstance(sender, QtWidgets.QToolButton):
            return
        for index, widgets in enumerate(self._rows):
            if widgets.remove is sender:
                self.remove_row(index)
                return
