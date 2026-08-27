"""Unit tests for configuration loader components."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from chapter_splitter.config.loader.build import settings as settings_builder
from chapter_splitter.config.loader.build.readers import (
    get_section,
    read_bool,
    read_float,
    read_int,
    read_int_list,
    read_str,
    read_str_list,
)
from chapter_splitter.config.loader.merge.deep_merge import coerce_dict
from chapter_splitter.config.loader.sources import read_default_settings, resolve_env_path
from chapter_splitter.config.loader.toml.reader import config_read_deadline, read_toml_file
from chapter_splitter.core import ConfigurationError


def test_coerce_dict_rejects_non_dict() -> None:
    """Verify deep-merge rejects non-dictionary nodes."""
    with pytest.raises(ConfigurationError):
        coerce_dict(["not-a-dict"], "tests.unit.test_config_loader_components")


def test_resolve_env_path_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override is optional."""
    monkeypatch.delenv("CHAPTER_SPLITTER_CONFIG", raising=False)
    assert resolve_env_path("tests.unit.test_config_loader_components") is None


def test_resolve_env_path_rejects_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment override fails fast when the file does not exist."""
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG", "/does/not/exist.toml")
    with pytest.raises(ConfigurationError):
        resolve_env_path("tests.unit.test_config_loader_components")


def test_resolve_env_path_rejects_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify environment override rejects directory paths."""
    config_dir = tmp_path / "config-dir.toml"
    config_dir.mkdir()
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG", str(config_dir))

    with pytest.raises(ConfigurationError, match="Config override path is not a file"):
        resolve_env_path("tests.unit.test_config_loader_components")


def test_read_default_settings_handles_missing_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing packaged defaults produce a configuration error."""
    import importlib.resources as importlib_resources

    def _raise(*_args: object, **_kwargs: object) -> Any:
        raise ModuleNotFoundError("boom")

    monkeypatch.setattr(importlib_resources, "files", _raise)
    with pytest.raises(ConfigurationError):
        read_default_settings("tests.unit.test_config_loader_components")


def test_read_default_settings_rejects_directory_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify packaged defaults reject non-file resources."""
    import importlib.resources as importlib_resources

    (tmp_path / "settings.toml").mkdir()

    def _return_tmp_path(*_args: object, **_kwargs: object) -> Path:
        return tmp_path

    monkeypatch.setattr(importlib_resources, "files", _return_tmp_path)

    with pytest.raises(ConfigurationError, match="Default settings path is not a file"):
        read_default_settings("tests.unit.test_config_loader_components")


def test_config_read_deadline_rejects_invalid_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config read deadline validates environment overrides."""
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "not-a-float")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_config_read_deadline_rejects_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify config read deadline rejects non-positive values."""
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "-1")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_invalid_toml(tmp_path: Path) -> None:
    """Verify invalid TOML returns a configuration error."""
    path = tmp_path / "bad.toml"
    path.write_text("[invalid", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_read_toml_file_rejects_non_utf8_bytes(tmp_path: Path) -> None:
    """Verify non-UTF8 config files fail with a configuration error."""
    path = tmp_path / "bytes.toml"
    path.write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(ConfigurationError):
        read_toml_file(path, "tests.unit.test_config_loader_components")


def test_build_readers_validate_types() -> None:
    """Verify typed readers reject unexpected values."""
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
    """Verify typed readers reject missing, blank, and malformed values."""
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
    """Verify settings builder enforces root type and literal enums."""
    location = "tests.unit.test_config_loader_components"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(cast(dict[str, object], []), location)

    defaults = read_default_settings(location)

    invalid_collision = deepcopy(defaults)
    io_section = cast(dict[str, object], invalid_collision["io"])
    io_section["output_collision_policy"] = "invalid"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(invalid_collision, location)

    invalid_color_mode = deepcopy(defaults)
    ui_section = cast(dict[str, object], invalid_color_mode["ui"])
    ui_section["color_mode"] = "invalid"
    with pytest.raises(ConfigurationError):
        settings_builder.build_settings(invalid_color_mode, location)


def test_build_settings_rejects_unknown_top_level_sections() -> None:
    """Verify settings builder rejects unknown top-level sections."""
    location = "tests.unit.test_config_loader_components"
    defaults = read_default_settings(location)
    invalid = deepcopy(defaults)
    invalid["typo_section"] = {"enabled": True}

    with pytest.raises(ConfigurationError, match="Unknown top-level config section"):
        settings_builder.build_settings(invalid, location)


def test_build_settings_rejects_unknown_section_keys() -> None:
    """Verify settings builder rejects unknown keys inside known sections."""
    location = "tests.unit.test_config_loader_components"
    defaults = read_default_settings(location)
    invalid = deepcopy(defaults)
    io_section = cast(dict[str, object], invalid["io"])
    io_section["pdf_read_timeout_secondz"] = 1.0

    with pytest.raises(ConfigurationError, match=r"Unknown config key\(s\) in \[io\]"):
        settings_builder.build_settings(invalid, location)


def test_config_read_deadline_integration_raises_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cancellation error paths are surfaced as configuration errors."""
    monkeypatch.setenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "0")
    with pytest.raises(ConfigurationError):
        config_read_deadline("tests.unit.test_config_loader_components")
