"""Tests for the optional desktop application boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chapter_splitter import app
from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import CancellationToken, ConfigurationError, UiError


def test_load_gui_workflow_maps_missing_qt_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLI-only install should receive an actionable optional-dependency error."""

    def _missing_qt(_name: str) -> object:
        raise ModuleNotFoundError("No module named 'PySide6'", name="PySide6")

    monkeypatch.setattr(app, "import_module", _missing_qt)

    with pytest.raises(UiError, match=r"pip install -e '\.\[desktop\]'"):
        app._load_gui_workflow()


def test_load_gui_workflow_does_not_mask_unrelated_missing_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected import defects must remain visible to the internal-error contract."""

    def _missing_other(_name: str) -> object:
        raise ModuleNotFoundError("No module named 'other'", name="other")

    monkeypatch.setattr(app, "import_module", _missing_other)

    with pytest.raises(ModuleNotFoundError, match="other"):
        app._load_gui_workflow()


def test_app_main_maps_configuration_failure_before_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Early configuration failures should return a stable exit code, not a traceback."""

    def _invalid_config(*_args: object, **_kwargs: object) -> object:
        raise ConfigurationError("invalid configuration")

    monkeypatch.setattr(app, "load_settings", _invalid_config)

    assert app.main() == 1


def test_app_main_runs_injected_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app boundary should load and invoke the desktop workflow exactly once."""
    settings = load_settings(None, "tests.unit.test_app")
    settings.logging.console_enabled = False
    settings.logging.file_enabled = False
    calls: list[tuple[object, object]] = []

    def _workflow(resolved_settings: object, token: object) -> None:
        calls.append((resolved_settings, token))

    monkeypatch.setattr(app, "_load_gui_workflow", lambda: _workflow)
    monkeypatch.setattr(app, "register_signal_handlers", lambda *_args, **_kwargs: None)

    assert app.main(settings=settings) == 0
    assert len(calls) == 1
    assert calls[0][0] is settings
    assert isinstance(calls[0][1], CancellationToken)


def test_load_gui_workflow_returns_typed_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lazy loader should return the workflow exported by the Qt module."""

    def _workflow(_settings: object, _token: object) -> None:
        return None

    monkeypatch.setattr(app, "import_module", lambda _name: SimpleNamespace(workflow=_workflow))

    assert app._load_gui_workflow() is _workflow
