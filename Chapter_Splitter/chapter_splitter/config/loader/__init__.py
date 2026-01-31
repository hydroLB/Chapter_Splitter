"""Configuration loader entrypoint.

The loader is split into small modules so each concern (source discovery, TOML IO, merging,
and typed object building) is easy to debug in isolation.
"""

from __future__ import annotations

from .api import load_settings

__all__ = ["load_settings"]
