# PDF Chapter Splitter

PDF Chapter Splitter is a focused desktop tool for exporting chapter PDFs with a clean, config driven workflow. It is built to keep the split pipeline independent from the UI so the project can grow without rewrites.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
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

CLI split:

```bash
chapter-splitter split --pdf path/to/book.pdf --chapters path/to/chapters.toml
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
- Tkinter workflow and UI widgets are in `Chapter_Splitter/chapter_splitter/ui/tk/workflow.py` and `Chapter_Splitter/chapter_splitter/ui/tk/widgets/chapter_grid/frame.py`

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

Release process:

- `CHANGELOG.md` and `RELEASE.md` outline the steps
- Tags follow the version in `pyproject.toml`
