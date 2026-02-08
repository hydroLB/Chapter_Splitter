"""Unit tests for the CLI entrypoint and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from chapter_splitter.cli import (
    _optional_int,
    _optional_path,
    _optional_str,
    _require_str,
    _run_detect,
    _run_split,
    main,
)
from chapter_splitter.config.schema import (
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
from chapter_splitter.core.errors import CancellationError, ChapterSplitterError
from chapter_splitter.core.models import ChapterDefinition
from chapter_splitter.core.runtime import CancellationToken


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app=AppConfig(title="t", environment="test", correlation_id_prefix="cid"),
        logging=LoggingConfig(
            level="INFO",
            formatter="json",
            console_enabled=False,
            file_enabled=False,
            file_path=tmp_path / "app.log",
            redact_keys=(),
            redact_values=(),
        ),
        io=IOConfig(
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
        ),
        retry=RetryConfig(
            max_attempts=1,
            initial_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter_ratio=0.0,
        ),
        ui=UIConfig(
            window_width=1,
            window_height=1,
            window_offset_x=0,
            window_offset_y=0,
            open_pdf_button_label="Open",
            close_button_label="Close",
            row_limit=1,
            base_height=1,
            row_height=1,
            height_threshold_rows=0,
            rows_per_column=1,
            column_widths=(1,),
            header_rows=0,
            grid_columns=4,
            grid_entry_width=1,
            grid_remove_button_width=1,
            grid_padding_x=0,
            grid_padding_y=0,
            grid_frame_padding_x=0,
            grid_frame_padding_y=0,
            grid_header_labels=("a", "b", "c", "d"),
            undo_button_label="u",
            remove_button_label="r",
            add_button_label="a",
            auto_detect_button_label="d",
            export_button_label="e",
            chapter_title_prefix="c",
            no_chapters_title="n",
            no_chapters_message="n",
            error_dialog_title="e",
            success_dialog_title="s",
            success_dialog_message_template="{count}",
            auto_open_viewer=False,
            action_rate_limit_seconds=0.0,
            chapter_window_title="w",
            file_dialog_title="f",
            button_row_padding=0,
            button_gap_padding=0,
            export_button_padding=0,
            confirm_auto_detect_overwrite=False,
            confirm_auto_detect_overwrite_title="t",
            confirm_auto_detect_overwrite_message="m",
            prompt_open_output_dir_after_export=False,
            open_output_dir_prompt_title="t",
            open_output_dir_prompt_message_template="m {count} {output_dir}",
            enable_keyboard_shortcuts=False,
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
            pdf_preview_cache_entries=0,
            pdf_preview_render_timeout_seconds=1.0,
            chapter_review_thumbnail_width=120,
            chapter_review_columns=1,
            auto_show_review_after_detect=False,
            auto_detect_on_open=False,
        ),
        validation=ValidationConfig(
            max_chapters=10,
            require_unique_titles=True,
            sort_chapters_by_start_page=False,
            reject_overlapping_ranges=False,
        ),
        detection=DetectionConfig(
            enable_toc_fallback=False,
            toc_auto_scan_max_start_page=1,
            toc_scan_max_pages=1,
            toc_entry_regexes=(r"^(?P<title>.+?)\s+\.\.{2,}\s*(?P<page>\d+)\s*$",),
            toc_ignore_title_regexes=(),
            toc_min_entries=1,
            toc_max_entries=10,
            outline_ignore_title_regexes=(),
            outline_min_depth=0,
            outline_merge_tiny_max_pages=0,
            outline_merge_tiny_title_joiner=" + ",
        ),
        performance=PerformanceConfig(benchmark_iterations=1, benchmark_budget_seconds=0.1),
    )


def test_require_str_rejects_invalid_values() -> None:
    """Verify required string parsing rejects empty or non-string values.

    Purpose:
        Keep CLI argument validation strict and deterministic.
    Ties To:
        Covers chapter_splitter.cli._require_str.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ChapterSplitterError):
        _require_str(None, "name", "tests.unit.test_cli")
    with pytest.raises(ChapterSplitterError):
        _require_str("", "name", "tests.unit.test_cli")


def test_optional_path_normalizes_values(tmp_path: Path) -> None:
    """Verify optional path parsing supports None, Path, and string inputs.

    Purpose:
        Keep parsing predictable for tests and entry points.
    Ties To:
        Covers chapter_splitter.cli._optional_path.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert _optional_path(None, "p", "tests.unit.test_cli") is None
    assert _optional_path(tmp_path, "p", "tests.unit.test_cli") == tmp_path
    assert _optional_path("x.toml", "p", "tests.unit.test_cli") == Path("x.toml")
    with pytest.raises(ChapterSplitterError):
        _optional_path(123, "p", "tests.unit.test_cli")


def test_optional_str_normalizes_values() -> None:
    """Verify optional string parsing supports None and strings.

    Purpose:
        Keep typed CLI parsing strict without leaking Any.
    Ties To:
        Covers chapter_splitter.cli._optional_str.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert _optional_str(None, "s", "tests.unit.test_cli") is None
    assert _optional_str("x", "s", "tests.unit.test_cli") == "x"
    with pytest.raises(ChapterSplitterError):
        _optional_str(123, "s", "tests.unit.test_cli")


def test_optional_int_normalizes_values() -> None:
    """Verify optional integer parsing supports None and integers.

    Purpose:
        Keep typed CLI parsing strict without leaking Any.
    Ties To:
        Covers chapter_splitter.cli._optional_int.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    assert _optional_int(None, "i", "tests.unit.test_cli") is None
    assert _optional_int(5, "i", "tests.unit.test_cli") == 5
    with pytest.raises(ChapterSplitterError):
        _optional_int("5", "i", "tests.unit.test_cli")


def test_run_split_fails_fast_when_cancelled(tmp_path: Path) -> None:
    """Verify split fails fast when cancellation is already requested.

    Purpose:
        Avoid doing IO when a shutdown is in progress.
    Ties To:
        Covers chapter_splitter.cli._run_split cancellation guard.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Cancels a token.
    Raises:
        - None.
    """
    token = CancellationToken()
    token.cancel("stop", "tests.unit.test_cli")
    with pytest.raises(CancellationError):
        _run_split(
            pdf_path=tmp_path / "a.pdf",
            chapters_path=tmp_path / "chapters.toml",
            output_dir=None,
            collision_policy=None,
            page_offset=None,
            settings=_settings(tmp_path),
            token=token,
            location="tests.unit.test_cli",
        )


def test_run_split_applies_cli_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify split CLI flags override common IO settings without a config file.

    Purpose:
        Keep one-off CLI runs ergonomic while preserving config defaults.
    Ties To:
        Covers chapter_splitter.cli._run_split override wiring.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    settings = _settings(tmp_path)
    token = CancellationToken()
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        "chapter_splitter.cli.load_chapter_file",
        lambda *_args, **_kwargs: [ChapterDefinition(title="One", start_page=1, end_page=1)],
    )

    def _split_stub(*_args: object, **kwargs: object) -> list[object]:
        assert kwargs["page_offset"] == 2
        io_config = kwargs["io_config"]
        assert isinstance(io_config, IOConfig)
        assert io_config.output_collision_policy == "overwrite"
        assert kwargs["output_dir"] == out_dir
        return []

    monkeypatch.setattr("chapter_splitter.cli.split_pdf_into_chapters", _split_stub)
    monkeypatch.setattr("chapter_splitter.cli.log_event", lambda *_args, **_kwargs: None)

    assert (
        _run_split(
            pdf_path=tmp_path / "a.pdf",
            chapters_path=tmp_path / "chapters.toml",
            output_dir=out_dir,
            collision_policy="overwrite",
            page_offset=2,
            settings=settings,
            token=token,
            location="tests.unit.test_cli",
        )
        == 0
    )


def test_main_gui_path_returns_gui_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify GUI subcommand delegates to the GUI entrypoint.

    Purpose:
        Keep CLI behavior predictable while allowing a separate GUI workflow.
    Ties To:
        Covers chapter_splitter.cli.main gui path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Patches the GUI entrypoint.
    Raises:
        - None.
    """
    monkeypatch.setattr(
        "chapter_splitter.cli.load_config", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("chapter_splitter.cli.gui_main", lambda *_args, **_kwargs: 42)
    assert (
        main(
            ["gui"],
        )
        == 42
    )


def test_main_split_path_returns_split_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify split subcommand delegates to the split workflow.

    Purpose:
        Ensure the entrypoint wiring stays stable.
    Ties To:
        Covers chapter_splitter.cli.main split path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Patches config loading, signal registration, and split execution.
    Raises:
        - None.
    """
    monkeypatch.setattr(
        "chapter_splitter.cli.load_config", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("chapter_splitter.cli._run_split", lambda *_args, **_kwargs: 0)
    assert main(["split", "--pdf", "a.pdf", "--chapters", "c.toml"]) == 0


def test_main_detect_path_returns_detect_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify detect subcommand delegates to the detect workflow.

    Purpose:
        Ensure the entrypoint wiring stays stable for chapter detection output.
    Ties To:
        Covers chapter_splitter.cli.main detect path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Patches config loading, signal registration, and detect execution.
    Raises:
        - None.
    """
    monkeypatch.setattr(
        "chapter_splitter.cli.load_config", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("chapter_splitter.cli._run_detect", lambda *_args, **_kwargs: 0)
    assert main(["detect", "--pdf", "a.pdf"]) == 0


def test_run_detect_requires_toc_hint_for_toc_strategy(tmp_path: Path) -> None:
    """Verify toc strategy requires a TOC hint page.

    Purpose:
        Keep the toc-only strategy deterministic and avoid surprising scans.
    Ties To:
        Covers chapter_splitter.cli._run_detect toc argument validation.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    token = CancellationToken()
    with pytest.raises(ChapterSplitterError):
        _run_detect(
            pdf_path=tmp_path / "a.pdf",
            out_path=tmp_path / "chapters.toml",
            strategy="toc",
            toc_hint_page=None,
            overwrite=False,
            settings=_settings(tmp_path),
            token=token,
            location="tests.unit.test_cli",
        )


def test_main_split_path_maps_cancellation_to_130(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify cancellation maps to exit code 130.

    Purpose:
        Use a standard exit code for SIGINT-like cancellation.
    Ties To:
        Covers CancellationError handling in chapter_splitter.cli.main.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Patches split execution to raise CancellationError.
    Raises:
        - None.
    """
    monkeypatch.setattr(
        "chapter_splitter.cli.load_config", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )

    def raise_cancel(*_args: object, **_kwargs: object) -> int:
        raise CancellationError("cancelled")

    monkeypatch.setattr("chapter_splitter.cli._run_split", raise_cancel)
    assert main(["split", "--pdf", "a.pdf", "--chapters", "c.toml"]) == 130


def test_main_split_path_maps_domain_error_to_1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify domain errors map to exit code 1.

    Purpose:
        Ensure predictable error signaling for scripts and CI.
    Ties To:
        Covers ChapterSplitterError handling in chapter_splitter.cli.main.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Patches split execution to raise ChapterSplitterError.
    Raises:
        - None.
    """
    monkeypatch.setattr(
        "chapter_splitter.cli.load_config", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )

    def raise_error(*_args: object, **_kwargs: object) -> int:
        raise ChapterSplitterError("boom")

    monkeypatch.setattr("chapter_splitter.cli._run_split", raise_error)
    assert main(["split", "--pdf", "a.pdf", "--chapters", "c.toml"]) == 1
