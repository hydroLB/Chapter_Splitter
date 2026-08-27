"""Input validation configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class ValidationConfig:
    """Input validation settings."""

    def __init__(
        self,
        max_chapters: int,
        require_unique_titles: bool,
        sort_chapters_by_start_page: bool,
        reject_overlapping_ranges: bool,
    ) -> None:
        """Initialize validation configuration."""
        self.max_chapters = max_chapters
        self.require_unique_titles = require_unique_titles
        self.sort_chapters_by_start_page = sort_chapters_by_start_page
        self.reject_overlapping_ranges = reject_overlapping_ranges

    def validate(self, location: str) -> None:
        """Validate validation configuration."""
        error_location = f"{__name__}.ValidationConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.max_chapters < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"validation.max_chapters must be at least 1.{context}"
                )
            )
