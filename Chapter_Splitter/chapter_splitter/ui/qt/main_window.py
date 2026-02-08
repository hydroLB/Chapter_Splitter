"""Main Qt window for chapter definition and export.

Summary:
    Provide the primary desktop UI with a vector PDF preview and chapter table.
Inputs:
    - None.
Outputs:
    - MainWindow widget.
Side effects:
    Creates Qt widgets and owns controllers for UI actions.
Error handling:
    Validates inputs and exposes signals for higher-level workflow error handling.
Ties to other methods:
    Constructed by ui.qt.workflow and then shown.
Why this exists:
    The application needs a single cohesive window coordinating preview, chapters, review, and
    export actions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ...config.schema import UIConfig
from ...core.models import ChapterDefinition
from .widgets.chapters_table import ChaptersTableWidget
from .widgets.pdf_viewer import PdfViewerWidget
from .widgets.review_panel import ReviewPanelWidget


@dataclass(frozen=True, slots=True)
class MainWindowActions:
    """Callback bundle for main window commands.

    Summary:
        Provide a typed set of callables so the window can remain UI-only.
    Inputs:
        - on_detect: Detect chapters from the loaded PDF.
        - on_export: Export chapters to PDF files.
        - on_close: Close the window.
        - on_open_in_system_viewer: Open PDF in the system viewer.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Wired by ui.qt.workflow after building the window.
    Why this exists:
        Keeping actions outside the widget prevents UI code from importing core pipelines.
    """

    on_detect: Callable[[], None]
    on_detect_from_current_page: Callable[[int], None]
    on_export_chapters: Callable[[], None]
    on_export_toml: Callable[[], None]
    on_import_toml: Callable[[], None]
    on_save_session: Callable[[], None]
    on_undo_auto_detect: Callable[[], None]
    on_done: Callable[[], None]
    on_close: Callable[[], None]


class MainWindow(QtWidgets.QMainWindow):
    """Main application window.

    Summary:
        Provide the window chrome and host the PDF viewer plus chapter controls.
    Inputs:
        - pdf_path: Loaded PDF path.
        - total_pages: Total pages in the PDF.
        - parent: Optional Qt parent widget.
    Outputs:
        - QMainWindow instance.
    Side effects:
        Creates widgets and layouts.
    Error handling:
        Defensive checks on arguments.
    Ties to other methods:
        Created by ui.qt.workflow.
    Why this exists:
        Main UI shell should be stable while internals evolve.
    """

    def __init__(
        self,
        *,
        pdf_path: Path,
        total_pages: int,
        ui_config: UIConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Create the main window and build child widgets.

        Summary:
            Store immutable window inputs and construct the UI tree.
        Inputs:
            - pdf_path: Selected PDF path.
            - total_pages: Total pages in the PDF.
            - ui_config: UI configuration for labels and defaults.
            - parent: Optional Qt parent widget.
        Outputs:
            - None.
        Side effects:
            Allocates Qt widgets and layouts.
        Error handling:
            Validates constructor arguments and raises for invalid state.
        Ties to other methods:
            Calls _build to create widgets and wire local signals.
        Why this exists:
            The main window owns the UI layout and exposes a small surface for workflows.
        """
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._total_pages = int(total_pages)
        self._ui_config = ui_config
        self._actions: MainWindowActions | None = None

        self._viewer = PdfViewerWidget(self)
        self._build()

    def set_actions(self, actions: MainWindowActions) -> None:
        """Attach workflow actions to UI controls.

        Summary:
            Store the callback bundle and connect UI triggers to workflow functions.
        Inputs:
            - actions: MainWindowActions bundle.
        Outputs:
            - None.
        Side effects:
            Connects Qt signals to the provided callbacks.
        Error handling:
            No-ops when actions are missing.
        Ties to other methods:
            Calls _wire_actions to bind the callbacks.
        Why this exists:
            The window should not import core pipelines directly.
        """
        self._actions = actions
        self._wire_actions()

    def viewer(self) -> PdfViewerWidget:
        """Return the PDF viewer widget.

        Summary:
            Expose the viewer so the workflow can load the selected PDF.
        Inputs:
            - None.
        Outputs:
            - PdfViewerWidget instance.
        Side effects:
            None.
        Error handling:
            None.
        Ties to other methods:
            Used by ui.qt.workflow after constructing MainWindow.
        Why this exists:
            Loading the PDF is a workflow boundary; the viewer is a UI detail owned by the window.
        """
        return self._viewer

    def show_export_tab(self) -> None:
        """Switch to the Export tab.

        Summary:
            Move the right-side tab widget to the final step of the workflow.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Changes the active tab and triggers export state refresh.
        Error handling:
            No-ops when tabs are not initialized.
        Ties to other methods:
            Used by ui.qt.workflow after successful detection when auto-show is enabled.
        Why this exists:
            Detection often implies the next step is review and export.
        """
        try:
            self._tabs.setCurrentIndex(1)
        except Exception:
            return

    def show_chapters_tab(self) -> None:
        """Switch to the Chapters tab.

        Summary:
            Move the right-side tab widget back to chapter editing.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Changes the active tab.
        Error handling:
            No-ops when tabs are not initialized.
        Ties to other methods:
            Can be used by workflows after imports to encourage review.
        Why this exists:
            The tab selection is part of the workflow and should not be hardcoded elsewhere.
        """
        try:
            self._tabs.setCurrentIndex(0)
        except Exception:
            return

    def set_undo_available(self, available: bool) -> None:
        """Enable or disable the Undo button.

        Summary:
            Update the UI so the user can revert the last auto-detect application when available.
        Inputs:
            - available: True when an undo snapshot exists, otherwise False.
        Outputs:
            - None.
        Side effects:
            Enables or disables the Undo button.
        Error handling:
            No-ops when the undo control is not initialized.
        Ties to other methods:
            Called by ui.qt.workflow after applying or undoing auto-detect results.
        Why this exists:
            Auto Detect should be safe to try since the user can quickly revert it.
        """
        try:
            self._undo_btn.setEnabled(bool(available))
        except Exception:
            return

    def export_readiness_errors(self) -> list[str]:
        """Return a list of export readiness errors for the current chapter grid.

        Summary:
            Provide a UI-facing validation list suitable for deciding whether Done can export.
        Inputs:
            - None.
        Outputs:
            - List of human-readable error strings.
        Side effects:
            None.
        Error handling:
            Returns a conservative error when readiness cannot be computed.
        Ties to other methods:
            Delegates to ChaptersTableWidget.export_readiness_errors.
        Why this exists:
            The workflow needs a stable readiness API without reaching into private widget fields.
        """
        try:
            return self._chapters.export_readiness_errors()
        except Exception:
            return ["Unable to validate chapters for export."]

    def is_ready_for_export(self) -> bool:
        """Return True when the current chapters are ready for export.

        Summary:
            Provide a fast readiness check used by Done and Export actions.
        Inputs:
            - None.
        Outputs:
            - True when ready, otherwise False.
        Side effects:
            None.
        Error handling:
            Returns False when readiness cannot be computed.
        Ties to other methods:
            Delegates to ChaptersTableWidget.is_ready_for_export.
        Why this exists:
            Done should be a single-step completion path that blocks when input is invalid.
        """
        try:
            return self._chapters.is_ready_for_export()
        except Exception:
            return False

    def _build(self) -> None:
        """Build the window layout and internal widgets.

        Summary:
            Create the splitter layout, tabs, and action bar for the chapter workflow.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Allocates Qt widgets and connects UI-only handlers.
        Error handling:
            Raises when required constructor inputs are invalid.
        Ties to other methods:
            Called by __init__; wires signals to _on_* handlers.
        Why this exists:
            Keeping widget construction in one method makes the window easier to evolve.
        """
        if not isinstance(self._pdf_path, Path):
            raise TypeError("pdf_path must be a pathlib.Path")
        if self._total_pages <= 0:
            raise ValueError("total_pages must be positive")

        self.setWindowTitle(f"Define Chapters - {self._pdf_path.name}")
        self.resize(1300, 860)

        central = QtWidgets.QWidget(self)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, central)
        splitter.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(splitter)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self._viewer, 1)

        boundary_row = QtWidgets.QHBoxLayout()
        boundary_row.setContentsMargins(0, 0, 0, 0)
        boundary_row.setSpacing(10)
        self._set_start = QtWidgets.QPushButton("Set Start", left)
        self._set_end = QtWidgets.QPushButton("Set End", left)
        boundary_row.addWidget(self._set_start, 1)
        boundary_row.addWidget(self._set_end, 1)
        left_layout.addLayout(boundary_row)

        self._tabs = QtWidgets.QTabWidget(splitter)
        self._tabs.setDocumentMode(True)
        self._tabs.setMovable(False)

        chapters_tab = QtWidgets.QWidget(self._tabs)
        chapters_layout = QtWidgets.QVBoxLayout(chapters_tab)
        chapters_layout.setContentsMargins(12, 12, 12, 12)
        chapters_layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header_label = QtWidgets.QLabel("Chapters", chapters_tab)
        font = header_label.font()
        font.setPointSize(max(11, font.pointSize()))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        header_label.setFont(font)
        header.addWidget(header_label, 1)

        self._add_btn = QtWidgets.QToolButton(chapters_tab)
        self._add_btn.setText(self._ui_config.add_button_label)
        self._add_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QtWidgets.QMenu(self._add_btn)
        self._add_blank_action = add_menu.addAction("Add Blank Chapter")
        self._add_at_page_action = add_menu.addAction("Add Chapter at Current Page")
        self._add_btn.setMenu(add_menu)
        header.addWidget(self._add_btn, 0)

        chapters_layout.addLayout(header)

        self._chapters = ChaptersTableWidget(
            total_pages=self._total_pages,
            title_prefix=self._ui_config.chapter_title_prefix,
            parent=chapters_tab,
        )
        chapters_layout.addWidget(self._chapters, 1)

        review_tab = QtWidgets.QWidget(self._tabs)
        review_layout = QtWidgets.QVBoxLayout(review_tab)
        review_layout.setContentsMargins(12, 12, 12, 12)
        review_layout.setSpacing(10)
        self._review_panel = ReviewPanelWidget(review_tab)
        review_layout.addWidget(self._review_panel, 1)

        self._tabs.addTab(chapters_tab, "Chapters")
        self._tabs.addTab(review_tab, "Export")

        splitter.addWidget(left)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, 1)

        action_bar = QtWidgets.QHBoxLayout()
        action_bar.setContentsMargins(0, 0, 0, 0)
        action_bar.setSpacing(10)

        self._file_btn = QtWidgets.QToolButton(central)
        self._file_btn.setText("File")
        self._file_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self._file_menu = QtWidgets.QMenu(self._file_btn)
        self._import_toml_action = self._file_menu.addAction("Import Chapters (TOML)")
        self._file_btn.setMenu(self._file_menu)

        self._detect_btn = QtWidgets.QToolButton(central)
        self._detect_btn.setText(self._ui_config.auto_detect_button_label)
        self._detect_btn.setToolTip("Auto-detect chapters and apply results automatically.")

        action_bar.addWidget(self._file_btn, 0)
        action_bar.addWidget(self._detect_btn, 0)
        self._undo_btn = QtWidgets.QToolButton(central)
        self._undo_btn.setText(self._ui_config.undo_button_label)
        self._undo_btn.setEnabled(False)
        self._undo_btn.setToolTip("Undo the last Auto Detect apply")
        action_bar.addWidget(self._undo_btn, 0)
        action_bar.addStretch(1)

        self._export_btn = QtWidgets.QToolButton(central)
        self._export_btn.setText(self._ui_config.export_button_label)
        self._export_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self._export_menu = QtWidgets.QMenu(self._export_btn)
        self._export_chapters_action = self._export_menu.addAction("Export Chapters")
        self._export_toml_action = self._export_menu.addAction("Export TOML")
        self._save_session_action = self._export_menu.addAction("Save Session")
        self._export_btn.setMenu(self._export_menu)
        self._export_btn.setVisible(False)
        action_bar.addWidget(self._export_btn, 0)

        self._done_btn = QtWidgets.QPushButton(self._ui_config.close_button_label, central)
        action_bar.addWidget(self._done_btn, 0)

        root.addLayout(action_bar)
        self.setCentralWidget(central)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._add_blank_action.triggered.connect(self._on_add_blank)
        self._add_at_page_action.triggered.connect(self._on_add_at_current_page)
        self._set_start.clicked.connect(self._on_set_start)
        self._set_end.clicked.connect(self._on_set_end)
        self._chapters.chapters_changed.connect(self._on_chapters_changed)
        self._chapters.active_row_changed.connect(self._on_active_row_changed)
        self._sync_export_state()
        self._refresh_active_row_context()

    def _wire_actions(self) -> None:
        """Connect workflow callbacks to UI triggers.

        Summary:
            Bind action callbacks provided by the workflow to UI elements.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Connects Qt signals and menu actions.
        Error handling:
            Returns early when actions are not yet set.
        Ties to other methods:
            Called by set_actions.
        Why this exists:
            Avoid importing pipeline code into UI widgets.
        """
        if self._actions is None:
            return
        self._done_btn.clicked.connect(self._actions.on_done)
        self._import_toml_action.triggered.connect(self._actions.on_import_toml)
        self._detect_btn.clicked.connect(self._actions.on_detect)
        self._undo_btn.clicked.connect(self._actions.on_undo_auto_detect)
        self._export_chapters_action.triggered.connect(self._actions.on_export_chapters)
        self._export_toml_action.triggered.connect(self._actions.on_export_toml)
        self._save_session_action.triggered.connect(self._actions.on_save_session)

    def _on_tab_changed(self, index: int) -> None:
        """Toggle export visibility based on active tab.

        Summary:
            Keep export actions out of the primary flow until the user switches to Review.
        Inputs:
            - index: Tab index for the QTabWidget.
        Outputs:
            - None.
        Side effects:
            Shows or hides the Export split button.
        Error handling:
            None.
        Ties to other methods:
            Connected to the tab widget currentChanged signal.
        Why this exists:
            The default workflow is detect and edit first, then export.
        """
        self._sync_export_state()
        if index == 1:
            self._refresh_review()

    def _on_chapters_changed(self) -> None:
        """Handle chapter grid changes.

        Summary:
            Re-evaluate export readiness and refresh the Export tab when visible.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Updates export button state and review panel content.
        Error handling:
            Best-effort refresh to avoid UI breakage due to transient editor state.
        Ties to other methods:
            Connected to ChaptersTableWidget.chapters_changed.
        Why this exists:
            Users should see export readiness feedback immediately as they edit chapters.
        """
        self._sync_export_state()
        self._refresh_active_row_context()
        if self._tabs.currentIndex() == 1:
            self._refresh_review()

    def _on_active_row_changed(self, _row_index: int) -> None:
        """Handle active chapter row changes.

        Summary:
            Refresh the "Editing" callout and Set Start/End tooltips when the user changes the
            selected chapter.
        Inputs:
            - _row_index: Active row index (unused; state is read from the chapter table).
        Outputs:
            - None.
        Side effects:
            Updates labels and button tooltips.
        Error handling:
            Best-effort only; falls back to generic tooltips when state cannot be computed.
        Ties to other methods:
            Connected to ChaptersTableWidget.active_row_changed in _build.
        Why this exists:
            Embedded editors can make selection subtle; a persistent callout removes ambiguity.
        """
        self._refresh_active_row_context()

    def _refresh_active_row_context(self) -> None:
        """Refresh the UI context for Set Start/End actions.

        Summary:
            Show which chapter is being edited and update boundary button tooltips accordingly.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the callout label and tooltips for Set Start/End buttons.
        Error handling:
            Falls back to generic messaging when the active row cannot be resolved.
        Ties to other methods:
            Called after chapter edits, selection changes, and initial build.
        Why this exists:
            Set Start/End are global actions and should always feel anchored to a specific chapter.
        """
        summary = None
        try:
            summary = self._chapters.active_row_summary()
        except Exception:
            summary = None

        if summary is None:
            self._set_start.setToolTip("Set start for the selected chapter to the current page.")
            self._set_end.setToolTip("Set end for the selected chapter to the current page.")
            return

        _row_index, text = summary
        self._set_start.setToolTip(f"Set start for {text} to the current page.")
        self._set_end.setToolTip(f"Set end for {text} to the current page.")

    def _sync_export_state(self) -> None:
        """Sync Export button visibility and enabled state.

        Summary:
            Show Export only on the Export tab and only after chapters exist.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates export button visibility and enabled state.
        Error handling:
            Uses conservative defaults when table state cannot be queried.
        Ties to other methods:
            Called by tab changes and chapter edits.
        Why this exists:
            Export should appear only when the user reaches the final step and the input is valid.
        """
        on_export_tab = self._tabs.currentIndex() == 1
        has_any = self._chapters.row_count() > 0
        ready = self._chapters.is_ready_for_export()
        self._export_btn.setVisible(bool(on_export_tab and has_any))
        self._export_btn.setEnabled(bool(ready))
        self._export_chapters_action.setEnabled(bool(ready))
        self._export_toml_action.setEnabled(bool(has_any))
        self._save_session_action.setEnabled(bool(has_any))

    def _refresh_review(self) -> None:
        """Refresh the Export tab review panel.

        Summary:
            Render a read-only chapter list and inline validation errors.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Updates ReviewPanelWidget content.
        Error handling:
            No-ops when review panel is not initialized.
        Ties to other methods:
            Called when entering the Export tab or when chapters change while on the tab.
        Why this exists:
            The Export step should be self-explanatory and show exactly what will be exported.
        """
        try:
            self._review_panel.set_state(
                chapters=self._chapters.get_chapters(),
                errors=self._chapters.export_readiness_errors(),
            )
        except Exception:
            return

    def chapters(self) -> list[ChapterDefinition]:
        """Return current chapters from the table.

        Summary:
            Extract the chapter definitions currently represented in the chapter grid.
        Inputs:
            - None.
        Outputs:
            - List of ChapterDefinition objects.
        Side effects:
            None.
        Error handling:
            Returns best-effort values from the table editors.
        Ties to other methods:
            Used by ui.qt.workflow before export and TOML writes.
        Why this exists:
            The workflow needs a stable way to read UI state without reaching into widgets.
        """
        return self._chapters.get_chapters()

    def set_chapters(self, chapters: list[ChapterDefinition]) -> None:
        """Replace table content with chapters.

        Summary:
            Clear existing rows and populate the grid from a chapter list.
        Inputs:
            - chapters: ChapterDefinition list to display.
        Outputs:
            - None.
        Side effects:
            Mutates the chapter grid UI.
        Error handling:
            Clamps pages to valid bounds and skips invalid entries.
        Ties to other methods:
            Used by ui.qt.workflow after detection or TOML import.
        Why this exists:
            Detection and import are pipeline features; the window should be able to render both.
        """
        self._chapters.set_chapters(chapters)

    def _ensure_row_selected(self) -> int:
        """Ensure a chapter row is selected and return its index.

        Summary:
            Create a new row when none is selected so Set Start/End always works.
        Inputs:
            - None.
        Outputs:
            - Row index to mutate.
        Side effects:
            May create a new chapter row.
        Error handling:
            Falls back to row 0 when selection queries fail.
        Ties to other methods:
            Used by _on_set_start and _on_set_end.
        Why this exists:
            Reduces user friction by removing the need to explicitly select before setting pages.
        """
        row = self._chapters.selected_row_index()
        if row is None:
            return self._chapters.add_blank_chapter()
        return int(row)

    def _on_add_blank(self) -> None:
        """Add a blank chapter row.

        Summary:
            Append a new chapter row with default title and boundary values.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the chapter grid UI.
        Error handling:
            Relies on ChaptersTableWidget to validate and raise for construction failures.
        Ties to other methods:
            Connected to the Add Blank Chapter menu action.
        Why this exists:
            Manual chapter entry is the primary fallback when detection is not accurate.
        """
        self._chapters.add_blank_chapter()

    def _on_add_at_current_page(self) -> None:
        """Add a chapter row at the current viewer page.

        Summary:
            Append a row and set start and end to the current page in the PDF viewer.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the chapter grid UI.
        Error handling:
            Clamps pages to valid bounds.
        Ties to other methods:
            Uses PdfViewerWidget.current_page_1based and ChaptersTableWidget.add_chapter_at_page.
        Why this exists:
            Clicking while reading is faster than typing page numbers.
        """
        page = self._viewer.current_page_1based()
        self._chapters.add_chapter_at_page(page)

    def _on_set_start(self) -> None:
        """Set the selected row start to the current page.

        Summary:
            Use the PDF viewer current page as the start boundary for the active chapter.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the start spinbox value for the selected row.
        Error handling:
            Creates a row when none is selected.
        Ties to other methods:
            Uses _ensure_row_selected and ChaptersTableWidget.set_row_start.
        Why this exists:
            Start and end boundaries should be set from the preview with minimal typing.
        """
        row = self._ensure_row_selected()
        self._chapters.set_row_start(row, self._viewer.current_page_1based())

    def _on_set_end(self) -> None:
        """Set the selected row end to the current page.

        Summary:
            Use the PDF viewer current page as the end boundary for the active chapter.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the end spinbox value for the selected row.
        Error handling:
            Creates a row when none is selected.
        Ties to other methods:
            Uses _ensure_row_selected and ChaptersTableWidget.set_row_end.
        Why this exists:
            End boundary selection should be one click while reading.
        """
        row = self._ensure_row_selected()
        self._chapters.set_row_end(row, self._viewer.current_page_1based())

    # Auto Detect from current page was removed from the primary UI to keep the workflow simple.
