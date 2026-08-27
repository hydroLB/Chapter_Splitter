"""Public API for loading settings from configuration sources."""

from __future__ import annotations

from pathlib import Path

from ..schema import Settings
from .build.settings import build_settings
from .merge.deep_merge import merge_configs
from .sources import read_default_settings, resolve_env_path
from .toml.reader import read_toml_file


def load_settings(config_path: Path | None, location: str) -> Settings:
    """Load settings from the packaged defaults and an optional override file."""
    default_data = read_default_settings(location)
    override_path = config_path or resolve_env_path(location)
    if override_path is not None:
        override_data = read_toml_file(override_path, location)
        merged = merge_configs(default_data, override_data, location)
    else:
        merged = default_data
    settings = build_settings(merged, location)
    settings.validate(location)
    return settings
