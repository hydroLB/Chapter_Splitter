"""Input validation configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class ValidationConfig:
    """Input validation settings.

    Summary:
        Define validation rules for chapter definitions and inputs.
    Ties to other methods:
        Used by chapter validation utilities and split workflows.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        - None.
    """

    def __init__(
        self,
        max_chapters: int,
        require_unique_titles: bool,
        sort_chapters_by_start_page: bool,
        reject_overlapping_ranges: bool,
    ) -> None:
        """Initialize validation configuration.

        Summary:
            Define limits and invariants for chapter inputs.
        Ties to other methods:
            Used by validation helpers for chapters and UI grid extraction.
        Inputs:
            - max_chapters: Maximum number of chapters per export.
            - require_unique_titles: Enforce unique chapter titles.
            - sort_chapters_by_start_page: Whether to sort chapters by start page before exporting.
            - reject_overlapping_ranges: Whether chapter ranges must not overlap.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - None.
        """
        self.max_chapters = max_chapters
        self.require_unique_titles = require_unique_titles
        self.sort_chapters_by_start_page = sort_chapters_by_start_page
        self.reject_overlapping_ranges = reject_overlapping_ranges

    def validate(self, location: str) -> None:
        """Validate validation configuration.

        Summary:
            Ensure validation limits are reasonable.
        Ties to other methods:
            Called by Settings.validate before validation is used.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            - ConfigurationError: When validation settings are invalid.
        """
        error_location = f"{__name__}.ValidationConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.max_chapters < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"validation.max_chapters must be at least 1.{context}"
                )
            )
