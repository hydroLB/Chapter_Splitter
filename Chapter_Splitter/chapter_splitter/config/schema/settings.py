"""Top-level settings container for the application."""

from __future__ import annotations

from .sections.app import AppConfig
from .sections.detection import DetectionConfig
from .sections.io import IOConfig
from .sections.logging import LoggingConfig
from .sections.performance import PerformanceConfig
from .sections.retry import RetryConfig
from .sections.ui import UIConfig
from .sections.validation import ValidationConfig


class Settings:
    """Top level application settings.

    Summary:
        Provide a validated container for all configuration sections.
    Ties to other methods:
        Loaded by config loader and used by CLI and UI entry points.
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
        app: AppConfig,
        logging: LoggingConfig,
        io: IOConfig,
        retry: RetryConfig,
        ui: UIConfig,
        validation: ValidationConfig,
        detection: DetectionConfig,
        performance: PerformanceConfig,
    ) -> None:
        """Initialize the settings registry.

        Summary:
            Aggregate all configuration sections into a single object.
        Ties to other methods:
            Used by config registry and injected into runtime modules.
        Inputs:
            - app: Application configuration.
            - logging: Logging configuration.
            - io: IO configuration.
            - retry: Retry policy configuration.
            - ui: UI configuration.
            - validation: Validation configuration.
            - detection: Detection configuration.
            - performance: Performance configuration.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.app = app
        self.logging = logging
        self.io = io
        self.retry = retry
        self.ui = ui
        self.validation = validation
        self.detection = detection
        self.performance = performance

    def validate(self, location: str) -> None:
        """Validate all configuration sections.

        Summary:
            Ensure configuration is internally consistent before use.
        Ties to other methods:
            Called after loading configuration and before runtime setup.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ConfigurationError: When any section fails validation.
        """
        self.app.validate(location)
        self.logging.validate(location)
        self.io.validate(location)
        self.retry.validate(location)
        self.ui.validate(location)
        self.validation.validate(location)
        self.detection.validate(location)
        self.performance.validate(location)
