"""Deep-merge logic for layered configuration dictionaries."""

from __future__ import annotations

from chapter_splitter.core.errors import ConfigurationError, format_error_message


def merge_configs(
    base: dict[str, object],
    override: dict[str, object],
    location: str,
) -> dict[str, object]:
    """Merge override configuration values into the base config."""
    merged: dict[str, object] = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(
                coerce_dict(merged[key], location),
                coerce_dict(value, location),
                location,
            )
        else:
            merged[key] = value
    return merged


def coerce_dict(value: object, location: str) -> dict[str, object]:
    """Ensure a value is a string keyed dictionary."""
    error_location = f"{__name__}.coerce_dict"
    context = f" Context: {location}." if location else ""
    if not isinstance(value, dict):
        raise ConfigurationError(
            format_error_message(
                error_location, f"Config merge expects dictionary values.{context}"
            )
        )
    return value
