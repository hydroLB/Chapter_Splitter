"""Enforce repository hygiene for reproducible public-source pushes."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES: tuple[str, ...] = (
    ".env.example",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".python-version",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.MD",
    "SECURITY.md",
    "pyproject.toml",
    "requirements-dev.lock",
    "requirements.lock",
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
        Raises RuntimeError when the expected repository marker files are missing.
    Ties to other methods:
        Used by main as the base path for all repository hygiene checks.
    Why this exists:
        Hygiene checks must behave consistently regardless of the current working directory.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / ".gitignore").exists():
        raise RuntimeError(
            "scripts.check_repo_hygiene._repo_root could not find .gitignore at repository root"
        )
    return root


def _git_ls_files(root: Path) -> list[str]:
    """Return tracked files from git.

    Summary:
        Query git for the complete tracked file set so hygiene checks operate on source-of-truth
        repository contents rather than the working tree.
    Inputs:
        - root: Repository root path.
    Outputs:
        - Sorted list of tracked file paths relative to the repository root.
    Side effects:
        Executes `git ls-files`.
    Error handling:
        Raises RuntimeError when git is unavailable or the command fails.
    Ties to other methods:
        Used by _validate_required_files, _validate_forbidden_tracked_files, and
        _validate_public_secret_boundaries.
    Why this exists:
        Public repository recovery quality depends on what is actually committed, not what happens
        to exist locally.
    """
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
            "scripts.check_repo_hygiene._git_ls_files failed launching git: " f"{exc}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "scripts.check_repo_hygiene._git_ls_files failed with exit code "
            f"{exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return sorted(files)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    """Return whether a path matches any fnmatch pattern.

    Summary:
        Apply centralized path-pattern matching so hygiene rules stay consistent across checks.
    Inputs:
        - path: Repository-relative path under evaluation.
        - patterns: Tuple of glob-style patterns.
    Outputs:
        - True when the path matches at least one pattern, otherwise False.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _validate_forbidden_tracked_files and _validate_public_secret_boundaries.
    Why this exists:
        Reusing one matcher reduces subtle drift between repository rule sets.
    """
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _validate_required_files(root: Path, tracked_files: list[str]) -> list[str]:
    """Validate required bootstrap files are committed.

    Summary:
        Ensure the repository contains the minimal committed bootstrap files needed for a fast
        recovery after local storage loss.
    Inputs:
        - root: Repository root path.
        - tracked_files: Tracked repository file paths.
    Outputs:
        - List of validation errors.
    Side effects:
        Reads filesystem metadata for required paths.
    Error handling:
        Returns structured validation errors instead of raising.
    Ties to other methods:
        Called by main.
    Why this exists:
        Public GitHub must remain sufficient to rebuild the project quickly with minimal guesswork.
    """
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
    """Validate that generated and machine-specific files are not tracked.

    Summary:
        Detect files that would add repository bloat, stale state, or machine-specific noise to a
        public source repository.
    Inputs:
        - tracked_files: Tracked repository file paths.
    Outputs:
        - List of validation errors.
    Side effects:
        None.
    Error handling:
        Returns structured validation errors instead of raising.
    Ties to other methods:
        Called by main.
    Why this exists:
        Recovery-ready repositories should contain durable source assets, not disposable artifacts.
    """
    errors: list[str] = []
    for path in tracked_files:
        if _matches_any(path, FORBIDDEN_TRACKED_PATTERNS):
            errors.append(f"tracked generated or local-only artifact must be removed: {path}")
    return errors


def _validate_public_secret_boundaries(tracked_files: list[str]) -> list[str]:
    """Validate that obvious secret-bearing file types are not committed.

    Summary:
        Detect committed files that commonly carry credentials, private keys, or local-only secret
        material in public repositories.
    Inputs:
        - tracked_files: Tracked repository file paths.
    Outputs:
        - List of validation errors.
    Side effects:
        None.
    Error handling:
        Returns structured validation errors instead of raising.
    Ties to other methods:
        Called by main.
    Why this exists:
        Public Git history should avoid even likely secret containers, not only known leaked values.
    """
    errors: list[str] = []
    for path in tracked_files:
        if path in ALLOWED_SECRET_EXCEPTIONS:
            continue
        if _matches_any(path, FORBIDDEN_SECRET_PATTERNS):
            errors.append(f"tracked secret-bearing file must not be committed: {path}")
    return errors


def main() -> int:
    """Run repository hygiene checks and return process exit code.

    Summary:
        Execute deterministic checks that keep the repository small, reproducible, and safe for
        public hosting.
    Inputs:
        - None.
    Outputs:
        - Process exit code (0 for success, 1 for validation failures).
    Side effects:
        Reads git metadata and writes status to stdout and stderr.
    Error handling:
        Handles RuntimeError from repository discovery or git execution and reports actionable
        error details.
    Ties to other methods:
        Entry point that orchestrates all repository hygiene validation methods.
    Why this exists:
        Future pushes need automated guardrails so cleanliness and recoverability do not depend on
        memory or manual review.
    """
    try:
        root = _repo_root()
        tracked_files = _git_ls_files(root)
    except RuntimeError as exc:
        print(f"repo-hygiene: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(_validate_required_files(root, tracked_files))
    errors.extend(_validate_forbidden_tracked_files(tracked_files))
    errors.extend(_validate_public_secret_boundaries(tracked_files))

    if errors:
        print("repo-hygiene failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "repo-hygiene passed: bootstrap files are present, generated artifacts are untracked, and "
        "obvious secret-bearing file types are excluded from git."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
