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
make install-dev
```

`make install-dev` installs both `pre-commit` and `pre-push` hooks so local changes are checked
before they are committed or pushed.

Manual secret scan:

```bash
.venv311/bin/pre-commit run --hook-stage manual gitleaks --all-files
```

The `gitleaks` hook also runs on `pre-push`, so pushes are blocked if a likely secret is staged in
history or the working branch.

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
- `make repo-hygiene`
- `make test`
- `make security`
- `pre-commit run --hook-stage manual gitleaks --all-files`

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
