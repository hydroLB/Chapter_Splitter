"""Read and parse TOML configuration files with time bounds."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from ....core.errors import CancellationError, ConfigurationError, format_error_message
from ....utils.timing import Deadline


def read_toml_file(path: Path, location: str) -> dict[str, object]:
    """Read and parse a TOML file into a dictionary.

    Purpose:
        Centralize TOML parsing with consistent error handling.
    Ties To:
        Used for default settings and user overrides.
    Inputs:
        - path: TOML file path.
        - location: Fully qualified module and method name.
    Outputs:
        - Parsed TOML content as a dictionary.
    Side Effects:
        Reads the file from disk.
    Raises:
        - ConfigurationError: When the file cannot be read or parsed.
    """
    error_location = f"{__name__}.read_toml_file"
    context = f" Context: {location}." if location else ""
    deadline = config_read_deadline(location)
    deadline.check(location)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ConfigurationError(
            format_error_message(error_location, f"Unable to read config file: {path}.{context}")
        ) from exc
    deadline.check(location)
    try:
        parsed = tomllib.loads(raw_bytes.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigurationError(
            format_error_message(error_location, f"Unable to parse TOML from: {path}.{context}")
        ) from exc
    if not isinstance(parsed, dict):
        raise ConfigurationError(
            format_error_message(
                error_location, f"Config content must be a table in: {path}.{context}"
            )
        )
    return parsed


def config_read_deadline(location: str) -> Deadline:
    """Return a deadline for config file reads.

    Purpose:
        Provide a tunable timeout for configuration file IO.
    Ties To:
        Used by read_toml_file when reading settings files.
    Inputs:
        - location: Fully qualified module and method name.
    Outputs:
        - Deadline instance for config reads.
    Side Effects:
        Reads environment variables for overrides.
    Raises:
        - ConfigurationError: When the timeout value is invalid.
    """
    error_location = f"{__name__}.config_read_deadline"
    context = f" Context: {location}." if location else ""
    raw_value = os.getenv("CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS", "5.0")
    try:
        timeout_seconds = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Invalid config timeout value: {raw_value}.{context}",
            )
        ) from exc
    try:
        return Deadline(timeout_seconds)
    except CancellationError as exc:
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Config timeout must be positive.{context}",
            )
        ) from exc
