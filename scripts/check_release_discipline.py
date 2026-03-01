"""Validate release process artifacts and version/changelog consistency."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _repo_root() -> Path:
    """Return repository root path.

    Summary:
        Resolve the repository root from this script location.
    Inputs:
        - None.
    Outputs:
        - Absolute repository root path.
    Side effects:
        Reads filesystem metadata.
    Error handling:
        Raises RuntimeError when expected files are not found under the computed root.
    Ties to other methods:
        Used by main as the base path for all release checks.
    Why this exists:
        Release checks must run consistently from any current working directory.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").exists():
        raise RuntimeError(
            f"scripts.check_release_discipline._repo_root could not find pyproject.toml at {root}"
        )
    return root


def _project_version(root: Path) -> str:
    """Load project version from pyproject metadata.

    Summary:
        Read `pyproject.toml` and return the project version string.
    Inputs:
        - root: Repository root path.
    Outputs:
        - Version string from `[project].version`.
    Side effects:
        Reads `pyproject.toml`.
    Error handling:
        Raises RuntimeError when version metadata is missing or file parsing fails.
    Ties to other methods:
        Used by _validate_semver and _validate_changelog.
    Why this exists:
        The package version is the canonical source for release/version checks.
    """
    pyproject_path = root / "pyproject.toml"
    try:
        raw = pyproject_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            "scripts.check_release_discipline._project_version failed reading "
            f"{pyproject_path}: {exc}"
        ) from exc

    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(
            "scripts.check_release_discipline._project_version failed parsing "
            f"{pyproject_path}: {exc}"
        ) from exc

    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(
            "scripts.check_release_discipline._project_version missing [project].version in "
            "pyproject.toml"
        )
    return version.strip()


def _validate_semver(version: str) -> list[str]:
    """Validate semantic version format.

    Summary:
        Ensure the project version uses a simple `MAJOR.MINOR.PATCH` format.
    Inputs:
        - version: Version string extracted from pyproject metadata.
    Outputs:
        - List of validation errors.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Called by main.
    Why this exists:
        A stable, parseable version format is required for repeatable release automation.
    """
    if SEMVER_PATTERN.fullmatch(version):
        return []
    return [f"pyproject version must match MAJOR.MINOR.PATCH, got: {version!r}"]


def _validate_changelog(root: Path, version: str) -> list[str]:
    """Validate changelog structure and version entry presence.

    Summary:
        Ensure `CHANGELOG.md` contains both an `Unreleased` section and the current version
        heading.
    Inputs:
        - root: Repository root path.
        - version: Version string from pyproject metadata.
    Outputs:
        - List of validation errors.
    Side effects:
        Reads `CHANGELOG.md`.
    Error handling:
        Returns structured error strings for missing or unreadable files.
    Ties to other methods:
        Called by main.
    Why this exists:
        Releases need deterministic changelog conventions enforced in CI.
    """
    changelog_path = root / "CHANGELOG.md"
    try:
        changelog = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"failed to read {changelog_path}: {exc}"]

    errors: list[str] = []
    if "## Unreleased" not in changelog:
        errors.append("CHANGELOG.md must include a '## Unreleased' section.")
    version_header = f"## {version}"
    if version_header not in changelog:
        errors.append(
            f"CHANGELOG.md must include a heading for the current version ({version_header})."
        )
    return errors


def _validate_release_artifacts(root: Path) -> list[str]:
    """Validate required release process artifacts and policy sections.

    Summary:
        Verify release template and policy documentation required by the release process.
    Inputs:
        - root: Repository root path.
    Outputs:
        - List of validation errors.
    Side effects:
        Reads release policy files.
    Error handling:
        Returns structured error strings for missing files or required sections.
    Ties to other methods:
        Called by main.
    Why this exists:
        Release process quality should be enforceable, not only documented.
    """
    errors: list[str] = []

    template_path = root / ".github" / "release_notes_template.md"
    if not template_path.exists():
        errors.append("missing release notes template: .github/release_notes_template.md")

    release_path = root / "RELEASE.md"
    versioning_path = root / "VERSIONING.md"

    try:
        release_doc = release_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"failed to read {release_path}: {exc}")
        release_doc = ""

    try:
        versioning_doc = versioning_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"failed to read {versioning_path}: {exc}")
        versioning_doc = ""

    if "## Tag Strategy" not in release_doc:
        errors.append("RELEASE.md must include a '## Tag Strategy' section.")
    if "## Deprecation Policy" not in versioning_doc:
        errors.append("VERSIONING.md must include a '## Deprecation Policy' section.")

    return errors


def main() -> int:
    """Run release discipline checks and return process exit code.

    Summary:
        Execute deterministic release checks for versioning, changelog, and release policy files.
    Inputs:
        - None.
    Outputs:
        - Process exit code (0 for success, 1 for validation failures).
    Side effects:
        Reads repository files and writes status to stdout/stderr.
    Error handling:
        Handles RuntimeError from root/version resolution and reports actionable error details.
    Ties to other methods:
        Entry point that orchestrates all helper validation methods.
    Why this exists:
        CI should enforce release discipline to keep publishing repeatable and auditable.
    """
    try:
        root = _repo_root()
        version = _project_version(root)
    except RuntimeError as exc:
        print(f"release-check: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(_validate_semver(version))
    errors.extend(_validate_changelog(root, version))
    errors.extend(_validate_release_artifacts(root))

    if errors:
        print("release-check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "release-check passed: version format, changelog entries, release template, and policy "
        "docs are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
