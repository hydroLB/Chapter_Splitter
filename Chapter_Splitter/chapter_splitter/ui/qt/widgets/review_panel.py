"""Review panel widget for the Qt GUI.

Summary:
    Provide a clean, read-only view of the current chapter list and export readiness.
Inputs:
    - None.
Outputs:
    - ReviewPanelWidget instance.
Side effects:
    Creates Qt widgets.
Error handling:
    Uses best-effort rendering and avoids raising during refresh.
Ties to other methods:
    Embedded by MainWindow on the Export tab.
Why this exists:
    The user needs a clear "done" step that summarizes chapters before export.
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

from ....core.models import ChapterDefinition


class ReviewPanelWidget(QtWidgets.QWidget):
    """Export review panel widget.

    Summary:
        Render a compact summary and list of chapters, plus inline validation feedback.
    Inputs:
        - parent: Optional Qt parent widget.
    Outputs:
        - QWidget instance.
    Side effects:
        Allocates labels and a list widget.
    Error handling:
        Avoids raising for empty or invalid chapter data.
    Ties to other methods:
        Used by MainWindow to render the Export tab content.
    Why this exists:
        A dedicated review panel keeps MainWindow layout code small and makes the flow clearer.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the review panel.

        Summary:
            Build the widget tree for summary, errors, and chapter list.
        Inputs:
            - parent: Optional Qt parent widget.
        Outputs:
            - None.
        Side effects:
            Creates child widgets and layouts.
        Error handling:
            None.
        Ties to other methods:
            Calls _build to construct the UI.
        Why this exists:
            The Export tab should remain lightweight and consistent.
        """
        super().__init__(parent)
        self._build()

    def set_state(self, *, chapters: list[ChapterDefinition], errors: list[str]) -> None:
        """Update panel content from chapter state.

        Summary:
            Render the chapter list and show inline validation errors when present.
        Inputs:
            - chapters: Chapter definitions to display.
            - errors: Validation errors to display.
        Outputs:
            - None.
        Side effects:
            Mutates label text and list contents.
        Error handling:
            Handles missing titles and invalid page values gracefully.
        Ties to other methods:
            Called by MainWindow whenever chapters change or export readiness is evaluated.
        Why this exists:
            The review view should always reflect the current editable table state.
        """
        self._summary.setText(f"{len(chapters)} chapter(s)")
        if errors:
            self._error.setText("Fix these before exporting:\n- " + "\n- ".join(errors))
            self._error.setVisible(True)
        else:
            self._error.setText("")
            self._error.setVisible(False)

        self._list.clear()
        if not chapters:
            self._list.setVisible(False)
            self._empty_state.setVisible(True)
            return
        self._list.setVisible(True)
        self._empty_state.setVisible(False)

        for chapter in chapters:
            title = (chapter.title or "").strip() or "Untitled"
            item = QtWidgets.QListWidgetItem(
                f"{title}  (Start: {chapter.start_page}, End: {chapter.end_page})"
            )
            item.setFlags(QtGui.Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)

    def _build(self) -> None:
        """Build the review panel UI.

        Summary:
            Create header, summary, inline error label, and read-only list widgets.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Allocates and arranges Qt widgets.
        Error handling:
            None.
        Ties to other methods:
            Called by __init__.
        Why this exists:
            Keeping widget construction isolated makes it easy to restyle the Export tab later.
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Export", self)
        title.setProperty("text_role", "section_header")
        font = title.font()
        font.setPointSize(max(12, font.pointSize()))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        title.setFont(font)
        layout.addWidget(title)

        self._summary = QtWidgets.QLabel("0 chapter(s)", self)
        self._summary.setProperty("text_role", "hint")
        layout.addWidget(self._summary)

        self._error = QtWidgets.QLabel("", self)
        self._error.setVisible(False)
        self._error.setWordWrap(True)
        self._error.setProperty("error", "true")
        layout.addWidget(self._error)

        self._list = QtWidgets.QListWidget(self)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        scrollbar_as_needed = int(getattr(QtGui.Qt, "ScrollBarAsNeeded", 0))
        self._list.setHorizontalScrollBarPolicy(scrollbar_as_needed)
        self._list.setVerticalScrollBarPolicy(scrollbar_as_needed)
        self._list.setVisible(False)
        layout.addWidget(self._list, 1)

        self._empty_state = QtWidgets.QLabel("No chapters yet. Detect or add chapters first.", self)
        self._empty_state.setProperty("text_role", "empty_state")
        self._empty_state.setAlignment(QtGui.Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setWordWrap(True)
        layout.addWidget(self._empty_state, 0)
