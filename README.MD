# PDF Chapter Splitter

PDF Chapter Splitter is a focused desktop tool for exporting chapter PDFs with a clean, config driven workflow. It is built to keep the split pipeline independent from the UI so the project can grow without rewrites.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

Optional extras:

- Embedded preview and review rendering (PyMuPDF):

```bash
pip install -e '.[preview]'
```

Development tools and quality gates:

```bash
pip install -r requirements-dev.lock
pre-commit install
```

## Run

GUI:

```bash
chapter-splitter gui
```

Inside the GUI, use:

- `Import TOML` to load an existing `chapters.toml` and prefill the grid
- `Export TOML` to write the current chapter list to a file
- `Save Session` to export chapters plus `[session]` metadata for repeat runs

CLI split:

```bash
chapter-splitter split --pdf path/to/book.pdf --chapters path/to/chapters.toml
```

One-off overrides (no config file):

```bash
chapter-splitter split --pdf path/to/book.pdf --chapters path/to/chapters.toml --output-dir out --collision-policy suffix --page-offset 0
```

CLI detect (generate a starter `chapters.toml` from outlines or TOC):

```bash
chapter-splitter detect --pdf path/to/book.pdf --strategy auto --out chapters.toml
```

Example `chapters.toml`:

```toml
[[chapters]]
title = "Intro"
start_page = 1
end_page = 4

[[chapters]]
title = "Chapter 1"
start_page = 5
end_page = 18
```

## Configuration

All tunable behavior lives in `Chapter_Splitter/chapter_splitter/config/settings.toml`. Overrides are supported via a file path:

```bash
chapter-splitter --config path/to/override.toml gui
```

Or through an environment variable:

```bash
export CHAPTER_SPLITTER_CONFIG=path/to/override.toml
```

Config file reads are time bounded with an environment override:

```bash
export CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS=5.0
```

Key sections to know:

- `app` controls title and correlation ID prefix
- `logging` controls structured JSON output and redaction
- `io` controls timeouts, output naming, and collision policy
- `ui` controls grid sizing, labels, and dialog text
- `validation` defines chapter limits and uniqueness rules
- `performance` sets benchmark budgets

Useful `io` knobs:

- `io.page_offset` aligns user-entered page numbers with PDF indices
- `io.infer_page_offset_from_labels` can auto-infer an offset from PDF page labels when present (see also `io.infer_page_offset_min_sequential_numeric_labels`)

## Testing

Unit, integration, and end to end tests:

```bash
pytest
```

Performance baselines and profiling:

```bash
python scripts/update_benchmarks.py
python scripts/profile_split.py
```

## Troubleshooting

- Missing `pypdf`: install with `pip install pypdf==6.6.2`
- Config errors: check `Chapter_Splitter/chapter_splitter/config/settings.toml` and any overrides
- Output collisions: set `io.output_collision_policy = "overwrite"` or `"suffix"`, or change `io.output_dir_suffix`
- UI actions ignored: increase `ui.action_rate_limit_seconds` if the OS is slow

## Architecture Overview

- Config loading and deep-merge live in `Chapter_Splitter/chapter_splitter/config/loader/api.py`, and validation lives in `Chapter_Splitter/chapter_splitter/config/schema/settings.py` plus the per-section schema under `Chapter_Splitter/chapter_splitter/config/schema/sections/`
- Structured logging, redaction, and correlation IDs are in `Chapter_Splitter/chapter_splitter/observability/logging.py`
- PDF outline detection is implemented in `Chapter_Splitter/chapter_splitter/pdf/detection/outlines.py`
- The split pipeline is in `Chapter_Splitter/chapter_splitter/pdf/splitting/splitter.py` and uses strict validation from `Chapter_Splitter/chapter_splitter/core/validation.py`
- Qt GUI workflow and widgets are in `Chapter_Splitter/chapter_splitter/ui/qt/workflow.py` and `Chapter_Splitter/chapter_splitter/ui/qt/main_window.py`

## Implementation Notes

- The config loader merges defaults with overrides and validates every field before use to keep tuning safe and centralized
- Logging is structured, redacted, and tagged with correlation IDs to make troubleshooting precise
- The split workflow uses deadlines, retries, and cancellation checks so IO cannot hang indefinitely
- Performance baselines in `benchmarks/baseline.json` guard the hot paths and are updated with `scripts/update_benchmarks.py`

## Screenshots

![Main window](README_IMAGES/main_screen.png)

![Export flow](README_IMAGES/export_example.png)

## Build and Release

Build:

```bash
python -m build
```

Desktop bundling (PyInstaller):

```bash
pip install -e '.[bundle]'
python scripts/bundle_pyinstaller.py --target gui
```

Release process:

- `CHANGELOG.md` and `RELEASE.md` outline the steps
- Tags follow the version in `pyproject.toml`
