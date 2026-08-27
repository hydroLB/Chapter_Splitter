"""Unit tests for structured logging helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from chapter_splitter.config.schema import AppConfig, LoggingConfig
from chapter_splitter.core import ConfigurationError
from chapter_splitter.observability import (
    CorrelationIdFilter,
    RedactionPolicy,
    StructuredFormatter,
    configure_logging,
    get_correlation_id,
    log_event,
    new_correlation_id,
    set_correlation_id,
)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _CaptureFormattedHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


def _app_config() -> AppConfig:
    return AppConfig(title="Chapter Splitter", environment="test", correlation_id_prefix="cid")


def _logging_config(
    tmp_path: Path,
    *,
    level: str = "INFO",
    formatter: str = "json",
) -> LoggingConfig:
    return LoggingConfig(
        level=level,
        formatter=formatter,
        console_enabled=False,
        file_enabled=False,
        file_path=tmp_path / "app.log",
        redact_keys=("password", "secret"),
        redact_values=("token",),
    )


def test_correlation_id_helpers_validate_inputs() -> None:
    """Verify correlation ID helpers validate inputs."""
    with pytest.raises(ConfigurationError):
        new_correlation_id("", "tests.unit.test_observability_logging")
    with pytest.raises(ConfigurationError):
        set_correlation_id("", "tests.unit.test_observability_logging")

    cid = new_correlation_id("cid", "tests.unit.test_observability_logging")
    set_correlation_id(cid, "tests.unit.test_observability_logging")
    assert get_correlation_id() == cid


def test_correlation_filter_sets_default_when_unset() -> None:
    """Verify correlation filter injects an unset value."""
    import contextvars

    def run_in_fresh_context() -> str:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
        assert CorrelationIdFilter().filter(record) is True
        return str(record.__dict__["correlation_id"])

    assert contextvars.Context().run(run_in_fresh_context) == "unset"


def test_redaction_policy_redacts_keys_and_values() -> None:
    """Verify redaction policy masks secrets."""
    policy = RedactionPolicy(keys=("password",), values=("token",))
    assert policy.redact_text("hello token") == "hello [REDACTED]"
    assert policy.redact_mapping({"password": "abc", "note": "token"}) == {
        "password": "[REDACTED]",
        "note": "[REDACTED]",
    }


def test_redaction_policy_recurses_through_nested_structures_and_cycles() -> None:
    """Nested fields are normalized and cycles cannot crash structured logging."""
    policy = RedactionPolicy(keys=("api_key", "password"), values=("token",))
    cyclic_items: list[object] = ["token"]
    cyclic_items.append(cyclic_items)
    cyclic: dict[str, object] = {
        "items": [
            {"API-Key": "credential", "note": "contains TOKEN"},
            ("safe", {"Pass-word": "credential"}),
        ],
        "cyclic_items": cyclic_items,
    }
    cyclic["self"] = cyclic

    assert policy.redact_mapping(cyclic) == {
        "items": [
            {"API-Key": "[REDACTED]", "note": "contains [REDACTED]"},
            ["safe", {"Pass-word": "[REDACTED]"}],
        ],
        "cyclic_items": ["[REDACTED]", "[CIRCULAR]"],
        "self": {"circular_reference": "[CIRCULAR]"},
    }


def test_structured_formatter_emits_expected_fields(tmp_path: Path) -> None:
    """Verify structured formatter emits stable JSON fields with redaction."""
    set_correlation_id("cid-123", "tests.unit.test_observability_logging")
    policy = RedactionPolicy(keys=("password",), values=("token",))
    formatter = StructuredFormatter(_app_config(), policy)
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello token", (), None)
    record.password = "super-secret"
    record.user = "alice"
    record.correlation_id = get_correlation_id()

    payload = json.loads(formatter.format(record))
    assert payload["environment"] == "test"
    assert payload["correlation_id"] == "cid-123"
    assert payload["message"] == "hello [REDACTED]"
    assert payload["password"] == "[REDACTED]"
    assert payload["user"] == "alice"


def test_structured_formatter_preserves_sanitized_exception_diagnostics() -> None:
    """Exception logs retain actionable diagnostics without leaking configured values."""
    logger = logging.getLogger("tests.unit.test_observability_logging.exception")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.ERROR)

    handler = _CaptureFormattedHandler()
    handler.setFormatter(
        StructuredFormatter(
            _app_config(),
            RedactionPolicy(keys=("api_key",), values=("token",)),
        )
    )
    logger.addHandler(handler)

    try:
        raise ValueError("invalid token")
    except ValueError:
        logger.exception(
            "operation failed for token",
            extra={"details": {"API-Key": "credential", "items": ["token", "safe"]}},
        )

    payload = json.loads(handler.messages[0])
    assert payload["message"] == "operation failed for [REDACTED]"
    assert payload["details"] == {
        "API-Key": "[REDACTED]",
        "items": ["[REDACTED]", "safe"],
    }
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["message"] == "invalid [REDACTED]"
    assert "Traceback (most recent call last)" in payload["exception"]["traceback"]
    assert "ValueError: invalid [REDACTED]" in payload["exception"]["traceback"]
    assert "token" not in handler.messages[0].lower()


def test_structured_log_contract_includes_schema_and_correlation_id(tmp_path: Path) -> None:
    """Verify emitted structured logs contain required schema keys and correlation IDs."""
    logger = logging.getLogger("tests.unit.test_observability_logging.contract")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = _CaptureFormattedHandler()
    handler.setFormatter(StructuredFormatter(_app_config(), RedactionPolicy(keys=(), values=())))
    handler.addFilter(CorrelationIdFilter())
    logger.addHandler(handler)

    set_correlation_id("cid-contract", "tests.unit.test_observability_logging")
    log_event(logger, logging.INFO, "contract_event", "contract_message", {"custom": "value"})

    assert len(handler.messages) == 1
    payload = json.loads(handler.messages[0])
    required_keys = {
        "timestamp",
        "level",
        "logger",
        "message",
        "correlation_id",
        "environment",
        "event",
    }
    assert required_keys.issubset(payload.keys())
    assert payload["correlation_id"] == "cid-contract"
    assert payload["event"] == "contract_event"
    assert payload["custom"] == "value"


def test_configure_logging_validates_formatter_and_level(tmp_path: Path) -> None:
    """Verify configure_logging rejects invalid formatter and level values."""
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, formatter="text"))
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, level="NOTALEVEL"))


def test_log_event_validates_event_and_message() -> None:
    """Verify log_event requires non-empty event and message."""
    logger = logging.getLogger("tests.unit.test_observability_logging")
    handler = _CaptureHandler()
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)

    with pytest.raises(ConfigurationError):
        log_event(logger, logging.INFO, "", "msg", None)
    with pytest.raises(ConfigurationError):
        log_event(logger, logging.INFO, "event", "", None)

    log_event(logger, logging.INFO, "event", "msg", {"a": 1})
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.__dict__["event"] == "event"
    assert record.__dict__["a"] == 1


def test_configure_logging_installs_handlers(tmp_path: Path) -> None:
    """Verify configure_logging installs structured handlers and filters."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    try:
        cfg = _logging_config(tmp_path)
        cfg.console_enabled = True
        configure_logging(_app_config(), cfg)
        assert root.handlers
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        assert any(
            any(isinstance(f, CorrelationIdFilter) for f in h.filters) for h in root.handlers
        )
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
