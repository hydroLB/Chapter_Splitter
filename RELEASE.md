# Release Process

1. Update `CHANGELOG.md` by moving release-ready notes from `## Unreleased` to `## X.Y.Z`.
2. Update the version in `pyproject.toml`.
3. Prepare release notes using `.github/release_notes_template.md`.
4. Run `make check` and confirm all gates pass, including `make release-check`.
5. Tag the release with `vX.Y.Z` and push the tag.
6. The release workflow validates the tag/version pair, builds and smoke-tests desktop and CLI
   executables on macOS, Windows, and Linux, adds SHA-256 files, and publishes the draft only after
   every platform succeeds.

## Tag Strategy

- Annotated tags only, formatted as `vMAJOR.MINOR.PATCH`.
- The tag version must match `[project].version` in `pyproject.toml`.
- Each release tag must map to one changelog heading `## MAJOR.MINOR.PATCH`.
- Never retag an existing version; increment and publish a new patch instead.

## Enforceable Checks

- `scripts/check_release_discipline.py` validates:
  - semantic version format in `pyproject.toml`
  - `CHANGELOG.md` includes `## Unreleased`
  - `CHANGELOG.md` includes an exact current-version heading
  - the runtime and package metadata versions match
  - release tags exactly match the version as `vX.Y.Z`
  - `.github/release_notes_template.md` exists
  - tag strategy and deprecation policy sections are documented
- CI runs this gate via `make release-check` on every pull request and push.
