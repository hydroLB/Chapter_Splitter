"""Structured logging, redaction, and correlation ID helpers."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterable, Mapping
from contextvars import ContextVar

from ..config.schema import AppConfig, LoggingConfig
from ..core.errors import ConfigurationError, format_error_message

_CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id(prefix: str, location: str) -> str:
    """Create a new correlation ID.

    Purpose:
        Generate a unique correlation ID for log tracing.
    Ties To:
        Used by entry points and long running workflows.
    Inputs:
        - prefix: Prefix for the correlation ID.
        - location: Fully qualified module and method name.
    Outputs:
        - Correlation ID string.
    Side Effects:
        None.
    Raises:
        - ConfigurationError: When the prefix is invalid.
    """
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
    """Set the current correlation ID.

    Purpose:
        Store the correlation ID in context local storage.
    Ties To:
        Used by entry points and workflow boundaries.
    Inputs:
        - value: Correlation ID to store.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side Effects:
        Updates the context variable for correlation ID.
    Raises:
        - ConfigurationError: When the correlation ID is empty.
    """
    error_location = f"{__name__}.set_correlation_id"
    context = f" Context: {location}." if location else ""
    if not value.strip():
        raise ConfigurationError(
            format_error_message(error_location, f"Correlation ID must be non empty.{context}")
        )
    _CORRELATION_ID.set(value)


def get_correlation_id() -> str:
    """Return the current correlation ID.

    Purpose:
        Provide correlation ID access for log formatters.
    Ties To:
        Used by CorrelationIdFilter.
    Inputs:
        - None.
    Outputs:
        - Correlation ID string.
    Side Effects:
        None.
    Raises:
        - None.
    """
    return _CORRELATION_ID.get()


class CorrelationIdFilter(logging.Filter):
    """Inject correlation IDs into log records.

    Purpose:
        Ensure log records include a correlation_id field.
    Ties To:
        Applied in configure_logging to enrich log records.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record.

        Purpose:
            Ensure every log record contains a correlation ID field.
        Ties To:
            Applied in configure_logging.
        Inputs:
            - record: LogRecord to enrich.
        Outputs:
            - True to allow logging.
        Side Effects:
            Adds correlation_id attribute to the record.
        Raises:
            - None.
        """
        record.correlation_id = get_correlation_id() or "unset"
        return True


class RedactionPolicy:
    """Redact sensitive content from log fields.

    Purpose:
        Define redaction rules for structured logging output.
    Ties To:
        Used by StructuredFormatter when building log payloads.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, keys: Iterable[str], values: Iterable[str]) -> None:
        """Initialize the redaction policy.

        Purpose:
            Define which fields and values must be redacted in logs.
        Ties To:
            Used by StructuredFormatter to sanitize output.
        Inputs:
            - keys: Field names to redact.
            - values: Substrings to redact from text fields.
        Outputs:
            - None.
        Side Effects:
            Compiles internal redaction patterns.
        Raises:
            - None.
        """
        self._key_set = {key.lower() for key in keys}
        self._value_patterns = [
            re.compile(re.escape(value), re.IGNORECASE) for value in values if value
        ]

    def redact_text(self, text: str) -> str:
        """Redact sensitive substrings in a text field.

        Purpose:
            Protect secrets from appearing in log messages.
        Ties To:
            Called by StructuredFormatter for log message strings.
        Inputs:
            - text: Text to redact.
        Outputs:
            - Redacted text.
        Side Effects:
            None.
        Raises:
            - None.
        """
        redacted = text
        for pattern in self._value_patterns:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def redact_mapping(self, fields: Mapping[str, object]) -> dict[str, object]:
        """Redact sensitive fields in structured log output.

        Purpose:
            Remove or mask fields identified as sensitive.
        Ties To:
            Called by StructuredFormatter before JSON serialization.
        Inputs:
            - fields: Mapping of log fields.
        Outputs:
            - Redacted field mapping.
        Side Effects:
            None.
        Raises:
            - None.
        """
        redacted: dict[str, object] = {}
        for key, value in fields.items():
            if key.lower() in self._key_set:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted[key] = self.redact_text(value)
            else:
                redacted[key] = value
        return redacted


class StructuredFormatter(logging.Formatter):
    """Format log records as structured JSON.

    Purpose:
        Produce consistent JSON logs with redaction and metadata.
    Ties To:
        Used by configure_logging to build logging handlers.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(self, app_config: AppConfig, redaction: RedactionPolicy) -> None:
        """Initialize the formatter.

        Purpose:
            Provide consistent JSON log output with redaction.
        Ties To:
            Used by configure_logging to build handlers.
        Inputs:
            - app_config: Application configuration for environment metadata.
            - redaction: Redaction policy for sensitive fields.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        super().__init__()
        self._app_config = app_config
        self._redaction = redaction

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into JSON.

        Purpose:
            Serialize log records with consistent fields and redaction.
        Ties To:
            Used by logging handlers configured in configure_logging.
        Inputs:
            - record: Log record to format.
        Outputs:
            - JSON log string.
        Side Effects:
            None.
        Raises:
            - None.
        """
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
        merged = {**base_fields, **extras}
        redacted = self._redaction.redact_mapping(merged)
        return json.dumps(redacted, ensure_ascii=True)


def _extract_extra_fields(record: logging.LogRecord, reserved: Iterable[str]) -> dict[str, object]:
    """Extract non standard log record attributes as structured fields.

    Purpose:
        Capture explicit extra fields supplied by the application.
    Ties To:
        Used by StructuredFormatter during log formatting.
    Inputs:
        - record: Log record containing extra attributes.
        - reserved: Keys that are already part of the base log payload.
    Outputs:
        - Mapping of extra field values.
    Side Effects:
        None.
    Raises:
        - None.
    """
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
    """Configure structured logging for the application.

    Purpose:
        Set up log handlers with structured formatting and redaction.
    Ties To:
        Called by app and CLI entry points before any work begins.
    Inputs:
        - app_config: Application configuration.
        - logging_config: Logging configuration.
    Outputs:
        - None.
    Side Effects:
        Configures the global logging system.
    Raises:
        - ConfigurationError: When logging level or formatter is invalid.
    """
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
    """Log a structured event with consistent fields.

    Purpose:
        Provide a single helper for structured event logging.
    Ties To:
        Used across CLI, UI, and PDF processing modules.
    Inputs:
        - logger: Logger instance.
        - level: Logging level.
        - event: Short event name.
        - message: Human readable message.
        - fields: Extra structured fields to attach.
    Outputs:
        - None.
    Side Effects:
        Emits a structured log record.
    Raises:
        - ConfigurationError: When event or message is empty.
    """
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
