"""Qt-based GUI implementation for the Chapter Splitter application.

Summary:
    Provide the desktop GUI built on Qt (PySide6) with a true PDF renderer.
Inputs:
    - None.
Outputs:
    - None.
Side effects:
    Imports Qt modules when referenced.
Error handling:
    None.
Ties to other methods:
    Used by chapter_splitter.app entrypoint when launching the GUI.
Why this exists:
    Tk cannot embed a vector PDF renderer; Qt can, and is the long-term GUI foundation.
"""

from __future__ import annotations

__all__ = ["workflow"]

from .workflow import workflow
