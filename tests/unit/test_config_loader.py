"""Unit tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from chapter_splitter.config.loader import load_settings
from chapter_splitter.core import ConfigurationError


def test_load_settings_applies_overrides(tmp_path: Path) -> None:
    """Verify override values are applied on top of defaults."""
    override_path = tmp_path / "override.toml"
    override_path.write_text(
        """
[logging]
console_enabled = false
file_enabled = false
file_path = "override.log"
""",
        encoding="utf-8",
    )
    settings = load_settings(override_path, "tests.unit.test_config_loader")
    assert settings.logging.console_enabled is False
    assert settings.logging.file_enabled is False
    assert settings.logging.file_path.name == "override.log"


@pytest.mark.parametrize("toml_value", ["nan", "+inf", "-inf"])
@pytest.mark.parametrize(
    ("section", "field_name"),
    [
        ("io", "viewer_timeout_seconds"),
        ("io", "pdf_read_timeout_seconds"),
        ("io", "pdf_write_timeout_seconds"),
        ("io", "operation_timeout_seconds"),
        ("retry", "initial_delay_seconds"),
        ("retry", "max_delay_seconds"),
        ("retry", "jitter_ratio"),
        ("performance", "benchmark_budget_seconds"),
    ],
)
def test_load_settings_rejects_non_finite_float_values(
    tmp_path: Path,
    section: str,
    field_name: str,
    toml_value: str,
) -> None:
    """Verify TOML special floats cannot enter runtime settings."""
    override_path = tmp_path / "override.toml"
    override_path.write_text(
        f"[{section}]\n{field_name} = {toml_value}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match=field_name):
        load_settings(override_path, "tests.unit.test_config_loader")
