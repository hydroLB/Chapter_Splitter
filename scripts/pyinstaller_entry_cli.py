"""PyInstaller entrypoint for the CLI application."""

from __future__ import annotations

from chapter_splitter.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
