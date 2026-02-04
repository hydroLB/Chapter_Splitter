"""Tkinter UI configuration schema."""

from __future__ import annotations

from collections.abc import Sequence

from ....core.errors import ConfigurationError, format_error_message


class UIConfig:
    """Tkinter UI configuration.

    Purpose:
        Centralize tunable UI labels, layout, and behavior settings.
    Ties To:
        Used by Tk window builders, dialogs, and widgets.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(
        self,
        window_width: int,
        window_height: int,
        window_offset_x: int,
        window_offset_y: int,
        pdf_info_template: str,
        pdf_info_wraplength: int,
        open_pdf_button_label: str,
        close_button_label: str,
        row_limit: int,
        base_height: int,
        row_height: int,
        height_threshold_rows: int,
        rows_per_column: int,
        column_widths: Sequence[int],
        header_rows: int,
        grid_columns: int,
        grid_entry_width: int,
        grid_remove_button_width: int,
        grid_padding_x: int,
        grid_padding_y: int,
        grid_frame_padding_x: int,
        grid_frame_padding_y: int,
        grid_header_labels: Sequence[str],
        undo_button_label: str,
        remove_button_label: str,
        add_button_label: str,
        auto_detect_button_label: str,
        export_button_label: str,
        chapter_title_prefix: str,
        no_chapters_title: str,
        no_chapters_message: str,
        error_dialog_title: str,
        success_dialog_title: str,
        success_dialog_message_template: str,
        auto_open_viewer: bool,
        action_rate_limit_seconds: float,
        chapter_window_title: str,
        file_dialog_title: str,
        button_row_padding: int,
        button_gap_padding: int,
        export_button_padding: int,
        confirm_auto_detect_overwrite: bool,
        confirm_auto_detect_overwrite_title: str,
        confirm_auto_detect_overwrite_message: str,
        prompt_open_output_dir_after_export: bool,
        open_output_dir_prompt_title: str,
        open_output_dir_prompt_message_template: str,
        enable_keyboard_shortcuts: bool,
        status_hint: str,
        enable_pdf_preview: bool,
        pdf_preview_zoom: float,
        pdf_preview_cache_entries: int,
        pdf_preview_render_timeout_seconds: float,
    ) -> None:
        """Initialize UI configuration.

        Purpose:
            Provide window sizing, limits, and behavior for the Tkinter UI.
        Ties To:
            Used by chapter window creation and grid layout logic.
        Inputs:
            - window_width: Default window width.
            - window_height: Default window height.
            - window_offset_x: Screen offset on the X axis.
            - window_offset_y: Screen offset on the Y axis.
            - pdf_info_template: Template string for the PDF info header.
            - pdf_info_wraplength: Wrap length for the PDF info header label.
            - open_pdf_button_label: Label for the open PDF button.
            - close_button_label: Label for the close window button.
            - row_limit: Maximum number of chapter rows.
            - base_height: Base height for the window.
            - row_height: Height increment per row.
            - height_threshold_rows: Row count before height expands.
            - rows_per_column: Number of rows per column block in the grid.
            - column_widths: List of window widths for column breakpoints.
            - header_rows: Number of header rows in the grid.
            - grid_columns: Number of grid columns per row block.
            - grid_entry_width: Width of chapter entry fields.
            - grid_remove_button_width: Width of the remove button.
            - grid_padding_x: Horizontal padding for grid widgets.
            - grid_padding_y: Vertical padding for grid widgets.
            - grid_frame_padding_x: Horizontal padding for the grid frame.
            - grid_frame_padding_y: Vertical padding for the grid frame.
            - grid_header_labels: Labels for grid header columns.
            - undo_button_label: Label for the undo button.
            - remove_button_label: Label for the remove row button.
            - add_button_label: Label for the add row button.
            - auto_detect_button_label: Label for the auto detect button.
            - export_button_label: Label for the export button.
            - chapter_title_prefix: Prefix used for auto named chapters.
            - no_chapters_title: Title for no chapters dialog.
            - no_chapters_message: Message for no chapters dialog.
            - error_dialog_title: Title for error dialogs.
            - success_dialog_title: Title for success dialogs.
            - success_dialog_message_template: Template for success message.
            - auto_open_viewer: Whether to auto open the PDF viewer.
            - action_rate_limit_seconds: Rate limit for button actions.
            - chapter_window_title: Title for the chapter window.
            - file_dialog_title: Title for the PDF file dialog.
            - button_row_padding: Padding for the action button row.
            - button_gap_padding: Horizontal gap between buttons.
            - export_button_padding: Vertical padding for the export button.
            - confirm_auto_detect_overwrite: Whether auto detect confirms before replacing the grid.
            - confirm_auto_detect_overwrite_title: Title for the overwrite confirmation.
            - confirm_auto_detect_overwrite_message: Message for the overwrite confirmation.
            - prompt_open_output_dir_after_export: Whether to prompt to open the output folder.
            - open_output_dir_prompt_title: Title for the open output folder prompt.
            - open_output_dir_prompt_message_template: Template for the prompt message.
            - enable_keyboard_shortcuts: Whether the chapter window binds keyboard shortcuts.
            - status_hint: Status bar hint displayed at the bottom of the window.
            - enable_pdf_preview: Whether the chapter window shows an embedded PDF preview panel.
            - pdf_preview_zoom: Render zoom factor for the embedded preview.
            - pdf_preview_cache_entries: Maximum number of rendered pages to cache in memory.
            - pdf_preview_render_timeout_seconds: Time budget for rendering a single preview page.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.window_width = window_width
        self.window_height = window_height
        self.window_offset_x = window_offset_x
        self.window_offset_y = window_offset_y
        self.pdf_info_template = pdf_info_template
        self.pdf_info_wraplength = pdf_info_wraplength
        self.open_pdf_button_label = open_pdf_button_label
        self.close_button_label = close_button_label
        self.row_limit = row_limit
        self.base_height = base_height
        self.row_height = row_height
        self.height_threshold_rows = height_threshold_rows
        self.rows_per_column = rows_per_column
        self.column_widths = tuple(column_widths)
        self.header_rows = header_rows
        self.grid_columns = grid_columns
        self.grid_entry_width = grid_entry_width
        self.grid_remove_button_width = grid_remove_button_width
        self.grid_padding_x = grid_padding_x
        self.grid_padding_y = grid_padding_y
        self.grid_frame_padding_x = grid_frame_padding_x
        self.grid_frame_padding_y = grid_frame_padding_y
        self.grid_header_labels = tuple(grid_header_labels)
        self.undo_button_label = undo_button_label
        self.remove_button_label = remove_button_label
        self.add_button_label = add_button_label
        self.auto_detect_button_label = auto_detect_button_label
        self.export_button_label = export_button_label
        self.chapter_title_prefix = chapter_title_prefix
        self.no_chapters_title = no_chapters_title
        self.no_chapters_message = no_chapters_message
        self.error_dialog_title = error_dialog_title
        self.success_dialog_title = success_dialog_title
        self.success_dialog_message_template = success_dialog_message_template
        self.auto_open_viewer = auto_open_viewer
        self.action_rate_limit_seconds = action_rate_limit_seconds
        self.chapter_window_title = chapter_window_title
        self.file_dialog_title = file_dialog_title
        self.button_row_padding = button_row_padding
        self.button_gap_padding = button_gap_padding
        self.export_button_padding = export_button_padding
        self.confirm_auto_detect_overwrite = confirm_auto_detect_overwrite
        self.confirm_auto_detect_overwrite_title = confirm_auto_detect_overwrite_title
        self.confirm_auto_detect_overwrite_message = confirm_auto_detect_overwrite_message
        self.prompt_open_output_dir_after_export = prompt_open_output_dir_after_export
        self.open_output_dir_prompt_title = open_output_dir_prompt_title
        self.open_output_dir_prompt_message_template = open_output_dir_prompt_message_template
        self.enable_keyboard_shortcuts = enable_keyboard_shortcuts
        self.status_hint = status_hint
        self.enable_pdf_preview = enable_pdf_preview
        self.pdf_preview_zoom = pdf_preview_zoom
        self.pdf_preview_cache_entries = pdf_preview_cache_entries
        self.pdf_preview_render_timeout_seconds = pdf_preview_render_timeout_seconds

    def validate(self, location: str) -> None:
        """Validate UI configuration.

        Purpose:
            Ensure window sizing and row limits are valid.
        Ties To:
            Called by Settings.validate before UI layout is used.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - ConfigurationError: When UI settings are invalid.
        """
        error_location = f"{__name__}.UIConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.window_width <= 0 or self.window_height <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.window_width and ui.window_height must be positive.{context}",
                )
            )
        if not self.pdf_info_template.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.pdf_info_template must be non empty.{context}",
                )
            )
        if self.pdf_info_wraplength <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.pdf_info_wraplength must be positive.{context}",
                )
            )
        if not self.open_pdf_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.open_pdf_button_label must be non empty.{context}",
                )
            )
        if not self.close_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.close_button_label must be non empty.{context}",
                )
            )
        if self.row_limit < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.row_limit must be at least 1.{context}",
                )
            )
        if self.base_height <= 0 or self.row_height <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.base_height and ui.row_height must be positive.{context}",
                )
            )
        if self.height_threshold_rows < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.height_threshold_rows must be non negative.{context}",
                )
            )
        if self.action_rate_limit_seconds < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.action_rate_limit_seconds must be non negative.{context}",
                )
            )
        if not self.chapter_window_title.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.chapter_window_title must be non empty.{context}",
                )
            )
        if self.rows_per_column < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.rows_per_column must be at least 1.{context}",
                )
            )
        if self.header_rows < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.header_rows must be non negative.{context}",
                )
            )
        if not self.column_widths:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.column_widths must not be empty.{context}",
                )
            )
        if any(width <= 0 for width in self.column_widths):
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.column_widths must contain positive values.{context}",
                )
            )
        if not self.file_dialog_title.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.file_dialog_title must be non empty.{context}",
                )
            )
        if self.grid_columns < 4:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.grid_columns must be at least 4.{context}",
                )
            )
        if self.grid_entry_width < 1 or self.grid_remove_button_width < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "ui.grid_entry_width and ui.grid_remove_button_width must be positive."
                    f"{context}",
                )
            )
        if self.grid_padding_x < 0 or self.grid_padding_y < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.grid_padding_x and ui.grid_padding_y must be non negative.{context}",
                )
            )
        if self.grid_frame_padding_x < 0 or self.grid_frame_padding_y < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "ui.grid_frame_padding_x and ui.grid_frame_padding_y must be non negative."
                    f"{context}",
                )
            )
        if not self.grid_header_labels:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.grid_header_labels must not be empty.{context}",
                )
            )
        if len(self.grid_header_labels) != self.grid_columns:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.grid_header_labels length must match ui.grid_columns.{context}",
                )
            )
        if not self.undo_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.undo_button_label must be non empty.{context}",
                )
            )
        if not self.remove_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.remove_button_label must be non empty.{context}",
                )
            )
        if not self.add_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.add_button_label must be non empty.{context}",
                )
            )
        if not self.auto_detect_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.auto_detect_button_label must be non empty.{context}",
                )
            )
        if not self.export_button_label.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.export_button_label must be non empty.{context}",
                )
            )
        if not self.chapter_title_prefix.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.chapter_title_prefix must be non empty.{context}",
                )
            )
        if not self.no_chapters_title.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.no_chapters_title must be non empty.{context}",
                )
            )
        if not self.no_chapters_message.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.no_chapters_message must be non empty.{context}",
                )
            )
        if not self.error_dialog_title.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.error_dialog_title must be non empty.{context}",
                )
            )
        if not self.success_dialog_title.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.success_dialog_title must be non empty.{context}",
                )
            )
        if not self.success_dialog_message_template.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.success_dialog_message_template must be non empty.{context}",
                )
            )
        if self.button_row_padding < 0 or self.button_gap_padding < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "ui.button_row_padding and ui.button_gap_padding must be non negative."
                    f"{context}",
                )
            )
        if self.export_button_padding < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.export_button_padding must be non negative.{context}",
                )
            )
        if self.confirm_auto_detect_overwrite:
            if not self.confirm_auto_detect_overwrite_title.strip():
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"ui.confirm_auto_detect_overwrite_title must be non empty.{context}",
                    )
                )
            if not self.confirm_auto_detect_overwrite_message.strip():
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"ui.confirm_auto_detect_overwrite_message must be non empty.{context}",
                    )
                )
        if self.prompt_open_output_dir_after_export:
            if not self.open_output_dir_prompt_title.strip():
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"ui.open_output_dir_prompt_title must be non empty.{context}",
                    )
                )
            if not self.open_output_dir_prompt_message_template.strip():
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"ui.open_output_dir_prompt_message_template must be non empty.{context}",
                    )
                )
        if not self.status_hint.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.status_hint must be non empty.{context}",
                )
            )
        if self.pdf_preview_zoom <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.pdf_preview_zoom must be positive.{context}",
                )
            )
        if self.pdf_preview_cache_entries < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"ui.pdf_preview_cache_entries must be non negative.{context}",
                )
            )
        if self.pdf_preview_render_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "ui.pdf_preview_render_timeout_seconds must be positive." f"{context}",
                )
            )
