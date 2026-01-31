# Release Process

1. Update `CHANGELOG.md` with the release notes.
2. Update the version in `pyproject.toml`.
3. Run `python -m build` and verify the artifacts in `dist/`.
4. Tag the release with `vX.Y.Z` and push the tag.
