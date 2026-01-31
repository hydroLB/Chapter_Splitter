"""Grid layout helpers for chapter grid rendering."""

from __future__ import annotations

from chapter_splitter.core.errors import ValidationError, format_error_message


def grid_position(
    idx: int,
    rows_per_column: int,
    header_rows: int,
    grid_columns: int,
) -> tuple[int, int]:
    """Map logical row index to a Tk grid position.

    Purpose:
        Convert a linear row index into a grid column and row.
    Ties To:
        Used by ChapterGridFrame._render_row to position widgets.
    Inputs:
        - idx: Logical row index.
        - rows_per_column: Number of rows per column block.
        - header_rows: Number of header rows.
        - grid_columns: Number of columns per grid block.
    Outputs:
        - Tuple of column and row indices.
    Side Effects:
        None.
    Raises:
        - ValidationError: When rows_per_column or grid_columns is invalid.
    """
    error_location = f"{__name__}.grid_position"
    if rows_per_column < 1:
        raise ValidationError(
            format_error_message(error_location, "rows_per_column must be at least 1.")
        )
    if grid_columns < 1:
        raise ValidationError(
            format_error_message(error_location, "grid_columns must be at least 1.")
        )
    base_col = (idx // rows_per_column) * grid_columns
    grid_row = (idx % rows_per_column) + header_rows
    return base_col, grid_row
