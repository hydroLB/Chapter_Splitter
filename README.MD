# PDF Chapter Splitter

PDF Chapter Splitter is a production-grade desktop and CLI tool for exporting chapter PDFs from a
source document. The codebase is organized so PDF domain logic can evolve independently from the
UI layer.

## Quickstart

Python is pinned in `.python-version` and CI uses the same runtime.

Install deterministic dependencies and local tooling:

```bash
make install-dev
```

`make install-dev` also installs the repository `pre-commit` and `pre-push` hooks so hygiene,
tests, and secret scanning stay attached to normal Git workflows. The hooks are committed under
`.githooks/` and `make install-dev` sets `core.hooksPath` so the clone uses the repo-owned hooks
instead of ad-hoc local copies.

Run the desktop workflow:

```bash
make dev
```

Verify the full repository quality gate:

```bash
make check
```

If you prefer zero setup commands, use:

```bash
./start
```

## Deterministic Commands

| Command | Purpose |
| --- | --- |
| `make install-dev` | Install pinned runtime and development dependencies |
| `make dev` | Launch local app flow (`MODE=gui` by default) |
| `make lint` | Run formatter check and linter |
| `make typecheck` | Run strict `mypy` checks |
| `make boundaries` | Enforce layered import dependency direction |
| `make deps-policy` | Enforce lockfile and Dependabot anti-spam policy |
| `make repo-hygiene` | Block tracked local artifacts, secret-bearing files, and missing bootstrap files |
| `make test` | Run tests with coverage gate |
| `make security` | Run Bandit and dependency audit |
| `make release-check` | Enforce release/version/changelog policy checks |
| `make check` | Run all checks used by CI |

## Usage

GUI:

```bash
make dev
```

CLI split:

```bash
chapter-splitter split --pdf path/to/book.pdf --chapters path/to/chapters.toml
```

CLI detect:

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

## Environment Variables

See `.env.example` for a starter set. Supported variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHAPTER_SPLITTER_CONFIG` | unset | Path to config override file used by app/CLI config loader |
| `CHAPTER_SPLITTER_CONFIG_TIMEOUT_SECONDS` | `5.0` | Timeout for reading config files |
| `CHAPTER_SPLITTER_MODE` | `gui` | `start` script mode (`gui` or `split`) |
| `CHAPTER_SPLITTER_CONFIG_PATH` | unset | Config path override used by `start` script |
| `PDF_PATH` | unset | PDF path for `CHAPTER_SPLITTER_MODE=split` in `start` |
| `CHAPTERS_PATH` | unset | Chapter TOML path for `CHAPTER_SPLITTER_MODE=split` in `start` |

## Configuration

Central defaults live in `Chapter_Splitter/chapter_splitter/config/settings.toml`.

Runtime override from file:

```bash
chapter-splitter --config path/to/override.toml gui
```

Important config areas:
- `app` for title and correlation ID prefix.
- `logging` for structured logs and redaction rules.
- `io` for timeouts, output naming, and collision policy.
- `validation` for chapter rules.
- `detection` for outlines and TOC parsing behavior.
- `performance` for benchmark budgets and iterations.

## Troubleshooting

- GUI fails to launch: run `make install-dev` and retry `make dev`.
- Config load failure: verify TOML syntax and paths in `CHAPTER_SPLITTER_CONFIG` or `--config`.
- Split mode from `start` fails: ensure `PDF_PATH` and `CHAPTERS_PATH` are set to existing files.
- Output collisions: set `io.output_collision_policy` to `overwrite` or `suffix`.
- Slow or interrupted operations: verify `io.operation_timeout_seconds` and `retry` settings.

## Testing and Performance

Run tests:

```bash
make test
```

`make test` enforces the repository coverage gate (`fail-under=90`) and fails when coverage drops
below that threshold.

Update performance baselines:

```bash
python scripts/update_benchmarks.py
```

Profile core split path:

```bash
python scripts/profile_split.py
```

## Architecture Snapshot

- Config load and validation: `Chapter_Splitter/chapter_splitter/config/`
- Domain models and validation rules: `Chapter_Splitter/chapter_splitter/core/`
- PDF detection and splitting: `Chapter_Splitter/chapter_splitter/pdf/`
- Chapter file IO: `Chapter_Splitter/chapter_splitter/io/chapters.py`
- Structured logging and correlation IDs: `Chapter_Splitter/chapter_splitter/observability/logging.py`
- Qt workflow and widgets: `Chapter_Splitter/chapter_splitter/ui/qt/`

## Governance

- Contribution guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Dependency update automation: `.github/dependabot.yml`
- Git hook enforcement: `.githooks/`
- Incident runbooks: `docs/runbooks/`
- Architecture narrative: `docs/architecture.md`
- ADRs: `docs/adr/`
- Design principles: `docs/design-principles.md`
- Performance and resilience governance: `docs/performance-governance.md`
- Release notes and process: `CHANGELOG.md` and `RELEASE.md`
- Ownership map: `.github/CODEOWNERS`

## Build and Bundle

Build package:

```bash
python -m build
```

Build desktop bundle:

```bash
pip install -e '.[bundle]'
python scripts/bundle_pyinstaller.py --target gui
```
