"""Validate release process artifacts and version/changelog consistency."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _repo_root() -> Path:
    """Return repository root path."""
    root = Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").exists():
        raise RuntimeError(
            f"scripts.check_release_discipline._repo_root could not find pyproject.toml at {root}"
        )
    return root


def _project_version(root: Path) -> str:
    """Load project version from pyproject metadata."""
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
    """Validate semantic version format."""
    if SEMVER_PATTERN.fullmatch(version):
        return []
    return [f"pyproject version must match MAJOR.MINOR.PATCH, got: {version!r}"]


def _validate_changelog(root: Path, version: str) -> list[str]:
    """Validate changelog structure and version entry presence."""
    changelog_path = root / "CHANGELOG.md"
    try:
        changelog = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"failed to read {changelog_path}: {exc}"]

    errors: list[str] = []
    if "## Unreleased" not in changelog:
        errors.append("CHANGELOG.md must include a '## Unreleased' section.")
    version_header = f"## {version}"
    if re.search(rf"^{re.escape(version_header)}(?:\s|$)", changelog, re.MULTILINE) is None:
        errors.append(
            f"CHANGELOG.md must include a heading for the current version ({version_header})."
        )
    return errors


def _validate_runtime_version(root: Path, version: str) -> list[str]:
    version_path = root / "Chapter_Splitter" / "chapter_splitter" / "_version.py"
    try:
        text = version_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"failed to read {version_path}: {exc}"]
    match = re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE)
    if match is None or match.group(1) != version:
        return [f"runtime __version__ must exactly match pyproject version {version}"]
    return []


def _validate_release_tag(version: str) -> list[str]:
    if os.environ.get("GITHUB_REF_TYPE") != "tag":
        return []
    expected = f"v{version}"
    actual = os.environ.get("GITHUB_REF_NAME", "")
    return [] if actual == expected else [f"release tag must be {expected}, got {actual!r}"]


def _validate_release_artifacts(root: Path) -> list[str]:
    """Validate required release process artifacts and policy sections."""
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
    """Run release discipline checks and return process exit code."""
    try:
        root = _repo_root()
        version = _project_version(root)
    except RuntimeError as exc:
        print(f"release-check: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(_validate_semver(version))
    errors.extend(_validate_changelog(root, version))
    errors.extend(_validate_runtime_version(root, version))
    errors.extend(_validate_release_tag(version))
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
