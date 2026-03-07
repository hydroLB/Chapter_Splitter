"""Runtime helpers for cancellation and graceful shutdown."""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from types import FrameType

from .errors import CancellationError, format_error_message


class CancellationToken:
    """Thread safe cancellation token for long running operations.

    Summary:
        Track cancellation requests across threads and workflows.
    Ties to other methods:
        Shared by CLI, UI, PDF processing, and IO operations.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(self) -> None:
        """Initialize the cancellation token.

        Summary:
            Create a token that can be shared across workflows and threads.
        Ties to other methods:
            Constructed in entry points and passed into long running functions.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Allocates an internal threading event.
        Error handling:
            - None.
        """
        self._event: threading.Event = threading.Event()
        self._reason: str | None = None

    def cancel(self, reason: str, location: str) -> None:
        """Record a cancellation request.

        Summary:
            Signal a cancellation request and store a reason for diagnostics.
        Ties to other methods:
            Used by signal handlers and UI close events to abort work.
        Inputs:
            - reason: Human readable reason for the cancellation.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Sets an internal event and records a reason.
        Error handling:
            - CancellationError: When the provided reason is empty.
        """
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
        """Raise when cancellation has been requested.

        Summary:
            Provide a consistent guard to stop work when cancellation is requested.
        Ties to other methods:
            Called inside IO loops, PDF processing, and UI workflows.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - CancellationError: When cancellation has been requested.
        """
        error_location = f"{__name__}.CancellationToken.check"
        if self._event.is_set():
            reason = self._reason or "Cancellation requested."
            context = f" Context: {location}." if location else ""
            raise CancellationError(format_error_message(error_location, f"{reason}{context}"))

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested.

        Summary:
            Allow non raising checks in shutdown paths.
        Ties to other methods:
            Used by UI teardown and CLI exit handlers.
        Inputs:
            - None.
        Outputs:
            - True when cancellation is requested.
        Side effects:
            None.
        Error handling:
            - None.
        """
        return self._event.is_set()


def register_signal_handlers(
    token: CancellationToken,
    logger: logging.Logger,
    on_shutdown: Callable[[], None],
    location: str,
) -> None:
    """Register SIGINT and SIGTERM handlers for graceful shutdown.

    Summary:
        Ensure a consistent shutdown path for CLI and GUI entry points.
    Ties to other methods:
        Called by chapter_splitter.app.main and chapter_splitter.cli.main.
    Inputs:
        - token: Cancellation token to trigger on signal.
        - logger: Logger for shutdown diagnostics.
        - on_shutdown: Callback to run before exiting.
        - location: Fully qualified module and method name.
    Outputs:
        - None.
    Side effects:
        Installs process wide signal handlers.
    Error handling:
        - CancellationError: When signal handlers cannot be registered.
    """

    def _handler(signum: int, _frame: FrameType | None) -> None:
        """Handle termination signals by triggering shutdown.

        Summary:
            Translate SIGINT and SIGTERM into a structured cancellation signal.
        Ties to other methods:
            Called by the Python signal module during process shutdown.
        Inputs:
            - signum: Numeric signal identifier from the OS.
            - _frame: Current stack frame, unused.
        Outputs:
            - None.
        Side effects:
            Cancels operations and invokes the shutdown callback.
        Error handling:
            - CancellationError: When cancellation fails to record a reason.
        """
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
