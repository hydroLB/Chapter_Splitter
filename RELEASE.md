# Release Process

1. Update `CHANGELOG.md` with the release notes.
2. Update the version in `pyproject.toml`.
3. Run `python -m build` and verify the artifacts in `dist/`.
4. Optional: run `pip install -e '.[bundle]'` and `python scripts/bundle_pyinstaller.py --target gui` to produce a desktop bundle.
5. Tag the release with `vX.Y.Z` and push the tag.
