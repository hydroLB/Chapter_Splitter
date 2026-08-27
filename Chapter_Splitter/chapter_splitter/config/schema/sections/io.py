"""File and process IO configuration schema."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from ....core.errors import ConfigurationError, format_error_message

OutputCollisionPolicy = Literal["error", "overwrite", "suffix"]


class IOConfig:
    """File and process IO configuration."""

    def __init__(
        self,
        open_viewer: bool,
        viewer_timeout_seconds: float,
        pdf_read_timeout_seconds: float,
        pdf_write_timeout_seconds: float,
        operation_timeout_seconds: float,
        output_dir_suffix: str,
        output_collision_policy: OutputCollisionPolicy,
        output_collision_max_suffix: int,
        fsync_writes: bool,
        page_offset: int,
        infer_page_offset_from_labels: bool,
        infer_page_offset_min_sequential_numeric_labels: int,
    ) -> None:
        """Initialize IO configuration."""
        self.open_viewer = open_viewer
        self.viewer_timeout_seconds = viewer_timeout_seconds
        self.pdf_read_timeout_seconds = pdf_read_timeout_seconds
        self.pdf_write_timeout_seconds = pdf_write_timeout_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self.output_dir_suffix = output_dir_suffix
        self.output_collision_policy = output_collision_policy
        self.output_collision_max_suffix = output_collision_max_suffix
        self.fsync_writes = fsync_writes
        self.page_offset = page_offset
        self.infer_page_offset_from_labels = infer_page_offset_from_labels
        self.infer_page_offset_min_sequential_numeric_labels = (
            infer_page_offset_min_sequential_numeric_labels
        )

    def validate(self, location: str) -> None:
        """Validate IO configuration."""
        error_location = f"{__name__}.IOConfig.validate"
        context = f" Context: {location}." if location else ""
        if not isfinite(self.viewer_timeout_seconds) or self.viewer_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"io.viewer_timeout_seconds must be finite and positive.{context}",
                )
            )
        if not isfinite(self.pdf_read_timeout_seconds) or self.pdf_read_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"io.pdf_read_timeout_seconds must be finite and positive.{context}",
                )
            )
        if not isfinite(self.pdf_write_timeout_seconds) or self.pdf_write_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"io.pdf_write_timeout_seconds must be finite and positive.{context}",
                )
            )
        if not isfinite(self.operation_timeout_seconds) or self.operation_timeout_seconds <= 0:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"io.operation_timeout_seconds must be finite and positive.{context}",
                )
            )
        if not self.output_dir_suffix.strip():
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.output_dir_suffix must be non empty.{context}"
                )
            )
        if self.output_collision_policy not in ("error", "overwrite", "suffix"):
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "io.output_collision_policy must be one of: error, overwrite, suffix."
                    f"{context}",
                )
            )
        if self.output_collision_max_suffix < 2:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    f"io.output_collision_max_suffix must be at least 2.{context}",
                )
            )
        if self.page_offset < 0:
            raise ConfigurationError(
                format_error_message(
                    error_location, f"io.page_offset must be non negative.{context}"
                )
            )
        if self.infer_page_offset_min_sequential_numeric_labels < 1:
            raise ConfigurationError(
                format_error_message(
                    error_location,
                    "io.infer_page_offset_min_sequential_numeric_labels must be at least 1."
                    f"{context}",
                )
            )
