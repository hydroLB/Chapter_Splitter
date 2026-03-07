"""Unit tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from chapter_splitter.config.loader import load_settings


def test_load_settings_applies_overrides(tmp_path: Path) -> None:
    """Verify override values are applied on top of defaults.

    Summary:
        Ensure load_settings merges overrides with default configuration.
    Ties to other methods:
        Covers chapter_splitter.config.loader.load_settings.
    Inputs:
        - tmp_path: Pytest provided temporary directory.
    Outputs:
        - None.
    Side effects:
        Writes a temporary TOML file.
    Error handling:
        - None.
    """
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
