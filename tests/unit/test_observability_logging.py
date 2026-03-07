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
    """Verify correlation ID helpers validate inputs.

    Summary:
        Ensure trace IDs are always present and usable.
    Ties to other methods:
        Covers new_correlation_id and set_correlation_id in chapter_splitter.observability.logging.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Writes correlation IDs into a context variable.
    Error handling:
        - None.
    """
    with pytest.raises(ConfigurationError):
        new_correlation_id("", "tests.unit.test_observability_logging")
    with pytest.raises(ConfigurationError):
        set_correlation_id("", "tests.unit.test_observability_logging")

    cid = new_correlation_id("cid", "tests.unit.test_observability_logging")
    set_correlation_id(cid, "tests.unit.test_observability_logging")
    assert get_correlation_id() == cid


def test_correlation_filter_sets_default_when_unset() -> None:
    """Verify correlation filter injects an unset value.

    Summary:
        Ensure structured logs always include correlation_id.
    Ties to other methods:
        Covers CorrelationIdFilter.filter.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Mutates a LogRecord instance.
    Error handling:
        - None.
    """
    import contextvars

    def run_in_fresh_context() -> str:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
        assert CorrelationIdFilter().filter(record) is True
        return str(record.__dict__["correlation_id"])

    assert contextvars.Context().run(run_in_fresh_context) == "unset"


def test_redaction_policy_redacts_keys_and_values() -> None:
    """Verify redaction policy masks secrets.

    Summary:
        Prevent accidental leakage of sensitive data in logs.
    Ties to other methods:
        Covers RedactionPolicy.redact_text and .redact_mapping.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    policy = RedactionPolicy(keys=("password",), values=("token",))
    assert policy.redact_text("hello token") == "hello [REDACTED]"
    assert policy.redact_mapping({"password": "abc", "note": "token"}) == {
        "password": "[REDACTED]",
        "note": "[REDACTED]",
    }


def test_structured_formatter_emits_expected_fields(tmp_path: Path) -> None:
    """Verify structured formatter emits stable JSON fields with redaction.

    Summary:
        Make log output deterministic and safe for ingestion.
    Ties to other methods:
        Covers StructuredFormatter.format and _extract_extra_fields.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        Serializes a LogRecord to JSON.
    Error handling:
        - None.
    """
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


def test_structured_log_contract_includes_schema_and_correlation_id(tmp_path: Path) -> None:
    """Verify emitted structured logs contain required schema keys and correlation IDs.

    Summary:
        Lock ingestion-facing structured log contract to deterministic required keys.
    Ties to other methods:
        Covers StructuredFormatter, CorrelationIdFilter, and log_event integration.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        Emits a single in-memory log message through a configured handler.
    Error handling:
        - None.
    """
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
    """Verify configure_logging rejects invalid formatter and level values.

    Summary:
        Keep logging configuration strict and predictable.
    Ties to other methods:
        Covers configure_logging in chapter_splitter.observability.logging.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, formatter="text"))
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, level="NOTALEVEL"))


def test_log_event_validates_event_and_message() -> None:
    """Verify log_event requires non-empty event and message.

    Summary:
        Ensure event logging stays structured and searchable.
    Ties to other methods:
        Covers log_event in chapter_splitter.observability.logging.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Emits a log record when inputs are valid.
    Error handling:
        - None.
    """
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
    """Verify configure_logging installs structured handlers and filters.

    Summary:
        Ensure global logging setup creates a usable baseline configuration.
    Ties to other methods:
        Covers configure_logging in chapter_splitter.observability.logging.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side effects:
        Mutates the process-global root logger.
    Error handling:
        - None.
    """
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
