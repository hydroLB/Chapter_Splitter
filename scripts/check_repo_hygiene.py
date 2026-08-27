"""Enforce repository hygiene for reproducible public-source pushes."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES: tuple[str, ...] = (
    ".env.example",
    ".gitignore",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    ".pre-commit-config.yaml",
    ".python-version",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.MD",
    "SECURITY.md",
    "scripts/check_dependency_policy.py",
    "scripts/run_with_repo_python.sh",
    "pyproject.toml",
    "requirements.txt",
    "start",
)

FORBIDDEN_TRACKED_PATTERNS: tuple[str, ...] = (
    ".coverage",
    ".coverage.*",
    ".mypy_cache/*",
    ".nox/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".tox/*",
    ".venv/*",
    ".venv311/*",
    ".DS_Store",
    "*.egg-info/*",
    "*.log",
    "*.pid",
    "*.pid.lock",
    "*.prof",
    "*.pstats",
    "*.pyc",
    "*.pyd",
    "*.pyo",
    "*~",
    "__pycache__/*",
    "build/*",
    "coverage.xml",
    "dist/*",
    "htmlcov/*",
    "junit.xml",
    "pip-wheel-metadata/*",
    "splitter.log",
)

FORBIDDEN_SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.asc",
    "*.cer",
    "*.crt",
    "*.der",
    "*.kdbx",
    "*.key",
    "*.p12",
    "*.pem",
    "*.pfx",
    "auth.json",
    "credentials.*",
    "secrets.*",
)

ALLOWED_SECRET_EXCEPTIONS: tuple[str, ...] = (".env.example",)


def _repo_root() -> Path:
    """Return repository root path."""
    root = Path(__file__).resolve().parents[1]
    if not (root / ".gitignore").exists():
        raise RuntimeError(
            "scripts.check_repo_hygiene._repo_root could not find .gitignore at repository root"
        )
    return root


def _git_ls_files(root: Path) -> list[str]:
    """Return tracked files from git."""
    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(
            f"scripts.check_repo_hygiene._git_ls_files failed launching git: {exc}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "scripts.check_repo_hygiene._git_ls_files failed with exit code "
            f"{exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return sorted(files)


def _git_ignored_tracked_files(root: Path, tracked_files: list[str]) -> list[str]:
    """Return tracked paths that still match the repository's ignore rules.

    Git normally suppresses tracked paths from ``check-ignore`` output. ``--no-index`` makes the
    command evaluate every tracked path against the same ignore rules that apply to new files,
    exposing stale or overly broad patterns before they hide future repository changes.
    """
    if not tracked_files:
        return []

    input_paths = "\0".join(tracked_files) + "\0"
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            check=False,
            cwd=root,
            capture_output=True,
            text=True,
            input=input_paths,
        )
    except OSError as exc:
        raise RuntimeError(
            f"scripts.check_repo_hygiene._git_ignored_tracked_files failed launching git: {exc}"
        ) from exc

    if completed.returncode not in (0, 1):
        raise RuntimeError(
            "scripts.check_repo_hygiene._git_ignored_tracked_files failed with exit code "
            f"{completed.returncode}: {completed.stderr.strip()}"
        )
    return sorted(path for path in completed.stdout.split("\0") if path)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    """Return whether a path matches any fnmatch pattern."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _validate_required_files(root: Path, tracked_files: list[str]) -> list[str]:
    """Validate required bootstrap files are committed."""
    tracked_set = set(tracked_files)
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if relative_path not in tracked_set:
            errors.append(f"missing required tracked bootstrap file: {relative_path}")
            continue
        if not (root / relative_path).exists():
            errors.append(
                f"tracked bootstrap file is missing from the working tree: {relative_path}"
            )
    return errors


def _validate_forbidden_tracked_files(tracked_files: list[str]) -> list[str]:
    """Validate that generated and machine-specific files are not tracked."""
    errors: list[str] = []
    for path in tracked_files:
        if _matches_any(path, FORBIDDEN_TRACKED_PATTERNS):
            errors.append(f"tracked generated or local-only artifact must be removed: {path}")
    return errors


def _validate_tracked_ignore_rules(ignored_tracked_files: list[str]) -> list[str]:
    """Reject tracked files that match ignore rules intended for untracked content."""
    return [
        f"tracked file matches an ignore rule; narrow or remove the rule: {path}"
        for path in ignored_tracked_files
    ]


def _validate_public_secret_boundaries(tracked_files: list[str]) -> list[str]:
    """Validate that obvious secret-bearing file types are not committed."""
    errors: list[str] = []
    for path in tracked_files:
        if path in ALLOWED_SECRET_EXCEPTIONS:
            continue
        if _matches_any(path, FORBIDDEN_SECRET_PATTERNS):
            errors.append(f"tracked secret-bearing file must not be committed: {path}")
    return errors


def main() -> int:
    """Run repository hygiene checks and return process exit code."""
    try:
        root = _repo_root()
        tracked_files = _git_ls_files(root)
        ignored_tracked_files = _git_ignored_tracked_files(root, tracked_files)
    except RuntimeError as exc:
        print(f"repo-hygiene: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(_validate_required_files(root, tracked_files))
    errors.extend(_validate_forbidden_tracked_files(tracked_files))
    errors.extend(_validate_tracked_ignore_rules(ignored_tracked_files))
    errors.extend(_validate_public_secret_boundaries(tracked_files))

    if errors:
        print("repo-hygiene failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "repo-hygiene passed: bootstrap files are present, generated artifacts are untracked, "
        "tracked paths are not ignored, and obvious secret-bearing file types are excluded "
        "from git."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
