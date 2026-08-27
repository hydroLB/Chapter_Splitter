"""Centralized mapping from exceptions to structured error payloads."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from .errors import CancellationError, ChapterSplitterError, ErrorCode, format_error_message


@dataclass(frozen=True, slots=True)
class ErrorPayload:
    """Structured error payload used across CLI, UI, and app boundaries."""

    code: ErrorCode
    event: str
    message: str
    reason: str
    exit_code: int
    log_level: int
    user_message: str

    def log_fields(self, *, location: str) -> dict[str, object]:
        """Return structured fields for logging."""
        return {
            "reason": self.reason,
            "error_code": self.code.value,
            "exit_code": self.exit_code,
            "location": location,
        }


def map_error(
    exc: BaseException,
    *,
    channel: Literal["app", "cli", "ui"],
    location: str,
) -> ErrorPayload:
    """Map an exception to a stable structured payload."""
    if isinstance(exc, CancellationError):
        reason = str(exc)
        return ErrorPayload(
            code=exc.code,
            event=f"{channel}_cancelled",
            message=format_error_message(location, reason),
            reason=reason,
            exit_code=130,
            log_level=logging.WARNING,
            user_message=f"[{exc.code.value}] {reason}",
        )
    if isinstance(exc, ChapterSplitterError):
        reason = str(exc)
        return ErrorPayload(
            code=exc.code,
            event=f"{channel}_error",
            message=format_error_message(location, reason),
            reason=reason,
            exit_code=1,
            log_level=logging.ERROR,
            user_message=f"[{exc.code.value}] {reason}",
        )

    reason = str(exc)
    return ErrorPayload(
        code=ErrorCode.INTERNAL,
        event=f"{channel}_unhandled_exception",
        message=format_error_message(location, reason),
        reason=reason,
        exit_code=1,
        log_level=logging.ERROR,
        user_message=f"[{ErrorCode.INTERNAL.value}] {reason}",
    )
