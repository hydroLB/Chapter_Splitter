"""Public configuration access for the application."""

from __future__ import annotations

from .loader import load_settings
from .schema import Settings

__all__ = ["Settings", "load_settings"]
