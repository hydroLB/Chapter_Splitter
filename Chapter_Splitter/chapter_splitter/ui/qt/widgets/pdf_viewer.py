"""PDF viewer widget backed by QtPdf."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

from .pdf_state import PdfViewerState


class PdfViewerWidget(QtWidgets.QWidget):
    """PDF viewing widget with navigation and zoom."""

    state_changed = QtCore.Signal(PdfViewerState)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the PDF viewer widget."""
        super().__init__(parent)
        self._doc = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._nav = self._view.pageNavigator()

        self._current_page = 0
        self._page_count = 0
        self._resize_debounce = QtCore.QTimer(self)
        self._resize_debounce.setSingleShot(True)
        self._resize_frozen_zoom_mode: QPdfView.ZoomMode | None = None
        self._resize_overlay: QtWidgets.QLabel | None = None
        self._build()
        self._wire()

    def load_pdf(self, pdf_path: Path) -> bool:
        """Load a PDF into the viewer."""
        if not isinstance(pdf_path, Path):
            return False
        if not pdf_path.exists():
            return False
        error = self._doc.load(str(pdf_path))
        if error != QPdfDocument.Error.None_:
            self._page_count = 0
            self._current_page = 0
            self._sync_page_edit_width()
            self._emit_state()
            return False
        self._page_count = int(self._doc.pageCount())
        self._current_page = 0
        self._sync_page_edit_width()
        self.set_fit_width()
        self._go_to_page(0)
        self._sync_zoom_label_later()
        self._emit_state()
        return True

    def current_page_1based(self) -> int:
        """Return the current page as a 1-based number."""
        return int(self._current_page) + 1

    def page_count(self) -> int:
        """Return the current loaded document page count."""
        return int(self._page_count)

    def set_fit_width(self) -> None:
        """Set the view to fit width."""
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._set_fit_combo_value("Fit Width")
        self._update_zoom_ui()
        self._sync_zoom_label_later()

    def set_fit_page(self) -> None:
        """Set the view to fit page."""
        self._view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._set_fit_combo_value("Fit Page")
        self._update_zoom_ui()
        self._sync_zoom_label_later()

    def set_manual_zoom(self, zoom: float) -> None:
        """Set a manual zoom level."""
        if zoom <= 0:
            return
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(float(zoom))
        self._set_fit_combo_value("Manual")
        # Some QtPdf builds do not emit navigator zoom signals for programmatic zoom changes.
        self._update_zoom_ui()

    def zoom_factor(self) -> float:
        """Return the current zoom factor."""
        return float(self._view.zoomFactor())

    def _build(self) -> None:
        """Build the toolbar and the PDF view."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)

        self._prev_btn = QtWidgets.QToolButton(self)
        self._prev_btn.setProperty("button_role", "toolbar")
        self._prev_btn.setText("◀")
        self._prev_btn.setAccessibleName("Previous page")
        self._prev_btn.setToolTip("Previous page (Alt+Left)")
        self._prev_btn.setShortcut(QtGui.QKeySequence("Alt+Left"))
        self._next_btn = QtWidgets.QToolButton(self)
        self._next_btn.setProperty("button_role", "toolbar")
        self._next_btn.setText("▶")
        self._next_btn.setAccessibleName("Next page")
        self._next_btn.setToolTip("Next page (Alt+Right)")
        self._next_btn.setShortcut(QtGui.QKeySequence("Alt+Right"))

        self._page_label = QtWidgets.QLabel("Page", self)
        self._page_label.setProperty("text_role", "form_label")
        self._page_edit = QtWidgets.QLineEdit(self)
        self._page_label.setBuddy(self._page_edit)
        self._page_edit.setAccessibleName("Page number")
        self._page_edit.setToolTip("Enter a page number and press Enter")
        self._page_edit.setFixedWidth(64)
        self._page_edit.setMinimumHeight(34)
        self._page_total = QtWidgets.QLabel("/ 0", self)
        self._page_total.setProperty("text_role", "form_label")
        self._go_btn = QtWidgets.QPushButton("Go", self)
        self._go_btn.setProperty("button_role", "default")
        self._go_btn.setFixedWidth(62)
        self._go_btn.setMinimumHeight(34)

        self._fit_combo = QtWidgets.QComboBox(self)
        self._fit_combo.setAccessibleName("Page fit mode")
        self._fit_combo.setToolTip("Choose how pages fit in the preview")
        self._fit_combo.addItems(["Fit Width", "Fit Page", "Manual"])
        self._fit_combo.setCurrentText("Fit Width")
        self._fit_combo.setMinimumHeight(32)

        self._zoom_out = QtWidgets.QToolButton(self)
        self._zoom_out.setProperty("button_role", "toolbar")
        self._zoom_out.setText("−")
        self._zoom_out.setAccessibleName("Zoom out")
        self._zoom_out.setToolTip("Zoom out")
        self._zoom_in = QtWidgets.QToolButton(self)
        self._zoom_in.setProperty("button_role", "toolbar")
        self._zoom_in.setText("+")
        self._zoom_in.setAccessibleName("Zoom in")
        self._zoom_in.setToolTip("Zoom in")
        self._zoom_pct = QtWidgets.QToolButton(self)
        self._zoom_pct.setProperty("button_role", "toolbar")
        self._zoom_pct.setText("100%")
        self._zoom_pct.setAccessibleName("Reset zoom to 100 percent")
        self._zoom_pct.setAutoRaise(True)
        self._zoom_pct.setToolTip("Reset zoom to 100%")

        toolbar.addWidget(self._prev_btn)
        toolbar.addWidget(self._next_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(self._page_label)
        toolbar.addWidget(self._page_edit)
        toolbar.addWidget(self._page_total)
        toolbar.addWidget(self._go_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._fit_combo)
        toolbar.addWidget(self._zoom_out)
        toolbar.addWidget(self._zoom_in)
        toolbar.addWidget(self._zoom_pct)
        toolbar.addStretch(1)

        layout.addLayout(toolbar)

        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setDocumentMargins(QtCore.QMargins(12, 12, 12, 12))
        scrollbar_as_needed = getattr(
            QtCore.Qt,
            "ScrollBarAsNeeded",
            cast(Any, QtCore.Qt).ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._view.setHorizontalScrollBarPolicy(scrollbar_as_needed)
        self._view.setVerticalScrollBarPolicy(scrollbar_as_needed)
        self.set_fit_width()
        self._configure_viewport_for_resizes()
        layout.addWidget(self._view, 1)

        self._resize_overlay = QtWidgets.QLabel(self)
        self._resize_overlay.setVisible(False)
        self._resize_overlay.setScaledContents(True)
        self._resize_overlay.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

    def _wire(self) -> None:
        """Wire toolbar controls to viewer behavior."""
        self._prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        self._go_btn.clicked.connect(self._on_go)
        self._page_edit.returnPressed.connect(self._on_go)
        self._fit_combo.currentTextChanged.connect(self._on_fit_mode)
        self._zoom_in.clicked.connect(lambda: self._bump_zoom(+0.1))
        self._zoom_out.clicked.connect(lambda: self._bump_zoom(-0.1))
        self._zoom_pct.clicked.connect(lambda: self.set_manual_zoom(1.0))

        self._nav.currentPageChanged.connect(self._on_current_page_changed)
        self._nav.currentZoomChanged.connect(self._on_zoom_changed)
        self._view.zoomFactorChanged.connect(self._on_zoom_changed)
        self._resize_debounce.timeout.connect(self._end_resize_redraw)
        with suppress(Exception):
            self._view.zoomModeChanged.connect(self._on_zoom_mode_changed)

    def _emit_state(self) -> None:
        """Emit a structured state snapshot."""
        self.state_changed.emit(PdfViewerState(self._current_page, self._page_count))

    def _set_page_text(self) -> None:
        """Refresh the page UI text fields."""
        self._page_edit.setText(str(self._current_page + 1))
        self._page_total.setText(f"/ {self._page_count}")

    def _sync_page_edit_width(self) -> None:
        """Sync the page input width to the document size."""
        try:
            digits = max(1, len(str(max(0, int(self._page_count)))))
            sample = "9" * digits
            metrics = QtGui.QFontMetrics(self._page_edit.font())
            text_width = int(metrics.horizontalAdvance(sample))
            # Include padding for the line edit frame and internal margins.
            width = max(44, min(120, text_width + 26))
            self._page_edit.setFixedWidth(width)
        except Exception:
            self._page_edit.setFixedWidth(44)

    def _go_to_page(self, page_index: int) -> None:
        """Navigate to a specific 0-based page index."""
        if self._page_count <= 0:
            return
        page_index = max(0, min(int(page_index), self._page_count - 1))
        if page_index == self._current_page and self._page_count > 0:
            self._set_page_text()
            self._emit_state()
            return
        self._current_page = int(page_index)
        self._nav.jump(self._current_page, QtCore.QPointF(0.0, 0.0))
        self._set_page_text()
        self._emit_state()

    def _on_go(self) -> None:
        """Handle a user "go to page" request."""
        raw = self._page_edit.text().strip()
        if not raw.isdigit():
            self._set_page_text()
            return
        page_1based = int(raw)
        self._go_to_page(page_1based - 1)

    def _on_fit_mode(self, mode: str) -> None:
        """Handle fit mode selection changes."""
        if mode == "Fit Page":
            self.set_fit_page()
            return
        if mode == "Manual":
            self.set_manual_zoom(self.zoom_factor())
            return
        self.set_fit_width()

    def _bump_zoom(self, delta: float) -> None:
        """Increment or decrement the current zoom."""
        zoom = max(0.1, min(12.0, self.zoom_factor() + float(delta)))
        self.set_manual_zoom(zoom)

    def _on_current_page_changed(self, page: int) -> None:
        """Handle navigator page changes."""
        self._current_page = int(page)
        self._set_page_text()
        self._emit_state()

    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle navigator zoom changes."""
        self._update_zoom_ui(zoom=float(zoom))

    def _on_zoom_mode_changed(self, _mode: object) -> None:
        """Handle zoom mode changes emitted by the QPdfView."""
        try:
            self._sync_fit_combo_to_view()
            self._sync_zoom_label_later()
        except Exception:
            return

    def _set_fit_combo_value(self, value: str) -> None:
        """Set the fit combo value without re-entering handlers."""
        try:
            if not hasattr(self, "_fit_combo"):
                return
            blocker = QtCore.QSignalBlocker(self._fit_combo)
            _ = blocker
            index = int(self._fit_combo.findText(value))
            if index >= 0:
                self._fit_combo.setCurrentIndex(index)
        except Exception:
            return

    def _sync_fit_combo_to_view(self) -> None:
        """Synchronize the fit combo to the current QPdfView zoom mode."""
        try:
            mode = self._view.zoomMode()
            if mode == QPdfView.ZoomMode.FitToWidth:
                self._set_fit_combo_value("Fit Width")
                return
            if mode == QPdfView.ZoomMode.FitInView:
                self._set_fit_combo_value("Fit Page")
                return
            self._set_fit_combo_value("Manual")
        except Exception:
            return

    def _sync_zoom_label_later(self) -> None:
        """Sync the zoom label after the event loop processes layout."""
        if self._page_count <= 0:
            return
        try:
            QtCore.QTimer.singleShot(0, self._sync_zoom_label_now)
        except Exception:
            return

    def _sync_zoom_label_now(self) -> None:
        """Sync the zoom label to the current view zoom factor."""
        try:
            self._update_zoom_ui(zoom=float(self._view.zoomFactor()))
        except Exception:
            return

    def _update_zoom_ui(self, *, zoom: float | None = None) -> None:
        """Update zoom-related toolbar UI."""
        try:
            mode = self._view.zoomMode()
        except Exception:
            mode = QPdfView.ZoomMode.Custom

        if mode == QPdfView.ZoomMode.FitToWidth:
            self._zoom_pct.setText("Fit")
            self._zoom_pct.setToolTip("Fit width")
            return
        if mode == QPdfView.ZoomMode.FitInView:
            self._zoom_pct.setText("Fit")
            self._zoom_pct.setToolTip("Fit page")
            return

        if zoom is None:
            try:
                zoom_value = float(self._view.zoomFactor())
            except Exception:
                zoom_value = 1.0
        else:
            try:
                zoom_value = float(zoom)
            except (TypeError, ValueError):
                zoom_value = 1.0

        zoom_value = max(0.01, min(100.0, zoom_value))
        pct = int(round(zoom_value * 100))
        self._zoom_pct.setText(f"{pct}%")
        self._zoom_pct.setToolTip("Reset zoom to 100%")

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        """Handle widget show events."""
        super().showEvent(event)
        self._sync_zoom_label_later()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        """Handle widget resize events."""
        super().resizeEvent(event)
        self._sync_resize_overlay_geometry()
        self._begin_resize_freeze()
        self._begin_resize_overlay()
        self._resize_debounce.start(120)

    def _end_resize_redraw(self) -> None:
        """Re-enable redraw after debounced resize."""
        try:
            if self._resize_frozen_zoom_mode is not None:
                self._view.setZoomMode(self._resize_frozen_zoom_mode)
                self._resize_frozen_zoom_mode = None
            self._sync_fit_combo_to_view()
            self._sync_zoom_label_later()
            self._view.viewport().update()
            self._view.update()
            self._end_resize_overlay()
        except Exception:
            return

    def _begin_resize_freeze(self) -> None:
        """Freeze fit-to-width/page zoom during live resizing."""
        try:
            if self._page_count <= 0:
                return
            current_mode = self._view.zoomMode()
            if current_mode == QPdfView.ZoomMode.Custom:
                return
            if self._resize_frozen_zoom_mode is None:
                self._resize_frozen_zoom_mode = current_mode
            # Freeze at the current zoom factor until resizing settles.
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(self._view.zoomFactor())
        except Exception:
            return

    def _sync_resize_overlay_geometry(self) -> None:
        """Keep the resize overlay positioned over the PDF view."""
        try:
            if self._resize_overlay is None:
                return
            self._resize_overlay.setGeometry(self._view.geometry())
        except Exception:
            return

    def _begin_resize_overlay(self) -> None:
        """Show a static overlay during live resizes."""
        if self._page_count <= 0:
            return
        if self._resize_overlay is None:
            return
        if self._resize_overlay.isVisible():
            return
        try:
            pixmap = self._view.viewport().grab()
            self._resize_overlay.setPixmap(pixmap)
            self._sync_resize_overlay_geometry()
            self._resize_overlay.raise_()
            self._resize_overlay.show()
            self._view.setUpdatesEnabled(False)
        except Exception:
            return

    def _end_resize_overlay(self) -> None:
        """Hide the resize overlay and re-enable view updates."""
        try:
            self._view.setUpdatesEnabled(True)
            QtCore.QTimer.singleShot(0, self._hide_resize_overlay)
        except Exception:
            return

    def _hide_resize_overlay(self) -> None:
        """Remove the resize overlay after the view has had a chance to repaint."""
        try:
            if self._resize_overlay is None:
                return
            self._resize_overlay.hide()
            self._resize_overlay.setPixmap(QtGui.QPixmap())
        except Exception:
            return

    def _configure_viewport_for_resizes(self) -> None:
        """Configure the PDF view to avoid flashing during repaints."""
        try:
            self._view.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self._view.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
            viewport = self._view.viewport()
            viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
            viewport.setAutoFillBackground(True)
        except Exception:
            return
