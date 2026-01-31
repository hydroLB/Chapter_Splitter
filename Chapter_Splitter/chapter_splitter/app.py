"""GUI entry point for the Chapter Splitter application."""

from __future__ import annotations

import logging
from pathlib import Path

from .config import load_config
from .core.errors import CancellationError, ChapterSplitterError, format_error_message
from .core.runtime import CancellationToken, register_signal_handlers
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)
from .ui.tk.workflow import workflow

logger = logging.getLogger(__name__)


def main(config_path: Path | None = None) -> int:
    """Run the GUI application workflow.

    Purpose:
        Initialize configuration, logging, and launch the Tkinter UI.
    Ties To:
        Called by the chapter-splitter-gui console script.
    Inputs:
        - config_path: Optional path to a configuration file.
    Outputs:
        - Exit code integer for the process.
    Side Effects:
        Configures logging, registers signal handlers, launches the GUI.
    Raises:
        - None.
    """
    location = "chapter_splitter.app.main"
    settings = load_config(config_path, location)
    configure_logging(settings.app, settings.logging)
    correlation_id = new_correlation_id(settings.app.correlation_id_prefix, location)
    set_correlation_id(correlation_id, location)

    token = CancellationToken()

    def _shutdown() -> None:
        """Handle a graceful shutdown request.

        Purpose:
            Provide a shutdown callback for signal handling.
        Ties To:
            Registered via register_signal_handlers.
        Inputs:
            - None.
        Outputs:
            - None.
        Side Effects:
            Marks the cancellation token as cancelled.
        Raises:
            - CancellationError: When cancellation reason is invalid.
        """
        token.cancel("Shutdown requested.", location)

    register_signal_handlers(token, logger, _shutdown, location)

    log_event(
        logger,
        logging.INFO,
        "app_started",
        f"{settings.app.title} started",
        {"title": settings.app.title},
    )

    try:
        workflow(settings, token)
        return 0
    except CancellationError as exc:
        log_event(
            logger,
            logging.WARNING,
            "app_cancelled",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
        return 130
    except ChapterSplitterError as exc:
        log_event(
            logger,
            logging.ERROR,
            "app_error",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
        return 1
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "Unhandled exception",
            extra={"event": "app_unhandled_exception", "reason": str(exc)},
        )
        return 1
    finally:
        log_event(
            logger,
            logging.INFO,
            "app_stopped",
            f"{settings.app.title} stopped",
            {"title": settings.app.title},
        )
