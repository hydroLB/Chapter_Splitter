"""File and process IO configuration schema."""

from __future__ import annotations

from ....core.errors import ConfigurationError, format_error_message


class IOConfig:
    """File and process IO configuration.

    Purpose:
        Configure IO timeouts, output behavior, and page offsets.
    Ties To:
        Used by PDF loading, writing, and viewer launching.
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
        open_viewer: bool,
        viewer_timeout_seconds: float,
        pdf_read_timeout_seconds: float,
        pdf_write_timeout_seconds: float,
        operation_timeout_seconds: float,
        output_dir_suffix: str,
        output_overwrite: bool,
        page_offset: int,
    ) -> None:
        """Initialize IO configuration.

        Purpose:
            Define IO behavior including timeouts and output paths.
        Ties To:
            Used by PDF loading, writing, and viewer launch.
        Inputs:
            - open_viewer: Whether to open PDFs in the system viewer.
            - viewer_timeout_seconds: Timeout for viewer launch.
            - pdf_read_timeout_seconds: Timeout for PDF read.
            - pdf_write_timeout_seconds: Timeout for PDF write.
            - operation_timeout_seconds: Timeout for long running operations.
            - output_dir_suffix: Suffix appended to output directory.
            - output_overwrite: Whether to overwrite existing output files.
            - page_offset: Default page offset for splits.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - None.
        """
        self.open_viewer = open_viewer
        self.viewer_timeout_seconds = viewer_timeout_seconds
        self.pdf_read_timeout_seconds = pdf_read_timeout_seconds
        self.pdf_write_timeout_seconds = pdf_write_timeout_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self.output_dir_suffix = output_dir_suffix
        self.output_overwrite = output_overwrite
        self.page_offset = page_offset

    def validate(self, location: str) -> None:
        """Validate IO configuration.

        Purpose:
            Ensure IO timeouts and output suffixes are valid.
        Ties To:
            Called by Settings.validate before IO is used.
        Inputs:
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side Effects:
            None.
        Raises:
            - ConfigurationError: When IO settings are invalid.
        """
        error_location = f"{__name__}.IOConfig.validate"
        context = f" Context: {location}." if location else ""
        if self.viewer_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.viewer_timeout_seconds must be positive.{context}"
                )
            )
        if self.pdf_read_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.pdf_read_timeout_seconds must be positive.{context}"
                )
            )
        if self.pdf_write_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.pdf_write_timeout_seconds must be positive.{context}"
                )
            )
        if self.operation_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.operation_timeout_seconds must be positive.{context}"
                )
            )
        if not self.output_dir_suffix.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.output_dir_suffix must be non empty.{context}"
                )
            )
        if self.page_offset < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.page_offset must be non negative.{context}"
                )
            )
