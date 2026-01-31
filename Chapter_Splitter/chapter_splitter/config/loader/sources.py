"""Configuration source discovery and default retrieval."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

from ...core.errors import ConfigurationError, format_error_message
from .toml.reader import read_toml_file


def read_default_settings(location: str) -> dict[str, object]:
    """Read the packaged default settings.toml file.

    Purpose:
        Load baseline configuration shipped with the application.
    Ties To:
        Invoked by load_settings before merging overrides.
    Inputs:
        - location: Fully qualified module and method name.
    Outputs:
        - Mapping of default configuration values.
    Side Effects:
        Reads the packaged settings.toml file from disk.
    Raises:
        - ConfigurationError: When the default config cannot be read or parsed.
    """
    error_location = f"{__name__}.read_default_settings"
    context = f" Context: {location}." if location else ""
    try:
        config_path = resources.files("chapter_splitter.config").joinpath("settings.toml")
    except (ModuleNotFoundError, AttributeError) as exc:
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Default settings file not found: {exc}.{context}",
            )
        ) from exc
    return read_toml_file(Path(str(config_path)), location)


def resolve_env_path(location: str) -> Path | None:
    """Resolve a user config path from the environment.

    Purpose:
        Allow optional overrides via CHAPTER_SPLITTER_CONFIG.
    Ties To:
        Used by load_settings when no explicit path is provided.
    Inputs:
        - location: Fully qualified module and method name.
    Outputs:
        - Path to the override config file or None.
    Side Effects:
        Reads environment variables.
    Raises:
        - ConfigurationError: When the path is invalid.
    """
    error_location = f"{__name__}.resolve_env_path"
    context = f" Context: {location}." if location else ""
    raw = os.getenv("CHAPTER_SPLITTER_CONFIG")
    if raw is None or not raw.strip():
        return None
    path = Path(raw).expanduser()
    if not path.exists():
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Config override path does not exist: {path}.{context}",
            )
        )
    return path
