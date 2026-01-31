"""Input validation configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class ValidationConfig:
    """Input validation settings.

    Purpose:
        Define validation rules for chapter definitions and inputs.
    Ties To:
        Used by chapter validation utilities and split workflows.
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
        max_chapters: int,
        require_unique_titles: bool,
    ) -> None:
        """Initialize validation configuration.

        Purpose:
            Define limits and invariants for chapter inputs.
        Ties To:
            Used by validation helpers for chapters and UI grid extraction.
        Inputs:
            - max_chapters: Maximum number of chapters per export.
            - require_unique_titles: Enforce unique chapter titles.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.max_chapters = max_chapters
        self.require_unique_titles = require_unique_titles

    def validate(self, location: str) -> None:
        """Validate validation configuration.

        Purpose:
            Ensure validation limits are reasonable.
        Ties To:
            Called by Settings.validate before validation is used.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
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
