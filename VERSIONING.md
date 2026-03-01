# Versioning

This project follows semantic versioning.

- Major versions change public behavior or formats in a breaking way.
- Minor versions add functionality in a backward compatible way.
- Patch versions include fixes and internal improvements.

Release tags match the version in `pyproject.toml`.

## Deprecation Policy

- Deprecations are announced in `CHANGELOG.md` under `## Unreleased` and in release notes.
- Each deprecation entry states:
  - the deprecated behavior or interface
  - the first version where deprecation started
  - the planned removal version (major or minor, as applicable)
  - migration guidance
- Removals occur only after at least one released version includes the deprecation notice.
- Security or correctness emergencies may accelerate removal; those exceptions must be documented
  in release notes and `CHANGELOG.md`.
