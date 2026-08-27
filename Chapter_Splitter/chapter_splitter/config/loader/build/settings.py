"""Build typed settings objects from raw configuration mappings."""

from __future__ import annotations

from inspect import Parameter, signature
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
from ...schema.sections.ui import UIColorMode
from .readers import (
    get_section,
    read_bool,
    read_float,
    read_int,
    read_str,
    read_str_list,
)


def _init_parameter_names(config_type: type[object]) -> frozenset[str]:
    """Return public configuration keys accepted by a schema constructor."""
    allowed_kinds = {
        Parameter.POSITIONAL_ONLY,
        Parameter.POSITIONAL_OR_KEYWORD,
        Parameter.KEYWORD_ONLY,
    }
    return frozenset(
        name
        for name, parameter in signature(config_type.__init__).parameters.items()
        if name != "self" and parameter.kind in allowed_kinds
    )


_ALLOWED_SECTION_KEYS: dict[str, frozenset[str]] = {
    "app": _init_parameter_names(AppConfig),
    "logging": _init_parameter_names(LoggingConfig),
    "io": _init_parameter_names(IOConfig),
    "retry": _init_parameter_names(RetryConfig),
    "ui": _init_parameter_names(UIConfig),
    "validation": _init_parameter_names(ValidationConfig),
    "detection": _init_parameter_names(DetectionConfig),
    "performance": _init_parameter_names(PerformanceConfig),
}


def build_settings(raw: dict[str, object], location: str) -> Settings:
    """Build a fully-typed Settings object from raw config values."""
    error_location = f"{__name__}.build_settings"
    context = f" Context: {location}." if location else ""
    if not isinstance(raw, dict):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Config root must be a table.{context}",
            )
        )
    _validate_known_config_shape(raw, location)

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


def _validate_known_config_shape(raw: dict[str, object], location: str) -> None:
    """Reject unknown config sections and keys before building typed settings."""
    error_location = f"{__name__}._validate_known_config_shape"
    context = f" Context: {location}." if location else ""

    unknown_sections = sorted(set(raw) - set(_ALLOWED_SECTION_KEYS))
    if unknown_sections:
        joined = ", ".join(unknown_sections)
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Unknown top-level config section(s): {joined}.{context}",
            )
        )

    for section_name, allowed_keys in _ALLOWED_SECTION_KEYS.items():
        section = raw.get(section_name)
        if not isinstance(section, dict):
            continue
        unknown_keys = sorted(set(section) - allowed_keys)
        if unknown_keys:
            joined = ", ".join(unknown_keys)
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"Unknown config key(s) in [{section_name}]: {joined}.{context}",
                )
            )


def _build_app_config(raw: dict[str, object], location: str) -> AppConfig:
    """Build AppConfig from raw section values."""
    section = get_section(raw, "app", location)
    return AppConfig(
        title=read_str(section, "title", location),
        environment=read_str(section, "environment", location),
        correlation_id_prefix=read_str(section, "correlation_id_prefix", location),
    )


def _build_logging_config(raw: dict[str, object], location: str) -> LoggingConfig:
    """Build LoggingConfig from raw section values."""
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
    """Build IOConfig from raw section values."""
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
    """Build RetryConfig from raw section values."""
    section = get_section(raw, "retry", location)
    return RetryConfig(
        max_attempts=read_int(section, "max_attempts", location),
        initial_delay_seconds=read_float(section, "initial_delay_seconds", location),
        max_delay_seconds=read_float(section, "max_delay_seconds", location),
        jitter_ratio=read_float(section, "jitter_ratio", location),
    )


def _build_ui_config(raw: dict[str, object], location: str) -> UIConfig:
    """Build UIConfig from raw section values."""
    section = get_section(raw, "ui", location)
    return UIConfig(
        window_width=read_int(section, "window_width", location),
        window_height=read_int(section, "window_height", location),
        close_button_label=read_str(section, "close_button_label", location),
        undo_button_label=read_str(section, "undo_button_label", location),
        add_button_label=read_str(section, "add_button_label", location),
        auto_detect_button_label=read_str(section, "auto_detect_button_label", location),
        export_button_label=read_str(section, "export_button_label", location),
        chapter_title_prefix=read_str(section, "chapter_title_prefix", location),
        no_chapters_title=read_str(section, "no_chapters_title", location),
        error_dialog_title=read_str(section, "error_dialog_title", location),
        success_dialog_title=read_str(section, "success_dialog_title", location),
        success_dialog_message_template=read_str(
            section, "success_dialog_message_template", location
        ),
        action_rate_limit_seconds=read_float(section, "action_rate_limit_seconds", location),
        chapter_window_title=read_str(section, "chapter_window_title", location),
        file_dialog_title=read_str(section, "file_dialog_title", location),
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
        color_mode=_read_ui_color_mode(section, location),
        auto_show_review_after_detect=read_bool(section, "auto_show_review_after_detect", location),
        auto_detect_on_open=read_bool(section, "auto_detect_on_open", location),
    )


def _build_validation_config(raw: dict[str, object], location: str) -> ValidationConfig:
    """Build ValidationConfig from raw section values."""
    section = get_section(raw, "validation", location)
    return ValidationConfig(
        max_chapters=read_int(section, "max_chapters", location),
        require_unique_titles=read_bool(section, "require_unique_titles", location),
        sort_chapters_by_start_page=read_bool(section, "sort_chapters_by_start_page", location),
        reject_overlapping_ranges=read_bool(section, "reject_overlapping_ranges", location),
    )


def _build_detection_config(raw: dict[str, object], location: str) -> DetectionConfig:
    """Build DetectionConfig from raw section values."""
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
    """Build PerformanceConfig from raw section values."""
    section = get_section(raw, "performance", location)
    return PerformanceConfig(
        benchmark_iterations=read_int(section, "benchmark_iterations", location),
        benchmark_budget_seconds=read_float(section, "benchmark_budget_seconds", location),
    )


def _read_output_collision_policy(
    section: dict[str, object],
    location: str,
) -> OutputCollisionPolicy:
    """Read and validate io.output_collision_policy."""
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


def _read_ui_color_mode(
    section: dict[str, object],
    location: str,
) -> UIColorMode:
    """Read and validate ui.color_mode."""
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
