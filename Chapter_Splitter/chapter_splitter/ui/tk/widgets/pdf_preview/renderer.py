"""PDF rendering helpers for embedded preview panels.

This module treats the PDF preview renderer as an optional dependency so the
application can run without additional native libraries.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .....core.errors import UiError, format_error_message
from .....core.runtime import CancellationToken
from .....utils.timing import Deadline


class PixmapProtocol(Protocol):
    width: int
    height: int

    def tobytes(self, output: str = ...) -> bytes: ...


class MatrixProtocol(Protocol):
    """Structural type for the PyMuPDF Matrix class."""

    def __init__(self, a: float, b: float) -> None: ...


class PageProtocol(Protocol):
    def get_pixmap(
        self, matrix: MatrixProtocol | None = ..., alpha: bool = ...
    ) -> PixmapProtocol: ...


class DocumentProtocol(Protocol):
    def load_page(self, pno: int) -> PageProtocol: ...

    def close(self) -> None: ...


class FitzModuleProtocol(Protocol):
    Matrix: type[MatrixProtocol]
    open: Callable[..., DocumentProtocol]


def _try_import_fitz() -> FitzModuleProtocol | None:
    """Attempt to import PyMuPDF without hard dependency.

    Summary:
        Provide a small import guard so the UI can fall back when PyMuPDF is not installed.
    Inputs:
        - None.
    Outputs:
        - The imported module object, or None when unavailable.
    Side effects:
        Imports a module when available.
    Error handling:
        Returns None for any import failure to keep the application usable.
    Ties to other methods:
        Used by is_preview_available and PdfPreviewRenderer.open.
    Why this exists:
        The project pins a minimal dependency set; embedded rendering should be optional.
    """
    try:
        import fitz
    except Exception:
        return None
    return cast(FitzModuleProtocol, fitz)


def is_preview_available() -> bool:
    """Return whether the embedded PDF preview dependency is available.

    Summary:
        Detect whether PyMuPDF is installed so the UI can decide between embedded preview or
        fallback.
    Inputs:
        - None.
    Outputs:
        - True when PyMuPDF is importable, otherwise False.
    Side effects:
        Attempts an import.
    Error handling:
        Returns False when import fails.
    Ties to other methods:
        Used by the preview frame to decide whether to show an install message.
    Why this exists:
        Avoid raising exceptions during UI construction when optional dependencies are missing.
    """
    return _try_import_fitz() is not None


@dataclass(frozen=True, slots=True)
class RenderedImage:
    """Rendered image payload for Tk PhotoImage consumption.

    Summary:
        Carry base64-encoded PNG data suitable for `tk.PhotoImage(data=...)`.
    Inputs:
        - png_base64: Base64 representation of the PNG bytes.
        - width: Image width in pixels.
        - height: Image height in pixels.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Returned by PdfPreviewRenderer.render_page_png_base64.
    Why this exists:
        Tkinter works cleanly with base64 PNG data and avoids a Pillow dependency.
    """

    png_base64: str
    width: int
    height: int


class PdfPreviewRenderer:
    """Render PDF pages to PNG bytes via PyMuPDF.

    Summary:
        Provide a small adapter around PyMuPDF for predictable rendering and error reporting.
    Inputs:
        - None.
    Outputs:
        - None.
    Side effects:
        Opens a PDF document when `open` is called.
    Error handling:
        Raises UiError with actionable install instructions or open failures.
    Ties to other methods:
        Used by PdfPreviewFrame to render pages on demand.
    Why this exists:
        Keep optional dependency handling isolated from UI widget code.
    """

    def __init__(self) -> None:
        """Initialize the renderer in a closed state.

        Summary:
            Create a renderer that can later open a document.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            None.
        Error handling:
            None.
        Ties to other methods:
            Used by PdfPreviewFrame during initialization.
        Why this exists:
            Allows the UI to create the widget even before the PDF is opened.
        """
        self._fitz: FitzModuleProtocol | None = None
        self._doc: DocumentProtocol | None = None

    def open(self, pdf_path: Path, token: CancellationToken, location: str) -> None:
        """Open a PDF document for rendering.

        Summary:
            Load the document through PyMuPDF so page rendering is fast.
        Inputs:
            - pdf_path: Path to the PDF file to open.
            - token: Cancellation token for graceful shutdown.
            - location: Fully qualified module and method name.
        Outputs:
            - None.
        Side effects:
            Opens and retains a document handle.
        Error handling:
            Raises UiError when PyMuPDF is missing or the document cannot be opened.
        Ties to other methods:
            Must be called before render_page_png_base64.
        Why this exists:
            Rendering requires a document handle; centralizing open improves error messaging.
        """
        token.check(location)
        error_location = f"{__name__}.PdfPreviewRenderer.open"
        context = f" Context: {location}." if location else ""
        if not isinstance(pdf_path, Path):
            raise UiError(
                format_error_message(error_location, f"pdf_path must be a Path.{context}")
            )
        fitz = _try_import_fitz()
        if fitz is None:
            raise UiError(
                format_error_message(
                    error_location,
                    "Embedded PDF preview requires PyMuPDF. Install it with: pip install pymupdf",
                )
            )
        try:
            # fitz.open returns a Document.
            self._fitz = fitz
            self._doc = fitz.open(str(pdf_path))
        except Exception as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to open PDF for preview: {pdf_path}.{context}",
                )
            ) from exc

    def close(self) -> None:
        """Close the document if open.

        Summary:
            Release renderer resources when the UI is closing.
        Inputs:
            - None.
        Outputs:
            - None.
        Side effects:
            Closes the underlying document handle if present.
        Error handling:
            Suppresses close errors to avoid masking the original shutdown path.
        Ties to other methods:
            Called by PdfPreviewFrame teardown.
        Why this exists:
            Avoid leaked file handles when the UI closes repeatedly in a single process.
        """
        doc = self._doc
        self._doc = None
        if doc is None:
            return
        try:
            doc.close()
        except Exception:
            return

    def render_page_png_base64(
        self,
        page_number: int,
        zoom: float,
        deadline: Deadline,
        token: CancellationToken,
        location: str,
    ) -> RenderedImage:
        """Render a 1-based page number to base64 PNG data.

        Summary:
            Render the requested page to a PNG and encode it for Tk `PhotoImage`.
        Inputs:
            - page_number: 1-based page number.
            - zoom: Render zoom factor (1.0 is 72dpi).
            - deadline: Deadline for time bounding render work.
            - token: Cancellation token for graceful shutdown.
            - location: Fully qualified module and method name.
        Outputs:
            - RenderedImage containing base64 PNG data and pixel dimensions.
        Side effects:
            Performs CPU work and allocates image memory.
        Error handling:
            Raises UiError when the renderer is not open or rendering fails.
        Ties to other methods:
            Used by PdfPreviewFrame._render_current_page.
        Why this exists:
            Centralizes rendering and encoding so the UI can focus on layout and navigation.
        """
        token.check(location)
        deadline.check(location)
        error_location = f"{__name__}.PdfPreviewRenderer.render_page_png_base64"
        context = f" Context: {location}." if location else ""
        if self._doc is None:
            raise UiError(
                format_error_message(error_location, f"Preview document not open.{context}")
            )
        if page_number < 1:
            raise UiError(
                format_error_message(
                    error_location,
                    f"page_number must be >= 1 (got {page_number}).{context}",
                )
            )
        if zoom <= 0:
            raise UiError(
                format_error_message(
                    error_location,
                    f"zoom must be positive (got {zoom}).{context}",
                )
            )
        try:
            # doc.load_page expects 0-based.
            page = self._doc.load_page(page_number - 1)
            deadline.check(location)
            fitz = self._fitz
            if fitz is None:
                raise RuntimeError("Missing fitz module after open().")
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")
            deadline.check(location)
        except Exception as exc:
            raise UiError(
                format_error_message(
                    error_location,
                    f"Unable to render page {page_number}.{context}",
                )
            ) from exc
        b64 = base64.b64encode(png_bytes).decode("ascii")
        width = int(getattr(pix, "width", 0))
        height = int(getattr(pix, "height", 0))
        return RenderedImage(png_base64=b64, width=width, height=height)
