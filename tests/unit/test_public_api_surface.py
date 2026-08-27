"""Tests for stable public import surface and deep-import guardrails."""

from __future__ import annotations

import ast
from pathlib import Path

import chapter_splitter
import chapter_splitter.config
import chapter_splitter.config.schema
import chapter_splitter.core
import chapter_splitter.io
import chapter_splitter.observability
import chapter_splitter.pdf
import chapter_splitter.pdf.io
import chapter_splitter.pdf.splitting
import chapter_splitter.utils


def test_public_api_all_contracts_are_explicit() -> None:
    """Verify key packages publish explicit, stable exports via __all__."""
    expected: dict[str, set[str]] = {
        "chapter_splitter": {
            "__version__",
            "CancellationError",
            "CancellationToken",
            "ChapterDefinition",
            "ChapterDetectionReport",
            "ChapterExportProgress",
            "ChapterFileSessionMetadata",
            "ChapterOutput",
            "ChapterSplitterError",
            "ConfigurationError",
            "DetectionRequest",
            "IoError",
            "PdfProcessingError",
            "Settings",
            "ValidationError",
            "detect_chapters",
            "detect_chapters_from_outlines",
            "load_chapter_file",
            "load_settings",
            "split_pdf_into_chapters",
            "write_chapter_file",
        },
        "chapter_splitter.core": {
            "CancellationError",
            "CancellationToken",
            "ChapterDefinition",
            "ChapterOutput",
            "ChapterSplitterError",
            "ConfigurationError",
            "ErrorCode",
            "ErrorPayload",
            "IoError",
            "PageRange",
            "PdfProcessingError",
            "UiError",
            "ValidationError",
            "format_error_message",
            "map_error",
            "register_signal_handlers",
            "validate_chapters",
            "validate_page_range",
        },
        "chapter_splitter.config": {
            "Settings",
            "load_settings",
        },
        "chapter_splitter.config.schema": {
            "AppConfig",
            "DetectionConfig",
            "IOConfig",
            "LoggingConfig",
            "OutputCollisionPolicy",
            "PerformanceConfig",
            "RetryConfig",
            "Settings",
            "UIConfig",
            "ValidationConfig",
        },
        "chapter_splitter.io": {
            "ChapterFileSessionMetadata",
            "load_chapter_file",
            "load_chapter_file_with_metadata",
            "write_chapter_file",
        },
        "chapter_splitter.observability": {
            "CorrelationIdFilter",
            "RedactionPolicy",
            "StructuredFormatter",
            "configure_logging",
            "get_correlation_id",
            "log_event",
            "new_correlation_id",
            "set_correlation_id",
        },
        "chapter_splitter.pdf": {
            "ChapterDetectionReport",
            "ChapterExportProgress",
            "DetectionRequest",
            "PdfReader",
            "PdfWriter",
            "detect_chapters",
            "detect_chapters_in_reader",
            "detect_chapters_from_outlines",
            "detect_chapters_from_toc_page",
            "extract_page_labels",
            "format_detection_report",
            "get_total_pages",
            "infer_page_offset_from_labels",
            "load_reader",
            "split_pdf_into_chapters",
        },
        "chapter_splitter.pdf.io": {
            "PdfReader",
            "PdfWriter",
            "extract_page_labels",
            "get_total_pages",
            "infer_page_offset_from_labels",
            "load_reader",
        },
        "chapter_splitter.pdf.splitting": {
            "ChapterExportProgress",
            "split_pdf_into_chapters",
        },
        "chapter_splitter.utils": {
            "Deadline",
            "RateLimiter",
            "open_path_in_default_viewer",
            "retry_with_backoff",
            "safe_filename",
        },
    }
    modules = {
        "chapter_splitter": chapter_splitter,
        "chapter_splitter.core": chapter_splitter.core,
        "chapter_splitter.config": chapter_splitter.config,
        "chapter_splitter.config.schema": chapter_splitter.config.schema,
        "chapter_splitter.io": chapter_splitter.io,
        "chapter_splitter.observability": chapter_splitter.observability,
        "chapter_splitter.pdf": chapter_splitter.pdf,
        "chapter_splitter.pdf.io": chapter_splitter.pdf.io,
        "chapter_splitter.pdf.splitting": chapter_splitter.pdf.splitting,
        "chapter_splitter.utils": chapter_splitter.utils,
    }
    for module_name, module in modules.items():
        assert hasattr(module, "__all__"), f"{module_name} is missing __all__"
        exported = set(module.__all__)
        assert exported == expected[module_name], f"{module_name} __all__ mismatch"
        for symbol in exported:
            assert hasattr(module, symbol), f"{module_name} missing exported symbol {symbol}"


def test_external_tests_and_scripts_avoid_deep_import_coupling() -> None:
    """Keep integration consumers and scripts on public modules.

    Unit tests may intentionally exercise a private implementation seam. Integration, end-to-end,
    performance, and repository scripts should instead prove the supported package surface.
    """
    repo_root = Path(__file__).resolve().parents[2]
    allowed_modules = {
        "chapter_splitter",
        "chapter_splitter.app",
        "chapter_splitter.cli",
        "chapter_splitter.config",
        "chapter_splitter.config.loader",
        "chapter_splitter.config.schema",
        "chapter_splitter.core",
        "chapter_splitter.io",
        "chapter_splitter.observability",
        "chapter_splitter.pdf",
        "chapter_splitter.pdf.detection",
        "chapter_splitter.pdf.io",
        "chapter_splitter.pdf.splitting",
        "chapter_splitter.ui",
        "chapter_splitter.utils",
    }
    disallowed_imports: list[str] = []
    consumer_roots = (
        repo_root / "tests" / "e2e",
        repo_root / "tests" / "integration",
        repo_root / "tests" / "performance",
        repo_root / "scripts",
    )
    for consumer_root in consumer_roots:
        for path in sorted(consumer_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if (
                            alias.name.startswith("chapter_splitter")
                            and alias.name not in allowed_modules
                        ):
                            disallowed_imports.append(
                                f"{path.relative_to(repo_root)}:{node.lineno} -> {alias.name}"
                            )
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("chapter_splitter")
                    and node.module not in allowed_modules
                ):
                    disallowed_imports.append(
                        f"{path.relative_to(repo_root)}:{node.lineno} -> {node.module}"
                    )
    assert not disallowed_imports, "Deep imports detected:\n" + "\n".join(disallowed_imports)
