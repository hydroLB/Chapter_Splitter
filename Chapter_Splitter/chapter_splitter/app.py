"""GUI entry point for the Chapter Splitter application.

Summary:
    Provide the desktop application entrypoint and launch the configured GUI workflow.
Inputs:
    - None.
Outputs:
    - None.
Side effects:
    Configures logging, registers signal handlers, and runs the GUI event loop.
Error handling:
    Converts known application errors into structured logs and exit codes.
Ties to other methods:
    Calls chapter_splitter.ui.qt.workflow.workflow.
Why this exists:
    Keep a stable process entrypoint regardless of GUI implementation details.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config.loader import load_settings
from .config.schema import Settings
from .core.error_mapping import map_error
from .core.runtime import CancellationToken, register_signal_handlers
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)
from .observability.metrics import MetricsSink, NoOpMetrics
from .ui.qt.workflow import workflow

logger = logging.getLogger(__name__)


def main(
    config_path: Path | None = None,
    settings: Settings | None = None,
    *,
    metrics: MetricsSink | None = None,
) -> int:
    """Run the GUI application workflow.

    Inputs:
        - config_path: Optional path to a configuration file.
        - settings: Optional pre-loaded settings instance injected by callers.
        - metrics: Optional metrics sink for counters and timers.
    Outputs:
        - Exit code integer for the process.
    Side effects:
        Loads configuration, configures logging, registers signal handlers, launches the GUI.
    Error handling:
        Returns a non-zero exit code for failures while emitting structured logs.
    Ties to other methods:
        Called by the chapter-splitter-gui console script.
    Why this exists:
        Desktop packaging expects a single entrypoint that returns an integer exit code.
    """
    location = "chapter_splitter.app.main"
    resolved_settings = settings or load_settings(config_path, location)
    metrics_sink = metrics or NoOpMetrics()
    configure_logging(resolved_settings.app, resolved_settings.logging)
    correlation_id = new_correlation_id(resolved_settings.app.correlation_id_prefix, location)
    set_correlation_id(correlation_id, location)

    token = CancellationToken()

    def _shutdown() -> None:
        """Handle a graceful shutdown request.

        Summary:
            Provide a shutdown callback for signal handling.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Cancels the workflow token.
        Error handling:
            Relies on CancellationToken.cancel validation and allows CancellationError to bubble.
        Ties to other methods:
            Registered via register_signal_handlers.
        Why this exists:
            Signal handlers need a small boundary function that updates the shared token.
        """
        token.cancel("Shutdown requested.", location)

    register_signal_handlers(token, logger, _shutdown, location)

    metrics_sink.increment("chapter_splitter.app.start_total", tags={"entrypoint": "app"})
    with metrics_sink.timer(
        "chapter_splitter.app.runtime_seconds",
        tags={"entrypoint": "app"},
    ):
        log_event(
            logger,
            logging.INFO,
            "app_started",
            f"{resolved_settings.app.title} started",
            {"title": resolved_settings.app.title},
        )
        try:
            workflow(resolved_settings, token)
            return 0
        except Exception as exc:
            payload = map_error(exc, channel="app", location=location)
            metrics_sink.increment(
                "chapter_splitter.app.error_total",
                tags={
                    "error_code": payload.code.value,
                    "event": payload.event,
                },
            )
            if payload.event == "app_unhandled_exception":
                logger.exception(
                    "Unhandled exception",
                    extra=payload.log_fields(location=location) | {"event": payload.event},
                )
                return payload.exit_code
            log_event(
                logger,
                payload.log_level,
                payload.event,
                payload.message,
                payload.log_fields(location=location),
            )
            return payload.exit_code
        finally:
            metrics_sink.increment("chapter_splitter.app.stop_total", tags={"entrypoint": "app"})
            log_event(
                logger,
                logging.INFO,
                "app_stopped",
                f"{resolved_settings.app.title} stopped",
                {"title": resolved_settings.app.title},
            )
