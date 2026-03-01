"""Enforce import boundary direction for chapter_splitter layers."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LayerRule:
    """Define an ordered layer with modules it owns.

    Summary:
        Represent one architecture layer and the module prefixes that belong to it.
    Inputs:
        - name: Human-readable layer name.
        - module_prefixes: Tuple of fully-qualified module prefixes owned by the layer.
    Outputs:
        - None.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _layer_for_module and _find_violations.
    Why this exists:
        A structured rule model keeps boundary checks deterministic and easy to maintain.
    """

    name: str
    module_prefixes: tuple[str, ...]


LAYER_RULES: tuple[LayerRule, ...] = (
    LayerRule(name="domain", module_prefixes=("chapter_splitter.core",)),
    LayerRule(
        name="services",
        module_prefixes=(
            "chapter_splitter.config",
            "chapter_splitter.io",
            "chapter_splitter.observability",
            "chapter_splitter.pdf",
            "chapter_splitter.utils",
        ),
    ),
    LayerRule(
        name="interfaces",
        module_prefixes=(
            "chapter_splitter.app",
            "chapter_splitter.cli",
            "chapter_splitter.ui",
            "chapter_splitter.__main__",
        ),
    ),
)


def _repo_root() -> Path:
    """Return repository root path for boundary checks.

    Summary:
        Resolve the project root based on this script location.
    Inputs:
        - None.
    Outputs:
        - Path to the repository root.
    Side effects:
        Reads filesystem metadata.
    Error handling:
        Raises RuntimeError when script layout is unexpected.
    Ties to other methods:
        Used by main to locate the application package.
    Why this exists:
        Boundary checks should be runnable from any working directory.
    """
    script_path = Path(__file__).resolve()
    root = script_path.parents[1]
    package_root = root / "Chapter_Splitter" / "chapter_splitter"
    if not package_root.exists():
        raise RuntimeError(
            "scripts.check_import_boundaries._repo_root failed. Missing package root: "
            f"{package_root}"
        )
    return root


def _module_name_from_path(path: Path, package_root: Path) -> str:
    """Translate a Python file path into a module name.

    Summary:
        Convert package-relative file paths to dotted import module names.
    Inputs:
        - path: Python source file path.
        - package_root: Root directory of chapter_splitter package.
    Outputs:
        - Fully-qualified module name.
    Side effects:
        None.
    Error handling:
        Raises ValueError when path is outside package root.
    Ties to other methods:
        Used by _collect_internal_imports.
    Why this exists:
        Layer checks operate on module names rather than filesystem paths.
    """
    try:
        rel = path.relative_to(package_root)
    except ValueError as exc:
        raise ValueError(
            "scripts.check_import_boundaries._module_name_from_path requires a package-relative "
            f"path, got: {path}"
        ) from exc

    parts = rel.parts[:-1] if rel.name == "__init__.py" else rel.with_suffix("").parts
    if not parts:
        return "chapter_splitter"
    return "chapter_splitter." + ".".join(parts)


def _resolve_relative_module(
    *,
    importer: str,
    level: int,
    target: str | None,
) -> str:
    """Resolve a relative import to an absolute module path.

    Summary:
        Convert relative import components (`level`, `target`) into a fully-qualified module name.
    Inputs:
        - importer: Importing module name.
        - level: Relative import level from AST node.
        - target: Optional module target component from AST node.
    Outputs:
        - Fully-qualified module path.
    Side effects:
        None.
    Error handling:
        Raises ValueError when level exceeds importer package depth.
    Ties to other methods:
        Used by _collect_internal_imports.
    Why this exists:
        Accurate relative resolution is required to enforce boundaries reliably.
    """
    importer_parts = importer.split(".")
    if level > len(importer_parts):
        raise ValueError(
            "scripts.check_import_boundaries._resolve_relative_module received invalid level "
            f"{level} for importer {importer}"
        )
    base_parts = importer_parts[:-level]
    if target:
        base_parts.extend(target.split("."))
    return ".".join(base_parts)


def _collect_internal_imports(package_root: Path) -> dict[str, set[str]]:
    """Collect chapter_splitter internal imports per module.

    Summary:
        Parse package source files and build a mapping of module imports limited to internal
        chapter_splitter references.
    Inputs:
        - package_root: Root directory of chapter_splitter package.
    Outputs:
        - Mapping of importer module to imported module names.
    Side effects:
        Reads source files from disk.
    Error handling:
        Raises RuntimeError when files cannot be read or parsed.
    Ties to other methods:
        Used by _find_violations.
    Why this exists:
        Boundary checks need a deterministic import graph source.
    """
    imports: dict[str, set[str]] = {}
    for path in sorted(package_root.rglob("*.py")):
        module_name = _module_name_from_path(path, package_root)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                "scripts.check_import_boundaries._collect_internal_imports failed reading "
                f"{path}: {exc}"
            ) from exc
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise RuntimeError(
                "scripts.check_import_boundaries._collect_internal_imports failed parsing "
                f"{path}: {exc}"
            ) from exc

        module_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith("chapter_splitter"):
                        module_imports.add(name)
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    resolved = _resolve_relative_module(
                        importer=module_name,
                        level=node.level,
                        target=node.module,
                    )
                else:
                    resolved = node.module or ""
                if resolved.startswith("chapter_splitter"):
                    module_imports.add(resolved)
        imports[module_name] = module_imports
    return imports


def _layer_for_module(module_name: str) -> int | None:
    """Return the layer index for a module.

    Summary:
        Map a module name to the configured architecture layer index.
    Inputs:
        - module_name: Fully-qualified module name.
    Outputs:
        - Zero-based layer index or None when module is outside configured layers.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _find_violations.
    Why this exists:
        Boundary validation depends on comparing importer and imported layer positions.
    """
    for idx, rule in enumerate(LAYER_RULES):
        for prefix in rule.module_prefixes:
            if module_name == prefix or module_name.startswith(prefix + "."):
                return idx
    return None


def _find_violations(imports: dict[str, set[str]]) -> list[str]:
    """Evaluate all imports against layering rules.

    Summary:
        Detect imports where a lower layer depends on a higher layer.
    Inputs:
        - imports: Mapping of importer module to imported modules.
    Outputs:
        - Sorted list of violation messages.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by main to determine process exit status.
    Why this exists:
        Layer direction enforcement should fail quickly with actionable output.
    """
    violations: list[str] = []
    for importer, imported_set in sorted(imports.items()):
        importer_layer = _layer_for_module(importer)
        if importer_layer is None:
            continue
        for imported in sorted(imported_set):
            imported_layer = _layer_for_module(imported)
            if imported_layer is None:
                continue
            if importer_layer < imported_layer:
                importer_name = LAYER_RULES[importer_layer].name
                imported_name = LAYER_RULES[imported_layer].name
                violations.append(
                    f"{importer} ({importer_name}) must not import {imported} ({imported_name})"
                )
    return violations


def main() -> int:
    """Run boundary checks and print violations.

    Summary:
        Build the internal import graph and enforce configured layered dependencies.
    Inputs:
        - None.
    Outputs:
        - Process exit code (0 success, 1 violation, 2 runtime failure).
    Side effects:
        Reads source files and writes status output to stdout and stderr.
    Error handling:
        Converts runtime failures into clear stderr messages with non-zero exit status.
    Ties to other methods:
        Invokes _repo_root, _collect_internal_imports, and _find_violations.
    Why this exists:
        CI and local checks need a deterministic architecture contract gate.
    """
    try:
        root = _repo_root()
        imports = _collect_internal_imports(root / "Chapter_Splitter" / "chapter_splitter")
        violations = _find_violations(imports)
    except Exception as exc:
        print(f"Import boundary check failed to run: {exc}", file=sys.stderr)
        return 2

    if violations:
        print("Import boundary violations detected:")
        for item in violations:
            print(f" - {item}")
        return 1

    print("Import boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
