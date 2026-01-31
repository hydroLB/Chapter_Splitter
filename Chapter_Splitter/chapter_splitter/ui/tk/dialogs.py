"""Tkinter file dialog helpers."""

from __future__ import annotations

from pathlib import Path
from tkinter import TclError, filedialog

from ...core.errors import UiError, format_error_message


def choose_pdf_file(dialog_title: str, location: str) -> Path | None:
    """Show a file picker for selecting a PDF file.

    Purpose:
        Provide a single point for PDF file selection.
    Ties To:
        Used by the UI workflow when starting a split session.
    Inputs:
        - dialog_title: Title string for the file dialog.
        - location: Fully qualified module and method name.
    Outputs:
        - Selected Path or None when no selection is made.
    Side Effects:
        Opens a file dialog window.
    Raises:
        - UiError: When the dialog cannot be shown.
    """
    error_location = f"{__name__}.choose_pdf_file"
    context = f" Context: {location}." if location else ""
    if not dialog_title.strip():
        raise UiError(
            format_error_message(error_location, f"Dialog title must be non empty.{context}")
        )
    try:
        pdf_path_str = filedialog.askopenfilename(
            title=dialog_title,
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
    except TclError as exc:
        raise UiError(
            format_error_message(error_location, f"Unable to open file dialog: {exc}.{context}")
        ) from exc
    return Path(pdf_path_str) if pdf_path_str else None
