"""Internal test seam for configuration loader subcomponents.

This module exists to avoid brittle test dependencies on nested implementation module paths.
It is intentionally excluded from public package exports and may change between minor releases.
"""

from __future__ import annotations

from .build import settings as settings_builder
from .build.readers import (
    get_section,
    read_bool,
    read_float,
    read_int,
    read_int_list,
    read_str,
    read_str_list,
)
from .merge.deep_merge import coerce_dict
from .sources import read_default_settings, resolve_env_path
from .toml.reader import config_read_deadline, read_toml_file

__all__ = [
    "coerce_dict",
    "config_read_deadline",
    "get_section",
    "read_bool",
    "read_default_settings",
    "read_float",
    "read_int",
    "read_int_list",
    "read_str",
    "read_str_list",
    "read_toml_file",
    "resolve_env_path",
    "settings_builder",
]
