"""Public configuration access for the application."""

from __future__ import annotations

from pathlib import Path

from .registry import get_config as _get_config
from .registry import load_config as _load_config
from .schema import Settings

__all__ = ["Settings", "get_config", "load_config"]


def load_config(config_path: Path | None, location: str) -> Settings:
    """Load settings into the global registry.

    Purpose:
        Provide a clear import path for entry points to load configuration.
    Ties To:
        Used by app and CLI main functions.
    Inputs:
        - config_path: Optional path to a user config file.
        - location: Fully qualified module and method name.
    Outputs:
        - Settings object.
    Side Effects:
        Initializes the global settings registry.
    Raises:
        - ConfigurationError: When settings fail to load.
    """
    return _load_config(config_path, location)


def get_config(location: str) -> Settings:
    """Return settings from the global registry.

    Purpose:
        Provide a stable access point for runtime settings.
    Ties To:
        Used by modules that require configuration values.
    Inputs:
        - location: Fully qualified module and method name.
    Outputs:
        - Settings object.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When settings have not been loaded.
    """
    return _get_config(location)
