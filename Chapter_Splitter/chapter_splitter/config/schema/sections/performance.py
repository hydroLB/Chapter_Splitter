"""Performance measurement configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class PerformanceConfig:
    """Performance measurement settings.

    Summary:
        Control profiling, benchmarks, and performance thresholds.
    Ties to other methods:
        Used by performance scripts and CI checks.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self, benchmark_iterations: int, benchmark_budget_seconds: float) -> None:
        """Initialize performance configuration.

        Summary:
            Control benchmark iteration count and performance budgets.
        Ties to other methods:
            Used by benchmark tests and profiling scripts.
        Inputs:
            - benchmark_iterations: Number of benchmark repetitions.
            - benchmark_budget_seconds: Target budget per benchmark.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.benchmark_iterations = benchmark_iterations
        self.benchmark_budget_seconds = benchmark_budget_seconds

    def validate(self, location: str) -> None:
        """Validate performance configuration.

        Summary:
            Ensure benchmark limits are usable in CI and local runs.
        Ties to other methods:
            Called by Settings.validate before benchmark checks run.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
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
