"""Enforce standardized Python docstring section headings."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import TypeAlias, cast

BOILERPLATE_HEADINGS: tuple[str, ...] = (
    "Purpose:",
    "Ties To:",
    "Side Effects:",
    "Raises:",
    "Summary:",
    "Ties to other methods:",
    "Inputs:",
    "Outputs:",
    "Side effects:",
    "Error handling:",
    "Why this exists:",
)

SEARCH_ROOTS: tuple[str, ...] = (
    "Chapter_Splitter",
    "scripts",
    "tests",
)

DocstringNode: TypeAlias = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _repo_root() -> Path:
    """Return repository root path."""
    root = Path(__file__).resolve().parents[1]
    if not (root / "pyproject.toml").exists():
        raise RuntimeError(
            "scripts.check_docstring_standards._repo_root could not find pyproject.toml"
        )
    return root


def _iter_python_files(root: Path) -> list[Path]:
    """Return Python files that should follow the docstring standard."""
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
    """Return whether an AST node should carry a standardized docstring."""
    return isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)


def _node_label(path: Path, node: ast.AST) -> str:
    """Return a readable label for an AST node."""
    relative_path = path.as_posix()
    if isinstance(node, ast.Module):
        return f"{relative_path}:module"
    node_name = getattr(node, "name", "<anonymous>")
    line = getattr(node, "lineno", 1)
    return f"{relative_path}:{line}:{node_name}"


def _validate_file_docstrings(root: Path, path: Path) -> list[str]:
    """Validate standardized docstring headings for one Python file."""
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

        if any(heading in docstring for heading in BOILERPLATE_HEADINGS):
            errors.append(f"{label}: contains boilerplate docstring headings")

    return errors


def main() -> int:
    """Run docstring standards checks and return process exit code."""
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

    print("docstring-standards passed: boilerplate Python docstring headings are not present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
