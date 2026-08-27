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
    """Top level application settings."""

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
        """Initialize the settings registry."""
        self.app = app
        self.logging = logging
        self.io = io
        self.retry = retry
        self.ui = ui
        self.validation = validation
        self.detection = detection
        self.performance = performance

    def validate(self, location: str) -> None:
        """Validate all configuration sections."""
        self.app.validate(location)
        self.logging.validate(location)
        self.io.validate(location)
        self.retry.validate(location)
        self.ui.validate(location)
        self.validation.validate(location)
        self.detection.validate(location)
        self.performance.validate(location)
