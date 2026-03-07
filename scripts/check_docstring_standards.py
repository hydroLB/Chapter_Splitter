"""Enforce standardized Python docstring section headings."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import TypeAlias, cast

LEGACY_HEADINGS: tuple[str, ...] = (
    "Purpose:",
    "Ties To:",
    "Side Effects:",
    "Raises:",
)

SEARCH_ROOTS: tuple[str, ...] = (
    "Chapter_Splitter",
    "scripts",
    "tests",
)

DocstringNode: TypeAlias = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


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
        Used by main to locate the Python source roots that require docstring validation.
    Why this exists:
        Docstring checks must behave consistently from any current working directory.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").exists():
        raise RuntimeError(
            "scripts.check_docstring_standards._repo_root could not find pyproject.toml"
        )
    return root


def _iter_python_files(root: Path) -> list[Path]:
    """Return Python files that should follow the docstring standard.

    Summary:
        Collect Python files under the tracked source, script, and test roots for validation.
    Inputs:
        - root: Repository root path.
    Outputs:
        - Sorted list of Python file paths.
    Side effects:
        Reads filesystem metadata.
    Error handling:
        Raises RuntimeError when an expected validation root is missing.
    Ties to other methods:
        Used by main to determine which files to parse.
    Why this exists:
        Centralizing file discovery keeps the validation scope explicit and reproducible.
    """
    files: list[Path] = []
    for relative_root in SEARCH_ROOTS:
        search_root = root / relative_root
        if not search_root.exists():
            raise RuntimeError(
                "scripts.check_docstring_standards._iter_python_files missing validation root: "
                f"{search_root}"
            )
        files.extend(sorted(search_root.rglob("*.py")))
    return files


def _is_relevant_node(node: ast.AST) -> bool:
    """Return whether an AST node should carry a standardized docstring.

    Summary:
        Limit validation to modules, functions, async functions, and classes because those are the
        documented Python units in this repository.
    Inputs:
        - node: AST node under evaluation.
    Outputs:
        - True when the node should be validated, otherwise False.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _validate_file_docstrings while walking parsed syntax trees.
    Why this exists:
        Keeping the target node set explicit avoids accidental under- or over-enforcement.
    """
    return isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)


def _node_label(path: Path, node: ast.AST) -> str:
    """Return a readable label for an AST node.

    Summary:
        Build stable error labels that identify the file and symbol requiring docstring fixes.
    Inputs:
        - path: Python file path.
        - node: AST node being reported.
    Outputs:
        - Human-readable validation label.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _validate_file_docstrings when building error messages.
    Why this exists:
        Actionable error output keeps repo-wide standards checks fast to fix.
    """
    relative_path = path.as_posix()
    if isinstance(node, ast.Module):
        return f"{relative_path}:module"
    node_name = getattr(node, "name", "<anonymous>")
    line = getattr(node, "lineno", 1)
    return f"{relative_path}:{line}:{node_name}"


def _validate_file_docstrings(root: Path, path: Path) -> list[str]:
    """Validate standardized docstring headings for one Python file.

    Summary:
        Parse one Python file and ensure docstrings do not use legacy heading names.
    Inputs:
        - root: Repository root path.
        - path: Python file path being validated.
    Outputs:
        - List of validation errors for the file.
    Side effects:
        Reads and parses source text from disk.
    Error handling:
        Returns structured validation errors for unreadable files, syntax errors, and legacy
        headings.
    Ties to other methods:
        Called by main for each discovered Python file.
    Why this exists:
        The repository standard only remains meaningful if it is enforced uniformly across the
        existing codebase.
    """
    relative_path = path.relative_to(root)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{relative_path.as_posix()}: failed to read file: {exc}"]

    try:
        tree = ast.parse(source, filename=str(relative_path))
    except SyntaxError as exc:
        return [
            f"{relative_path.as_posix()}:{exc.lineno}: syntax error during docstring check: "
            f"{exc.msg}"
        ]

    errors: list[str] = []
    for node in ast.walk(tree):
        if not _is_relevant_node(node):
            continue

        docstring_node = cast(DocstringNode, node)
        docstring = ast.get_docstring(docstring_node, clean=False)
        label = _node_label(relative_path, node)
        if docstring is None:
            continue

        if any(legacy_heading in docstring for legacy_heading in LEGACY_HEADINGS):
            errors.append(f"{label}: contains legacy docstring headings")

    return errors


def main() -> int:
    """Run docstring standards checks and return process exit code.

    Summary:
        Execute deterministic repository-wide validation that forbids legacy docstring section
        names.
    Inputs:
        - None.
    Outputs:
        - Process exit code (0 for success, 1 for validation failures).
    Side effects:
        Reads repository Python files and writes status to stdout and stderr.
    Error handling:
        Handles RuntimeError from repository discovery and reports actionable error details.
    Ties to other methods:
        Entry point that orchestrates file discovery and per-file docstring validation.
    Why this exists:
        Future pushes should not be able to regress method-level documentation consistency.
    """
    try:
        root = _repo_root()
        files = _iter_python_files(root)
    except RuntimeError as exc:
        print(f"docstring-standards: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in files:
        errors.extend(_validate_file_docstrings(root, path))

    if errors:
        print("docstring-standards failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("docstring-standards passed: legacy Python docstring headings are not present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
