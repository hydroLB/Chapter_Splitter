"""Type aliases for chapter grid widgets."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TypeAlias

GridRow: TypeAlias = tuple[tk.Entry, tk.Entry, tk.Entry, ttk.Button]
ChapterRowValues: TypeAlias = tuple[str, str, str]
