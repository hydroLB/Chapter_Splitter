"""Qt theme and style helpers.

Summary:
    Provide a small design system for the Qt GUI (colors, typography, spacing) and a single
    application-wide stylesheet so the UI stays cohesive and easy to restyle.
Inputs:
    - None.
Outputs:
    - None.
Side effects:
    Applies a QPalette and a Qt style sheet to the QApplication.
Error handling:
    Uses best-effort defaults and avoids raising from theme application.
Ties to other methods:
    Called by ui.qt.workflow before creating windows.
Why this exists:
    A centralized theme prevents mismatched widget colors and makes restyling a one-file change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Theme tokens for the Qt GUI.

    Summary:
        Collect the minimal set of tokens needed to keep styling consistent across widgets.
    Inputs:
        - bg: App background color.
        - surface: Surface color for panels.
        - surface_alt: Alternate surface color for striped lists.
        - border: Border color.
        - text: Primary text color.
        - text_muted: Muted text color.
        - primary: Primary action accent color.
        - danger: Destructive action color.
        - radius: Default border radius.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by build_stylesheet and apply_theme.
    Why this exists:
        Tokens make it trivial to restyle the app without hunting through widget code.
    """

    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    primary: str
    danger: str
    radius: int


def default_tokens() -> ThemeTokens:
    """Return the default light theme tokens.

    Summary:
        Provide a professional, minimal light theme that matches macOS expectations.
    Inputs:
        - None.
    Outputs:
        - ThemeTokens instance.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by apply_theme when no explicit theme is configured.
    Why this exists:
        The GUI should look clean out of the box without requiring manual theme tuning.
    """
    return ThemeTokens(
        bg="#f6f7f9",
        surface="#ffffff",
        surface_alt="#f2f4f7",
        border="#d0d7de",
        text="#11181c",
        text_muted="#5c6b76",
        primary="#0a84ff",
        danger="#d92d20",
        radius=8,
    )


def default_dark_tokens() -> ThemeTokens:
    """Return the default dark theme tokens.

    Summary:
        Provide a professional dark theme that tracks macOS dark mode expectations.
    Inputs:
        - None.
    Outputs:
        - ThemeTokens instance.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by apply_theme when the OS color scheme is dark.
    Why this exists:
        Dark mode should be a first-class experience rather than an afterthought.
    """
    return ThemeTokens(
        bg="#0a0d12",
        surface="#0f172a",
        surface_alt="#141f37",
        border="#2a3b58",
        text="#e6edf3",
        text_muted="#a8b3bf",
        primary="#0a84ff",
        danger="#ff453a",
        radius=8,
    )


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Build a Qt stylesheet from theme tokens.

    Summary:
        Generate a small QSS ruleset to standardize widget spacing, borders, and focus behavior.
    Inputs:
        - tokens: Theme token set.
    Outputs:
        - QSS string.
    Side effects:
        None.
    Error handling:
        Returns an empty string when tokens are invalid.
    Ties to other methods:
        Used by apply_theme.
    Why this exists:
        Centralizing QSS avoids one-off widget styling and reduces visual drift.
    """
    if not isinstance(tokens, ThemeTokens):
        return ""
    r = int(tokens.radius)
    return f"""
QWidget {{
  color: {tokens.text};
}}

QMainWindow {{
  background: {tokens.bg};
}}

QSplitter::handle {{
  background: {tokens.bg};
}}

QTabWidget::pane {{
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface};
}}

QTabBar::tab {{
  padding: 12px 20px;
  min-height: 34px;
  min-width: 120px;
  font-size: 14px;
  border: 1px solid {tokens.border};
  border-bottom: none;
  border-top-left-radius: {r}px;
  border-top-right-radius: {r}px;
  background: {tokens.surface_alt};
}}
QTabBar::tab:selected {{
  background: {tokens.surface};
  font-weight: 600;
}}

QTabBar::tab:hover {{
  background: {tokens.surface};
}}

QLineEdit, QSpinBox, QComboBox {{
  padding: 6px 8px;
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
  border: 1px solid {tokens.primary};
}}

QLineEdit[active_row=\"true\"], QSpinBox[active_row=\"true\"] {{
  border: 1px solid {tokens.primary};
  background: {tokens.surface};
}}

QLineEdit[pulse=\"true\"], QSpinBox[pulse=\"true\"] {{
  background: rgba(10, 132, 255, 0.22);
}}

QToolButton[pulse=\"true\"] {{
  background: rgba(10, 132, 255, 0.18);
}}

QToolButton[active_row=\"true\"] {{
  border: 1px solid {tokens.primary};
}}

QToolButton[active_row=\"true\"][destructive=\"true\"] {{
  color: {tokens.danger};
}}

QPushButton, QToolButton {{
  padding: 8px 12px;
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface};
}}
QPushButton:hover, QToolButton:hover {{
  background: {tokens.surface_alt};
}}
QPushButton:pressed, QToolButton:pressed {{
  background: {tokens.surface_alt};
}}
QPushButton:disabled, QToolButton:disabled {{
  color: {tokens.text_muted};
  background: {tokens.surface_alt};
}}

QToolButton[destructive=\"true\"] {{
  color: {tokens.danger};
}}

QToolButton[muted=\"true\"], QLabel[muted=\"true\"] {{
  color: {tokens.text_muted};
}}

QLabel[error=\"true\"] {{
  color: {tokens.danger};
}}

QTableWidget {{
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface};
  gridline-color: {tokens.border};
  selection-background-color: {tokens.surface_alt};
  selection-color: {tokens.text};
}}
QTableView {{
  outline: 0;
  selection-background-color: {tokens.surface_alt};
  selection-color: {tokens.text};
}}
QTableWidget::item:selected, QTableView::item:selected {{
  background: {tokens.surface_alt};
}}
QTableWidget::item:selected:active, QTableView::item:selected:active {{
  background: {tokens.surface_alt};
}}
QTableWidget::item:selected:!active, QTableView::item:selected:!active {{
  background: {tokens.surface_alt};
}}
QHeaderView::section {{
  padding: 8px 8px;
  border: none;
  border-bottom: 1px solid {tokens.border};
  background: {tokens.surface_alt};
  color: {tokens.text_muted};
}}

QListWidget {{
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface};
}}

QPdfView {{
  border: 1px solid {tokens.border};
  border-radius: {r}px;
  background: {tokens.surface_alt};
}}
QPdfView::viewport {{
  background: {tokens.surface_alt};
}}

QScrollBar:vertical {{
  background: transparent;
  width: 12px;
  margin: 2px;
}}
QScrollBar::handle:vertical {{
  background: {tokens.border};
  border-radius: 6px;
  min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0px;
}}
QScrollBar:horizontal {{
  background: transparent;
  height: 12px;
  margin: 2px;
}}
QScrollBar::handle:horizontal {{
  background: {tokens.border};
  border-radius: 6px;
  min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
  width: 0px;
}}
""".strip()


def _system_color_scheme() -> str:
    """Return the OS color scheme for auto theme selection.

    Summary:
        Query Qt style hints for the current system color scheme.
    Inputs:
        - None.
    Outputs:
        - 'dark' or 'light'.
    Side effects:
        Imports Qt modules.
    Error handling:
        Returns 'light' when the scheme cannot be detected.
    Ties to other methods:
        Used by apply_theme and install_system_theme_listener.
    Why this exists:
        The GUI should follow the user's OS preference by default.
    """
    try:
        from PySide6 import QtCore, QtGui

        scheme = QtGui.QGuiApplication.styleHints().colorScheme()
        if scheme == QtCore.Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        return "light"
    return "light"


def apply_theme(*, app: object) -> None:
    """Apply the default theme to a Qt application.

    Summary:
        Set a consistent Qt style, palette, and stylesheet for the entire app.
    Inputs:
        - app: QApplication instance.
    Outputs:
        - None.
    Side effects:
        Mutates QApplication style, palette, and stylesheet.
    Error handling:
        Best-effort only; no exceptions escape from this function.
    Ties to other methods:
        Called by ui.qt.workflow.workflow.
    Why this exists:
        The UI should not depend on platform widget palette defaults that can vary by theme.
    """
    try:
        from PySide6 import QtGui, QtWidgets

        if not isinstance(app, QtWidgets.QApplication):
            return
        tokens = default_dark_tokens() if _system_color_scheme() == "dark" else default_tokens()
        app.setStyle("Fusion")
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(tokens.bg))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(tokens.surface))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(tokens.surface_alt))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(tokens.text))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(tokens.text))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(tokens.surface))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(tokens.text))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(tokens.primary))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
        app.setPalette(palette)
        app.setStyleSheet(build_stylesheet(tokens))
    except Exception:
        return


def install_system_theme_listener(*, app: object) -> None:
    """Install an OS theme change listener that re-applies theme tokens.

    Summary:
        Subscribe to Qt's colorSchemeChanged signal so the UI auto-toggles light and dark mode.
    Inputs:
        - app: QApplication instance.
    Outputs:
        - None.
    Side effects:
        Connects a signal handler and stores a reference on the app to keep it alive.
    Error handling:
        No-ops when Qt style hints are unavailable.
    Ties to other methods:
        Called by ui.qt.workflow after creating the QApplication.
    Why this exists:
        Users expect dark mode to follow OS settings automatically.
    """
    try:
        from PySide6 import QtCore, QtGui, QtWidgets

        if not isinstance(app, QtWidgets.QApplication):
            return
        hints = QtGui.QGuiApplication.styleHints()
        if not hasattr(hints, "colorSchemeChanged"):
            return

        class _ThemeListener(QtCore.QObject):
            def __init__(self) -> None:
                super().__init__()

            def on_scheme_changed(self, _scheme: object) -> None:
                apply_theme(app=app)

        listener = _ThemeListener()
        hints.colorSchemeChanged.connect(listener.on_scheme_changed)
        app.setProperty("_chapter_splitter_theme_listener", listener)
    except Exception:
        return
