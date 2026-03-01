# Contributing

## Scope

This repository accepts focused, incremental changes that preserve behavior unless a bug fix is
explicitly targeted and covered by tests.

## Prerequisites

- Python version from `.python-version`
- GNU Make

## Local Setup

```bash
make install-dev
```

Install local hooks:

```bash
.venv311/bin/pre-commit install
```

If `.venv311` is not present in your environment, use the active virtual environment path that
contains `pre-commit`.

Optional secret scanning hook (manual stage):

```bash
.venv311/bin/pre-commit run gitleaks --all-files
```

The `gitleaks` hook is configured with `stages: [manual]`, so it does not block normal commits
unless you run it explicitly.

## Development Workflow

1. Create a small branch focused on one change.
2. Add or update tests before changing behavior.
3. Run `make check` locally.
4. Submit a PR using the PR template.

## Quality Gates

The same checks run locally and in CI:

- `make lint`
- `make typecheck`
- `make boundaries`
- `make test`
- `make security`
- `pre-commit run gitleaks --all-files` (recommended for security-sensitive changes)

Use `make check` to run all gates in one command.

Coverage policy:

- `make test` enforces coverage at `>= 90%` via the configured coverage fail-under gate.
- CI uses the same gate to prevent drift between local and remote validation.

## Testing Expectations

- Unit tests for core logic.
- Integration tests for IO boundaries.
- End-to-end smoke coverage for critical CLI workflows.
- Deterministic tests only.

## Pull Request Guidelines

- Keep PRs small and reviewable.
- Document behavior changes in PR description.
- Include exact commands used to validate changes.
- Update docs and examples when command or config behavior changes.
