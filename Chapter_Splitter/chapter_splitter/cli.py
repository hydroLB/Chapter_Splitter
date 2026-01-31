"""Command line entry point for chapter splitting workflows."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .app import main as gui_main
from .config import load_config
from .config.schema import Settings
from .core.errors import CancellationError, ChapterSplitterError, format_error_message
from .core.models import ChapterDefinition
from .core.runtime import CancellationToken, register_signal_handlers
from .io.chapters import load_chapter_file
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)
from .pdf.splitting.splitter import split_pdf_into_chapters
from .utils.timing import Deadline

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Purpose:
        Provide a CLI for splitting PDFs and launching the GUI.
    Ties To:
        Used by the chapter-splitter console script and python -m entry point.
    Inputs:
        - argv: Optional sequence of CLI arguments for testing.
    Outputs:
        - Exit code integer for the process.
    Side Effects:
        Parses CLI arguments and triggers application workflows.
    Raises:
        - None.
    """
    args = _parse_args(argv, "chapter_splitter.cli.main")

    location = "chapter_splitter.cli.main"
    settings = load_config(args.config, location)
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

    error_location = f"{__name__}.main"
    try:
        if args.command == "gui":
            return gui_main(args.config)
        if args.command == "split":
            if args.pdf is None or args.chapters is None:
                raise ChapterSplitterError(
                    format_error_message(
                        error_location,
                        "Split command requires --pdf and --chapters.",
                    )
                )
            return _run_split(args.pdf, args.chapters, settings, token, location)
        raise ChapterSplitterError(
            format_error_message(error_location, f"Unknown command: {args.command}")
        )
    except CancellationError as exc:
        log_event(
            logger,
            logging.WARNING,
            "cli_cancelled",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
        return 130
    except ChapterSplitterError as exc:
        log_event(
            logger,
            logging.ERROR,
            "cli_error",
            format_error_message(location, str(exc)),
            {"reason": str(exc)},
        )
        return 1
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "Unhandled exception",
            extra={"event": "cli_unhandled_exception", "reason": str(exc)},
        )
        return 1


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Purpose:
        Define command line arguments and subcommands.
    Ties To:
        Used by main to parse CLI arguments.
    Inputs:
        - None.
    Outputs:
        - Configured ArgumentParser instance.
    Side Effects:
        None.
    Raises:
        - None.
    """
    parser = argparse.ArgumentParser(
        prog="chapter-splitter",
        description="Split a PDF into chapters using a config driven workflow.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to an override configuration TOML file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gui_parser = subparsers.add_parser("gui", help="Launch the GUI workflow.")
    gui_parser.set_defaults(command="gui")

    split_parser = subparsers.add_parser("split", help="Split a PDF with a chapter file.")
    split_parser.add_argument("--pdf", type=Path, required=True, help="Path to the PDF file.")
    split_parser.add_argument(
        "--chapters",
        type=Path,
        required=True,
        help="Path to a TOML file containing chapter ranges.",
    )
    split_parser.set_defaults(command="split")
    return parser


class ParsedArgs:
    """Strongly typed CLI arguments container.

    Purpose:
        Store parsed CLI inputs in a typed structure.
    Ties To:
        Produced by _parse_args and consumed by main.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """

    def __init__(
        self,
        command: str,
        config: Path | None,
        pdf: Path | None,
        chapters: Path | None,
    ) -> None:
        """Initialize parsed CLI arguments.

        Purpose:
            Provide typed access to CLI arguments without relying on Any.
        Ties To:
            Used by _parse_args and main.
        Inputs:
            - command: Parsed subcommand.
            - config: Optional config path.
            - pdf: Optional PDF path for split command.
            - chapters: Optional chapters file path for split command.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.command = command
        self.config = config
        self.pdf = pdf
        self.chapters = chapters


def _parse_args(argv: Sequence[str] | None, location: str) -> ParsedArgs:
    """Parse CLI arguments into a typed container.

    Purpose:
        Normalize argparse output into a typed object for strict typing.
    Ties To:
        Used by main to parse CLI arguments.
    Inputs:
        - argv: Optional sequence of CLI arguments.
        - location: Fully qualified module and method name.
    Outputs:
        - ParsedArgs instance.
    Side Effects:
        Parses CLI arguments using argparse.
    Raises:
        - ChapterSplitterError: When required arguments are missing or invalid.
    """
    parser = _build_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)
    command = _require_str(namespace.command, "command", location)
    config = _optional_path(namespace.config, "config", location)
    pdf = _optional_path(namespace.pdf if hasattr(namespace, "pdf") else None, "pdf", location)
    chapters = _optional_path(
        namespace.chapters if hasattr(namespace, "chapters") else None,
        "chapters",
        location,
    )
    return ParsedArgs(command=command, config=config, pdf=pdf, chapters=chapters)


def _require_str(value: object, name: str, location: str) -> str:
    """Validate and return a required string value.

    Purpose:
        Ensure required CLI arguments are present and strings.
    Ties To:
        Used by _parse_args to validate parsed values.
    Inputs:
        - value: Parsed value to validate.
        - name: Name of the argument.
        - location: Fully qualified module and method name.
    Outputs:
        - Validated string value.
    Side Effects:
        None.
    Raises:
        - ChapterSplitterError: When the value is missing or not a string.
    """
    error_location = f"{__name__}._require_str"
    context = f" Context: {location}." if location else ""
    if not isinstance(value, str) or not value.strip():
        raise ChapterSplitterError(
            format_error_message(
                error_location, f"Argument '{name}' must be a non empty string.{context}"
            )
        )
    return value


def _optional_path(value: object, name: str, location: str) -> Path | None:
    """Validate and return an optional path value.

    Purpose:
        Normalize optional CLI path arguments to Path objects.
    Ties To:
        Used by _parse_args to validate parsed path values.
    Inputs:
        - value: Parsed value to validate.
        - name: Name of the argument.
        - location: Fully qualified module and method name.
    Outputs:
        - Path instance or None.
    Side Effects:
        None.
    Raises:
        - ChapterSplitterError: When the value is not a path or string.
    """
    error_location = f"{__name__}._optional_path"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be a path.{context}")
    )


def _run_split(
    pdf_path: Path,
    chapters_path: Path,
    settings: Settings,
    token: CancellationToken,
    location: str,
) -> int:
    """Execute the split command workflow.

    Purpose:
        Perform a CLI based chapter split using the config driven pipeline.
    Ties To:
        Called by main when the split command is selected.
    Inputs:
        - pdf_path: Path to the source PDF.
        - chapters_path: Path to the chapters TOML file.
        - settings: Loaded Settings instance.
        - token: Cancellation token for signal handling.
        - location: Fully qualified module and method name.
    Outputs:
        - Exit code integer for the command.
    Side Effects:
        Writes chapter PDFs to disk.
    Raises:
        - ChapterSplitterError: When splitting fails.
    """
    if token.is_cancelled():
        error_location = f"{__name__}._run_split"
        context = f" Context: {location}." if location else ""
        raise CancellationError(
            format_error_message(error_location, f"Split cancelled before start.{context}")
        )

    chapter_deadline = Deadline(settings.io.operation_timeout_seconds)
    chapter_defs: list[ChapterDefinition] = load_chapter_file(
        chapters_path,
        chapter_deadline,
        token,
        location,
    )
    split_deadline = Deadline(settings.io.operation_timeout_seconds)
    outputs = split_pdf_into_chapters(
        pdf_path=pdf_path,
        chapters=chapter_defs,
        page_offset=settings.io.page_offset,
        deadline=split_deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=settings.io,
        location=location,
    )
    output_dir = str(outputs[0].output_path.parent) if outputs else str(pdf_path.parent)
    log_event(
        logger,
        logging.INFO,
        "split_complete",
        "Chapter export complete.",
        {"output_count": len(outputs), "output_dir": output_dir},
    )
    return 0
