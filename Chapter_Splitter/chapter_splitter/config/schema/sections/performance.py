"""Performance measurement configuration schema."""

from __future__ import annotations

from math import isfinite

from ....core.errors import ConfigurationError, format_error_message


class PerformanceConfig:
    """Performance measurement settings."""

    def __init__(self, benchmark_iterations: int, benchmark_budget_seconds: float) -> None:
        """Initialize performance configuration."""
        self.benchmark_iterations = benchmark_iterations
        self.benchmark_budget_seconds = benchmark_budget_seconds

    def validate(self, location: str) -> None:
        """Validate performance configuration."""
        error_location = f"{__name__}.PerformanceConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.benchmark_iterations < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"performance.benchmark_iterations must be at least 1.{context}",
                )
            )
        if not isfinite(self.benchmark_budget_seconds) or self.benchmark_budget_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"performance.benchmark_budget_seconds must be finite and positive.{context}",
                )
            )
