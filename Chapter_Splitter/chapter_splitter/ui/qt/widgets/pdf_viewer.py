"""PDF viewer widget backed by QtPdf.

Summary:
    Provide a true PDF renderer (vector) for crisp previews at any DPI.
Inputs:
    - None.
Outputs:
    - PdfViewerWidget which can load a PDF and provide current page state.
Side effects:
    Opens PDF files via QtPdf.
Error handling:
    Converts Qt load failures into False returns and safe signals.
Ties to other methods:
    Used by the main window to display PDFs and drive Set Start/End actions.
Why this exists:
    Tk-based previews are raster and cannot match system PDF viewers; QtPdf is vector.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView


@dataclass(frozen=True, slots=True)
class PdfViewerState:
    """Small immutable snapshot of viewer state.

    Summary:
        Carry the current page and page count for wiring to toolbars.
    Inputs:
        - page_index: Current 0-based page index.
        - page_count: Total number of pages in the loaded document.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Emitted by PdfViewerWidget when state changes.
    Why this exists:
        State updates should be structured to avoid ad-hoc tuple unpacking.
    """

    page_index: int
    page_count: int


class PdfViewerWidget(QtWidgets.QWidget):
    """PDF viewing widget with navigation and zoom.

    Summary:
        Wrap QPdfView and a small toolbar to provide page navigation, fit modes, and zoom.
    Inputs:
        - parent: Optional Qt parent widget.
    Outputs:
        - QWidget subclass with signals and helpers.
    Side effects:
        Creates Qt widgets and holds a QPdfDocument.
    Error handling:
        Validates page indices and handles load failures gracefully.
    Ties to other methods:
        Embedded by MainWindow and controlled by chapter actions.
    Why this exists:
        A dedicated widget keeps PDF view logic isolated from chapter grid logic.
    """

    state_changed = QtCore.Signal(PdfViewerState)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the PDF viewer widget.

        Summary:
            Construct the QtPdf document/viewer pair and a lightweight toolbar.
        Inputs:
            - parent: Optional Qt parent widget.
        Outputs:
            - None.
        Side effects:
            Allocates Qt widgets and attaches a QPdfDocument to a QPdfView.
        Error handling:
            Keeps the widget usable even when document loading fails later.
        Ties to other methods:
            Calls _build and _wire to set up UI and signals.
        Why this exists:
            The PDF viewer is a distinct concept from the chapter table and should remain isolated.
        """
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
        """Load a PDF into the viewer.

        Summary:
            Open the specified PDF file and reset the viewer state.
        Inputs:
            - pdf_path: Path to a PDF file.
        Outputs:
            - True when loaded successfully, otherwise False.
        Side effects:
            Loads the document and updates the view.
        Error handling:
            Returns False on Qt load errors or invalid paths.
        Ties to other methods:
            Called by the workflow after file selection.
        Why this exists:
            The viewer must be ready before chapter actions can use page state.
        """
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
        """Return the current page as a 1-based number.

        Summary:
            Convert the internal 0-based page index into a human-friendly value.
        Inputs:
            - None.
        Outputs:
            - 1-based page number.
        Side effects:
            None.
        Error handling:
            Returns 1 when no document is loaded.
        Ties to other methods:
            Used by MainWindow boundary actions (Set Start/End, detect-from-page).
        Why this exists:
            The rest of the app uses 1-based pages for user-facing chapter definitions.
        """
        return int(self._current_page) + 1

    def page_count(self) -> int:
        """Return the current loaded document page count.

        Summary:
            Provide total page count of the loaded PDF document.
        Inputs:
            - None.
        Outputs:
            - Total page count integer.
        Side effects:
            None.
        Error handling:
            Returns 0 when no document is loaded.
        Ties to other methods:
            Used by UI to clamp navigation and chapter page bounds.
        Why this exists:
            Page count is needed for both navigation UI and chapter editing.
        """
        return int(self._page_count)

    def set_fit_width(self) -> None:
        """Set the view to fit width.

        Summary:
            Configure the view to fit pages to the available width.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Changes the QPdfView zoom mode.
        Error handling:
            No-ops when the view is unavailable.
        Ties to other methods:
            Used by the fit mode selector.
        Why this exists:
            Fit width is the most readable default for multi-page scrolling.
        """
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._set_fit_combo_value("Fit Width")
        self._update_zoom_ui()
        self._sync_zoom_label_later()

    def set_fit_page(self) -> None:
        """Set the view to fit page.

        Summary:
            Configure the view to fit the whole page into the viewport.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Changes the QPdfView zoom mode.
        Error handling:
            No-ops when the view is unavailable.
        Ties to other methods:
            Used by the fit mode selector.
        Why this exists:
            Fit page helps users quickly see page boundaries and layout.
        """
        self._view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._set_fit_combo_value("Fit Page")
        self._update_zoom_ui()
        self._sync_zoom_label_later()

    def set_manual_zoom(self, zoom: float) -> None:
        """Set a manual zoom level.

        Summary:
            Switch the viewer into custom zoom mode and apply the specified zoom factor.
        Inputs:
            - zoom: Zoom factor where 1.0 is 100%.
        Outputs:
            - None.
        Side effects:
            Updates the QPdfView zoom factor.
        Error handling:
            Clamps invalid zoom inputs and ignores non-positive values.
        Ties to other methods:
            Used by zoom controls and the fit mode selector.
        Why this exists:
            Users need a deterministic 100% mode to compare with system PDF viewers.
        """
        if zoom <= 0:
            return
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(float(zoom))
        self._set_fit_combo_value("Manual")
        # Some QtPdf builds do not emit navigator zoom signals for programmatic zoom changes.
        self._update_zoom_ui()

    def zoom_factor(self) -> float:
        """Return the current zoom factor.

        Summary:
            Expose the underlying QPdfView zoom factor for UI display and stepping.
        Inputs:
            - None.
        Outputs:
            - Zoom factor float.
        Side effects:
            None.
        Error handling:
            Returns 1.0 when the view reports invalid values.
        Ties to other methods:
            Used by manual zoom updates and labels.
        Why this exists:
            Zoom is a first-class UI control for inspecting PDFs on high DPI displays.
        """
        return float(self._view.zoomFactor())

    def _build(self) -> None:
        """Build the toolbar and the PDF view.

        Summary:
            Create navigation controls and configure the QPdfView for multi-page scroll.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Allocates Qt widgets and sets up layout.
        Error handling:
            Uses conservative defaults for sizing to avoid clipped controls.
        Ties to other methods:
            Called by __init__.
        Why this exists:
            Separating UI construction from behavior wiring keeps the widget readable.
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)

        self._prev_btn = QtWidgets.QToolButton(self)
        self._prev_btn.setText("◀")
        self._next_btn = QtWidgets.QToolButton(self)
        self._next_btn.setText("▶")

        self._page_label = QtWidgets.QLabel("Page", self)
        self._page_edit = QtWidgets.QLineEdit(self)
        self._page_edit.setFixedWidth(44)
        self._page_total = QtWidgets.QLabel("/ 0", self)
        self._go_btn = QtWidgets.QPushButton("Go", self)
        self._go_btn.setFixedWidth(56)

        self._fit_combo = QtWidgets.QComboBox(self)
        self._fit_combo.addItems(["Fit Width", "Fit Page", "Manual"])
        self._fit_combo.setCurrentText("Fit Width")

        self._zoom_out = QtWidgets.QToolButton(self)
        self._zoom_out.setText("−")
        self._zoom_in = QtWidgets.QToolButton(self)
        self._zoom_in.setText("+")
        self._zoom_pct = QtWidgets.QToolButton(self)
        self._zoom_pct.setText("100%")
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
        """Wire toolbar controls to viewer behavior.

        Summary:
            Connect button clicks and navigator signals to internal handlers.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Connects Qt signals.
        Error handling:
            Uses safe wrappers for navigation and ignores invalid input.
        Ties to other methods:
            Called by __init__.
        Why this exists:
            Keeping signal wiring separate reduces the cognitive load of _build.
        """
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
        """Emit a structured state snapshot.

        Summary:
            Notify listeners whenever page index or page count changes.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Emits the state_changed Qt signal.
        Error handling:
            None.
        Ties to other methods:
            Called by load_pdf and navigation handlers.
        Why this exists:
            The main window needs page state without directly reading widget internals.
        """
        self.state_changed.emit(PdfViewerState(self._current_page, self._page_count))

    def _set_page_text(self) -> None:
        """Refresh the page UI text fields.

        Summary:
            Update the page edit and total label to reflect current state.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates line edit and label widgets.
        Error handling:
            No-ops when widgets are missing.
        Ties to other methods:
            Called after navigation and load.
        Why this exists:
            Keeping UI updates centralized avoids subtle inconsistencies during navigation.
        """
        self._page_edit.setText(str(self._current_page + 1))
        self._page_total.setText(f"/ {self._page_count}")

    def _sync_page_edit_width(self) -> None:
        """Sync the page input width to the document size.

        Summary:
            Resize the page number input so it fits the maximum page count digit length without
            wasting horizontal space.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Updates the QLineEdit fixed width.
        Error handling:
            Uses conservative defaults when font metrics are unavailable.
        Ties to other methods:
            Called by load_pdf when the page count becomes known.
        Why this exists:
            A tight page input keeps the toolbar compact and reduces visual noise.
        """
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
        """Navigate to a specific 0-based page index.

        Summary:
            Clamp the requested page to valid bounds and update the navigator position.
        Inputs:
            - page_index: 0-based page index.
        Outputs:
            - None.
        Side effects:
            Updates internal page state and scrolls the QPdfView.
        Error handling:
            No-ops when no document is loaded.
        Ties to other methods:
            Used by prev/next buttons and manual page navigation.
        Why this exists:
            Navigation logic needs a single clamping implementation.
        """
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
        """Handle a user "go to page" request.

        Summary:
            Parse the page input and navigate to the requested page number.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Scrolls the QPdfView when the input is valid.
        Error handling:
            Restores the current page text when the input is invalid.
        Ties to other methods:
            Connected to the Go button and line edit returnPressed.
        Why this exists:
            Page jumps are useful even with continuous scrolling for large documents.
        """
        raw = self._page_edit.text().strip()
        if not raw.isdigit():
            self._set_page_text()
            return
        page_1based = int(raw)
        self._go_to_page(page_1based - 1)

    def _on_fit_mode(self, mode: str) -> None:
        """Handle fit mode selection changes.

        Summary:
            Switch between fit width, fit page, and manual zoom modes.
        Inputs:
            - mode: Selected mode label.
        Outputs:
            - None.
        Side effects:
            Updates QPdfView zoom mode.
        Error handling:
            Defaults to fit width for unknown values.
        Ties to other methods:
            Connected to the fit combo currentTextChanged signal.
        Why this exists:
            Users should be able to control the reading layout without hunting for settings.
        """
        if mode == "Fit Page":
            self.set_fit_page()
            return
        if mode == "Manual":
            self.set_manual_zoom(self.zoom_factor())
            return
        self.set_fit_width()

    def _bump_zoom(self, delta: float) -> None:
        """Increment or decrement the current zoom.

        Summary:
            Step the zoom factor and switch to manual zoom mode.
        Inputs:
            - delta: Signed zoom delta.
        Outputs:
            - None.
        Side effects:
            Updates QPdfView zoom factor.
        Error handling:
            Clamps zoom to a safe range.
        Ties to other methods:
            Connected to zoom in and zoom out buttons.
        Why this exists:
            Zoom stepping is the fastest way to inspect text on high DPI displays.
        """
        zoom = max(0.1, min(12.0, self.zoom_factor() + float(delta)))
        self.set_manual_zoom(zoom)

    def _on_current_page_changed(self, page: int) -> None:
        """Handle navigator page changes.

        Summary:
            Sync internal state and UI when the user scrolls or navigates.
        Inputs:
            - page: New 0-based page index.
        Outputs:
            - None.
        Side effects:
            Updates page fields and emits state.
        Error handling:
            None.
        Ties to other methods:
            Connected to QPdfPageNavigator.currentPageChanged.
        Why this exists:
            The toolbar must reflect scroll-based navigation as well as explicit jumps.
        """
        self._current_page = int(page)
        self._set_page_text()
        self._emit_state()

    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle navigator zoom changes.

        Summary:
            Update the zoom percentage UI when the view zoom changes.
        Inputs:
            - zoom: New zoom factor.
        Outputs:
            - None.
        Side effects:
            Updates the zoom percent button text.
        Error handling:
            Clamps displayed values to sensible percentages.
        Ties to other methods:
            Connected to QPdfPageNavigator.currentZoomChanged.
        Why this exists:
            Users need immediate feedback about zoom level to achieve a 100% reference view.
        """
        self._update_zoom_ui(zoom=float(zoom))

    def _on_zoom_mode_changed(self, _mode: object) -> None:
        """Handle zoom mode changes emitted by the QPdfView.

        Summary:
            Keep the fit mode combo and zoom label synchronized with programmatic or internal view
            changes.
        Inputs:
            - _mode: Qt signal payload (unused, mode is read from the view).
        Outputs:
            - None.
        Side effects:
            Updates the fit mode combo and zoom label.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Wired in _wire when QPdfView exposes zoomModeChanged.
        Why this exists:
            Fit zoom computations occur after layout, so syncing UI on mode changes prevents stale
            "100%" labels that do not match the rendered PDF.
        """
        try:
            self._sync_fit_combo_to_view()
            self._sync_zoom_label_later()
        except Exception:
            return

    def _set_fit_combo_value(self, value: str) -> None:
        """Set the fit combo value without re-entering handlers.

        Summary:
            Update the fit mode combo programmatically while preventing recursive signal handling.
        Inputs:
            - value: Combo label value to select.
        Outputs:
            - None.
        Side effects:
            Mutates the combo box selection.
        Error handling:
            No-ops when the combo is not initialized or the value is not present.
        Ties to other methods:
            Used by set_fit_width, set_fit_page, and set_manual_zoom.
        Why this exists:
            The toolbar should reflect the actual view mode after any action.
        """
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
        """Synchronize the fit combo to the current QPdfView zoom mode.

        Summary:
            Map QPdfView zoom modes to the toolbar combo labels so the UI stays consistent.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the combo box selection.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Called by _on_zoom_mode_changed and _end_resize_redraw.
        Why this exists:
            Resizes and programmatic changes can toggle zoom modes without user interaction.
        """
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
        """Sync the zoom label after the event loop processes layout.

        Summary:
            Defer zoom label updates so fit-to-width/page computations have a stable viewport size.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Schedules a single-shot timer callback.
        Error handling:
            No-ops when no document is loaded or Qt timers are unavailable.
        Ties to other methods:
            Called after loading PDFs, changing fit modes, and completing debounced resizes.
        Why this exists:
            Fit modes can render at a zoom factor that differs from 1.0, and the label must reflect
            the real computed zoom rather than a hard-coded default.
        """
        if self._page_count <= 0:
            return
        try:
            QtCore.QTimer.singleShot(0, self._sync_zoom_label_now)
        except Exception:
            return

    def _sync_zoom_label_now(self) -> None:
        """Sync the zoom label to the current view zoom factor.

        Summary:
            Read QPdfView.zoomFactor and update the zoom percent label.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates the zoom percent toolbutton text.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Scheduled by _sync_zoom_label_later.
        Why this exists:
            The only reliable source of truth for "current zoom" is the view itself.
        """
        try:
            self._update_zoom_ui(zoom=float(self._view.zoomFactor()))
        except Exception:
            return

    def _update_zoom_ui(self, *, zoom: float | None = None) -> None:
        """Update zoom-related toolbar UI.

        Summary:
            Keep the zoom readout consistent with the current zoom mode.
        Inputs:
            - zoom: Optional zoom factor; when omitted, reads the current factor from QPdfView.
        Outputs:
            - None.
        Side effects:
            Updates the zoom readout text and tooltip.
        Error handling:
            Best-effort only; invalid values fall back to safe defaults.
        Ties to other methods:
            Called by zoom mode changes, manual zoom setters, and zoom changed signals.
        Why this exists:
            Fit modes do not represent a stable numeric percent. Showing "100%" in a fit mode is
            misleading and caused the perceived inconsistency when returning to 100%.
        """
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
        """Handle widget show events.

        Summary:
            Trigger a deferred zoom label sync once the widget has a real size.
        Inputs:
            - event: Qt show event.
        Outputs:
            - None.
        Side effects:
            Schedules a zoom label update.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Uses _sync_zoom_label_later to avoid stale fit-mode zoom labels.
        Why this exists:
            Fit-to-width/page zoom factors are computed after layout, so syncing on show ensures the
            percent display reflects the true rendered scale.
        """
        super().showEvent(event)
        self._sync_zoom_label_later()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        """Handle widget resize events.

        Summary:
            Freeze fit-to-width/page zoom during live resizing to reduce flicker.
        Inputs:
            - event: Qt resize event.
        Outputs:
            - None.
        Side effects:
            Switches QPdfView into manual zoom during resize and restores fit mode after.
        Error handling:
            Falls back to default QWidget behavior when the view cannot be updated.
        Ties to other methods:
            Uses _end_resize_redraw to re-enable updates after resizing settles.
        Why this exists:
            QtPdf can repaint aggressively during resizes; debouncing reduces visible flashing.
        """
        super().resizeEvent(event)
        self._sync_resize_overlay_geometry()
        self._begin_resize_freeze()
        self._begin_resize_overlay()
        self._resize_debounce.start(120)

    def _end_resize_redraw(self) -> None:
        """Re-enable redraw after debounced resize.

        Summary:
            Restore the previous fit zoom mode and trigger a single repaint.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Restores the saved QPdfView zoom mode when one was frozen.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Scheduled by resizeEvent via _resize_debounce.
        Why this exists:
            Avoids repeated fit computations that present as flicker to the user.
        """
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
        """Freeze fit-to-width/page zoom during live resizing.

        Summary:
            Temporarily switch QPdfView from a fit mode into manual zoom so repeated size changes do
            not trigger expensive re-layout and re-render cycles that look like flicker.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Updates the QPdfView zoom mode when it is currently a fit mode.
        Error handling:
            No-ops when the view is not in a fit mode or zoom state cannot be queried.
        Ties to other methods:
            Called by resizeEvent; restored by _end_resize_redraw.
        Why this exists:
            Fit zoom modes are correct at rest, but they are visually unstable during live resizing.
        """
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
        """Keep the resize overlay positioned over the PDF view.

        Summary:
            Update the overlay geometry so it covers the QPdfView during resizes.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates overlay widget geometry.
        Error handling:
            No-ops when the overlay is not available.
        Ties to other methods:
            Called by resizeEvent before overlay capture.
        Why this exists:
            The overlay prevents flicker by holding a stable frame while QtPdf reflows pages.
        """
        try:
            if self._resize_overlay is None:
                return
            self._resize_overlay.setGeometry(self._view.geometry())
        except Exception:
            return

    def _begin_resize_overlay(self) -> None:
        """Show a static overlay during live resizes.

        Summary:
            Capture the current rendered PDF view into a pixmap and display it over the viewer
            while disabling live updates to prevent visible flicker.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Shows an overlay label and temporarily disables updates on the QPdfView.
        Error handling:
            Best-effort only; if capture fails, resizing continues with default behavior.
        Ties to other methods:
            Started from resizeEvent; stopped by _end_resize_overlay.
        Why this exists:
            QtPdf can clear and repaint repeatedly during resizes, which reads as flashing.
        """
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
        """Hide the resize overlay and re-enable view updates.

        Summary:
            Restore normal PDF rendering after the resize debounce timer fires, leaving the overlay
            in place until the next event loop tick so the view can repaint before the snapshot is
            removed.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Re-enables updates on QPdfView and schedules overlay removal.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Called by _end_resize_redraw after restoring fit zoom.
        Why this exists:
            Resuming normal rendering only once per resize reduces flashing.
        """
        try:
            self._view.setUpdatesEnabled(True)
            QtCore.QTimer.singleShot(0, self._hide_resize_overlay)
        except Exception:
            return

    def _hide_resize_overlay(self) -> None:
        """Remove the resize overlay after the view has had a chance to repaint.

        Summary:
            Hide the snapshot overlay and clear its pixmap after enabling updates.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Hides the overlay label.
        Error handling:
            Best-effort only; ignores Qt errors.
        Ties to other methods:
            Scheduled by _end_resize_overlay using a single-shot timer.
        Why this exists:
            Removing the overlay immediately can reveal an intermediate blank frame during repaint.
        """
        try:
            if self._resize_overlay is None:
                return
            self._resize_overlay.hide()
            self._resize_overlay.setPixmap(QtGui.QPixmap())
        except Exception:
            return

    def _configure_viewport_for_resizes(self) -> None:
        """Configure the PDF view to avoid flashing during repaints.

        Summary:
            Set widget attributes to reduce background clears that can appear as flicker.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Mutates widget attributes on QPdfView and its viewport.
        Error handling:
            No-ops when attributes cannot be set on a given platform.
        Ties to other methods:
            Called by _build after the view is configured.
        Why this exists:
            The default background clearing behavior can cause white flashes during resizing.
        """
        try:
            self._view.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self._view.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
            viewport = self._view.viewport()
            viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            viewport.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
            viewport.setAutoFillBackground(True)
        except Exception:
            return
