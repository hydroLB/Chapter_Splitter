"""Command line entry point for chapter splitting workflows."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .app import main as gui_main
from .config import load_config
from .config.schema import IOConfig, Settings
from .config.schema.sections.io import OutputCollisionPolicy
from .core.errors import CancellationError, ChapterSplitterError, format_error_message
from .core.models import ChapterDefinition
from .core.runtime import CancellationToken, register_signal_handlers
from .io.chapters import load_chapter_file, write_chapter_file
from .observability.logging import (
    configure_logging,
    log_event,
    new_correlation_id,
    set_correlation_id,
)
from .pdf.detection.detector import DetectionRequest, detect_chapters
from .pdf.detection.report import ChapterDetectionStrategy
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
    split_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the output directory for chapter PDFs.",
    )
    split_parser.add_argument(
        "--collision-policy",
        choices=("error", "overwrite", "suffix"),
        default=None,
        help="Override io.output_collision_policy for this run.",
    )
    split_parser.add_argument(
        "--page-offset",
        type=int,
        default=None,
        help="Override io.page_offset for this run (non-negative).",
    )
    split_parser.set_defaults(command="split")

    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect chapters from a PDF and write a chapters TOML file.",
    )
    detect_parser.add_argument("--pdf", type=Path, required=True, help="Path to the PDF file.")
    detect_parser.add_argument(
        "--strategy",
        choices=("auto", "outlines", "toc"),
        default="auto",
        help="Detection strategy: auto, outlines, or toc.",
    )
    detect_parser.add_argument(
        "--toc-hint-page",
        type=int,
        default=None,
        help=(
            "1-based page number where the Table of Contents starts "
            "(required for --strategy toc)."
        ),
    )
    detect_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the generated chapters TOML file (default: <pdf>.chapters.toml).",
    )
    detect_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file when it already exists.",
    )
    detect_parser.set_defaults(command="detect")
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
        out: Path | None,
        strategy: str | None,
        toc_hint_page: int | None,
        overwrite: bool,
        output_dir: Path | None,
        collision_policy: str | None,
        page_offset: int | None,
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
            - out: Optional output path for detect command.
            - strategy: Optional detect strategy for detect command.
            - toc_hint_page: Optional TOC hint page for detect command.
            - overwrite: Whether detect output should overwrite an existing file.
            - output_dir: Optional output directory for split command.
            - collision_policy: Optional collision policy override for split command.
            - page_offset: Optional page offset override for split command.
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
        self.out = out
        self.strategy = strategy
        self.toc_hint_page = toc_hint_page
        self.overwrite = overwrite
        self.output_dir = output_dir
        self.collision_policy = collision_policy
        self.page_offset = page_offset


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
    out = _optional_path(namespace.out if hasattr(namespace, "out") else None, "out", location)
    strategy = _optional_str(
        namespace.strategy if hasattr(namespace, "strategy") else None,
        "strategy",
        location,
    )
    toc_hint_page = _optional_int(
        namespace.toc_hint_page if hasattr(namespace, "toc_hint_page") else None,
        "toc_hint_page",
        location,
    )
    overwrite = bool(getattr(namespace, "overwrite", False))
    output_dir = _optional_path(
        namespace.output_dir if hasattr(namespace, "output_dir") else None,
        "output_dir",
        location,
    )
    collision_policy = _optional_str(
        namespace.collision_policy if hasattr(namespace, "collision_policy") else None,
        "collision_policy",
        location,
    )
    page_offset = _optional_int(
        namespace.page_offset if hasattr(namespace, "page_offset") else None,
        "page_offset",
        location,
    )
    return ParsedArgs(
        command=command,
        config=config,
        pdf=pdf,
        chapters=chapters,
        out=out,
        strategy=strategy,
        toc_hint_page=toc_hint_page,
        overwrite=overwrite,
        output_dir=output_dir,
        collision_policy=collision_policy,
        page_offset=page_offset,
    )


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


def _optional_str(value: object, name: str, location: str) -> str | None:
    """Validate and return an optional string value.

    Purpose:
        Normalize optional CLI string arguments and keep typing strict.
    Ties To:
        Used by _parse_args for detect strategy parsing.
    Inputs:
        - value: Parsed value to validate.
        - name: Name of the argument.
        - location: Fully qualified module and method name.
    Outputs:
        - String value or None.
    Side Effects:
        None.
    Raises:
        - ChapterSplitterError: When the value is not a string.
    """
    error_location = f"{__name__}._optional_str"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be a string.{context}")
    )


def _optional_int(value: object, name: str, location: str) -> int | None:
    """Validate and return an optional integer value.

    Purpose:
        Normalize optional CLI integer arguments and keep typing strict.
    Ties To:
        Used by _parse_args for detect TOC hint parsing.
    Inputs:
        - value: Parsed value to validate.
        - name: Name of the argument.
        - location: Fully qualified module and method name.
    Outputs:
        - Integer value or None.
    Side Effects:
        None.
    Raises:
        - ChapterSplitterError: When the value is not an integer.
    """
    error_location = f"{__name__}._optional_int"
    context = f" Context: {location}." if location else ""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ChapterSplitterError(
        format_error_message(error_location, f"Argument '{name}' must be an integer.{context}")
    )


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
    output_dir: Path | None,
    collision_policy: str | None,
    page_offset: int | None,
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
        - output_dir: Optional output directory override for chapter PDFs.
        - collision_policy: Optional collision policy override for this run.
        - page_offset: Optional page offset override for this run.
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

    error_location = f"{__name__}._run_split"
    context = f" Context: {location}." if location else ""
    effective_page_offset = page_offset
    if effective_page_offset is not None and effective_page_offset < 0:
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"--page-offset must be non-negative (got {effective_page_offset}).{context}",
            )
        )
    effective_io = settings.io
    if collision_policy is not None:
        policy = cast(OutputCollisionPolicy, collision_policy)
        effective_io = IOConfig(
            open_viewer=settings.io.open_viewer,
            viewer_timeout_seconds=settings.io.viewer_timeout_seconds,
            pdf_read_timeout_seconds=settings.io.pdf_read_timeout_seconds,
            pdf_write_timeout_seconds=settings.io.pdf_write_timeout_seconds,
            operation_timeout_seconds=settings.io.operation_timeout_seconds,
            output_dir_suffix=settings.io.output_dir_suffix,
            output_collision_policy=policy,
            output_collision_max_suffix=settings.io.output_collision_max_suffix,
            fsync_writes=settings.io.fsync_writes,
            page_offset=settings.io.page_offset,
            infer_page_offset_from_labels=settings.io.infer_page_offset_from_labels,
            infer_page_offset_min_sequential_numeric_labels=(
                settings.io.infer_page_offset_min_sequential_numeric_labels
            ),
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
        page_offset=effective_page_offset,
        deadline=split_deadline,
        token=token,
        retry_config=settings.retry,
        validation_config=settings.validation,
        io_config=effective_io,
        location=location,
        output_dir=output_dir,
    )
    output_dir_str = str(outputs[0].output_path.parent) if outputs else str(pdf_path.parent)
    log_event(
        logger,
        logging.INFO,
        "split_complete",
        "Chapter export complete.",
        {"output_count": len(outputs), "output_dir": output_dir_str},
    )
    return 0


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
    """Execute the detect command workflow.

    Purpose:
        Detect chapter ranges from a PDF and write a chapter definition TOML file.
    Ties To:
        Called by main when the detect command is selected.
    Inputs:
        - pdf_path: Path to the source PDF.
        - out_path: Optional output TOML path.
        - strategy: Detection strategy selection (auto, outlines, toc).
        - toc_hint_page: Optional TOC hint start page (required for toc strategy).
        - overwrite: Whether to overwrite output when it exists.
        - settings: Loaded Settings instance.
        - token: Cancellation token for signal handling.
        - location: Fully qualified module and method name.
    Outputs:
        - Exit code integer for the command.
    Side Effects:
        Reads the PDF and writes a chapters TOML file to disk.
    Raises:
        - ChapterSplitterError: When detection fails or arguments are invalid.
    """
    error_location = f"{__name__}._run_detect"
    context = f" Context: {location}." if location else ""
    if token.is_cancelled():
        raise CancellationError(
            format_error_message(error_location, f"Detect cancelled before start.{context}")
        )
    if strategy is None:
        raise ChapterSplitterError(
            format_error_message(error_location, f"Detect requires a strategy.{context}")
        )
    if strategy not in ("auto", "outlines", "toc"):
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"Unsupported detect strategy: {strategy}.{context}",
            )
        )
    if strategy == "toc" and toc_hint_page is None:
        raise ChapterSplitterError(
            format_error_message(
                error_location,
                f"--toc-hint-page is required when --strategy toc.{context}",
            )
        )

    effective_out = out_path or pdf_path.with_suffix(".chapters.toml")
    deadline = Deadline(settings.io.operation_timeout_seconds)
    force_strategy: ChapterDetectionStrategy | None = None
    if strategy != "auto":
        force_strategy = cast(ChapterDetectionStrategy, strategy)
    request = DetectionRequest(
        toc_hint_page=toc_hint_page,
        force_strategy=force_strategy,
    )
    report = detect_chapters(
        pdf_path=pdf_path,
        deadline=deadline,
        token=token,
        retry_config=settings.retry,
        io_config=settings.io,
        detection_config=settings.detection,
        request=request,
        location=location,
    )
    write_chapter_file(
        effective_out,
        report.chapters,
        report=report,
        overwrite=overwrite,
        deadline=deadline,
        token=token,
        location=location,
    )
    log_event(
        logger,
        logging.INFO,
        "detect_complete",
        "Chapter detection complete.",
        {
            "strategy": report.strategy,
            "confidence": report.confidence,
            "chapter_count": len(report.chapters),
            "output_path": str(effective_out),
            "warnings": list(report.warnings),
        },
    )
    return 0
