"""Unit tests for typed error codes and centralized error payload mapping."""

from __future__ import annotations

import logging

from chapter_splitter.core import (
    CancellationError,
    ChapterSplitterError,
    ConfigurationError,
    ErrorCode,
    map_error,
)


def test_error_classes_expose_stable_default_codes() -> None:
    """Verify default error codes are assigned by exception type."""
    assert ConfigurationError("bad config").code is ErrorCode.CONFIGURATION
    assert CancellationError("cancelled").code is ErrorCode.CANCELLATION
    assert ChapterSplitterError("base").code is ErrorCode.UNKNOWN


def test_error_classes_allow_explicit_code_override() -> None:
    """Verify explicit code overrides are preserved on exception instances."""
    exc = ChapterSplitterError("override", code=ErrorCode.INTERNAL)
    assert exc.code is ErrorCode.INTERNAL


def test_map_error_cancellation_preserves_exit_semantics() -> None:
    """Verify cancellation maps to warning-level payload with exit code 130."""
    payload = map_error(
        CancellationError("user cancelled"),
        channel="cli",
        location="tests.unit.test_error_mapping",
    )
    assert payload.code is ErrorCode.CANCELLATION
    assert payload.event == "cli_cancelled"
    assert payload.exit_code == 130
    assert payload.log_level == logging.WARNING
    assert payload.user_message.startswith("[CHAPTER_SPLITTER_CANCELLATION]")
    assert payload.log_fields(location="x")["error_code"] == ErrorCode.CANCELLATION.value


def test_map_error_domain_and_unhandled_paths() -> None:
    """Verify domain and unexpected exceptions map to stable payload contracts."""
    domain_payload = map_error(
        ConfigurationError("invalid"),
        channel="app",
        location="tests.unit.test_error_mapping",
    )
    assert domain_payload.code is ErrorCode.CONFIGURATION
    assert domain_payload.event == "app_error"
    assert domain_payload.exit_code == 1

    unhandled_payload = map_error(
        RuntimeError("boom"),
        channel="ui",
        location="tests.unit.test_error_mapping",
    )
    assert unhandled_payload.code is ErrorCode.INTERNAL
    assert unhandled_payload.event == "ui_unhandled_exception"
    assert unhandled_payload.exit_code == 1
