"""Application metadata configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class AppConfig:
    """Application metadata configuration.

    Summary:
        Define application identity, environment, and correlation settings.
    Ties to other methods:
        Used by logging, UI titles, and CLI output.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self, title: str, environment: str, correlation_id_prefix: str) -> None:
        """Initialize application configuration.

        Summary:
            Store application level metadata and identity settings.
        Ties to other methods:
            Consumed by logging, UI titles, and CLI output.
        Inputs:
            - title: Human readable application title.
            - environment: Environment label used in logs.
            - correlation_id_prefix: Prefix for correlation IDs.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.title = title
        self.environment = environment
        self.correlation_id_prefix = correlation_id_prefix

    def validate(self, location: str) -> None:
        """Validate application configuration.

        Summary:
            Ensure required metadata is present and well formed.
        Ties to other methods:
            Called by Settings.validate before runtime configuration is accepted.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ConfigurationError: When values are empty or invalid.
        """
        error_location = f"{__name__}.AppConfig.validate"
        context = f" Context: {location}." if location else ""
        if not self.title.strip():
            raise ConfigurationError(
                format_error_message(error_location, f"app.title must be non empty.{context}")
            )
        if not self.environment.strip():
            raise ConfigurationError(
                format_error_message(error_location, f"app.environment must be non empty.{context}")
            )
        if not self.correlation_id_prefix.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"app.correlation_id_prefix must be non empty.{context}",
                )
            )
