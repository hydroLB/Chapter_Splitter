"""Build typed settings objects from raw configuration mappings."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ....core.errors import ConfigurationError, format_error_message
from ...schema import (
    AppConfig,
    DetectionConfig,
    IOConfig,
    LoggingConfig,
    PerformanceConfig,
    RetryConfig,
    Settings,
    UIConfig,
    ValidationConfig,
)
from ...schema.sections.io import OutputCollisionPolicy
from ...schema.sections.ui import PdfPreviewFitMode, UIColorMode
from .readers import (
    get_section,
    read_bool,
    read_float,
    read_int,
    read_int_list,
    read_str,
    read_str_list,
)


def build_settings(raw: dict[str, object], location: str) -> Settings:
    """Build a fully-typed Settings object from raw config values.

    Summary:
        Convert merged TOML dictionaries into strict schema objects consumed by runtime modules.
    Ties to other methods:
        Used by chapter_splitter.config.loader.api.load_settings.
    Inputs:
        - raw: Merged top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - Settings object with all typed sections.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When top-level config data is invalid.
    """
    error_location = f"{__name__}.build_settings"
    context = f" Context: {location}." if location else ""
    if not isinstance(raw, dict):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Config root must be a table.{context}",
            )
        )

    app = _build_app_config(raw, location)
    logging = _build_logging_config(raw, location)
    io = _build_io_config(raw, location)
    retry = _build_retry_config(raw, location)
    ui = _build_ui_config(raw, location)
    validation = _build_validation_config(raw, location)
    detection = _build_detection_config(raw, location)
    performance = _build_performance_config(raw, location)

    return Settings(
        app=app,
        logging=logging,
        io=io,
        retry=retry,
        ui=ui,
        validation=validation,
        detection=detection,
        performance=performance,
    )


def _build_app_config(raw: dict[str, object], location: str) -> AppConfig:
    """Build AppConfig from raw section values.

    Summary:
        Convert the [app] section to a typed AppConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - AppConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When app section keys are missing or invalid.
    """
    section = get_section(raw, "app", location)
    return AppConfig(
        title=read_str(section, "title", location),
        environment=read_str(section, "environment", location),
        correlation_id_prefix=read_str(section, "correlation_id_prefix", location),
    )


def _build_logging_config(raw: dict[str, object], location: str) -> LoggingConfig:
    """Build LoggingConfig from raw section values.

    Summary:
        Convert the [logging] section to a typed LoggingConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - LoggingConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When logging section keys are missing or invalid.
    """
    section = get_section(raw, "logging", location)
    return LoggingConfig(
        level=read_str(section, "level", location),
        formatter=read_str(section, "formatter", location),
        console_enabled=read_bool(section, "console_enabled", location),
        file_enabled=read_bool(section, "file_enabled", location),
        file_path=Path(read_str(section, "file_path", location)),
        redact_keys=read_str_list(section, "redact_keys", location),
        redact_values=read_str_list(section, "redact_values", location),
    )


def _build_io_config(raw: dict[str, object], location: str) -> IOConfig:
    """Build IOConfig from raw section values.

    Summary:
        Convert the [io] section to a typed IOConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - IOConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When io section keys are missing or invalid.
    """
    section = get_section(raw, "io", location)
    return IOConfig(
        open_viewer=read_bool(section, "open_viewer", location),
        viewer_timeout_seconds=read_float(section, "viewer_timeout_seconds", location),
        pdf_read_timeout_seconds=read_float(section, "pdf_read_timeout_seconds", location),
        pdf_write_timeout_seconds=read_float(section, "pdf_write_timeout_seconds", location),
        operation_timeout_seconds=read_float(section, "operation_timeout_seconds", location),
        output_dir_suffix=read_str(section, "output_dir_suffix", location),
        output_collision_policy=_read_output_collision_policy(section, location),
        output_collision_max_suffix=read_int(section, "output_collision_max_suffix", location),
        fsync_writes=read_bool(section, "fsync_writes", location),
        page_offset=read_int(section, "page_offset", location),
        infer_page_offset_from_labels=read_bool(section, "infer_page_offset_from_labels", location),
        infer_page_offset_min_sequential_numeric_labels=read_int(
            section,
            "infer_page_offset_min_sequential_numeric_labels",
            location,
        ),
    )


def _build_retry_config(raw: dict[str, object], location: str) -> RetryConfig:
    """Build RetryConfig from raw section values.

    Summary:
        Convert the [retry] section to a typed RetryConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - RetryConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When retry section keys are missing or invalid.
    """
    section = get_section(raw, "retry", location)
    return RetryConfig(
        max_attempts=read_int(section, "max_attempts", location),
        initial_delay_seconds=read_float(section, "initial_delay_seconds", location),
        max_delay_seconds=read_float(section, "max_delay_seconds", location),
        jitter_ratio=read_float(section, "jitter_ratio", location),
    )


def _build_ui_config(raw: dict[str, object], location: str) -> UIConfig:
    """Build UIConfig from raw section values.

    Summary:
        Convert the [ui] section to a typed UIConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - UIConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When ui section keys are missing or invalid.
    """
    section = get_section(raw, "ui", location)
    return UIConfig(
        window_width=read_int(section, "window_width", location),
        window_height=read_int(section, "window_height", location),
        window_offset_x=read_int(section, "window_offset_x", location),
        window_offset_y=read_int(section, "window_offset_y", location),
        open_pdf_button_label=read_str(section, "open_pdf_button_label", location),
        close_button_label=read_str(section, "close_button_label", location),
        row_limit=read_int(section, "row_limit", location),
        base_height=read_int(section, "base_height", location),
        row_height=read_int(section, "row_height", location),
        height_threshold_rows=read_int(section, "height_threshold_rows", location),
        rows_per_column=read_int(section, "rows_per_column", location),
        column_widths=read_int_list(section, "column_widths", location),
        header_rows=read_int(section, "header_rows", location),
        grid_columns=read_int(section, "grid_columns", location),
        grid_entry_width=read_int(section, "grid_entry_width", location),
        grid_remove_button_width=read_int(section, "grid_remove_button_width", location),
        grid_padding_x=read_int(section, "grid_padding_x", location),
        grid_padding_y=read_int(section, "grid_padding_y", location),
        grid_frame_padding_x=read_int(section, "grid_frame_padding_x", location),
        grid_frame_padding_y=read_int(section, "grid_frame_padding_y", location),
        grid_header_labels=read_str_list(section, "grid_header_labels", location),
        undo_button_label=read_str(section, "undo_button_label", location),
        remove_button_label=read_str(section, "remove_button_label", location),
        add_button_label=read_str(section, "add_button_label", location),
        auto_detect_button_label=read_str(section, "auto_detect_button_label", location),
        export_button_label=read_str(section, "export_button_label", location),
        chapter_title_prefix=read_str(section, "chapter_title_prefix", location),
        no_chapters_title=read_str(section, "no_chapters_title", location),
        no_chapters_message=read_str(section, "no_chapters_message", location),
        error_dialog_title=read_str(section, "error_dialog_title", location),
        success_dialog_title=read_str(section, "success_dialog_title", location),
        success_dialog_message_template=read_str(
            section, "success_dialog_message_template", location
        ),
        auto_open_viewer=read_bool(section, "auto_open_viewer", location),
        action_rate_limit_seconds=read_float(section, "action_rate_limit_seconds", location),
        chapter_window_title=read_str(section, "chapter_window_title", location),
        file_dialog_title=read_str(section, "file_dialog_title", location),
        button_row_padding=read_int(section, "button_row_padding", location),
        button_gap_padding=read_int(section, "button_gap_padding", location),
        export_button_padding=read_int(section, "export_button_padding", location),
        confirm_auto_detect_overwrite=read_bool(section, "confirm_auto_detect_overwrite", location),
        confirm_auto_detect_overwrite_title=read_str(
            section, "confirm_auto_detect_overwrite_title", location
        ),
        confirm_auto_detect_overwrite_message=read_str(
            section, "confirm_auto_detect_overwrite_message", location
        ),
        prompt_open_output_dir_after_export=read_bool(
            section, "prompt_open_output_dir_after_export", location
        ),
        open_output_dir_prompt_title=read_str(section, "open_output_dir_prompt_title", location),
        open_output_dir_prompt_message_template=read_str(
            section, "open_output_dir_prompt_message_template", location
        ),
        enable_keyboard_shortcuts=read_bool(section, "enable_keyboard_shortcuts", location),
        show_status_bar=read_bool(section, "show_status_bar", location),
        status_hint=read_str(section, "status_hint", location),
        color_mode=_read_ui_color_mode(section, location),
        enable_pdf_preview=read_bool(section, "enable_pdf_preview", location),
        pdf_preview_zoom=read_float(section, "pdf_preview_zoom", location),
        pdf_preview_fit_mode=_read_pdf_preview_fit_mode(section, location),
        pdf_preview_fit_padding_px=read_int(section, "pdf_preview_fit_padding_px", location),
        pdf_preview_continuous_scroll=read_bool(section, "pdf_preview_continuous_scroll", location),
        pdf_preview_supersample=read_int(section, "pdf_preview_supersample", location),
        pdf_preview_min_zoom=read_float(section, "pdf_preview_min_zoom", location),
        pdf_preview_max_zoom=read_float(section, "pdf_preview_max_zoom", location),
        pdf_preview_zoom_step=read_float(section, "pdf_preview_zoom_step", location),
        pdf_preview_cache_entries=read_int(section, "pdf_preview_cache_entries", location),
        pdf_preview_render_timeout_seconds=read_float(
            section, "pdf_preview_render_timeout_seconds", location
        ),
        chapter_review_thumbnail_width=read_int(
            section, "chapter_review_thumbnail_width", location
        ),
        chapter_review_columns=read_int(section, "chapter_review_columns", location),
        auto_show_review_after_detect=read_bool(section, "auto_show_review_after_detect", location),
        auto_detect_on_open=read_bool(section, "auto_detect_on_open", location),
    )


def _build_validation_config(raw: dict[str, object], location: str) -> ValidationConfig:
    """Build ValidationConfig from raw section values.

    Summary:
        Convert the [validation] section to a typed ValidationConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - ValidationConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When validation section keys are missing or invalid.
    """
    section = get_section(raw, "validation", location)
    return ValidationConfig(
        max_chapters=read_int(section, "max_chapters", location),
        require_unique_titles=read_bool(section, "require_unique_titles", location),
        sort_chapters_by_start_page=read_bool(section, "sort_chapters_by_start_page", location),
        reject_overlapping_ranges=read_bool(section, "reject_overlapping_ranges", location),
    )


def _build_detection_config(raw: dict[str, object], location: str) -> DetectionConfig:
    """Build DetectionConfig from raw section values.

    Summary:
        Convert the [detection] section to a typed DetectionConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - DetectionConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When detection section keys are missing or invalid.
    """
    section = get_section(raw, "detection", location)
    return DetectionConfig(
        enable_toc_fallback=read_bool(section, "enable_toc_fallback", location),
        toc_auto_scan_max_start_page=read_int(section, "toc_auto_scan_max_start_page", location),
        toc_scan_max_pages=read_int(section, "toc_scan_max_pages", location),
        toc_entry_regexes=read_str_list(section, "toc_entry_regexes", location),
        toc_ignore_title_regexes=read_str_list(section, "toc_ignore_title_regexes", location),
        toc_min_entries=read_int(section, "toc_min_entries", location),
        toc_max_entries=read_int(section, "toc_max_entries", location),
        outline_ignore_title_regexes=read_str_list(
            section, "outline_ignore_title_regexes", location
        ),
        outline_min_depth=read_int(section, "outline_min_depth", location),
        outline_merge_tiny_max_pages=read_int(section, "outline_merge_tiny_max_pages", location),
        outline_merge_tiny_title_joiner=read_str(
            section, "outline_merge_tiny_title_joiner", location
        ),
    )


def _build_performance_config(raw: dict[str, object], location: str) -> PerformanceConfig:
    """Build PerformanceConfig from raw section values.

    Summary:
        Convert the [performance] section to a typed PerformanceConfig.
    Ties to other methods:
        Used by build_settings.
    Inputs:
        - raw: Top-level config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - PerformanceConfig instance.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When performance section keys are missing or invalid.
    """
    section = get_section(raw, "performance", location)
    return PerformanceConfig(
        benchmark_iterations=read_int(section, "benchmark_iterations", location),
        benchmark_budget_seconds=read_float(section, "benchmark_budget_seconds", location),
    )


def _read_output_collision_policy(
    section: dict[str, object],
    location: str,
) -> OutputCollisionPolicy:
    """Read and validate io.output_collision_policy.

    Summary:
        Keep literal-typed policy parsing centralized for clearer error messages.
    Ties to other methods:
        Used by _build_io_config.
    Inputs:
        - section: [io] section mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - OutputCollisionPolicy literal value.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When the value is not one of the supported policies.
    """
    error_location = f"{__name__}._read_output_collision_policy"
    context = f" Context: {location}." if location else ""
    value = read_str(section, "output_collision_policy", location)
    if value not in ("error", "overwrite", "suffix"):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"io.output_collision_policy must be one of: error, overwrite, suffix.{context}",
            )
        )
    return cast(OutputCollisionPolicy, value)


def _read_pdf_preview_fit_mode(
    section: dict[str, object],
    location: str,
) -> PdfPreviewFitMode:
    """Read and validate ui.pdf_preview_fit_mode.

    Summary:
        Keep literal-typed fit-mode parsing centralized for clearer error messages.
    Ties to other methods:
        Used by _build_ui_config.
    Inputs:
        - section: [ui] section mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - PdfPreviewFitMode literal value.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When the value is not one of the supported fit modes.
    """
    error_location = f"{__name__}._read_pdf_preview_fit_mode"
    context = f" Context: {location}." if location else ""
    value = read_str(section, "pdf_preview_fit_mode", location)
    if value not in ("page", "width", "none"):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"ui.pdf_preview_fit_mode must be one of: page, width, none.{context}",
            )
        )
    return cast(PdfPreviewFitMode, value)


def _read_ui_color_mode(
    section: dict[str, object],
    location: str,
) -> UIColorMode:
    """Read and validate ui.color_mode.

    Summary:
        Keep literal-typed color-mode parsing centralized for clearer error messages.
    Ties to other methods:
        Used by _build_ui_config.
    Inputs:
        - section: [ui] section mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - UIColorMode literal value.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When the value is not one of the supported color modes.
    """
    error_location = f"{__name__}._read_ui_color_mode"
    context = f" Context: {location}." if location else ""
    value = read_str(section, "color_mode", location)
    if value not in ("light", "dark", "auto"):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"ui.color_mode must be one of: light, dark, auto.{context}",
            )
        )
    return cast(UIColorMode, value)
