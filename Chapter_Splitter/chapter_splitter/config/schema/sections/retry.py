"""Retry policy configuration schema."""

from __future__ import annotations

from math import isfinite

from ....core.errors import ConfigurationError, format_error_message


class RetryConfig:
    """Retry policy configuration."""

    def __init__(
        self,
        max_attempts: int,
        initial_delay_seconds: float,
        max_delay_seconds: float,
        jitter_ratio: float,
    ) -> None:
        """Initialize retry configuration."""
        self.max_attempts = max_attempts
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter_ratio = jitter_ratio

    def validate(self, location: str) -> None:
        """Validate retry configuration."""
        error_location = f"{__name__}.RetryConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.max_attempts < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"retry.max_attempts must be at least 1.{context}"
                )
            )
        if not isfinite(self.initial_delay_seconds) or self.initial_delay_seconds < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"retry.initial_delay_seconds must be finite and non negative.{context}",
                )
            )
        if not isfinite(self.max_delay_seconds):
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"retry.max_delay_seconds must be finite.{context}",
                )
            )
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"retry.max_delay_seconds must be >= initial delay.{context}",
                )
            )
        if not isfinite(self.jitter_ratio) or not 0 <= self.jitter_ratio <= 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"retry.jitter_ratio must be finite and between 0 and 1.{context}",
                )
            )
