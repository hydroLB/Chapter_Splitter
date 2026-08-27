"""Unit tests for the CLI entrypoint and helpers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from chapter_splitter.cli import (
    _run_detect,
    _run_split,
    gui_main,
    main,
)
from chapter_splitter.cli_commands import optional_int, optional_path, optional_str, require_str
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
from chapter_splitter.core import (
    CancellationError,
    CancellationToken,
    ChapterDefinition,
    ChapterSplitterError,
    ConfigurationError,
)


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
            close_button_label="Close",
            undo_button_label="u",
            add_button_label="a",
            auto_detect_button_label="d",
            export_button_label="e",
            chapter_title_prefix="c",
            no_chapters_title="n",
            error_dialog_title="e",
            success_dialog_title="s",
            success_dialog_message_template="{count}",
            action_rate_limit_seconds=0.0,
            chapter_window_title="w",
            file_dialog_title="f",
            confirm_auto_detect_overwrite=False,
            confirm_auto_detect_overwrite_title="t",
            confirm_auto_detect_overwrite_message="m",
            prompt_open_output_dir_after_export=False,
            open_output_dir_prompt_title="t",
            open_output_dir_prompt_message_template="m {count} {output_dir}",
            enable_keyboard_shortcuts=False,
            color_mode="auto",
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


def test_cli_reports_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Expose a release-verifiable CLI version."""
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])
    assert capsys.readouterr().out == "chapter-splitter 0.1.0\n"


def test_require_str_rejects_invalid_values() -> None:
    """Verify required string parsing rejects empty or non-string values."""
    with pytest.raises(ChapterSplitterError):
        require_str(None, "name", "tests.unit.test_cli")
    with pytest.raises(ChapterSplitterError):
        require_str("", "name", "tests.unit.test_cli")


def test_optional_path_normalizes_values(tmp_path: Path) -> None:
    """Verify optional path parsing supports None, Path, and string inputs."""
    assert optional_path(None, "p", "tests.unit.test_cli") is None
    assert optional_path(tmp_path, "p", "tests.unit.test_cli") == tmp_path
    assert optional_path("x.toml", "p", "tests.unit.test_cli") == Path("x.toml")
    with pytest.raises(ChapterSplitterError):
        optional_path(123, "p", "tests.unit.test_cli")


def test_optional_str_normalizes_values() -> None:
    """Verify optional string parsing supports None and strings."""
    assert optional_str(None, "s", "tests.unit.test_cli") is None
    assert optional_str("x", "s", "tests.unit.test_cli") == "x"
    with pytest.raises(ChapterSplitterError):
        optional_str(123, "s", "tests.unit.test_cli")


def test_optional_int_normalizes_values() -> None:
    """Verify optional integer parsing supports None and integers."""
    assert optional_int(None, "i", "tests.unit.test_cli") is None
    assert optional_int(5, "i", "tests.unit.test_cli") == 5
    with pytest.raises(ChapterSplitterError):
        optional_int("5", "i", "tests.unit.test_cli")


def test_run_split_fails_fast_when_cancelled(tmp_path: Path) -> None:
    """Verify split fails fast when cancellation is already requested."""
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
    """Verify split CLI flags override common IO settings without a config file."""
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
    """Verify GUI subcommand delegates to the GUI entrypoint."""
    expected_settings = _settings(tmp_path)
    monkeypatch.setattr(
        "chapter_splitter.cli.load_settings", lambda *_args, **_kwargs: expected_settings
    )
    captured: dict[str, object] = {}

    def _gui_main(*_args: object, **kwargs: object) -> int:
        captured.update(kwargs)
        return 42

    monkeypatch.setattr("chapter_splitter.cli.gui_main", _gui_main)
    assert (
        main(
            ["gui"],
        )
        == 42
    )
    assert captured["settings"] is expected_settings


def test_gui_main_passes_injected_settings_to_app_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify gui_main forwards injected settings to the GUI app boundary."""
    expected_settings = _settings(tmp_path)
    captured: dict[str, object] = {}

    fake_module = types.ModuleType("chapter_splitter.app")

    def _app_main(
        *,
        config_path: Path | None = None,
        settings: Settings | None = None,
        metrics: object | None = None,
    ) -> int:
        captured["config_path"] = config_path
        captured["settings"] = settings
        captured["metrics"] = metrics
        return 7

    fake_module.main = _app_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "chapter_splitter.app", fake_module)

    config_path = tmp_path / "settings.toml"
    assert gui_main(config_path=config_path, settings=expected_settings) == 7
    assert captured["config_path"] == config_path
    assert captured["settings"] is expected_settings
    assert captured["metrics"] is None


def test_main_split_path_returns_split_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify split subcommand delegates to the split workflow."""
    monkeypatch.setattr(
        "chapter_splitter.cli.load_settings", lambda *_args, **_kwargs: _settings(tmp_path)
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
    """Verify detect subcommand delegates to the detect workflow."""
    monkeypatch.setattr(
        "chapter_splitter.cli.load_settings", lambda *_args, **_kwargs: _settings(tmp_path)
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
    """Verify toc strategy requires a TOC hint page."""
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


def test_run_detect_rejects_non_positive_toc_hint_for_toc_strategy(tmp_path: Path) -> None:
    """Verify toc strategy rejects non-positive TOC hint pages."""
    token = CancellationToken()
    with pytest.raises(ChapterSplitterError, match="must be at least 1"):
        _run_detect(
            pdf_path=tmp_path / "a.pdf",
            out_path=tmp_path / "chapters.toml",
            strategy="toc",
            toc_hint_page=0,
            overwrite=False,
            settings=_settings(tmp_path),
            token=token,
            location="tests.unit.test_cli",
        )


def test_run_detect_forced_toc_fails_when_no_chapters_are_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify forced TOC mode fails closed when no chapters are detected."""

    class _EmptyReport:
        strategy = "toc"
        confidence = 0.0
        chapters: list[ChapterDefinition] = []
        warnings = ["hint page contained no TOC entries"]

    token = CancellationToken()

    monkeypatch.setattr("chapter_splitter.cli.detect_chapters", lambda **_kwargs: _EmptyReport())

    with pytest.raises(ChapterSplitterError, match="Forced TOC detection found no chapters"):
        _run_detect(
            pdf_path=tmp_path / "a.pdf",
            out_path=tmp_path / "chapters.toml",
            strategy="toc",
            toc_hint_page=2,
            overwrite=False,
            settings=_settings(tmp_path),
            token=token,
            location="tests.unit.test_cli",
        )


@pytest.mark.parametrize(
    ("strategy", "toc_hint_page", "message"),
    [
        ("auto", None, "Automatic detection found no chapters"),
        ("outlines", None, "Forced outline detection found no chapters"),
        ("toc", 2, "Forced TOC detection found no chapters"),
    ],
)
def test_run_detect_empty_result_never_writes_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    strategy: str,
    toc_hint_page: int | None,
    message: str,
) -> None:
    """Every detection strategy fails before writing an empty chapter map."""

    class _EmptyReport:
        confidence = 0.0
        chapters: list[ChapterDefinition] = []
        warnings = ["no candidates"]

        def __init__(self, report_strategy: str) -> None:
            self.strategy = report_strategy

    write_called = False

    def _write_stub(*_args: object, **_kwargs: object) -> None:
        nonlocal write_called
        write_called = True

    monkeypatch.setattr(
        "chapter_splitter.cli.detect_chapters",
        lambda **_kwargs: _EmptyReport(strategy if strategy != "auto" else "none"),
    )
    monkeypatch.setattr("chapter_splitter.cli.write_chapter_file", _write_stub)

    with pytest.raises(ChapterSplitterError, match=message):
        _run_detect(
            pdf_path=tmp_path / "a.pdf",
            out_path=tmp_path / "chapters.toml",
            strategy=strategy,
            toc_hint_page=toc_hint_page,
            overwrite=False,
            settings=_settings(tmp_path),
            token=CancellationToken(),
            location="tests.unit.test_cli",
        )

    assert write_called is False
    assert not (tmp_path / "chapters.toml").exists()


def test_main_startup_configuration_errors_use_structured_exit_handling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify startup failures still map through the CLI error contract."""
    captured: dict[str, object] = {}

    def _raise_config(*_args: object, **_kwargs: object) -> Settings:
        raise ConfigurationError("bad config")

    def _log_event_stub(*args: object, **_kwargs: object) -> None:
        if len(args) >= 5:
            captured["fields"] = args[4]

    monkeypatch.setattr("chapter_splitter.cli.load_settings", _raise_config)
    monkeypatch.setattr("chapter_splitter.cli.log_event", _log_event_stub)

    assert main(["split", "--pdf", "a.pdf", "--chapters", "c.toml"]) == 1
    fields = captured["fields"]
    assert isinstance(fields, dict)
    assert fields["error_code"] == "CHAPTER_SPLITTER_CONFIGURATION"
    assert fields["exit_code"] == 1


def test_main_split_path_maps_cancellation_to_130(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify cancellation maps to exit code 130."""
    monkeypatch.setattr(
        "chapter_splitter.cli.load_settings", lambda *_args, **_kwargs: _settings(tmp_path)
    )
    monkeypatch.setattr("chapter_splitter.cli.configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.new_correlation_id", lambda *_args, **_kwargs: "cid-1"
    )
    monkeypatch.setattr("chapter_splitter.cli.set_correlation_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "chapter_splitter.cli.register_signal_handlers", lambda *_args, **_kwargs: None
    )
    captured: dict[str, object] = {}

    def _log_event_stub(*args: object, **_kwargs: object) -> None:
        if len(args) >= 5:
            captured["fields"] = args[4]

    monkeypatch.setattr("chapter_splitter.cli.log_event", _log_event_stub)

    def raise_cancel(*_args: object, **_kwargs: object) -> int:
        raise CancellationError("cancelled")

    monkeypatch.setattr("chapter_splitter.cli._run_split", raise_cancel)
    assert main(["split", "--pdf", "a.pdf", "--chapters", "c.toml"]) == 130
    fields = captured["fields"]
    assert isinstance(fields, dict)
    assert fields["error_code"] == "CHAPTER_SPLITTER_CANCELLATION"
    assert fields["exit_code"] == 130


def test_main_split_path_maps_domain_error_to_1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify domain errors map to exit code 1."""
    monkeypatch.setattr(
        "chapter_splitter.cli.load_settings", lambda *_args, **_kwargs: _settings(tmp_path)
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
