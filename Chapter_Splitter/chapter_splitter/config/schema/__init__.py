"""Configuration schema and validation for application settings.

This package keeps each configuration section isolated in its own module so the schema is
easy to navigate, modify, and debug.
"""

from __future__ import annotations

from .sections.app import AppConfig
from .sections.io import IOConfig
from .sections.logging import LoggingConfig
from .sections.performance import PerformanceConfig
from .sections.retry import RetryConfig
from .sections.ui import UIConfig
from .sections.validation import ValidationConfig
from .settings import Settings

__all__ = [
    "AppConfig",
    "IOConfig",
    "LoggingConfig",
    "PerformanceConfig",
    "RetryConfig",
    "Settings",
    "UIConfig",
    "ValidationConfig",
]
