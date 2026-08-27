"""Application metadata configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class AppConfig:
    """Application metadata configuration."""

    def __init__(self, title: str, environment: str, correlation_id_prefix: str) -> None:
        """Initialize application configuration."""
        self.title = title
        self.environment = environment
        self.correlation_id_prefix = correlation_id_prefix

    def validate(self, location: str) -> None:
        """Validate application configuration."""
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
