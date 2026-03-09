"""Enforce low-noise dependency management and lockfile consistency."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def _repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").exists():
        raise RuntimeError("scripts.check_dependency_policy could not locate pyproject.toml")
    return root


def _read_requirements(path: Path) -> list[str]:
    items: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        items.append(line)
    return items


def _read_raw_non_comment_lines(path: Path) -> list[str]:
    items: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(line)
    return items


def _assert_equal(label: str, actual: list[str], expected: list[str], errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{label} mismatch.\n" f"  actual:   {actual}\n" f"  expected: {expected}")


def _validate_requirements(pyproject: dict[str, object], root: Path, errors: list[str]) -> None:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        errors.append("pyproject.toml is missing [project]")
        return

    runtime_requirements = _read_requirements(root / "requirements.txt")
    runtime_lock = _read_requirements(root / "requirements.lock")
    dev_requirements = _read_raw_non_comment_lines(root / "requirements-dev.txt")
    dev_lock = _read_requirements(root / "requirements-dev.lock")

    project_runtime = project.get("dependencies", [])
    if not isinstance(project_runtime, list):
        errors.append("pyproject.toml project.dependencies must be a list")
        return

    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        errors.append("pyproject.toml project.optional-dependencies must be a table")
        return

    project_dev = optional.get("dev", [])
    if not isinstance(project_dev, list):
        errors.append("pyproject.toml project.optional-dependencies.dev must be a list")
        return

    _assert_equal(
        "requirements.txt vs pyproject project.dependencies",
        runtime_requirements,
        project_runtime,
        errors,
    )
    _assert_equal(
        "requirements.lock vs requirements.txt",
        runtime_lock,
        runtime_requirements,
        errors,
    )
    _assert_equal(
        "requirements-dev.txt vs pyproject dev optional-dependencies",
        dev_requirements,
        ["-r requirements.txt", *project_dev],
        errors,
    )
    _assert_equal(
        "requirements-dev.lock vs flattened runtime+dev requirements",
        dev_lock,
        [*runtime_requirements, *project_dev],
        errors,
    )


def _validate_dependabot(root: Path, errors: list[str]) -> None:
    text = (root / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    required_snippets = (
        "open-pull-requests-limit: 1",
        'interval: "monthly"',
        'dependency-name: "pypdf"',
        'patterns:\n          - "*"',
    )
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f".github/dependabot.yml is missing required policy snippet: {snippet!r}")

    if len(re.findall(r'package-ecosystem:\s*"pip"', text)) != 1:
        errors.append(".github/dependabot.yml must define exactly one pip update block")


def main() -> int:
    root = _repo_root()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    errors: list[str] = []

    _validate_requirements(pyproject, root, errors)
    _validate_dependabot(root, errors)

    if errors:
        for error in errors:
            print(f"dependency-policy failed: {error}", file=sys.stderr)
        return 1

    print("dependency-policy passed: lockfiles, pyproject, and Dependabot policy are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
