"""Unit tests for configuration loader components."""

from __future__ import annotations

import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from chapter_splitter.config import ConfigRegistry, load_config
from chapter_splitter.config.loader._internal import (
    coerce_dict,
    config_read_deadline,
    get_section,
    read_bool,
    read_default_settings,
    read_float,
    read_int,
    read_int_list,
    read_str,
    read_str_list,
    read_toml_file,
    resolve_env_path,
    settings_builder,
)
from chapter_splitter.core import ConfigurationError


def test_coerce_dict_rejects_non_dict() -> None:
    """Verify deep-merge rejects non-dictionary nodes.

    Summary:
        Ensure type safety for recursive merges.
    Ties to other methods:
        Covers chapter_splitter.config.loader.merge.deep_merge.coerce_dict.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    with pytest.raises(ConfigurationError):
        coerce_dict(["not-a-dict"], "tests.unit.test_config_loader_components")


def test_resolve_env_path_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override is optional.

    Summary:
        Avoid forcing users to set CHAPTER_SPLITTER_CONFIG.
    Ties to other methods:
        Covers chapter_splitter.config.loader.sources.resolve_env_path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Modifies environment variables for the duration of the test.
    Error handling:
        - None.
    """
    monkeypatch.delenv("CHAPTER_SPLITTER_CONFIG", raising=False)
    assert resolve_env_path("tests.unit.test_config_loader_components") is None


def test_resolve_env_path_rejects_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override fails fast when the file does not exist.

    Summary:
        Provide immediate, actionable feedback for misconfiguration.
    Ties to other methods:
        Covers chapter_splitter.config.loader.sources.resolve_env_path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Modifies environment variables for the duration of the test.
    Error handling:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG", "/does/not/exist.toml")
    with pytest.raises(ConfigurationError):
        resolve_env_path("tests.unit.test_config_loader_components")


def test_read_default_settings_handles_missing_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing packaged defaults produce a configuration error.

    Summary:
        Ensure the loader fails with a clear message when package data is missing.
    Ties to other methods:
        Covers chapter_splitter.config.loader.sources.read_default_settings.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Patches importlib.resources lookup.
    Error handling:
        - None.
    """
    import importlib.resources as importlib_resources

    def _raise(*_args: object, **_kwargs: object) -> Any:
        raise ModuleNotFoundError("boom")

    monkeypatch.setattr(importlib_resources, "files", _raise)
    with pytest.raises(ConfigurationError):
        read_default_settings("tests.unit.test_config_loader_components")


def test_config_read_deadline_rejects_invalid_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config read deadline validates environment overrides.

    Summary:
        Prevent invalid timeout values from silently breaking IO bounds.
    Ties to other methods:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Modifies environment variables for the duration of the test.
    Error handling:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "not-a-float")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_config_read_deadline_rejects_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config read deadline rejects non-positive values.

    Summary:
        Avoid timeouts that would immediately cancel all config IO.
    Ties to other methods:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Modifies environment variables for the duration of the test.
    Error handling:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "-1")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_invalid_toml(tmp_path: Path) -> None:
    """Verify invalid TOML returns a configuration error.

    Summary:
        Ensure errors are consistently surfaced at the loader boundary.
    Ties to other methods:
        Covers chapter_splitter.config.loader.toml.reader.read_toml_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        Writes a temporary file.
    Error handling:
        - None.
    """
    path = tmp_path / "bad.toml"
    path.write_text("[invalid", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_non_utf8_bytes(tmp_path: Path) -> None:
    """Verify non-UTF8 config files fail with a configuration error.

    Summary:
        Avoid undefined behavior when config files contain invalid encoding.
    Ties to other methods:
        Covers chapter_splitter.config.loader.toml.reader.read_toml_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        Writes a temporary file with invalid bytes.
    Error handling:
        - None.
    """
    path = tmp_path / "bytes.toml"
    path.write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_build_readers_validate_types() -> None:
    """Verify typed readers reject unexpected values.

    Summary:
        Ensure raw config parsing stays strict under mypy and at runtime.
    Ties to other methods:
        Covers chapter_splitter.config.loader.build.readers.*.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    raw: dict[str, object] = {"section": {"name": "ok", "flag": True, "count": 3, "ratio": 0.25}}
    section = get_section(raw, "section", "tests.unit.test_config_loader_components")
    assert read_str(section, "name", "tests.unit.test_config_loader_components") == "ok"
    assert read_bool(section, "flag", "tests.unit.test_config_loader_components") is True
    assert read_int(section, "count", "tests.unit.test_config_loader_components") == 3
    assert read_float(
        section,
        "ratio",
        "tests.unit.test_config_loader_components",
    ) == pytest.approx(0.25)

    with pytest.raises(ConfigurationError):
        read_int(section, "name", "tests.unit.test_config_loader_components")


def test_build_readers_cover_error_branches() -> None:
    """Verify typed readers reject missing, blank, and malformed values.

    Summary:
        Cover branch-level error handling in reader helpers and keep loader diagnostics stable.
    Ties to other methods:
        Covers chapter_splitter.config.loader.build.readers.get_section and read_* helpers.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    location = "tests.unit.test_config_loader_components"
    raw: dict[str, object] = {
        "section": {
            "name": "ok",
            "flag": True,
            "count": 3,
            "ratio": 0.25,
            "names": ["a", "b"],
            "numbers": [1, 2, 3],
        }
    }
    section = get_section(raw, "section", location)

    with pytest.raises(ConfigurationError):
        get_section(raw, "", location)
    with pytest.raises(ConfigurationError):
        get_section(raw, "missing", location)
    with pytest.raises(ConfigurationError):
        get_section({"section": 1}, "section", location)

    with pytest.raises(ConfigurationError):
        read_str(section, "flag", location)
    with pytest.raises(ConfigurationError):
        read_bool(section, "name", location)
    with pytest.raises(ConfigurationError):
        read_int({"count": True}, "count", location)
    with pytest.raises(ConfigurationError):
        read_float({"ratio": True}, "ratio", location)
    with pytest.raises(ConfigurationError):
        read_str(section, "", location)
    with pytest.raises(ConfigurationError):
        read_str(section, "missing", location)

    assert read_str_list(section, "names", location) == ["a", "b"]
    assert read_int_list(section, "numbers", location) == [1, 2, 3]
    with pytest.raises(ConfigurationError):
        read_str_list(section, "name", location)
    with pytest.raises(ConfigurationError):
        read_str_list({"names": [1]}, "names", location)
    with pytest.raises(ConfigurationError):
        read_int_list(section, "name", location)
    with pytest.raises(ConfigurationError):
        read_int_list({"numbers": [1, True]}, "numbers", location)


def test_build_settings_rejects_invalid_root_and_literal_values() -> None:
    """Verify settings builder enforces root type and literal enums.

    Summary:
        Keep config builder failure paths deterministic and actionable.
    Ties to other methods:
        Covers chapter_splitter.config.loader.build.settings.build_settings and helper readers.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Loads packaged default settings and mutates copied dictionaries.
    Error handling:
        - None.
    """
    location = "tests.unit.test_config_loader_components"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(cast(dict[str, object], []), location)

    defaults = read_default_settings(location)

    invalid_collision = deepcopy(defaults)
    io_section = cast(dict[str, object], invalid_collision["io"])
    io_section["output_collision_policy"] = "invalid"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(invalid_collision, location)

    invalid_fit_mode = deepcopy(defaults)
    ui_section = cast(dict[str, object], invalid_fit_mode["ui"])
    ui_section["pdf_preview_fit_mode"] = "invalid"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(invalid_fit_mode, location)

    invalid_color_mode = deepcopy(defaults)
    ui_section = cast(dict[str, object], invalid_color_mode["ui"])
    ui_section["color_mode"] = "invalid"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(invalid_color_mode, location)


def test_config_registry_get_requires_load() -> None:
    """Verify registry enforces load-before-get usage.

    Summary:
        Prevent accidental use of configuration before initialization.
    Ties to other methods:
        Covers chapter_splitter.config.registry.ConfigRegistry.get.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    registry = ConfigRegistry()
    with pytest.raises(ConfigurationError):
        registry.get("tests.unit.test_config_loader_components")


def test_config_registry_load_and_get_round_trip() -> None:
    """Verify registry returns the same settings instance after load.

    Summary:
        Ensure configuration is a single source of truth after loading.
    Ties to other methods:
        Covers chapter_splitter.config.registry.ConfigRegistry.load and .get.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Loads default settings from packaged data.
    Error handling:
        - None.
    """
    registry = ConfigRegistry()
    settings = registry.load(None, "tests.unit.test_config_loader_components")
    assert registry.get("tests.unit.test_config_loader_components") is settings


def test_config_read_deadline_integration_raises_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cancellation error paths are surfaced as configuration errors.

    Summary:
        Ensure internal cancellation maps to a stable config-loader boundary error.
    Ties to other methods:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Modifies environment variables for the duration of the test.
    Error handling:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "0")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_load_config_is_stateless_and_delegates_to_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify module-level load_config no longer depends on global mutable state.

    Summary:
        Lock in explicit loader delegation so configuration state stays boundary-local.
    Ties to other methods:
        Covers chapter_splitter.config.load_config.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side effects:
        Monkeypatches the config loader wrapper.
    Error handling:
        - None.
    """
    calls: list[tuple[Path | None, str]] = []
    sentinel_one = object()
    sentinel_two = object()
    responses = [sentinel_one, sentinel_two]

    def _fake_loader(config_path: Path | None, location: str) -> object:
        calls.append((config_path, location))
        return responses.pop(0)

    monkeypatch.setattr("chapter_splitter.config._load_settings", _fake_loader)

    first = load_config(None, "tests.unit.test_config_loader_components.first")
    second = load_config(None, "tests.unit.test_config_loader_components.second")

    assert first is sentinel_one
    assert second is sentinel_two
    assert calls == [
        (None, "tests.unit.test_config_loader_components.first"),
        (None, "tests.unit.test_config_loader_components.second"),
    ]


def test_registry_module_has_no_global_singleton_state() -> None:
    """Verify the registry module does not expose hidden global mutable singleton state.

    Summary:
        Prevent regressions that reintroduce process-global config state.
    Ties to other methods:
        Covers chapter_splitter.config.registry module contract.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    config_registry_module = importlib.import_module("chapter_splitter.config.registry")
    assert not hasattr(config_registry_module, "_REGISTRY")
