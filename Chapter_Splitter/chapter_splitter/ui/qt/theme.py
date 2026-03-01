"""Qt theme and style helpers.

Summary:
    Provide a semantic design system for the Qt GUI (tokens, color modes, and control states)
    and apply one application-wide stylesheet so widgets never rely on host defaults.
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
    A centralized semantic theme prevents visual drift and keeps light/dark tuning maintainable.
"""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ColorMode = Literal["light", "dark", "auto"]
ResolvedColorMode = Literal["light", "dark"]


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Theme tokens for the Qt GUI.

    Summary:
        Collect semantic tokens for all surfaces, text roles, borders, states, and controls.
    Inputs:
        - colors: Mapping of semantic color roles to hex values.
        - radius: Primary corner radius.
        - compact_radius: Corner radius for compact controls.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by resolve_color, build_stylesheet, and apply_theme.
    Why this exists:
        Semantic tokens keep styling consistent while preserving flexibility for future expansion.
    """

    colors: Mapping[str, str]
    radius: int
    compact_radius: int


def default_tokens() -> ThemeTokens:
    """Return default light-mode tokens.

    Summary:
        Provide a balanced light palette with explicit semantics for every role.
    Inputs:
        - None.
    Outputs:
        - ThemeTokens for light mode.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _tokens_for_mode.
    Why this exists:
        Light mode must stay readable with softened non-primary colors.
    """
    return ThemeTokens(
        colors={
            "surface.app": "#eef2f6",
            "surface.root": "#f7f9fc",
            "surface.section_outer": "#ffffff",
            "surface.section_inset": "#f9fbfd",
            "surface.panel": "#ffffff",
            "surface.panel_alt": "#f4f7fb",
            "surface.input": "#ffffff",
            "surface.input_active": "#f7fbff",
            "surface.selection": "#dbeafe",
            "surface.disabled": "#eef1f5",
            "surface.table_header": "#edf2f7",
            "surface.scroll_track": "#ecf1f6",
            "surface.scroll_thumb": "#c5cfda",
            "surface.scroll_thumb_hover": "#b5c1ce",
            "surface.status_ready": "#eef6ff",
            "surface.status_working": "#fff7e8",
            "surface.status_success": "#edf9f0",
            "surface.status_error": "#fff0ef",
            "text.primary": "#17212b",
            "text.section_header": "#0f1720",
            "text.form_label": "#304152",
            "text.hint": "#5b6c7d",
            "text.empty_state": "#627284",
            "text.status": "#1f2d3a",
            "text.inverse": "#ffffff",
            "text.disabled": "#8c9ba8",
            "text.ready": "#215d9c",
            "text.working": "#8a5a00",
            "text.success": "#1f6d34",
            "text.error": "#a72a1f",
            "border.default": "#c9d3df",
            "border.subtle": "#d9e1ea",
            "border.focus": "#4f8ccf",
            "border.selected": "#5f95d6",
            "border.disabled": "#d7dfe8",
            "border.ready": "#c8def8",
            "border.working": "#f0d8ad",
            "border.success": "#c3e5cc",
            "border.error": "#f0c5c2",
            "control.button_default_bg": "#ffffff",
            "control.button_default_hover": "#f4f7fb",
            "control.button_default_pressed": "#e8eef5",
            "control.button_toolbar_bg": "#f6f9fc",
            "control.button_toolbar_hover": "#ebf2f9",
            "control.button_primary_bg": "#2b77c7",
            "control.button_primary_hover": "#2468ad",
            "control.button_primary_pressed": "#1f5993",
            "control.button_segment_bg": "#eef3f8",
            "control.button_segment_hover": "#e4ebf3",
            "control.button_segment_selected": "#ffffff",
            "control.input_bg": "#ffffff",
            "control.input_disabled_bg": "#eef1f5",
            "control.tab_bg": "#edf3f9",
            "control.tab_hover": "#e5edf6",
            "control.tab_selected": "#ffffff",
            "state.focus_ring": "#4f8ccf",
            "state.selected_bg": "#dbeafe",
            "state.disabled_bg": "#eef1f5",
            "state.disabled_text": "#8c9ba8",
            "state.pulse_bg": "rgba(79, 140, 207, 0.18)",
            "state.pulse_soft": "rgba(79, 140, 207, 0.12)",
        },
        radius=10,
        compact_radius=7,
    )


def default_dark_tokens() -> ThemeTokens:
    """Return default dark-mode tokens.

    Summary:
        Provide a high-contrast dark palette with separate semantic tuning.
    Inputs:
        - None.
    Outputs:
        - ThemeTokens for dark mode.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _tokens_for_mode.
    Why this exists:
        Dark mode must remain legible while preserving a softer non-primary surface hierarchy.
    """
    return ThemeTokens(
        colors={
            "surface.app": "#0c1117",
            "surface.root": "#111926",
            "surface.section_outer": "#141f2d",
            "surface.section_inset": "#0f1823",
            "surface.panel": "#162231",
            "surface.panel_alt": "#1a2a3a",
            "surface.input": "#132030",
            "surface.input_active": "#17283c",
            "surface.selection": "#24415f",
            "surface.disabled": "#111b28",
            "surface.table_header": "#1b2a3b",
            "surface.scroll_track": "#122030",
            "surface.scroll_thumb": "#324960",
            "surface.scroll_thumb_hover": "#3d5973",
            "surface.status_ready": "#132744",
            "surface.status_working": "#3a2b10",
            "surface.status_success": "#153222",
            "surface.status_error": "#3a1c1a",
            "text.primary": "#e5edf6",
            "text.section_header": "#f3f8ff",
            "text.form_label": "#c7d4e2",
            "text.hint": "#9fb0c1",
            "text.empty_state": "#a9b8c8",
            "text.status": "#deebf8",
            "text.inverse": "#0b1320",
            "text.disabled": "#6f8297",
            "text.ready": "#9cc7ff",
            "text.working": "#ffd787",
            "text.success": "#8cdba2",
            "text.error": "#ffb7b3",
            "border.default": "#2f455d",
            "border.subtle": "#24374c",
            "border.focus": "#6ba9eb",
            "border.selected": "#7fb7f2",
            "border.disabled": "#1f2f42",
            "border.ready": "#355982",
            "border.working": "#6f5630",
            "border.success": "#356248",
            "border.error": "#724240",
            "control.button_default_bg": "#172637",
            "control.button_default_hover": "#1c3045",
            "control.button_default_pressed": "#203752",
            "control.button_toolbar_bg": "#1a2a3d",
            "control.button_toolbar_hover": "#22354b",
            "control.button_primary_bg": "#3c88d9",
            "control.button_primary_hover": "#4a93e2",
            "control.button_primary_pressed": "#2f77c8",
            "control.button_segment_bg": "#1a2a3d",
            "control.button_segment_hover": "#22354a",
            "control.button_segment_selected": "#2a3d55",
            "control.input_bg": "#132030",
            "control.input_disabled_bg": "#111b28",
            "control.tab_bg": "#182838",
            "control.tab_hover": "#22364b",
            "control.tab_selected": "#2a3d55",
            "state.focus_ring": "#6ba9eb",
            "state.selected_bg": "#24415f",
            "state.disabled_bg": "#111b28",
            "state.disabled_text": "#6f8297",
            "state.pulse_bg": "rgba(107, 169, 235, 0.24)",
            "state.pulse_soft": "rgba(107, 169, 235, 0.16)",
        },
        radius=10,
        compact_radius=7,
    )


def resolve_color(*, tokens: ThemeTokens, role: str) -> str:
    """Resolve a semantic color role.

    Summary:
        Return one color value for a semantic role from the active token set.
    Inputs:
        - tokens: Active theme token set.
        - role: Semantic role key such as "surface.panel" or "text.hint".
    Outputs:
        - Hex or rgba color string.
    Side effects:
        None.
    Error handling:
        Falls back to a visible debug color when a role is missing.
    Ties to other methods:
        Used by build_stylesheet and apply_theme for every color lookup.
    Why this exists:
        A single resolver guarantees widgets do not use host defaults or ad-hoc color literals.
    """
    return str(tokens.colors.get(role, "#ff00ff"))


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Build a Qt stylesheet from semantic tokens.

    Summary:
        Generate one QSS ruleset with semantic roles for text, containers, controls, and states.
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
        Keeping all visual behavior in one stylesheet prevents drift and simplifies tuning.
    """
    if not isinstance(tokens, ThemeTokens):
        return ""

    def c(role: str) -> str:
        return resolve_color(tokens=tokens, role=role)

    r = int(tokens.radius)
    cr = int(tokens.compact_radius)
    return f"""
QWidget {{
  color: {c("text.primary")};
  background: transparent;
}}

QMainWindow {{
  background: {c("surface.app")};
}}

QWidget#chapterSplitterRoot {{
  background: {c("surface.root")};
}}

QSplitter::handle {{
  background: {c("surface.root")};
}}

QWidget[container_role="outer_section"] {{
  background: {c("surface.section_outer")};
  border: 1px solid {c("border.subtle")};
  border-radius: {r}px;
}}

QWidget[container_role="inset_content"] {{
  background: {c("surface.section_inset")};
  border: 1px solid {c("border.default")};
  border-radius: {r}px;
}}

QLabel {{
  color: {c("text.primary")};
  background: transparent;
}}

QLabel[text_role="section_header"] {{
  color: {c("text.section_header")};
  font-size: 14px;
  font-weight: 600;
}}

QLabel[text_role="form_label"] {{
  color: {c("text.form_label")};
  font-size: 12px;
  font-weight: 500;
}}

QLabel[text_role="hint"],
QLabel[text_role="muted"],
QToolButton[muted="true"],
QLabel[muted="true"] {{
  color: {c("text.hint")};
}}

QLabel[text_role="empty_state"] {{
  color: {c("text.empty_state")};
  background: {c("surface.section_inset")};
  border: 1px dashed {c("border.subtle")};
  border-radius: {cr}px;
  padding: 12px;
}}

QLabel[text_role="status"] {{
  color: {c("text.ready")};
  background: {c("surface.status_ready")};
  border: 1px solid {c("border.ready")};
  border-radius: {cr}px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}}

QLabel[text_role="status"][status_level="working"] {{
  color: {c("text.working")};
  background: {c("surface.status_working")};
  border: 1px solid {c("border.working")};
}}

QLabel[text_role="status"][status_level="success"] {{
  color: {c("text.success")};
  background: {c("surface.status_success")};
  border: 1px solid {c("border.success")};
}}

QLabel[text_role="status"][status_level="error"] {{
  color: {c("text.error")};
  background: {c("surface.status_error")};
  border: 1px solid {c("border.error")};
}}

QLabel[error="true"] {{
  color: {c("text.error")};
}}

QTabWidget::pane {{
  border: none;
  background: transparent;
  margin-top: 10px;
}}

QTabBar::tab {{
  min-height: 30px;
  min-width: 120px;
  padding: 6px 16px;
  font-size: 13px;
  color: {c("text.form_label")};
  background: {c("control.tab_bg")};
  border: 1px solid {c("border.default")};
  border-right: none;
}}

QTabBar::tab:first {{
  border-top-left-radius: {r}px;
  border-bottom-left-radius: {r}px;
}}

QTabBar::tab:last {{
  border-right: 1px solid {c("border.default")};
  border-top-right-radius: {r}px;
  border-bottom-right-radius: {r}px;
}}

QTabBar::tab:hover:!selected {{
  background: {c("control.tab_hover")};
}}

QTabBar::tab:selected {{
  color: {c("text.primary")};
  background: {c("control.tab_selected")};
  border-color: {c("border.selected")};
  font-weight: 600;
}}

QLineEdit, QSpinBox, QComboBox {{
  color: {c("text.primary")};
  background: {c("control.input_bg")};
  border: 1px solid {c("border.default")};
  border-radius: {cr}px;
  padding: 6px 8px;
  selection-background-color: {c("state.selected_bg")};
  selection-color: {c("text.primary")};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
  border: 1px solid {c("state.focus_ring")};
}}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
  color: {c("state.disabled_text")};
  background: {c("control.input_disabled_bg")};
  border: 1px solid {c("border.disabled")};
}}

QLineEdit[active_row="true"], QSpinBox[active_row="true"] {{
  background: {c("surface.input_active")};
  border: 1px solid {c("border.selected")};
}}

QLineEdit[pulse="true"], QSpinBox[pulse="true"] {{
  background: {c("state.pulse_bg")};
}}

QToolButton[pulse="true"] {{
  background: {c("state.pulse_soft")};
}}

QToolButton[active_row="true"] {{
  border: 1px solid {c("border.selected")};
}}

QPushButton, QToolButton {{
  color: {c("text.primary")};
  background: {c("control.button_default_bg")};
  border: 1px solid {c("border.default")};
  border-radius: {cr}px;
  padding: 8px 12px;
}}

QPushButton[button_role="default"], QToolButton[button_role="default"] {{
  background: {c("control.button_default_bg")};
}}

QPushButton[button_role="toolbar"], QToolButton[button_role="toolbar"] {{
  background: {c("control.button_toolbar_bg")};
}}

QPushButton[button_role="primary_cta"], QToolButton[button_role="primary_cta"] {{
  color: {c("text.inverse")};
  background: {c("control.button_primary_bg")};
  border: 1px solid {c("control.button_primary_bg")};
  font-weight: 600;
}}

QPushButton[button_role="segmented_tab"], QToolButton[button_role="segmented_tab"] {{
  background: {c("control.button_segment_bg")};
}}

QPushButton[button_role="segmented_tab"][selected="true"],
QToolButton[button_role="segmented_tab"][selected="true"] {{
  background: {c("control.button_segment_selected")};
  border-color: {c("border.selected")};
}}

QPushButton:hover, QToolButton:hover {{
  background: {c("control.button_default_hover")};
}}

QPushButton[button_role="toolbar"]:hover, QToolButton[button_role="toolbar"]:hover {{
  background: {c("control.button_toolbar_hover")};
}}

QPushButton[button_role="primary_cta"]:hover, QToolButton[button_role="primary_cta"]:hover {{
  background: {c("control.button_primary_hover")};
  border-color: {c("control.button_primary_hover")};
}}

QPushButton:pressed, QToolButton:pressed {{
  background: {c("control.button_default_pressed")};
}}

QPushButton[button_role="primary_cta"]:pressed,
QToolButton[button_role="primary_cta"]:pressed {{
  background: {c("control.button_primary_pressed")};
  border-color: {c("control.button_primary_pressed")};
}}

QPushButton:focus, QToolButton:focus {{
  border: 1px solid {c("state.focus_ring")};
}}

QPushButton:disabled, QToolButton:disabled {{
  color: {c("state.disabled_text")};
  background: {c("state.disabled_bg")};
  border: 1px solid {c("border.disabled")};
}}

QToolButton[destructive="true"] {{
  color: {c("text.error")};
}}

QToolButton[active_row="true"][destructive="true"] {{
  color: {c("text.error")};
  border-color: {c("border.error")};
}}

QTableWidget, QTableView {{
  color: {c("text.primary")};
  border: 1px solid {c("border.default")};
  border-radius: {r}px;
  background: {c("surface.panel")};
  alternate-background-color: {c("surface.panel_alt")};
  gridline-color: {c("border.subtle")};
  selection-background-color: {c("state.selected_bg")};
  selection-color: {c("text.primary")};
}}

QTableView {{
  outline: 0;
}}

QTableWidget::item:selected, QTableView::item:selected {{
  background: {c("state.selected_bg")};
}}

QHeaderView::section {{
  color: {c("text.form_label")};
  background: {c("surface.table_header")};
  border: none;
  border-bottom: 1px solid {c("border.default")};
  padding: 0 8px;
  min-height: 30px;
  font-size: 12px;
  font-weight: 600;
}}

QListWidget {{
  color: {c("text.primary")};
  border: 1px solid {c("border.default")};
  border-radius: {r}px;
  background: {c("surface.section_inset")};
  selection-background-color: {c("state.selected_bg")};
}}

QPdfView {{
  border: 1px solid {c("border.default")};
  border-radius: {r}px;
  background: {c("surface.panel_alt")};
}}

QPdfView::viewport {{
  background: {c("surface.panel_alt")};
}}

QScrollBar:vertical {{
  background: {c("surface.scroll_track")};
  border: none;
  width: 10px;
  margin: 2px;
}}

QScrollBar::handle:vertical {{
  background: {c("surface.scroll_thumb")};
  border-radius: 5px;
  min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
  background: {c("surface.scroll_thumb_hover")};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0px;
}}

QScrollBar:horizontal {{
  background: {c("surface.scroll_track")};
  border: none;
  height: 10px;
  margin: 2px;
}}

QScrollBar::handle:horizontal {{
  background: {c("surface.scroll_thumb")};
  border-radius: 5px;
  min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
  background: {c("surface.scroll_thumb_hover")};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
  width: 0px;
}}
""".strip()


def _system_color_scheme() -> ResolvedColorMode:
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
        Used by _resolve_color_mode and install_system_theme_listener.
    Why this exists:
        Auto mode must track OS-level dark mode preference.
    """
    try:
        from PySide6 import QtCore, QtGui

        scheme = QtGui.QGuiApplication.styleHints().colorScheme()
        if scheme == QtCore.Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        return "light"
    return "light"


def _resolve_color_mode(color_mode: ColorMode) -> ResolvedColorMode:
    """Resolve the requested color mode to a concrete light or dark mode.

    Summary:
        Expand the user-facing color mode setting into the active runtime mode.
    Inputs:
        - color_mode: Requested mode (light, dark, auto).
    Outputs:
        - Concrete resolved mode (light or dark).
    Side effects:
        Reads OS color scheme in auto mode.
    Error handling:
        Falls back to light mode for unsupported values.
    Ties to other methods:
        Used by apply_theme.
    Why this exists:
        Theme application and palette generation need a deterministic mode.
    """
    if color_mode == "light":
        return "light"
    if color_mode == "dark":
        return "dark"
    if color_mode == "auto":
        return _system_color_scheme()
    return "light"


def _tokens_for_mode(mode: ResolvedColorMode) -> ThemeTokens:
    """Return tokens for a resolved color mode.

    Summary:
        Provide a token set tailored to the active light or dark mode.
    Inputs:
        - mode: Resolved mode.
    Outputs:
        - ThemeTokens instance.
    Side effects:
        None.
    Error handling:
        Falls back to light tokens for unknown modes.
    Ties to other methods:
        Used by apply_theme.
    Why this exists:
        Mode-specific token lookup should stay in one location.
    """
    return default_dark_tokens() if mode == "dark" else default_tokens()


def _preferred_style_name(*, available_styles: list[str]) -> str:
    """Return the preferred Qt widget style for the current platform.

    Summary:
        Prefer native rounded controls where available and fall back safely.
    Inputs:
        - available_styles: Styles reported by QStyleFactory.
    Outputs:
        - Selected style name.
    Side effects:
        Reads the host platform name.
    Error handling:
        Falls back to Fusion when no styles are available.
    Ties to other methods:
        Used by apply_theme before setting palette and stylesheet.
    Why this exists:
        Native style improves baseline control quality, especially on macOS.
    """
    if not available_styles:
        return "Fusion"

    style_by_lower = {name.lower(): name for name in available_styles}
    platform_name = platform.system().lower()
    preferred = ["macOS", "macintosh", "Fusion"] if platform_name == "darwin" else ["Fusion"]
    for style_name in preferred:
        resolved = style_by_lower.get(style_name.lower())
        if resolved is not None:
            return resolved
    return available_styles[0]


def apply_theme(*, app: object, color_mode: ColorMode = "auto") -> None:
    """Apply the configured theme mode to a Qt application.

    Summary:
        Select a widget style, build the token set, and apply palette plus stylesheet globally.
    Inputs:
        - app: QApplication instance.
        - color_mode: Preferred mode (light, dark, auto).
    Outputs:
        - None.
    Side effects:
        Mutates QApplication style, palette, stylesheet, and app properties.
    Error handling:
        Best-effort only; no exceptions escape from this function.
    Ties to other methods:
        Called by ui.qt.workflow.workflow and the theme-change listener.
    Why this exists:
        The UI must be deterministic across platforms and independent of host defaults.
    """
    try:
        from PySide6 import QtGui, QtWidgets

        if not isinstance(app, QtWidgets.QApplication):
            return

        resolved_mode = _resolve_color_mode(color_mode)
        tokens = _tokens_for_mode(resolved_mode)

        style_factory = getattr(QtWidgets, "QStyleFactory", None)
        available_styles = list(style_factory.keys()) if style_factory is not None else ["Fusion"]
        app.setStyle(_preferred_style_name(available_styles=available_styles))

        palette = QtGui.QPalette()
        palette.setColor(
            QtGui.QPalette.ColorRole.Window,
            QtGui.QColor(resolve_color(tokens=tokens, role="surface.app")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.Base,
            QtGui.QColor(resolve_color(tokens=tokens, role="surface.input")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.AlternateBase,
            QtGui.QColor(resolve_color(tokens=tokens, role="surface.panel_alt")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.Text,
            QtGui.QColor(resolve_color(tokens=tokens, role="text.primary")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.WindowText,
            QtGui.QColor(resolve_color(tokens=tokens, role="text.primary")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.Button,
            QtGui.QColor(resolve_color(tokens=tokens, role="control.button_default_bg")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.ButtonText,
            QtGui.QColor(resolve_color(tokens=tokens, role="text.primary")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.Highlight,
            QtGui.QColor(resolve_color(tokens=tokens, role="state.selected_bg")),
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.HighlightedText,
            QtGui.QColor(resolve_color(tokens=tokens, role="text.primary")),
        )
        app.setPalette(palette)
        app.setStyleSheet(build_stylesheet(tokens))
        app.setProperty("_chapter_splitter_color_mode", color_mode)
        app.setProperty("_chapter_splitter_resolved_mode", resolved_mode)
    except Exception:
        return


def install_system_theme_listener(*, app: object, color_mode: ColorMode = "auto") -> None:
    """Install an OS theme change listener that re-applies theme tokens.

    Summary:
        Subscribe to Qt's colorSchemeChanged signal so auto mode follows system light or dark.
    Inputs:
        - app: QApplication instance.
        - color_mode: Preferred mode (light, dark, auto).
    Outputs:
        - None.
    Side effects:
        Connects a signal handler and stores a reference on the app to keep it alive.
    Error handling:
        No-ops when Qt style hints are unavailable or mode is not auto.
    Ties to other methods:
        Called by ui.qt.workflow after creating the QApplication.
    Why this exists:
        Auto mode should react instantly when OS appearance changes.
    """
    if color_mode != "auto":
        return
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
                apply_theme(app=app, color_mode=color_mode)

        listener = _ThemeListener()
        hints.colorSchemeChanged.connect(listener.on_scheme_changed)
        app.setProperty("_chapter_splitter_theme_listener", listener)
    except Exception:
        return
