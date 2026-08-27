"""Command line entry point for chapter splitting workflows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from .cli_commands import (
    ParsedArgs,
    parse_args,
)
from .cli_commands.detect import run_detect
from .cli_commands.split import run_split
from .config.loader import load_settings
from .config.schema import Settings
from .core.error_mapping import map_error
from .core.errors import ChapterSplitterError, format_error_message
from .core.runtime import CancellationToken, register_signal_handlers
from .io.chapters import load_chapter_file, write_chapter_file
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)
from .pdf.detection.detector import detect_chapters
from .pdf.splitting.splitter import split_pdf_into_chapters

logger = logging.getLogger(__name__)


def gui_main(
    config_path: Path | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Launch the GUI entrypoint lazily."""
    from .app import main as app_main

    return app_main(config_path=config_path, settings=settings)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface."""
    args = _parse_args(argv, "chapter_splitter.cli.main")
    location = "chapter_splitter.cli.main"
    command = args.command
    error_location = f"{__name__}.main"
    try:
        settings = load_settings(args.config, location)
        if command == "gui":
            return gui_main(config_path=args.config, settings=settings)

        configure_logging(settings.app, settings.logging)
        correlation_id = new_correlation_id(settings.app.correlation_id_prefix, location)
        set_correlation_id(correlation_id, location)

        token = CancellationToken()

        def _shutdown() -> None:
            token.cancel("Shutdown requested.", location)

        register_signal_handlers(token, logger, _shutdown, location)

        if args.command == "split":
            if args.pdf is None or args.chapters is None:
                raise ChapterSplitterError(
                    format_error_message(
                        error_location,
                        "Split command requires --pdf and --chapters.",
                    )
                )
            return _run_split(
                pdf_path=args.pdf,
                chapters_path=args.chapters,
                output_dir=args.output_dir,
                collision_policy=args.collision_policy,
                page_offset=args.page_offset,
                settings=settings,
                token=token,
                location=location,
            )
        if args.command == "detect":
            if args.pdf is None:
                raise ChapterSplitterError(
                    format_error_message(
                        error_location,
                        "Detect command requires --pdf.",
                    )
                )
            return _run_detect(
                pdf_path=args.pdf,
                out_path=args.out,
                strategy=args.strategy,
                toc_hint_page=args.toc_hint_page,
                overwrite=args.overwrite,
                settings=settings,
                token=token,
                location=location,
            )
        raise ChapterSplitterError(
            format_error_message(error_location, f"Unknown command: {args.command}")
        )
    except Exception as exc:
        payload = map_error(exc, channel="cli", location=location)
        if payload.event == "cli_unhandled_exception":
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


def _parse_args(argv: Sequence[str] | None, location: str) -> ParsedArgs:
    return parse_args(list(argv) if argv is not None else None, location)


def _run_split(
    pdf_path: Path,
    chapters_path: Path,
    output_dir: Path | None,
    collision_policy: str | None,
    page_offset: int | None,
    settings: Settings,
    token: CancellationToken,
    location: str,
) -> int:
    return run_split(
        pdf_path=pdf_path,
        chapters_path=chapters_path,
        output_dir=output_dir,
        collision_policy=collision_policy,
        page_offset=page_offset,
        settings=settings,
        token=token,
        location=location,
        logger=logger,
        load_chapter_file_fn=load_chapter_file,
        split_pdf_into_chapters_fn=split_pdf_into_chapters,
        log_event_fn=log_event,
    )


def _run_detect(
    pdf_path: Path,
    out_path: Path | None,
    strategy: str | None,
    toc_hint_page: int | None,
    overwrite: bool,
    settings: Settings,
    token: CancellationToken,
    location: str,
) -> int:
    return run_detect(
        pdf_path=pdf_path,
        out_path=out_path,
        strategy=strategy,
        toc_hint_page=toc_hint_page,
        overwrite=overwrite,
        settings=settings,
        token=token,
        location=location,
        logger=logger,
        detect_chapters_fn=detect_chapters,
        write_chapter_file_fn=write_chapter_file,
        log_event_fn=log_event,
    )
