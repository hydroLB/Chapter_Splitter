"""Review panel widget for the Qt GUI."""

from __future__ import annotations

from typing import Any, cast

from PySide6 import QtGui, QtWidgets

from ....core.models import ChapterDefinition


class ReviewPanelWidget(QtWidgets.QWidget):
    """Export review panel widget."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the review panel."""
        super().__init__(parent)
        self._build()

    def set_state(self, *, chapters: list[ChapterDefinition], errors: list[str]) -> None:
        """Update panel content from chapter state."""
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
        """Build the review panel UI."""
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
        self._summary.setAccessibleName("Export summary")
        layout.addWidget(self._summary)

        self._error = QtWidgets.QLabel("", self)
        self._error.setVisible(False)
        self._error.setWordWrap(True)
        self._error.setProperty("error", "true")
        self._error.setAccessibleName("Export validation errors")
        layout.addWidget(self._error)

        self._list = QtWidgets.QListWidget(self)
        self._list.setAccessibleName("Chapters ready for export")
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        scrollbar_as_needed = getattr(
            QtGui.Qt,
            "ScrollBarAsNeeded",
            cast(Any, QtGui.Qt).ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._list.setHorizontalScrollBarPolicy(scrollbar_as_needed)
        self._list.setVerticalScrollBarPolicy(scrollbar_as_needed)
        self._list.setVisible(False)
        layout.addWidget(self._list, 1)

        self._empty_state = QtWidgets.QLabel("No chapters yet. Detect or add chapters first.", self)
        self._empty_state.setProperty("text_role", "empty_state")
        self._empty_state.setAlignment(QtGui.Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setWordWrap(True)
        layout.addWidget(self._empty_state, 0)
