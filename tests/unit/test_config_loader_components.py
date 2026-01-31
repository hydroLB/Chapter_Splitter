"""Unit tests for configuration loader components."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chapter_splitter.config.loader.build.readers import (
    get_section,
    read_bool,
    read_float,
    read_int,
    read_str,
)
from chapter_splitter.config.loader.merge.deep_merge import coerce_dict
from chapter_splitter.config.loader.sources import read_default_settings, resolve_env_path
from chapter_splitter.config.loader.toml.reader import config_read_deadline, read_toml_file
from chapter_splitter.config.registry import ConfigRegistry
from chapter_splitter.core.errors import ConfigurationError


def test_coerce_dict_rejects_non_dict() -> None:
    """Verify deep-merge rejects non-dictionary nodes.

    Purpose:
        Ensure type safety for recursive merges.
    Ties To:
        Covers chapter_splitter.config.loader.merge.deep_merge.coerce_dict.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ConfigurationError):
        coerce_dict(["not-a-dict"], "tests.unit.test_config_loader_components")


def test_resolve_env_path_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override is optional.

    Purpose:
        Avoid forcing users to set CHAPTER_SPLITTER_CONFIG.
    Ties To:
        Covers chapter_splitter.config.loader.sources.resolve_env_path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Modifies environment variables for the duration of the test.
    Raises:
        - None.
    """
    monkeypatch.delenv("CHAPTER_SPLITTER_CONFIG", raising=False)
    assert resolve_env_path("tests.unit.test_config_loader_components") is None


def test_resolve_env_path_rejects_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override fails fast when the file does not exist.

    Purpose:
        Provide immediate, actionable feedback for misconfiguration.
    Ties To:
        Covers chapter_splitter.config.loader.sources.resolve_env_path.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Modifies environment variables for the duration of the test.
    Raises:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG", "/does/not/exist.toml")
    with pytest.raises(ConfigurationError):
        resolve_env_path("tests.unit.test_config_loader_components")


def test_read_default_settings_handles_missing_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing packaged defaults produce a configuration error.

    Purpose:
        Ensure the loader fails with a clear message when package data is missing.
    Ties To:
        Covers chapter_splitter.config.loader.sources.read_default_settings.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches importlib.resources lookup.
    Raises:
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

    Purpose:
        Prevent invalid timeout values from silently breaking IO bounds.
    Ties To:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Modifies environment variables for the duration of the test.
    Raises:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "not-a-float")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_config_read_deadline_rejects_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config read deadline rejects non-positive values.

    Purpose:
        Avoid timeouts that would immediately cancel all config IO.
    Ties To:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Modifies environment variables for the duration of the test.
    Raises:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "-1")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_invalid_toml(tmp_path: Path) -> None:
    """Verify invalid TOML returns a configuration error.

    Purpose:
        Ensure errors are consistently surfaced at the loader boundary.
    Ties To:
        Covers chapter_splitter.config.loader.toml.reader.read_toml_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a temporary file.
    Raises:
        - None.
    """
    path = tmp_path / "bad.toml"
    path.write_text("[invalid", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_non_utf8_bytes(tmp_path: Path) -> None:
    """Verify non-UTF8 config files fail with a configuration error.

    Purpose:
        Avoid undefined behavior when config files contain invalid encoding.
    Ties To:
        Covers chapter_splitter.config.loader.toml.reader.read_toml_file.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Writes a temporary file with invalid bytes.
    Raises:
        - None.
    """
    path = tmp_path / "bytes.toml"
    path.write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_build_readers_validate_types() -> None:
    """Verify typed readers reject unexpected values.

    Purpose:
        Ensure raw config parsing stays strict under mypy and at runtime.
    Ties To:
        Covers chapter_splitter.config.loader.build.readers.*.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
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


def test_config_registry_get_requires_load() -> None:
    """Verify registry enforces load-before-get usage.

    Purpose:
        Prevent accidental use of configuration before initialization.
    Ties To:
        Covers chapter_splitter.config.registry.ConfigRegistry.get.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    registry = ConfigRegistry()
    with pytest.raises(ConfigurationError):
        registry.get("tests.unit.test_config_loader_components")


def test_config_registry_load_and_get_round_trip() -> None:
    """Verify registry returns the same settings instance after load.

    Purpose:
        Ensure configuration is a single source of truth after loading.
    Ties To:
        Covers chapter_splitter.config.registry.ConfigRegistry.load and .get.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Loads default settings from packaged data.
    Raises:
        - None.
    """
    registry = ConfigRegistry()
    settings = registry.load(None, "tests.unit.test_config_loader_components")
    assert registry.get("tests.unit.test_config_loader_components") is settings


def test_config_read_deadline_integration_raises_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cancellation error paths are surfaced as configuration errors.

    Purpose:
        Ensure internal cancellation maps to a stable config-loader boundary error.
    Ties To:
        Covers chapter_splitter.config.loader.toml.reader.config_read_deadline.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Modifies environment variables for the duration of the test.
    Raises:
        - None.
    """
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "0")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")
