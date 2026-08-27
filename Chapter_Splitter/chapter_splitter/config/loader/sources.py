"""Configuration source discovery and default retrieval."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

from ...core.errors import ConfigurationError, format_error_message
from .toml.reader import read_toml_file


def _require_file_path(
    path: Path,
    *,
    error_location: str,
    missing_detail: str,
    not_file_detail: str,
    location: str,
) -> Path:
    """Validate that a configuration path exists and points to a file."""
    context = f" Context: {location}." if location else ""
    if not path.exists():
        raise ConfigurationError(
            format_error_message(error_location, f"{missing_detail}: {path}.{context}")
        )
    if not path.is_file():
        raise ConfigurationError(
            format_error_message(error_location, f"{not_file_detail}: {path}.{context}")
        )
    return path


def read_default_settings(location: str) -> dict[str, object]:
    """Read the packaged default settings.toml file."""
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
    resolved_path = _require_file_path(
        Path(str(config_path)),
        error_location=error_location,
        missing_detail="Default settings file not found",
        not_file_detail="Default settings path is not a file",
        location=location,
    )
    return read_toml_file(resolved_path, location)


def resolve_env_path(location: str) -> Path | None:
    """Resolve a user config path from the environment."""
    error_location = f"{__name__}.resolve_env_path"
    raw = os.getenv("CHAPTER_SPLITTER_CONFIG")
    if raw is None or not raw.strip():
        return None
    return _require_file_path(
        Path(raw).expanduser(),
        error_location=error_location,
        missing_detail="Config override path does not exist",
        not_file_detail="Config override path is not a file",
        location=location,
    )
