"""Configuration for the desktop interface."""

from __future__ import annotations

from typing import Literal

from ....core.errors import ConfigurationError, format_error_message

UIColorMode = Literal["light", "dark", "auto"]


class UIConfig:
    """Settings consumed by the Qt workflow."""

    def __init__(
        self,
        window_width: int,
        window_height: int,
        close_button_label: str,
        undo_button_label: str,
        add_button_label: str,
        auto_detect_button_label: str,
        export_button_label: str,
        chapter_title_prefix: str,
        no_chapters_title: str,
        error_dialog_title: str,
        success_dialog_title: str,
        success_dialog_message_template: str,
        action_rate_limit_seconds: float,
        chapter_window_title: str,
        file_dialog_title: str,
        confirm_auto_detect_overwrite: bool,
        confirm_auto_detect_overwrite_title: str,
        confirm_auto_detect_overwrite_message: str,
        prompt_open_output_dir_after_export: bool,
        open_output_dir_prompt_title: str,
        open_output_dir_prompt_message_template: str,
        enable_keyboard_shortcuts: bool,
        color_mode: UIColorMode,
        auto_show_review_after_detect: bool,
        auto_detect_on_open: bool,
    ) -> None:
        self.window_width = window_width
        self.window_height = window_height
        self.close_button_label = close_button_label
        self.undo_button_label = undo_button_label
        self.add_button_label = add_button_label
        self.auto_detect_button_label = auto_detect_button_label
        self.export_button_label = export_button_label
        self.chapter_title_prefix = chapter_title_prefix
        self.no_chapters_title = no_chapters_title
        self.error_dialog_title = error_dialog_title
        self.success_dialog_title = success_dialog_title
        self.success_dialog_message_template = success_dialog_message_template
        self.action_rate_limit_seconds = action_rate_limit_seconds
        self.chapter_window_title = chapter_window_title
        self.file_dialog_title = file_dialog_title
        self.confirm_auto_detect_overwrite = confirm_auto_detect_overwrite
        self.confirm_auto_detect_overwrite_title = confirm_auto_detect_overwrite_title
        self.confirm_auto_detect_overwrite_message = confirm_auto_detect_overwrite_message
        self.prompt_open_output_dir_after_export = prompt_open_output_dir_after_export
        self.open_output_dir_prompt_title = open_output_dir_prompt_title
        self.open_output_dir_prompt_message_template = open_output_dir_prompt_message_template
        self.enable_keyboard_shortcuts = enable_keyboard_shortcuts
        self.color_mode = color_mode
        self.auto_show_review_after_detect = auto_show_review_after_detect
        self.auto_detect_on_open = auto_detect_on_open

    def validate(self, location: str) -> None:
        """Reject values that would make the interface unusable."""
        error_location = f"{__name__}.UIConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.window_width <= 0 or self.window_height <= 0:
            self._invalid(
                error_location,
                f"ui.window_width and ui.window_height must be positive.{context}",
            )
        if self.action_rate_limit_seconds < 0:
            self._invalid(
                error_location,
                f"ui.action_rate_limit_seconds must be non negative.{context}",
            )
        required_text = {
            "close_button_label": self.close_button_label,
            "undo_button_label": self.undo_button_label,
            "add_button_label": self.add_button_label,
            "auto_detect_button_label": self.auto_detect_button_label,
            "export_button_label": self.export_button_label,
            "chapter_title_prefix": self.chapter_title_prefix,
            "no_chapters_title": self.no_chapters_title,
            "error_dialog_title": self.error_dialog_title,
            "success_dialog_title": self.success_dialog_title,
            "success_dialog_message_template": self.success_dialog_message_template,
            "chapter_window_title": self.chapter_window_title,
            "file_dialog_title": self.file_dialog_title,
        }
        for key, value in required_text.items():
            if not value.strip():
                self._invalid(error_location, f"ui.{key} must be non empty.{context}")
        if self.confirm_auto_detect_overwrite:
            for key, value in (
                ("confirm_auto_detect_overwrite_title", self.confirm_auto_detect_overwrite_title),
                (
                    "confirm_auto_detect_overwrite_message",
                    self.confirm_auto_detect_overwrite_message,
                ),
            ):
                if not value.strip():
                    self._invalid(error_location, f"ui.{key} must be non empty.{context}")
        if self.prompt_open_output_dir_after_export:
            for key, value in (
                ("open_output_dir_prompt_title", self.open_output_dir_prompt_title),
                (
                    "open_output_dir_prompt_message_template",
                    self.open_output_dir_prompt_message_template,
                ),
            ):
                if not value.strip():
                    self._invalid(error_location, f"ui.{key} must be non empty.{context}")
        if self.color_mode not in ("light", "dark", "auto"):
            self._invalid(
                error_location,
                f"ui.color_mode must be one of: light, dark, auto.{context}",
            )

    @staticmethod
    def _invalid(error_location: str, message: str) -> None:
        raise ConfigurationError(format_error_message(error_location, message))


__all__ = ["UIColorMode", "UIConfig"]
