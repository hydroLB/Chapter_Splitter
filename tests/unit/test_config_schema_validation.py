"""Unit tests for configuration schema validation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from chapter_splitter.config.schema import (
    AppConfig,
    DetectionConfig,
    IOConfig,
    LoggingConfig,
    OutputCollisionPolicy,
    PerformanceConfig,
    RetryConfig,
    UIConfig,
    ValidationConfig,
)
from chapter_splitter.core import ConfigurationError


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
        close_button_label="Close",
        undo_button_label="Undo",
        add_button_label="Add",
        auto_detect_button_label="Auto",
        export_button_label="Export",
        chapter_title_prefix="Chapter",
        no_chapters_title="No chapters",
        error_dialog_title="Error",
        success_dialog_title="Success",
        success_dialog_message_template="{count}",
        action_rate_limit_seconds=0.0,
        chapter_window_title="Chapters",
        file_dialog_title="Select PDF",
        confirm_auto_detect_overwrite=True,
        confirm_auto_detect_overwrite_title="Replace?",
        confirm_auto_detect_overwrite_message="Replace.",
        prompt_open_output_dir_after_export=True,
        open_output_dir_prompt_title="Done",
        open_output_dir_prompt_message_template="{count} {output_dir}",
        enable_keyboard_shortcuts=True,
        color_mode="auto",
        auto_show_review_after_detect=False,
        auto_detect_on_open=False,
    )


def test_schema_validates_happy_path(tmp_path: Path) -> None:
    """Verify config sections accept valid settings."""
    _valid_app().validate("tests.unit.test_config_schema_validation")
    _valid_logging(tmp_path).validate("tests.unit.test_config_schema_validation")
    _valid_io().validate("tests.unit.test_config_schema_validation")
    _valid_retry().validate("tests.unit.test_config_schema_validation")
    _valid_validation().validate("tests.unit.test_config_schema_validation")
    _valid_performance().validate("tests.unit.test_config_schema_validation")
    _valid_ui().validate("tests.unit.test_config_schema_validation")
    _valid_detection().validate("tests.unit.test_config_schema_validation")


ConfigFactory = Callable[[], IOConfig | RetryConfig | PerformanceConfig]


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    ("config_factory", "field_name"),
    [
        (_valid_io, "viewer_timeout_seconds"),
        (_valid_io, "pdf_read_timeout_seconds"),
        (_valid_io, "pdf_write_timeout_seconds"),
        (_valid_io, "operation_timeout_seconds"),
        (_valid_retry, "initial_delay_seconds"),
        (_valid_retry, "max_delay_seconds"),
        (_valid_retry, "jitter_ratio"),
        (_valid_performance, "benchmark_budget_seconds"),
    ],
)
def test_float_config_fields_reject_non_finite_values(
    config_factory: ConfigFactory,
    field_name: str,
    invalid_value: float,
) -> None:
    """Verify every floating-point field rejects NaN and infinities."""
    config = config_factory()
    setattr(config, field_name, invalid_value)

    with pytest.raises(ConfigurationError, match=field_name):
        config.validate("tests.unit.test_config_schema_validation")


def test_ui_config_validation_catches_all_key_invariants() -> None:
    """Verify UIConfig emits actionable errors for invalid parameters."""

    def assert_invalid(mutator: Callable[[UIConfig], None]) -> None:
        cfg = _valid_ui()
        mutator(cfg)
        with pytest.raises(ConfigurationError):
            cfg.validate("tests.unit.test_config_schema_validation")

    assert_invalid(lambda c: setattr(c, "window_width", 0))
    assert_invalid(lambda c: setattr(c, "action_rate_limit_seconds", -1))
    assert_invalid(lambda c: setattr(c, "chapter_window_title", ""))
    assert_invalid(lambda c: setattr(c, "file_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "undo_button_label", ""))
    assert_invalid(lambda c: setattr(c, "add_button_label", ""))
    assert_invalid(lambda c: setattr(c, "auto_detect_button_label", ""))
    assert_invalid(lambda c: setattr(c, "export_button_label", ""))
    assert_invalid(lambda c: setattr(c, "chapter_title_prefix", ""))
    assert_invalid(lambda c: setattr(c, "no_chapters_title", ""))
    assert_invalid(lambda c: setattr(c, "error_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "success_dialog_title", ""))
    assert_invalid(lambda c: setattr(c, "success_dialog_message_template", ""))


def test_other_section_validators_fail_fast(tmp_path: Path) -> None:
    """Verify validators reject representative invalid values."""
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


def test_ui_config_validation_catches_prompt_and_theme_invariants() -> None:
    """Verify UIConfig validates conditional prompts and color mode."""

    def assert_invalid(mutator: Callable[[UIConfig], None]) -> None:
        cfg = _valid_ui()
        mutator(cfg)
        with pytest.raises(ConfigurationError):
            cfg.validate("tests.unit.test_config_schema_validation")

    assert_invalid(lambda c: setattr(c, "close_button_label", ""))
    assert_invalid(lambda c: setattr(c, "confirm_auto_detect_overwrite_title", ""))
    assert_invalid(lambda c: setattr(c, "confirm_auto_detect_overwrite_message", ""))
    assert_invalid(lambda c: setattr(c, "open_output_dir_prompt_title", ""))
    assert_invalid(lambda c: setattr(c, "open_output_dir_prompt_message_template", ""))
    assert_invalid(lambda c: setattr(c, "color_mode", "bad"))


def test_ui_config_allows_optional_prompt_fields_when_flags_are_disabled() -> None:
    """Verify optional prompt fields can be empty when their feature flags are disabled."""
    cfg = _valid_ui()
    cfg.confirm_auto_detect_overwrite = False
    cfg.confirm_auto_detect_overwrite_title = ""
    cfg.confirm_auto_detect_overwrite_message = ""
    cfg.prompt_open_output_dir_after_export = False
    cfg.open_output_dir_prompt_title = ""
    cfg.open_output_dir_prompt_message_template = ""
    cfg.validate("tests.unit.test_config_schema_validation")


def test_detection_config_validation_catches_remaining_error_branches() -> None:
    """Verify DetectionConfig validation rejects malformed detection settings."""

    def assert_invalid(mutator: Callable[[DetectionConfig], None]) -> None:
        cfg = _valid_detection()
        mutator(cfg)
        with pytest.raises(ConfigurationError):
            cfg.validate("tests.unit.test_config_schema_validation")

    assert_invalid(lambda c: setattr(c, "toc_scan_max_pages", 0))
    assert_invalid(lambda c: setattr(c, "toc_entry_regexes", ()))
    assert_invalid(lambda c: setattr(c, "toc_min_entries", 0))
    assert_invalid(lambda c: setattr(c, "toc_max_entries", 1))
    assert_invalid(lambda c: setattr(c, "toc_entry_regexes", ("(",)))
    assert_invalid(lambda c: setattr(c, "toc_entry_regexes", (r"^(?P<title>.+)$",)))
    assert_invalid(lambda c: setattr(c, "toc_ignore_title_regexes", ("(",)))
    assert_invalid(lambda c: setattr(c, "outline_min_depth", -1))
    assert_invalid(lambda c: setattr(c, "outline_merge_tiny_max_pages", -1))
    assert_invalid(lambda c: setattr(c, "outline_merge_tiny_title_joiner", ""))
    assert_invalid(lambda c: setattr(c, "outline_ignore_title_regexes", ("(",)))


def test_other_section_validators_cover_remaining_branches(tmp_path: Path) -> None:
    """Verify section validators reject all remaining invalid parameter branches."""
    with pytest.raises(ConfigurationError):
        AppConfig(title="ok", environment="", correlation_id_prefix="cid").validate(
            "tests.unit.test_config_schema_validation"
        )
    with pytest.raises(ConfigurationError):
        AppConfig(title="ok", environment="test", correlation_id_prefix="").validate(
            "tests.unit.test_config_schema_validation"
        )

    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=0.0,
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
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=0.0,
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
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=0.0,
            output_dir_suffix="_out",
            output_collision_policy="error",
            output_collision_max_suffix=10,
            fsync_writes=False,
            page_offset=0,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=1.0,
            output_dir_suffix="",
            output_collision_policy="error",
            output_collision_max_suffix=10,
            fsync_writes=False,
            page_offset=0,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=1.0,
            output_dir_suffix="_out",
            output_collision_policy=cast(OutputCollisionPolicy, "bad"),
            output_collision_max_suffix=10,
            fsync_writes=False,
            page_offset=0,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=1.0,
            output_dir_suffix="_out",
            output_collision_policy="error",
            output_collision_max_suffix=1,
            fsync_writes=False,
            page_offset=0,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
            open_viewer=False,
            viewer_timeout_seconds=1.0,
            pdf_read_timeout_seconds=1.0,
            pdf_write_timeout_seconds=1.0,
            operation_timeout_seconds=1.0,
            output_dir_suffix="_out",
            output_collision_policy="error",
            output_collision_max_suffix=10,
            fsync_writes=False,
            page_offset=-1,
            infer_page_offset_from_labels=False,
            infer_page_offset_min_sequential_numeric_labels=3,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        _valid_io().__class__(
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
            infer_page_offset_min_sequential_numeric_labels=0,
        ).validate("tests.unit.test_config_schema_validation")

    with pytest.raises(ConfigurationError):
        RetryConfig(
            max_attempts=1,
            initial_delay_seconds=-0.1,
            max_delay_seconds=1.0,
            jitter_ratio=0.0,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        RetryConfig(
            max_attempts=1,
            initial_delay_seconds=1.0,
            max_delay_seconds=0.5,
            jitter_ratio=0.0,
        ).validate("tests.unit.test_config_schema_validation")
    with pytest.raises(ConfigurationError):
        RetryConfig(
            max_attempts=1,
            initial_delay_seconds=0.0,
            max_delay_seconds=1.0,
            jitter_ratio=1.5,
        ).validate("tests.unit.test_config_schema_validation")

    with pytest.raises(ConfigurationError):
        PerformanceConfig(benchmark_iterations=1, benchmark_budget_seconds=0.0).validate(
            "tests.unit.test_config_schema_validation"
        )

    _valid_logging(tmp_path).validate("tests.unit.test_config_schema_validation")
