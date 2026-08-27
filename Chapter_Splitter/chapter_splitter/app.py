"""GUI entry point for the Chapter Splitter application."""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

from .config.loader import load_settings
from .config.schema import Settings
from .core.error_mapping import map_error
from .core.errors import UiError, format_error_message
from .core.runtime import CancellationToken, register_signal_handlers
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger(__name__)

GuiWorkflow = Callable[[Settings, CancellationToken], None]


def _load_gui_workflow() -> GuiWorkflow:
    """Load the optional Qt workflow and return an actionable dependency error."""
    try:
        module = import_module("chapter_splitter.ui.qt.workflow")
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing == "PySide6" or missing.startswith("PySide6."):
            raise UiError(
                format_error_message(
                    "chapter_splitter.app._load_gui_workflow",
                    "Qt desktop dependencies are not installed. "
                    "Install them with: pip install -e '.[desktop]'",
                )
            ) from exc
        raise
    return cast(GuiWorkflow, module.workflow)


def main(
    config_path: Path | None = None,
    settings: Settings | None = None,
) -> int:
    """Run the GUI application workflow."""
    location = "chapter_splitter.app.main"
    logging_configured = False
    app_started = False
    try:
        resolved_settings = settings or load_settings(config_path, location)
        configure_logging(resolved_settings.app, resolved_settings.logging)
        logging_configured = True
        correlation_id = new_correlation_id(
            resolved_settings.app.correlation_id_prefix,
            location,
        )
        set_correlation_id(correlation_id, location)

        token = CancellationToken()

        def _shutdown() -> None:
            token.cancel("Shutdown requested.", location)

        register_signal_handlers(token, logger, _shutdown, location)
        workflow = _load_gui_workflow()
        log_event(
            logger,
            logging.INFO,
            "app_started",
            f"{resolved_settings.app.title} started",
            {"title": resolved_settings.app.title},
        )
        app_started = True
        workflow(resolved_settings, token)
        return 0
    except Exception as exc:
        payload = map_error(exc, channel="app", location=location)
        if payload.event == "app_unhandled_exception":
            logger.exception(
                "Unhandled exception",
                extra=payload.log_fields(location=location) | {"event": payload.event},
            )
            return payload.exit_code
        if logging_configured:
            log_event(
                logger,
                payload.log_level,
                payload.event,
                payload.message,
                payload.log_fields(location=location),
            )
        else:
            logger.error(payload.user_message)
        return payload.exit_code
    finally:
        if app_started:
            log_event(
                logger,
                logging.INFO,
                "app_stopped",
                f"{resolved_settings.app.title} stopped",
                {"title": resolved_settings.app.title},
            )
