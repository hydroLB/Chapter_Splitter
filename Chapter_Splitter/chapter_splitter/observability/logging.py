"""Structured logging, redaction, and correlation ID helpers."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from contextvars import ContextVar

from ..config.schema import AppConfig, LoggingConfig
from ..core.errors import ConfigurationError, format_error_message

_CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="")
_CIRCULAR_REFERENCE = "[CIRCULAR]"
_REDACTED = "[REDACTED]"


def _normalize_sensitive_key(key: str) -> str:
    """Return a separator-insensitive, case-normalized key for policy matching."""
    return "".join(character for character in key.casefold() if character.isalnum())


def new_correlation_id(prefix: str, location: str) -> str:
    """Create a new correlation ID."""
    error_location = f"{__name__}.new_correlation_id"
    context = f" Context: {location}." if location else ""
    if not prefix.strip():
        raise ConfigurationError(
            format_error_message(
                error_location,
                f"Correlation ID prefix must be non empty.{context}",
            )
        )
    return f"{prefix}-{uuid.uuid4()}"


def set_correlation_id(value: str, location: str) -> None:
    """Set the current correlation ID."""
    error_location = f"{__name__}.set_correlation_id"
    context = f" Context: {location}." if location else ""
    if not value.strip():
        raise ConfigurationError(
            format_error_message(error_location, f"Correlation ID must be non empty.{context}")
        )
    _CORRELATION_ID.set(value)


def get_correlation_id() -> str:
    """Return the current correlation ID."""
    return _CORRELATION_ID.get()


class CorrelationIdFilter(logging.Filter):
    """Inject correlation IDs into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = get_correlation_id() or "unset"
        return True


class RedactionPolicy:
    """Redact sensitive content from log fields."""

    def __init__(self, keys: Iterable[str], values: Iterable[str]) -> None:
        """Initialize the redaction policy."""
        self._key_set = {_normalize_sensitive_key(key) for key in keys}
        self._value_patterns = [
            re.compile(re.escape(value), re.IGNORECASE) for value in values if value
        ]

    def redact_text(self, text: str) -> str:
        """Redact sensitive substrings in a text field."""
        redacted = text
        for pattern in self._value_patterns:
            redacted = pattern.sub(_REDACTED, redacted)
        return redacted

    def redact_mapping(self, fields: Mapping[str, object]) -> dict[str, object]:
        """Redact sensitive fields in structured log output."""
        return self._redact_mapping(fields, active_container_ids=set())

    def _redact_mapping(
        self,
        fields: Mapping[str, object],
        active_container_ids: set[int],
    ) -> dict[str, object]:
        """Recursively redact a mapping while detecting cycles on the active path."""
        container_id = id(fields)
        if container_id in active_container_ids:
            return {"circular_reference": _CIRCULAR_REFERENCE}

        active_container_ids.add(container_id)
        try:
            redacted: dict[str, object] = {}
            for key, value in fields.items():
                if _normalize_sensitive_key(key) in self._key_set:
                    redacted[key] = _REDACTED
                else:
                    redacted[key] = self._redact_value(value, active_container_ids)
            return redacted
        finally:
            active_container_ids.remove(container_id)

    def _redact_value(self, value: object, active_container_ids: set[int]) -> object:
        """Recursively sanitize supported JSON-like structured values."""
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, Mapping):
            return self._redact_mapping(value, active_container_ids)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            container_id = id(value)
            if container_id in active_container_ids:
                return _CIRCULAR_REFERENCE
            active_container_ids.add(container_id)
            try:
                return [self._redact_value(item, active_container_ids) for item in value]
            finally:
                active_container_ids.remove(container_id)
        return value


class StructuredFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def __init__(self, app_config: AppConfig, redaction: RedactionPolicy) -> None:
        """Initialize the formatter."""
        super().__init__()
        self._app_config = app_config
        self._redaction = redaction

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into JSON."""
        message = self._redaction.redact_text(record.getMessage())
        base_fields: dict[str, object] = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "correlation_id": getattr(record, "correlation_id", "unset"),
            "environment": self._app_config.environment,
        }
        extras = _extract_extra_fields(record, base_fields.keys())
        if record.exc_info is not None:
            exception = record.exc_info[1]
            extras["exception"] = {
                "type": type(exception).__name__ if exception is not None else "Unknown",
                "message": str(exception) if exception is not None else "",
                "traceback": self.formatException(record.exc_info),
            }
        merged = {**base_fields, **extras}
        redacted = self._redaction.redact_mapping(merged)
        return json.dumps(redacted, ensure_ascii=True)


def _extract_extra_fields(record: logging.LogRecord, reserved: Iterable[str]) -> dict[str, object]:
    """Extract non standard log record attributes as structured fields."""
    reserved_set = set(reserved)
    extras: dict[str, object] = {}
    for key, value in record.__dict__.items():
        if key.startswith("_") or key in reserved_set:
            continue
        if key in (
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        ):
            continue
        extras[key] = value
    return extras


def configure_logging(app_config: AppConfig, logging_config: LoggingConfig) -> None:
    """Configure structured logging for the application."""
    formatter_name = logging_config.formatter.lower()
    if formatter_name != "json":
        raise ConfigurationError(
            format_error_message(
                "chapter_splitter.observability.logging.configure_logging",
                f"Unsupported logging formatter: {logging_config.formatter}",
            )
        )

    level = logging.getLevelName(logging_config.level.upper())
    if not isinstance(level, int):
        raise ConfigurationError(
            format_error_message(
                "chapter_splitter.observability.logging.configure_logging",
                f"Invalid logging level: {logging_config.level}",
            )
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    redaction = RedactionPolicy(logging_config.redact_keys, logging_config.redact_values)
    formatter = StructuredFormatter(app_config, redaction)
    correlation_filter = CorrelationIdFilter()

    if logging_config.console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(correlation_filter)
        root_logger.addHandler(console_handler)

    if logging_config.file_enabled:
        try:
            logging_config.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError(
                format_error_message(
                    "chapter_splitter.observability.logging.configure_logging",
                    f"Unable to create log directory: {logging_config.file_path.parent}",
                )
            ) from exc
        file_handler = logging.FileHandler(logging_config.file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(correlation_filter)
        root_logger.addHandler(file_handler)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    fields: Mapping[str, object] | None,
) -> None:
    """Log a structured event with consistent fields."""
    error_location = f"{__name__}.log_event"
    if not event.strip():
        raise ConfigurationError(
            format_error_message(error_location, "Event name must be non empty.")
        )
    if not message.strip():
        raise ConfigurationError(
            format_error_message(error_location, "Log message must be non empty.")
        )
    extra_fields = dict(fields or {})
    extra_fields["event"] = event
    logger.log(level, message, extra=extra_fields)
