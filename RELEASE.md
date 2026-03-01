# Release Process

1. Update `CHANGELOG.md` by moving release-ready notes from `## Unreleased` to `## X.Y.Z`.
2. Update the version in `pyproject.toml`.
3. Prepare release notes using `.github/release_notes_template.md`.
4. Run `make check` and confirm all gates pass, including `make release-check`.
5. Run `make build` and verify the artifacts in `dist/`.
6. Optional: run `pip install -e '.[bundle]'` and `python scripts/bundle_pyinstaller.py --target gui` to produce a desktop bundle.
7. Tag the release with `vX.Y.Z` and push the tag.
8. Publish a GitHub release using the matching tag and the prepared release notes.

## Tag Strategy

- Annotated tags only, formatted as `vMAJOR.MINOR.PATCH`.
- The tag version must match `[project].version` in `pyproject.toml`.
- Each release tag must map to one changelog heading `## MAJOR.MINOR.PATCH`.
- Never retag an existing version; increment and publish a new patch instead.

## Enforceable Checks

- `scripts/check_release_discipline.py` validates:
  - semantic version format in `pyproject.toml`
  - `CHANGELOG.md` includes `## Unreleased`
  - `CHANGELOG.md` includes the current version heading
  - `.github/release_notes_template.md` exists
  - tag strategy and deprecation policy sections are documented
- CI runs this gate via `make release-check` on every pull request and push.
