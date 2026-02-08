"""Unit tests for configuration schema validation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from chapter_splitter.config.schema import (
    AppConfig,
    DetectionConfig,
    IOConfig,
    LoggingConfig,
    PerformanceConfig,
    RetryConfig,
    UIConfig,
    ValidationConfig,
)
from chapter_splitter.core.errors import ConfigurationError


def _valid_app() -> AppConfig:
    return AppConfig(title="Chapter Splitter", environment="test", correlation_id_prefix="cid")


def _valid_logging(tmp_path: Path) -> LoggingConfig:
    return LoggingConfig(
        level="INFO",
        formatter="json",
        console_enabled=True,
        file_enabled=False,
        file_path=tmp_path / "app.log",
        redact_keys=("password",),
        redact_values=("secret",),
    )


def _valid_io() -> IOConfig:
    return IOConfig(
        open_viewer=False,
        viewer_timeout_seconds=1.0,
        pdf_read_timeout_seconds=1.0,
        pdf_write_timeout_seconds=1.0,
        operation_timeout_seconds=1.0,
        output_dir_suffix="_out",
        output_collision_policy="error",
        output_collision_max_suffix=10,
        fsync_writes=False,
        page_offset=0,
        infer_page_offset_from_labels=False,
        infer_page_offset_min_sequential_numeric_labels=3,
    )


def _valid_retry() -> RetryConfig:
    return RetryConfig(
        max_attempts=3,
        initial_delay_seconds=0.0,
        max_delay_seconds=1.0,
        jitter_ratio=0.0,
    )


def _valid_validation() -> ValidationConfig:
    return ValidationConfig(
        max_chapters=10,
        require_unique_titles=True,
        sort_chapters_by_start_page=True,
        reject_overlapping_ranges=True,
    )


def _valid_performance() -> PerformanceConfig:
    return PerformanceConfig(benchmark_iterations=3, benchmark_budget_seconds=0.5)


def _valid_detection() -> DetectionConfig:
    return DetectionConfig(
        enable_toc_fallback=True,
        toc_auto_scan_max_start_page=5,
        toc_scan_max_pages=3,
        toc_entry_regexes=(
            r"^(?P<title>.+?)\s+\.\.{2,}\s*(?P<page>\d+)\s*$",
            r"^(?P<title>.+?)\s+(?P<page>\d+)\s*$",
        ),
        toc_ignore_title_regexes=(r"(?i)^(table of contents|contents)$",),
        toc_min_entries=2,
        toc_max_entries=100,
        outline_ignore_title_regexes=(),
        outline_min_depth=0,
        outline_merge_tiny_max_pages=0,
        outline_merge_tiny_title_joiner=" + ",
    )


def _valid_ui() -> UIConfig:
    return UIConfig(
        window_width=800,
        window_height=600,
        window_offset_x=10,
        window_offset_y=10,
        open_pdf_button_label="Open PDF",
        close_button_label="Close",
        row_limit=10,
        base_height=100,
        row_height=10,
        height_threshold_rows=0,
        rows_per_column=10,
        column_widths=(800,),
        header_rows=1,
        grid_columns=4,
        grid_entry_width=10,
        grid_remove_button_width=4,
        grid_padding_x=0,
        grid_padding_y=0,
        grid_frame_padding_x=0,
        grid_frame_padding_y=0,
        grid_header_labels=("Title", "Start", "End", ""),
        undo_button_label="Undo",
        remove_button_label="Remove",
        add_button_label="Add",
        auto_detect_button_label="Auto",
        export_button_label="Export",
        chapter_title_prefix="Chapter",
        no_chapters_title="No chapters",
        no_chapters_message="No outlines found.",
        error_dialog_title="Error",
        success_dialog_title="Success",
        success_dialog_message_template="{count}",
        auto_open_viewer=False,
        action_rate_limit_seconds=0.0,
        chapter_window_title="Chapters",
        file_dialog_title="Select PDF",
        button_row_padding=0,
        button_gap_padding=0,
        export_button_padding=0,
        confirm_auto_detect_overwrite=True,
        confirm_auto_detect_overwrite_title="Replace?",
        confirm_auto_detect_overwrite_message="Replace.",
        prompt_open_output_dir_after_export=True,
        open_output_dir_prompt_title="Done",
        open_output_dir_prompt_message_template="{count} {output_dir}",
        enable_keyboard_shortcuts=True,
        show_status_bar=True,
        status_hint="hint",
        enable_pdf_preview=False,
        pdf_preview_zoom=1.0,
        pdf_preview_fit_mode="none",
        pdf_preview_fit_padding_px=0,
        pdf_preview_continuous_scroll=True,
        pdf_preview_supersample=1,
        pdf_preview_min_zoom=0.25,
        pdf_preview_max_zoom=4.0,
        pdf_preview_zoom_step=0.1,
        pdf_preview_cache_entries=4,
        pdf_preview_render_timeout_seconds=1.0,
        chapter_review_thumbnail_width=120,
        chapter_review_columns=1,
        auto_show_review_after_detect=False,
        auto_detect_on_open=False,
    )


def test_schema_validates_happy_path(tmp_path: Path) -> None:
    """Verify config sections accept valid settings.

    Purpose:
        Ensure baseline configs pass validation as a sanity check.
    Ties To:
        Covers *.validate methods in chapter_splitter.config.schema sections.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    _valid_app().validate("tests.unit.test_config_schema_validation")
    _valid_logging(tmp_path).validate("tests.unit.test_config_schema_validation")
    _valid_io().validate("tests.unit.test_config_schema_validation")
    _valid_retry().validate("tests.unit.test_config_schema_validation")
    _valid_validation().validate("tests.unit.test_config_schema_validation")
    _valid_performance().validate("tests.unit.test_config_schema_validation")
    _valid_ui().validate("tests.unit.test_config_schema_validation")
    _valid_detection().validate("tests.unit.test_config_schema_validation")


def test_ui_config_validation_catches_all_key_invariants() -> None:
    """Verify UIConfig emits actionable errors for invalid parameters.

    Purpose:
        Ensure each invariant check stays covered and debuggable.
    Ties To:
        Covers chapter_splitter.config.schema.sections.ui.UIConfig.validate.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def assert_invalid(mutator: Callable[[UIConfig], None]) -> None:
        cfg = _valid_ui()
        mutator(cfg)
        with pytest.raises(ConfigurationError):
            cfg.validate("tests.unit.test_config_schema_validation")

    assert_invalid(lambda c: setattr(c, "window_width", 0))
    assert_invalid(lambda c: setattr(c, "row_limit", 0))
    assert_invalid(lambda c: setattr(c, "base_height", 0))
    assert_invalid(lambda c: setattr(c, "height_threshold_rows", -1))
    assert_invalid(lambda c: setattr(c, "action_rate_limit_seconds", -1))
    assert_invalid(lambda c: setattr(c, "chapter_window_title", ""))
    assert_invalid(lambda c: setattr(c, "rows_per_column", 0))
    assert_invalid(lambda c: setattr(c, "header_rows", -1))
    assert_invalid(lambda c: setattr(c, "column_widths", ()))
    assert_invalid(lambda c: setattr(c, "file_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "grid_columns", 3))
    assert_invalid(lambda c: setattr(c, "grid_entry_width", 0))
    assert_invalid(lambda c: setattr(c, "grid_padding_x", -1))
    assert_invalid(lambda c: setattr(c, "grid_frame_padding_x", -1))
    assert_invalid(lambda c: setattr(c, "grid_header_labels", ()))
    assert_invalid(lambda c: setattr(c, "undo_button_label", ""))
    assert_invalid(lambda c: setattr(c, "remove_button_label", ""))
    assert_invalid(lambda c: setattr(c, "add_button_label", ""))
    assert_invalid(lambda c: setattr(c, "auto_detect_button_label", ""))
    assert_invalid(lambda c: setattr(c, "export_button_label", ""))
    assert_invalid(lambda c: setattr(c, "chapter_title_prefix", ""))
    assert_invalid(lambda c: setattr(c, "no_chapters_title", ""))
    assert_invalid(lambda c: setattr(c, "no_chapters_message", ""))
    assert_invalid(lambda c: setattr(c, "error_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "success_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "success_dialog_message_template", ""))
    assert_invalid(lambda c: setattr(c, "button_row_padding", -1))
    assert_invalid(lambda c: setattr(c, "export_button_padding", -1))


def test_other_section_validators_fail_fast(tmp_path: Path) -> None:
    """Verify validators reject representative invalid values.

    Purpose:
        Increase coverage for error branches and keep messages actionable.
    Ties To:
        Covers validate methods across non-UI config sections.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ConfigurationError):
        AppConfig(title="", environment="test", correlation_id_prefix="cid").validate(
            "tests.unit.test_config_schema_validation"
        )
    with pytest.raises(ConfigurationError):
        _valid_logging(tmp_path=tmp_path).__class__(
            level="",
            formatter="json",
            console_enabled=True,
            file_enabled=False,
            file_path=tmp_path / "app.log",
            redact_keys=(),
            redact_values=(),
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        IOConfig(
            open_viewer=False,
            viewer_timeout_seconds=0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=1.0,
            output_dir_suffix="_out",
            output_collision_policy="error",
            output_collision_max_suffix=10,
            fsync_writes=False,
            page_offset=0,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        RetryConfig(
            max_attempts=0,
            initial_delay_seconds=0,
            max_delay_seconds=0,
            jitter_ratio=0,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        ValidationConfig(
            max_chapters=0,
            require_unique_titles=True,
            sort_chapters_by_start_page=True,
            reject_overlapping_ranges=True,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        PerformanceConfig(benchmark_iterations=0, benchmark_budget_seconds=1.0).validate(
            "tests.unit.test_config_schema_validation"
        )
