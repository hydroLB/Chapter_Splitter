"""Structured logging configuration schema."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ....core.errors import ConfigurationError, format_error_message


class LoggingConfig:
    """Structured logging configuration.

    Purpose:
        Control log levels, outputs, and redaction behavior.
    Ties To:
        Consumed by observability logging setup.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(
        self,
        level: str,
        formatter: str,
        console_enabled: bool,
        file_enabled: bool,
        file_path: Path,
        redact_keys: Sequence[str],
        redact_values: Sequence[str],
    ) -> None:
        """Initialize logging configuration.

        Purpose:
            Define structured logging output and redaction behavior.
        Ties To:
            Used by observability logging setup.
        Inputs:
            - level: Logging level name.
            - formatter: Output format name.
            - console_enabled: Enable console logging.
            - file_enabled: Enable file logging.
            - file_path: Path to the log file.
            - redact_keys: Field names to redact from structured logs.
            - redact_values: Substrings to redact from log messages.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.level = level
        self.formatter = formatter
        self.console_enabled = console_enabled
        self.file_enabled = file_enabled
        self.file_path = file_path
        self.redact_keys = tuple(redact_keys)
        self.redact_values = tuple(redact_values)

    def validate(self, location: str) -> None:
        """Validate logging configuration.

        Purpose:
            Ensure logging settings are coherent and safe.
        Ties To:
            Called by Settings.validate prior to logging setup.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - ConfigurationError: When logging settings are invalid.
        """
        error_location = f"{__name__}.LoggingConfig.validate"
        context = f" Context: {location}." if location else ""
        if not self.level.strip():
            raise ConfigurationError(
                format_error_message(error_location, f"logging.level must be non empty.{context}")
            )
        if not self.formatter.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location, f"logging.formatter must be non empty.{context}"
                )
            )
        if self.file_enabled and not str(self.file_path).strip():
            raise ConfigurationError(
                format_error_message(error_location, f"logging.file_path must be set.{context}")
            )
