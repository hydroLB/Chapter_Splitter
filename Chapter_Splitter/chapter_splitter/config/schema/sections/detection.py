"""Detection configuration for chapter inference heuristics."""

from __future__ import annotations

import re
from collections.abc import Sequence

from ....core.errors import ConfigurationError, format_error_message


class DetectionConfig:
    """Detection configuration for chapter inference.

    Purpose:
        Centralize knobs for fallback chapter detection when outline metadata is unavailable.
    Ties To:
        Used by TOC-based detection in chapter_splitter.pdf.detection.toc.
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
        enable_toc_fallback: bool,
        toc_scan_max_pages: int,
        toc_entry_regexes: Sequence[str],
        toc_ignore_title_regexes: Sequence[str],
        toc_min_entries: int,
        toc_max_entries: int,
    ) -> None:
        """Initialize detection configuration.

        Purpose:
            Provide validated knobs for TOC fallback parsing.
        Ties To:
            Loaded via the config loader and validated in Settings.validate.
        Inputs:
            - enable_toc_fallback: Whether TOC parsing fallback is enabled.
            - toc_scan_max_pages: Maximum number of pages to scan for TOC entries.
            - toc_entry_regexes: Regex patterns that must expose groups named 'title' and 'page'.
            - toc_ignore_title_regexes: Regex patterns for titles to ignore during parsing.
            - toc_min_entries: Minimum number of entries required to accept a parsed TOC.
            - toc_max_entries: Maximum number of entries to keep from a parsed TOC.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.enable_toc_fallback = enable_toc_fallback
        self.toc_scan_max_pages = toc_scan_max_pages
        self.toc_entry_regexes = tuple(toc_entry_regexes)
        self.toc_ignore_title_regexes = tuple(toc_ignore_title_regexes)
        self.toc_min_entries = toc_min_entries
        self.toc_max_entries = toc_max_entries

    def validate(self, location: str) -> None:
        """Validate detection configuration.

        Purpose:
            Ensure regex patterns compile and numeric limits are consistent.
        Ties To:
            Called by Settings.validate before detection logic uses the configuration.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            Compiles regex patterns to validate.
        Raises:
            - ConfigurationError: When configuration values are invalid.
        """
        error_location = f"{__name__}.DetectionConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.toc_scan_max_pages < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"detection.toc_scan_max_pages must be at least 1.{context}",
                )
            )
        if not self.toc_entry_regexes:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"detection.toc_entry_regexes must not be empty.{context}",
                )
            )
        if self.toc_min_entries < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"detection.toc_min_entries must be at least 1.{context}",
                )
            )
        if self.toc_max_entries < self.toc_min_entries:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "detection.toc_max_entries must be >= detection.toc_min_entries." f"{context}",
                )
            )
        for pattern in self.toc_entry_regexes:
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"Invalid detection.toc_entry_regexes pattern: {pattern}.{context}",
                    )
                ) from exc
            group_names = set(compiled.groupindex.keys())
            if "title" not in group_names or "page" not in group_names:
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        "detection.toc_entry_regexes patterns must define groups named 'title' "
                        "and 'page'."
                        f"{context}",
                    )
                )
        for pattern in self.toc_ignore_title_regexes:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ConfigurationError(
                    format_error_message(
                        error_location,
                        f"Invalid detection.toc_ignore_title_regexes pattern: {pattern}.{context}",
                    )
                ) from exc
