"""PyInstaller entrypoint for the GUI application."""

from __future__ import annotations

from chapter_splitter.app import main

if __name__ == "__main__":
    raise SystemExit(main())
