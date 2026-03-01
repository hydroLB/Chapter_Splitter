"""Typed readers for raw configuration mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ....core.errors import ConfigurationError, format_error_message

_MISSING = object()


def get_section(raw: Mapping[str, object], section_name: str, location: str) -> dict[str, object]:
    """Return a section dictionary from the top-level raw config mapping.

    Purpose:
        Validate and extract section mappings so per-section builders can rely on strict types.
    Ties To:
        Used by chapter_splitter.config.loader.build.settings.
    Inputs:
        - raw: Top-level configuration mapping.
        - section_name: Section key to extract.
        - location: Fully qualified module and method name.
    Outputs:
        - Section dictionary.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the section is missing or not a dictionary.
    """
    error_location = f"{__name__}.get_section"
    context = f" Context: {location}." if location else ""
    if not section_name.strip():
        raise ConfigurationError(
            format_error_message(error_location, f"Section name must be non empty.{context}")
        )
    value = raw.get(section_name, _MISSING)
    if value is _MISSING:
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Missing required section: [{section_name}].{context}",
            )
        )
    if not isinstance(value, dict):
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Section [{section_name}] must be a table.{context}",
            )
        )
    return value


def read_str(section: Mapping[str, object], key: str, location: str) -> str:
    """Read a required string key from a section.

    Purpose:
        Enforce strict string typing for configuration values.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - String value.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or not a string.
    """
    error_location = f"{__name__}.read_str"
    value = _require_key(section, key, location, error_location)
    if not isinstance(value, str):
        raise _type_error(error_location, key, "string", value, location)
    return value


def read_bool(section: Mapping[str, object], key: str, location: str) -> bool:
    """Read a required boolean key from a section.

    Purpose:
        Enforce strict boolean typing for configuration values.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - Boolean value.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or not a boolean.
    """
    error_location = f"{__name__}.read_bool"
    value = _require_key(section, key, location, error_location)
    if not isinstance(value, bool):
        raise _type_error(error_location, key, "boolean", value, location)
    return value


def read_int(section: Mapping[str, object], key: str, location: str) -> int:
    """Read a required integer key from a section.

    Purpose:
        Enforce strict integer typing while rejecting boolean values.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - Integer value.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or not an integer.
    """
    error_location = f"{__name__}.read_int"
    value = _require_key(section, key, location, error_location)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _type_error(error_location, key, "integer", value, location)
    return value


def read_float(section: Mapping[str, object], key: str, location: str) -> float:
    """Read a required floating-point key from a section.

    Purpose:
        Accept numeric values for float fields while rejecting booleans.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - Float value.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or not numeric.
    """
    error_location = f"{__name__}.read_float"
    value = _require_key(section, key, location, error_location)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _type_error(error_location, key, "number", value, location)
    return float(value)


def read_str_list(section: Mapping[str, object], key: str, location: str) -> list[str]:
    """Read a required list of strings from a section.

    Purpose:
        Enforce strict list-of-strings typing for config arrays.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - List of strings.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or contains invalid values.
    """
    error_location = f"{__name__}.read_str_list"
    value = _require_key(section, key, location, error_location)
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise _type_error(error_location, key, "array of strings", value, location)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _type_error(error_location, key, "array of strings", value, location)
        result.append(item)
    return result


def read_int_list(section: Mapping[str, object], key: str, location: str) -> list[int]:
    """Read a required list of integers from a section.

    Purpose:
        Enforce strict list-of-integers typing for config arrays.
    Ties To:
        Used by settings builders in chapter_splitter.config.loader.build.settings.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
    Outputs:
        - List of integers.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the key is missing or contains invalid values.
    """
    error_location = f"{__name__}.read_int_list"
    value = _require_key(section, key, location, error_location)
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise _type_error(error_location, key, "array of integers", value, location)
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise _type_error(error_location, key, "array of integers", value, location)
        result.append(item)
    return result


def _require_key(
    section: Mapping[str, object],
    key: str,
    location: str,
    error_location: str,
) -> object:
    """Read a required key from a section or raise a configuration error.

    Purpose:
        Provide consistent missing-key handling for typed readers.
    Ties To:
        Used by read_str/read_bool/read_int/read_float/read_str_list/read_int_list.
    Inputs:
        - section: Section mapping.
        - key: Required key name.
        - location: Fully qualified module and method name.
        - error_location: Reader method location used in the error message.
    Outputs:
        - Raw value from the section mapping.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When key is missing or key name is invalid.
    """
    context = f" Context: {location}." if location else ""
    if not key.strip():
        raise ConfigurationError(
            format_error_message(error_location, f"Config key must be non empty.{context}")
        )
    value = section.get(key, _MISSING)
    if value is _MISSING:
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Missing required key: {key}.{context}",
            )
        )
    return value


def _type_error(
    error_location: str,
    key: str,
    expected: str,
    value: object,
    location: str,
) -> ConfigurationError:
    """Create a standardized type-mismatch configuration error.

    Purpose:
        Keep type mismatch error messages consistent and actionable.
    Ties To:
        Used by all typed readers in this module.
    Inputs:
        - error_location: Reader method location used in the error message.
        - key: Key name with the wrong type.
        - expected: Human-readable expected type description.
        - value: Actual value encountered.
        - location: Fully qualified module and method name.
    Outputs:
        - ConfigurationError ready to be raised.
    Side Effects:
        None.
    Raises:
        - None.
    """
    context = f" Context: {location}." if location else ""
    return ConfigurationError(
        format_error_message(
            error_location,
            f"Key '{key}' must be {expected}; got {type(value).__name__}.{context}",
        )
    )
