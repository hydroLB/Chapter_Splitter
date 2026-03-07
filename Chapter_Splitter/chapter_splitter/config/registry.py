"""Global settings registry for centralized configuration access."""

from __future__ import annotations

from pathlib import Path

from ..core.errors import ConfigurationError, format_error_message
from .loader import load_settings
from .schema import Settings


class ConfigRegistry:
    """Explicit registry object for application settings.

    Summary:
        Provide caller-owned storage for loaded configuration.
    Ties to other methods:
        Used by tests and explicit wiring where in-memory settings reuse is desired.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self) -> None:
        """Initialize the registry in an unloaded state.

        Summary:
            Provide a central location for configuration retrieval.
        Ties to other methods:
            Used by get_settings and entry points to share configuration.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self._settings: Settings | None = None

    def load(self, config_path: Path | None, location: str) -> Settings:
        """Load settings into the registry.

        Summary:
            Ensure configuration is loaded once and reused consistently.
        Ties to other methods:
            Invoked by entry points before running application workflows.
        Inputs:
            - config_path: Optional path to a user config file.
            - location: Fully qualified module and method name.
        Outputs:
            - Loaded Settings object.
        Side effects:
            Stores settings in the registry.
        Error handling:
            - ConfigurationError: When configuration loading fails.
        """
        self._settings = load_settings(config_path, location)
        return self._settings

    def get(self, location: str) -> Settings:
        """Return settings from the registry.

        Summary:
            Provide access to loaded configuration throughout the app.
        Ties to other methods:
            Used by modules that require configuration values.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - Settings object.
        Side effects:
            None.
        Error handling:
            - ConfigurationError: When settings have not been loaded.
        """
        error_location = f"{__name__}.ConfigRegistry.get"
        context = f" Context: {location}." if location else ""
        if self._settings is None:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"Configuration has not been loaded.{context}",
                )
            )
        return self._settings
