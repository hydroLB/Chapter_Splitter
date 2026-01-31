"""Performance measurement configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class PerformanceConfig:
    """Performance measurement settings.

    Purpose:
        Control profiling, benchmarks, and performance thresholds.
    Ties To:
        Used by performance scripts and CI checks.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, benchmark_iterations: int, benchmark_budget_seconds: float) -> None:
        """Initialize performance configuration.

        Purpose:
            Control benchmark iteration count and performance budgets.
        Ties To:
            Used by benchmark tests and profiling scripts.
        Inputs:
            - benchmark_iterations: Number of benchmark repetitions.
            - benchmark_budget_seconds: Target budget per benchmark.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.benchmark_iterations = benchmark_iterations
        self.benchmark_budget_seconds = benchmark_budget_seconds

    def validate(self, location: str) -> None:
        """Validate performance configuration.

        Purpose:
            Ensure benchmark limits are usable in CI and local runs.
        Ties To:
            Called by Settings.validate before benchmark checks run.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - ConfigurationError: When performance settings are invalid.
        """
        error_location = f"{__name__}.PerformanceConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.benchmark_iterations < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"performance.benchmark_iterations must be at least 1.{context}",
                )
            )
        if self.benchmark_budget_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"performance.benchmark_budget_seconds must be positive.{context}",
                )
            )
