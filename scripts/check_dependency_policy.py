"""Enforce low-noise dependency management and direct-pin consistency."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

EXACT_PIN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[^=\s]+$")


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
        errors.append(f"{label} mismatch.\n  actual:   {actual}\n  expected: {expected}")


def _validate_exact_pins(label: str, dependencies: list[object], errors: list[str]) -> None:
    """Require reproducible direct dependency declarations in every install group."""
    for dependency in dependencies:
        if not isinstance(dependency, str) or not EXACT_PIN_PATTERN.fullmatch(dependency):
            errors.append(f"{label} dependency must use an exact == pin: {dependency!r}")


def _validate_requirements(pyproject: dict[str, object], root: Path, errors: list[str]) -> None:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        errors.append("pyproject.toml is missing [project]")
        return

    runtime_requirements = _read_requirements(root / "requirements.txt")
    dev_requirements = _read_raw_non_comment_lines(root / "requirements-dev.txt")
    bundle_requirements = _read_requirements(root / "requirements-bundle.txt")

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

    project_desktop = optional.get("desktop", [])
    project_bundle = optional.get("bundle", [])
    if not isinstance(project_desktop, list) or not isinstance(project_bundle, list):
        errors.append("pyproject desktop and bundle optional-dependencies must be lists")
        return

    _validate_exact_pins("runtime", project_runtime, errors)
    for group_name, dependencies in optional.items():
        if not isinstance(dependencies, list):
            errors.append(f"pyproject optional-dependencies.{group_name} must be a list")
            continue
        _validate_exact_pins(f"optional group {group_name}", dependencies, errors)

    missing_bundle_runtime = [dep for dep in project_desktop if dep not in project_bundle]
    if missing_bundle_runtime:
        errors.append(
            "bundle extra must include every desktop runtime dependency; missing: "
            f"{missing_bundle_runtime}"
        )

    _assert_equal(
        "requirements.txt vs pyproject project.dependencies",
        runtime_requirements,
        project_runtime,
        errors,
    )
    _assert_equal(
        "requirements-dev.txt vs pyproject dev optional-dependencies",
        dev_requirements,
        ["-r requirements.txt", *project_dev],
        errors,
    )
    _assert_equal(
        "requirements-bundle.txt vs pyproject bundle optional-dependencies",
        bundle_requirements,
        project_bundle,
        errors,
    )


def _validate_build_system(pyproject: dict[str, object], errors: list[str]) -> None:
    """Require the isolated package builder to use exact, reviewable pins."""
    build_system = pyproject.get("build-system")
    if not isinstance(build_system, dict):
        errors.append("pyproject.toml is missing [build-system]")
        return
    build_requirements = build_system.get("requires")
    if not isinstance(build_requirements, list):
        errors.append("pyproject build-system.requires must be a list")
        return
    _validate_exact_pins("build system", build_requirements, errors)


def _validate_dependabot(root: Path, errors: list[str]) -> None:
    text = (root / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    required_snippets = (
        "open-pull-requests-limit: 1",
        'interval: "monthly"',
        'dependency-type: "direct"',
        'patterns:\n          - "*"',
    )
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f".github/dependabot.yml is missing required policy snippet: {snippet!r}")

    if len(re.findall(r'package-ecosystem:\s*"pip"', text)) != 1:
        errors.append(".github/dependabot.yml must define exactly one pip update block")
    if 'dependency-name: "pypdf"' in text:
        errors.append(".github/dependabot.yml must not restrict pip updates to pypdf only")


def main() -> int:
    root = _repo_root()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    errors: list[str] = []

    _validate_build_system(pyproject, errors)
    _validate_requirements(pyproject, root, errors)
    _validate_dependabot(root, errors)

    if errors:
        for error in errors:
            print(f"dependency-policy failed: {error}", file=sys.stderr)
        return 1

    print("dependency-policy passed: requirement pins, pyproject, and Dependabot are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
