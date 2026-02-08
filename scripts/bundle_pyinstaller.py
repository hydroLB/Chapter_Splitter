"""Bundle the application into a standalone desktop binary via PyInstaller."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Build a standalone binary using PyInstaller.

    Purpose:
        Provide a single, repeatable command to bundle the GUI and/or CLI into distributable
        artifacts without requiring users to install Python.
    Ties To:
        Used for producing a true desktop app style install for local distribution.
    Inputs:
        - None.
    Outputs:
        - Exit code integer (0 success, non-zero failure).
    Side Effects:
        Invokes PyInstaller and writes build artifacts under the selected output directory.
    Raises:
        - RuntimeError: When PyInstaller is not available or the build fails.
    """
    parser = argparse.ArgumentParser(description="Bundle Chapter Splitter via PyInstaller.")
    parser.add_argument(
        "--target",
        choices=("gui", "cli", "both"),
        default="gui",
        help="Which artifacts to build (default: gui).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/pyinstaller"),
        help="Destination directory for built artifacts.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("build/pyinstaller"),
        help="Work directory used by PyInstaller.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Produce a single-file executable instead of a directory-based bundle.",
    )
    parser.add_argument(
        "--include-preview",
        action="store_true",
        help="Require and bundle the embedded preview dependency (PyMuPDF).",
    )
    args = parser.parse_args()

    if args.include_preview:
        _require_preview_dependency()

    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = (repo_root / args.output_dir).resolve()
    work_dir = (repo_root / args.work_dir).resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    gui_entry = repo_root / "scripts" / "pyinstaller_entry_gui.py"
    cli_entry = repo_root / "scripts" / "pyinstaller_entry_cli.py"

    if args.target in ("gui", "both"):
        _run_pyinstaller(
            entry=gui_entry,
            name="ChapterSplitter",
            windowed=True,
            onefile=args.onefile,
            dist_dir=dist_dir,
            work_dir=work_dir,
            include_preview=args.include_preview,
        )
    if args.target in ("cli", "both"):
        _run_pyinstaller(
            entry=cli_entry,
            name="chapter-splitter",
            windowed=False,
            onefile=args.onefile,
            dist_dir=dist_dir,
            work_dir=work_dir,
            include_preview=args.include_preview,
        )
    print(f"Bundle complete. Output: {dist_dir}")
    return 0


def _require_preview_dependency() -> None:
    """Ensure the optional preview dependency is installed.

    Purpose:
        Allow bundling to fail fast with a clear message when preview inclusion is requested.
    Ties To:
        Used by main when --include-preview is set.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Imports the fitz module to confirm availability.
    Raises:
        - RuntimeError: When PyMuPDF is not installed.
    """
    try:
        import fitz  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Preview bundling requires PyMuPDF. Install with: pip install -e '.[preview]'"
        ) from exc


def _run_pyinstaller(
    *,
    entry: Path,
    name: str,
    windowed: bool,
    onefile: bool,
    dist_dir: Path,
    work_dir: Path,
    include_preview: bool,
) -> None:
    """Invoke PyInstaller with consistent options.

    Purpose:
        Keep the bundling invocation deterministic and centralized so updates do not drift.
    Ties To:
        Used by main for each requested build target.
    Inputs:
        - entry: Entry script path.
        - name: Output artifact name.
        - windowed: Whether to build without a console window.
        - onefile: Whether to build a single-file executable.
        - dist_dir: Destination directory for outputs.
        - work_dir: Work directory for intermediate build output.
        - include_preview: Whether to include preview-related hidden imports.
    Outputs:
        - None.
    Side Effects:
        Runs a subprocess to execute PyInstaller.
    Raises:
        - RuntimeError: When the build fails or PyInstaller is unavailable.
    """
    if not entry.exists():
        raise RuntimeError(f"scripts.bundle_pyinstaller._run_pyinstaller missing entry: {entry}")

    cmd: list[str] = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    cmd.extend(["--name", name])
    cmd.extend(["--distpath", str(dist_dir)])
    cmd.extend(["--workpath", str(work_dir / name)])
    cmd.extend(["--specpath", str(work_dir / "spec")])
    cmd.extend(["--clean"])

    if windowed:
        cmd.append("--windowed")
    if onefile:
        cmd.append("--onefile")

    # Ensure the packaged default config is embedded so importlib.resources works in the bundle.
    cmd.extend(["--collect-data", "chapter_splitter.config"])

    if include_preview:
        cmd.extend(["--hidden-import", "fitz"])

    cmd.append(str(entry))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(
            "scripts.bundle_pyinstaller._run_pyinstaller failed to invoke PyInstaller. "
            "Install with: pip install -e '.[bundle]'"
        ) from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = "\n".join(part for part in (stdout, stderr) if part)
        raise RuntimeError(
            "scripts.bundle_pyinstaller._run_pyinstaller build failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"{details}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
