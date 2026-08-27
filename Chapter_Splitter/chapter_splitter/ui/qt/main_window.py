"""Main Qt window for chapter definition and export."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6 import QtCore, QtGui, QtWidgets

from ...config.schema import UIConfig, ValidationConfig
from ...core.models import ChapterDefinition
from .widgets.chapters_table import ChaptersTableWidget
from .widgets.pdf_viewer import PdfViewerWidget
from .widgets.review_panel import ReviewPanelWidget

StatusLevel = Literal["ready", "working", "success", "error"]


@dataclass(frozen=True, slots=True)
class MainWindowActions:
    """Callback bundle for main window commands."""

    on_detect: Callable[[], None]
    on_export_chapters: Callable[[], None]
    on_export_toml: Callable[[], None]
    on_import_toml: Callable[[], None]
    on_save_session: Callable[[], None]
    on_undo_auto_detect: Callable[[], None]
    on_done: Callable[[], None]


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(
        self,
        *,
        pdf_path: Path,
        total_pages: int,
        ui_config: UIConfig,
        validation_config: ValidationConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Create the main window and build child widgets."""
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._total_pages = int(total_pages)
        self._ui_config = ui_config
        self._validation_config = validation_config
        self._actions: MainWindowActions | None = None

        self._viewer = PdfViewerWidget(self)
        self._build()

    def set_actions(self, actions: MainWindowActions) -> None:
        """Attach workflow actions to UI controls."""
        self._actions = actions
        self._wire_actions()

    def viewer(self) -> PdfViewerWidget:
        """Return the PDF viewer widget."""
        return self._viewer

    def show_export_tab(self) -> None:
        """Switch to the Export tab."""
        try:
            self._tabs.setCurrentIndex(1)
        except Exception:
            return

    def show_chapters_tab(self) -> None:
        """Switch to the Chapters tab."""
        try:
            self._tabs.setCurrentIndex(0)
        except Exception:
            return

    def set_undo_available(self, available: bool) -> None:
        """Enable or disable the Undo button."""
        try:
            self._undo_btn.setEnabled(bool(available))
        except Exception:
            return

    def export_readiness_errors(self) -> list[str]:
        """Return a list of export readiness errors for the current chapter grid."""
        try:
            return self._chapters.export_readiness_errors()
        except Exception:
            return ["Unable to validate chapters for export."]

    def is_ready_for_export(self) -> bool:
        """Return True when the current chapters are ready for export."""
        try:
            return self._chapters.is_ready_for_export()
        except Exception:
            return False

    def set_status(self, *, level: StatusLevel, text: str) -> None:
        """Set the status badge text and semantic level."""
        try:
            self._status_label.setText(text)
            self._status_label.setAccessibleDescription(text)
            self._status_label.setProperty("status_level", level)
            self._status_label.style().unpolish(self._status_label)
            self._status_label.style().polish(self._status_label)
        except Exception:
            return

    def _build(self) -> None:
        """Build the window layout and internal widgets."""
        if not isinstance(self._pdf_path, Path):
            raise TypeError("pdf_path must be a pathlib.Path")
        if self._total_pages <= 0:
            raise ValueError("total_pages must be positive")

        self.setWindowTitle(f"{self._ui_config.chapter_window_title} - {self._pdf_path.name}")
        self.resize(self._ui_config.window_width, self._ui_config.window_height)

        central = QtWidgets.QWidget(self)
        central.setObjectName("chapterSplitterRoot")
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, central)
        splitter.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(splitter)
        left.setProperty("container_role", "outer_section")
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        viewer_frame = QtWidgets.QWidget(left)
        viewer_frame.setProperty("container_role", "inset_content")
        viewer_layout = QtWidgets.QVBoxLayout(viewer_frame)
        viewer_layout.setContentsMargins(8, 8, 8, 8)
        viewer_layout.setSpacing(8)
        viewer_layout.addWidget(self._viewer, 1)
        left_layout.addWidget(viewer_frame, 1)

        boundary_row = QtWidgets.QHBoxLayout()
        boundary_row.setContentsMargins(0, 0, 0, 0)
        boundary_row.setSpacing(10)
        self._set_start = QtWidgets.QPushButton("Set Start", left)
        self._set_start.setProperty("button_role", "default")
        self._set_end = QtWidgets.QPushButton("Set End", left)
        self._set_end.setProperty("button_role", "default")
        boundary_row.addWidget(self._set_start, 1)
        boundary_row.addWidget(self._set_end, 1)
        left_layout.addLayout(boundary_row)

        self._tabs = QtWidgets.QTabWidget(splitter)
        self._tabs.setDocumentMode(True)
        self._tabs.setMovable(False)

        chapters_tab = QtWidgets.QWidget(self._tabs)
        chapters_shell = QtWidgets.QVBoxLayout(chapters_tab)
        chapters_shell.setContentsMargins(0, 0, 0, 0)
        chapters_shell.setSpacing(0)
        chapters_container = QtWidgets.QWidget(chapters_tab)
        chapters_container.setProperty("container_role", "outer_section")
        chapters_shell.addWidget(chapters_container, 1)
        chapters_layout = QtWidgets.QVBoxLayout(chapters_container)
        chapters_layout.setContentsMargins(12, 12, 12, 12)
        chapters_layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header_label = QtWidgets.QLabel("Chapters", chapters_container)
        header_label.setProperty("text_role", "section_header")
        font = header_label.font()
        font.setPointSize(max(11, font.pointSize()))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        header_label.setFont(font)
        header.addWidget(header_label, 0)

        self._active_row_label = QtWidgets.QLabel(
            "Editing: No chapter selected",
            chapters_container,
        )
        self._active_row_label.setProperty("text_role", "hint")
        header.addWidget(self._active_row_label, 1)

        self._add_btn = QtWidgets.QToolButton(chapters_container)
        self._add_btn.setProperty("button_role", "toolbar")
        self._add_btn.setText(self._ui_config.add_button_label)
        self._add_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QtWidgets.QMenu(self._add_btn)
        self._add_blank_action = add_menu.addAction("Add Blank Chapter")
        self._add_at_page_action = add_menu.addAction("Add Chapter at Current Page")
        self._add_btn.setMenu(add_menu)
        header.addWidget(self._add_btn, 0)

        chapters_layout.addLayout(header)

        chapters_frame = QtWidgets.QWidget(chapters_container)
        chapters_frame.setProperty("container_role", "inset_content")
        chapters_frame_layout = QtWidgets.QVBoxLayout(chapters_frame)
        chapters_frame_layout.setContentsMargins(8, 8, 8, 8)
        chapters_frame_layout.setSpacing(0)
        self._chapters = ChaptersTableWidget(
            total_pages=self._total_pages,
            title_prefix=self._ui_config.chapter_title_prefix,
            validation_config=self._validation_config,
            parent=chapters_frame,
        )
        chapters_frame_layout.addWidget(self._chapters, 1)
        chapters_layout.addWidget(chapters_frame, 1)

        review_tab = QtWidgets.QWidget(self._tabs)
        review_shell = QtWidgets.QVBoxLayout(review_tab)
        review_shell.setContentsMargins(0, 0, 0, 0)
        review_shell.setSpacing(0)
        review_container = QtWidgets.QWidget(review_tab)
        review_container.setProperty("container_role", "outer_section")
        review_shell.addWidget(review_container, 1)
        review_layout = QtWidgets.QVBoxLayout(review_container)
        review_layout.setContentsMargins(12, 12, 12, 12)
        review_layout.setSpacing(10)
        self._review_panel = ReviewPanelWidget(review_container)
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
        self._file_btn.setProperty("button_role", "toolbar")
        self._file_btn.setText("File")
        self._file_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self._file_menu = QtWidgets.QMenu(self._file_btn)
        self._import_toml_action = self._file_menu.addAction("Import Chapters (TOML)")
        self._file_btn.setMenu(self._file_menu)

        self._detect_btn = QtWidgets.QToolButton(central)
        self._detect_btn.setProperty("button_role", "toolbar")
        self._detect_btn.setText(self._ui_config.auto_detect_button_label)
        self._detect_btn.setToolTip("Auto-detect chapters and apply results automatically.")

        action_bar.addWidget(self._file_btn, 0)
        action_bar.addWidget(self._detect_btn, 0)
        self._undo_btn = QtWidgets.QToolButton(central)
        self._undo_btn.setProperty("button_role", "toolbar")
        self._undo_btn.setText(self._ui_config.undo_button_label)
        self._undo_btn.setEnabled(False)
        self._undo_btn.setToolTip("Undo the last Auto Detect apply")
        action_bar.addWidget(self._undo_btn, 0)
        self._status_label = QtWidgets.QLabel("Ready", central)
        self._status_label.setProperty("text_role", "status")
        self._status_label.setProperty("status_level", "ready")
        self._status_label.setAccessibleName("Application status")
        action_bar.addWidget(self._status_label, 0)
        action_bar.addStretch(1)

        self._export_btn = QtWidgets.QToolButton(central)
        self._export_btn.setProperty("button_role", "toolbar")
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
        self._done_btn.setProperty("button_role", "primary_cta")
        self._done_btn.setMinimumHeight(36)
        action_bar.addWidget(self._done_btn, 0)

        root.addLayout(action_bar)
        self.setCentralWidget(central)
        self._root_layout = root
        self._left_layout = left_layout
        self._viewer_layout = viewer_layout
        self._boundary_row_layout = boundary_row
        self._chapters_layout = chapters_layout
        self._review_layout = review_layout
        self._action_bar_layout = action_bar

        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._add_blank_action.triggered.connect(self._on_add_blank)
        self._add_at_page_action.triggered.connect(self._on_add_at_current_page)
        self._set_start.clicked.connect(self._on_set_start)
        self._set_end.clicked.connect(self._on_set_end)
        self._chapters.chapters_changed.connect(self._on_chapters_changed)
        self._chapters.active_row_changed.connect(self._on_active_row_changed)
        self._configure_keyboard_shortcuts()
        self._sync_export_state()
        self._refresh_active_row_context()
        self.set_status(level="ready", text="Ready")
        self._apply_density_for_size(self.width(), self.height())

    def _configure_keyboard_shortcuts(self) -> None:
        """Install discoverable shortcuts when enabled by UI configuration."""
        if not self._ui_config.enable_keyboard_shortcuts:
            return
        self._import_toml_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        self._add_blank_action.setShortcut(QtGui.QKeySequence("Ctrl+N"))
        self._add_at_page_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+N"))
        self._detect_btn.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self._detect_btn.setToolTip("Auto-detect chapters (Ctrl+D)")
        self._undo_btn.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        self._undo_btn.setToolTip("Undo the last Auto Detect apply (Ctrl+Z)")
        self._export_chapters_action.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        self._done_btn.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self._done_btn.setToolTip("Validate and export chapters (Ctrl+Enter)")

    def _wire_actions(self) -> None:
        """Connect workflow callbacks to UI triggers."""
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
        """Toggle export visibility based on active tab."""
        self._sync_export_state()
        if index == 1:
            self._refresh_review()

    def _on_chapters_changed(self) -> None:
        """Handle chapter grid changes."""
        self._sync_export_state()
        self._refresh_active_row_context()
        if self._tabs.currentIndex() == 1:
            self._refresh_review()

    def _on_active_row_changed(self, _row_index: int) -> None:
        """Handle active chapter row changes."""
        self._refresh_active_row_context()

    def _refresh_active_row_context(self) -> None:
        """Refresh the UI context for Set Start/End actions."""
        summary = None
        try:
            summary = self._chapters.active_row_summary()
        except Exception:
            summary = None

        if summary is None:
            self._active_row_label.setText("Editing: No chapter selected")
            self._set_start.setToolTip("Set start for the selected chapter to the current page.")
            self._set_end.setToolTip("Set end for the selected chapter to the current page.")
            return

        _row_index, text = summary
        self._active_row_label.setText(f"Editing: {text}")
        self._set_start.setToolTip(f"Set start for {text} to the current page.")
        self._set_end.setToolTip(f"Set end for {text} to the current page.")

    def _sync_export_state(self) -> None:
        """Sync Export button visibility and enabled state."""
        on_export_tab = self._tabs.currentIndex() == 1
        has_any = self._chapters.row_count() > 0
        ready = self._chapters.is_ready_for_export()
        self._export_btn.setVisible(bool(on_export_tab and has_any))
        self._export_btn.setEnabled(bool(ready))
        self._export_chapters_action.setEnabled(bool(ready))
        self._export_toml_action.setEnabled(bool(has_any))
        self._save_session_action.setEnabled(bool(has_any))

    def _refresh_review(self) -> None:
        """Refresh the Export tab review panel."""
        try:
            self._review_panel.set_state(
                chapters=self._chapters.get_chapters(),
                errors=self._chapters.export_readiness_errors(),
            )
        except Exception:
            return

    def _apply_density_for_size(self, width_px: int, height_px: int) -> None:
        """Apply compact spacing and typography when the window is constrained."""
        compact = int(width_px) < 1120 or int(height_px) < 760
        root_margin = 8 if compact else 12
        section_margin = 8 if compact else 12
        inset_margin = 6 if compact else 8
        spacing = 8 if compact else 10
        try:
            self._root_layout.setContentsMargins(
                root_margin,
                root_margin,
                root_margin,
                root_margin,
            )
            self._root_layout.setSpacing(spacing)
            self._left_layout.setContentsMargins(
                section_margin,
                section_margin,
                section_margin,
                section_margin,
            )
            self._left_layout.setSpacing(spacing)
            self._viewer_layout.setContentsMargins(
                inset_margin,
                inset_margin,
                inset_margin,
                inset_margin,
            )
            self._viewer_layout.setSpacing(spacing)
            self._boundary_row_layout.setSpacing(spacing)
            self._chapters_layout.setContentsMargins(
                section_margin,
                section_margin,
                section_margin,
                section_margin,
            )
            self._chapters_layout.setSpacing(spacing)
            self._review_layout.setContentsMargins(
                section_margin,
                section_margin,
                section_margin,
                section_margin,
            )
            self._review_layout.setSpacing(spacing)
            self._action_bar_layout.setSpacing(spacing)
            self._done_btn.setMinimumHeight(34 if compact else 36)
            self._chapters.set_compact_mode(compact)
        except Exception:
            return

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        """Handle resize events."""
        super().resizeEvent(event)
        self._apply_density_for_size(self.width(), self.height())

    def chapters(self) -> list[ChapterDefinition]:
        """Return current chapters from the table."""
        return self._chapters.get_chapters()

    def set_chapters(self, chapters: list[ChapterDefinition]) -> None:
        """Replace table content with chapters."""
        self._chapters.set_chapters(chapters)

    def _ensure_row_selected(self) -> int:
        """Ensure a chapter row is selected and return its index."""
        row = self._chapters.selected_row_index()
        if row is None:
            return self._chapters.add_blank_chapter()
        return int(row)

    def _on_add_blank(self) -> None:
        """Add a blank chapter row."""
        self._chapters.add_blank_chapter()

    def _on_add_at_current_page(self) -> None:
        """Add a chapter row at the current viewer page."""
        page = self._viewer.current_page_1based()
        self._chapters.add_chapter_at_page(page)

    def _on_set_start(self) -> None:
        """Set the selected row start to the current page."""
        row = self._ensure_row_selected()
        self._chapters.set_row_start(row, self._viewer.current_page_1based())

    def _on_set_end(self) -> None:
        """Set the selected row end to the current page."""
        row = self._ensure_row_selected()
        self._chapters.set_row_end(row, self._viewer.current_page_1based())

    # Auto Detect from current page was removed from the primary UI to keep the workflow simple.
