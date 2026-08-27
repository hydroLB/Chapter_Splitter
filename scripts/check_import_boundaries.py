"""Enforce import boundary direction for chapter_splitter layers."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LayerRule:
    """Define an ordered layer with modules it owns."""

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
            "chapter_splitter.cli_commands",
            "chapter_splitter.ui",
            "chapter_splitter.__main__",
        ),
    ),
)

# The package root is metadata/public API glue rather than an architecture layer. Every other
# Python module must be owned by one of the layer rules above so new packages cannot bypass the
# checker merely because their name is unfamiliar.
UNCLASSIFIED_MODULE_EXCEPTIONS: frozenset[str] = frozenset(
    {"chapter_splitter", "chapter_splitter._version"}
)


def _repo_root() -> Path:
    """Return repository root path for boundary checks."""
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
    """Translate a Python file path into a module name."""
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
    """Resolve a relative import to an absolute module path."""
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
    """Collect chapter_splitter internal imports per module."""
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
    """Return the layer index for a module."""
    for idx, rule in enumerate(LAYER_RULES):
        for prefix in rule.module_prefixes:
            if module_name == prefix or module_name.startswith(prefix + "."):
                return idx
    return None


def _find_violations(imports: dict[str, set[str]]) -> list[str]:
    """Evaluate all imports against layering rules."""
    violations: list[str] = []
    for importer, imported_set in sorted(imports.items()):
        importer_layer = _layer_for_module(importer)
        if importer_layer is None:
            if importer not in UNCLASSIFIED_MODULE_EXCEPTIONS:
                violations.append(
                    f"{importer} is not assigned to an architecture layer; add a layer prefix "
                    "or an explicit exception"
                )
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
    """Run boundary checks and print violations."""
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
