"""Runtime helpers for cancellation and graceful shutdown."""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from types import FrameType

from .errors import CancellationError, format_error_message


class CancellationToken:
    """Thread safe cancellation token for long running operations."""

    def __init__(self) -> None:
        """Initialize the cancellation token."""
        self._event: threading.Event = threading.Event()
        self._reason: str | None = None

    def cancel(self, reason: str, location: str) -> None:
        """Record a cancellation request."""
        error_location = f"{__name__}.CancellationToken.cancel"
        context = f" Context: {location}." if location else ""
        if not reason.strip():
            raise CancellationError(
                format_error_message(
                    error_location, f"Cancellation reason must be provided.{context}"
                )
            )
        self._reason = reason
        self._event.set()

    def check(self, location: str) -> None:
        """Raise when cancellation has been requested."""
        error_location = f"{__name__}.CancellationToken.check"
        if self._event.is_set():
            reason = self._reason or "Cancellation requested."
            context = f" Context: {location}." if location else ""
            raise CancellationError(format_error_message(error_location, f"{reason}{context}"))

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()


def register_signal_handlers(
    token: CancellationToken,
    logger: logging.Logger,
    on_shutdown: Callable[[], None],
    location: str,
) -> None:
    """Register SIGINT and SIGTERM handlers for graceful shutdown."""

    def _handler(signum: int, _frame: FrameType | None) -> None:
        """Handle termination signals by triggering shutdown."""
        signal_name = signal.Signals(signum).name
        token.cancel(f"Received {signal_name}.", location)
        logger.warning("Shutdown signal received", extra={"signal": signal_name})
        on_shutdown()

    error_location = f"{__name__}.register_signal_handlers"
    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, RuntimeError) as exc:
        context = f" Context: {location}." if location else ""
        raise CancellationError(
            format_error_message(
                error_location,
                f"Signal handler registration failed: {exc}.{context}",
            )
        ) from exc
