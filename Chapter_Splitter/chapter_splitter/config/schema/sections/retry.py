"""Retry policy configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class RetryConfig:
    """Retry policy configuration.

    Summary:
        Define retry limits and backoff settings for transient failures.
    Ties to other methods:
        Used by retry utilities and IO workflows.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(
        self,
        max_attempts: int,
        initial_delay_seconds: float,
        max_delay_seconds: float,
        jitter_ratio: float,
    ) -> None:
        """Initialize retry configuration.

        Summary:
            Define exponential backoff behavior for transient IO errors.
        Ties to other methods:
            Used by retry helpers in IO and PDF loading.
        Inputs:
            - max_attempts: Maximum retry attempts.
            - initial_delay_seconds: Initial delay between attempts.
            - max_delay_seconds: Maximum delay between attempts.
            - jitter_ratio: Jitter ratio applied to delays.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.max_attempts = max_attempts
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter_ratio = jitter_ratio

    def validate(self, location: str) -> None:
        """Validate retry configuration.

        Summary:
            Ensure retry settings remain within reasonable bounds.
        Ties to other methods:
            Called by Settings.validate before retry policy is used.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ConfigurationError: When retry settings are invalid.
        """
        error_location = f"{__name__}.RetryConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.max_attempts < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"retry.max_attempts must be at least 1.{context}"
                )
            )
        if self.initial_delay_seconds < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"retry.initial_delay_seconds must be non negative.{context}"
                )
            )
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"retry.max_delay_seconds must be >= initial delay.{context}",
                )
            )
        if not 0 <= self.jitter_ratio <= 1:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"retry.jitter_ratio must be between 0 and 1.{context}"
                )
            )
