"""Deep-merge logic for layered configuration dictionaries."""

from __future__ import annotations

from chapter_splitter.core.errors import ConfigurationError, format_error_message


def merge_configs(
    base: dict[str, object],
    override: dict[str, object],
    location: str,
) -> dict[str, object]:
    """Merge override configuration values into the base config.

    Summary:
        Support configuration overlays without losing default values.
    Ties to other methods:
        Used by load_settings after reading override config files.
    Inputs:
        - base: Base config mapping.
        - override: Override config mapping.
        - location: Fully qualified module and method name.
    Outputs:
        - Merged configuration mapping.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When config structures are incompatible.
    """
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
    """Ensure a value is a string keyed dictionary.

    Summary:
        Provide safe typing for recursive config merges.
    Ties to other methods:
        Used by merge_configs when merging nested dictionaries.
    Inputs:
        - value: Candidate dictionary value.
        - location: Fully qualified module and method name.
    Outputs:
        - Dictionary with string keys.
    Side effects:
        None.
    Error handling:
        - ConfigurationError: When the value is not a dictionary.
    """
    error_location = f"{__name__}.coerce_dict"
    context = f" Context: {location}." if location else ""
    if not isinstance(value, dict):
        raise ConfigurationError(
            format_error_message(
                error_location, f"Config merge expects dictionary values.{context}"
            )
        )
    return value
