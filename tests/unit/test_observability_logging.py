"""Unit tests for structured logging helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from chapter_splitter.config.schema import AppConfig, LoggingConfig
from chapter_splitter.core.errors import ConfigurationError
from chapter_splitter.observability.logging import (
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

    Purpose:
        Ensure trace IDs are always present and usable.
    Ties To:
        Covers new_correlation_id and set_correlation_id in chapter_splitter.observability.logging.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Writes correlation IDs into a context variable.
    Raises:
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

    Purpose:
        Ensure structured logs always include correlation_id.
    Ties To:
        Covers CorrelationIdFilter.filter.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Mutates a LogRecord instance.
    Raises:
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

    Purpose:
        Prevent accidental leakage of sensitive data in logs.
    Ties To:
        Covers RedactionPolicy.redact_text and .redact_mapping.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
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

    Purpose:
        Make log output deterministic and safe for ingestion.
    Ties To:
        Covers StructuredFormatter.format and _extract_extra_fields.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Serializes a LogRecord to JSON.
    Raises:
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


def test_configure_logging_validates_formatter_and_level(tmp_path: Path) -> None:
    """Verify configure_logging rejects invalid formatter and level values.

    Purpose:
        Keep logging configuration strict and predictable.
    Ties To:
        Covers configure_logging in chapter_splitter.observability.logging.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, formatter="text"))
    with pytest.raises(ConfigurationError):
        configure_logging(_app_config(), _logging_config(tmp_path, level="NOTALEVEL"))


def test_log_event_validates_event_and_message() -> None:
    """Verify log_event requires non-empty event and message.

    Purpose:
        Ensure event logging stays structured and searchable.
    Ties To:
        Covers log_event in chapter_splitter.observability.logging.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Emits a log record when inputs are valid.
    Raises:
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

    Purpose:
        Ensure global logging setup creates a usable baseline configuration.
    Ties To:
        Covers configure_logging in chapter_splitter.observability.logging.
    Inputs:
        - tmp_path: Pytest temporary directory.
    Outputs:
        - None.
    Side Effects:
        Mutates the process-global root logger.
    Raises:
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
