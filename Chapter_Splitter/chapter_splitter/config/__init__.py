"""Public configuration access for the application."""

from __future__ import annotations

from pathlib import Path

from .loader import load_settings as _load_settings
from .registry import ConfigRegistry
from .schema import Settings

__all__ = ["ConfigRegistry", "Settings", "load_config"]


def load_config(config_path: Path | None, location: str) -> Settings:
    """Load settings using the explicit loader.

    Summary:
        Provide a compatibility wrapper while keeping configuration loading stateless.
    Ties to other methods:
        Used by app and CLI main functions.
    Inputs:
        - config_path: Optional path to a user config file.
        - location: Fully qualified module and method name.
    Outputs:
        - Settings object.
    Side effects:
        Reads default and override configuration from disk.
    Error handling:
        - ConfigurationError: When settings fail to load.
    """
    return _load_settings(config_path, location)
