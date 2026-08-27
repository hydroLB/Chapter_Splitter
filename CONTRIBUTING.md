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
source .venv/bin/activate
```

Use `make install-desktop` instead when changing the Qt workflow. Both targets create the same
`.venv` and install the repo-owned hooks. Pre-push scans repository history with `gitleaks`, then
runs `make check`.

Manual secret scan:

```bash
.venv/bin/pre-commit run --hook-stage manual gitleaks --all-files
```

The `gitleaks` hook also runs on `pre-push`, so pushes are blocked if a likely secret is staged in
history or the working branch.

## Development Workflow

1. Create a small branch focused on one change.
2. Add or update tests before changing behavior.
3. Keep exact direct dependency pins aligned across `pyproject.toml` and `requirements*.txt`.
4. Run `make check` locally.
5. Submit a PR using the PR template.

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

Dependency policy:

- `make deps-policy` enforces that `pyproject.toml`, `requirements*.txt`, and `.github/dependabot.yml` stay aligned with exact direct pins.
- Dependabot is intentionally limited to grouped direct dependency updates to keep the repository low-noise.

Coverage policy:

- `make test` enforces branch-aware coverage at `>= 90%` across the configured non-Qt
  core/application scope; Qt modules have separate offscreen tests and are excluded from this
  percentage.
- CI uses the same gate to prevent drift between local and remote validation.

## Testing Expectations

- Unit tests for core logic.
- Integration tests for IO boundaries.
- End-to-end smoke coverage for critical CLI workflows.
- Offscreen Qt tests for startup and deterministic interaction behavior; do not describe these as a
  full real detect-review-export E2E unless the test actually drives that complete workflow.
- Deterministic tests only.

## Pull Request Guidelines

- Keep PRs small and reviewable.
- Document behavior changes in PR description.
- Include exact commands used to validate changes.
- Update docs and examples when command or config behavior changes.
