"""Bundle the application into a standalone desktop binary via PyInstaller."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from contextlib import suppress
from pathlib import Path

GUI_WORKFLOW_MODULE = "chapter_splitter.ui.qt.workflow"
GUI_START_EVENT = "app_started"
MACOS_BUNDLE_IDENTIFIER = "io.github.hydrolb.chapter-splitter"


def main() -> int:
    """Build a standalone binary using PyInstaller."""
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
        "--skip-smoke-test",
        action="store_true",
        help="Skip post-build launch verification (intended only for constrained builders).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    project_version = _read_project_version(repo_root)
    dist_dir = (repo_root / args.output_dir).resolve()
    work_dir = (repo_root / args.work_dir).resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    gui_entry = repo_root / "scripts" / "pyinstaller_entry_gui.py"
    cli_entry = repo_root / "scripts" / "pyinstaller_entry_cli.py"

    if args.target in ("gui", "both"):
        artifact = _run_pyinstaller(
            entry=gui_entry,
            name="ChapterSplitter",
            windowed=True,
            onefile=args.onefile,
            dist_dir=dist_dir,
            work_dir=work_dir,
            hidden_imports=(GUI_WORKFLOW_MODULE,),
        )
        _finalize_macos_bundle(artifact, project_version=project_version)
        if not args.skip_smoke_test:
            _smoke_test_gui(artifact)
    if args.target in ("cli", "both"):
        artifact = _run_pyinstaller(
            entry=cli_entry,
            name="chapter-splitter",
            windowed=False,
            onefile=args.onefile,
            dist_dir=dist_dir,
            work_dir=work_dir,
        )
        if not args.skip_smoke_test:
            _smoke_test_cli(artifact)
    print(f"Bundle complete. Output: {dist_dir}")
    return 0


def _run_pyinstaller(
    *,
    entry: Path,
    name: str,
    windowed: bool,
    onefile: bool,
    dist_dir: Path,
    work_dir: Path,
    hidden_imports: tuple[str, ...] = (),
) -> Path:
    """Invoke PyInstaller with consistent options."""
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
    if sys.platform == "darwin" and windowed:
        cmd.extend(["--osx-bundle-identifier", MACOS_BUNDLE_IDENTIFIER])

    for module in hidden_imports:
        cmd.extend(["--hidden-import", module])

    # Ensure the packaged default config is embedded so importlib.resources works in the bundle.
    cmd.extend(["--collect-data", "chapter_splitter.config"])

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
    return _artifact_executable(
        name=name,
        windowed=windowed,
        onefile=onefile,
        dist_dir=dist_dir,
    )


def _artifact_executable(*, name: str, windowed: bool, onefile: bool, dist_dir: Path) -> Path:
    """Resolve PyInstaller's platform-specific executable path."""
    if sys.platform == "darwin" and windowed:
        return dist_dir / f"{name}.app" / "Contents" / "MacOS" / name
    executable_name = f"{name}.exe" if os.name == "nt" else name
    return dist_dir / executable_name if onefile else dist_dir / name / executable_name


def _read_project_version(repo_root: Path) -> str:
    """Read the canonical semantic version from project metadata."""
    pyproject_path = repo_root / "pyproject.toml"
    try:
        document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(
            "scripts.bundle_pyinstaller._read_project_version could not read project metadata: "
            f"{pyproject_path}"
        ) from exc
    project = document.get("project")
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(
            "scripts.bundle_pyinstaller._read_project_version missing [project].version in "
            f"{pyproject_path}"
        )
    return version.strip()


def _finalize_macos_bundle(executable: Path, *, project_version: str) -> None:
    """Apply canonical macOS metadata and restore the bundle's ad-hoc signature."""
    if sys.platform != "darwin":
        return
    app_bundle = executable.parents[2]
    info_path = app_bundle / "Contents" / "Info.plist"
    try:
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        info["CFBundleDisplayName"] = "PDF Chapter Splitter"
        info["CFBundleIdentifier"] = MACOS_BUNDLE_IDENTIFIER
        info["CFBundleShortVersionString"] = project_version
        info["CFBundleVersion"] = project_version
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream, sort_keys=True)
    except (OSError, plistlib.InvalidFileException) as exc:
        raise RuntimeError(
            "scripts.bundle_pyinstaller._finalize_macos_bundle could not update metadata: "
            f"{info_path}"
        ) from exc

    try:
        result = subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(
            "scripts.bundle_pyinstaller._finalize_macos_bundle could not invoke codesign"
        ) from exc
    if result.returncode != 0:
        details = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise RuntimeError(
            "scripts.bundle_pyinstaller._finalize_macos_bundle could not restore the ad-hoc "
            f"signature for {app_bundle}.\n{details}"
        )


def _require_artifact(executable: Path) -> None:
    """Reject builds that did not create the expected executable."""
    if not executable.is_file():
        raise RuntimeError(
            "scripts.bundle_pyinstaller._require_artifact expected executable was not created: "
            f"{executable}"
        )


def _smoke_test_cli(executable: Path) -> None:
    """Verify the bundled CLI can load its package and render help."""
    _require_artifact(executable)
    try:
        result = subprocess.run(
            [str(executable), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "scripts.bundle_pyinstaller._smoke_test_cli could not execute the bundled CLI: "
            f"{executable}"
        ) from exc
    if result.returncode != 0:
        details = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise RuntimeError(
            "scripts.bundle_pyinstaller._smoke_test_cli bundled CLI failed --help.\n"
            f"Executable: {executable}\n{details}"
        )


def _smoke_test_gui(executable: Path, *, startup_seconds: float = 30.0) -> None:
    """Verify the bundled GUI reaches its structured startup event and remains alive."""
    _require_artifact(executable)
    with tempfile.TemporaryDirectory(prefix="chapter-splitter-smoke-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        log_path = temp_dir / "startup.jsonl"
        output_path = temp_dir / "startup-output.txt"
        config_path = temp_dir / "smoke.toml"
        config_path.write_text(
            "[logging]\n"
            "console_enabled = true\n"
            "file_enabled = true\n"
            f"file_path = {json.dumps(str(log_path))}\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["CHAPTER_SPLITTER_CONFIG"] = str(config_path)
        env["QT_QPA_PLATFORM"] = "offscreen"
        started = False
        return_code: int | None = None
        with output_path.open("w", encoding="utf-8") as output_stream:
            try:
                process = subprocess.Popen(
                    [str(executable)],
                    stdout=output_stream,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    start_new_session=(os.name != "nt"),
                )
            except OSError as exc:
                raise RuntimeError(
                    "scripts.bundle_pyinstaller._smoke_test_gui could not execute the bundled "
                    f"GUI: {executable}"
                ) from exc

            deadline = time.monotonic() + startup_seconds
            try:
                while time.monotonic() < deadline:
                    if _log_contains_event(log_path, GUI_START_EVENT):
                        started = True
                        break
                    return_code = process.poll()
                    time.sleep(0.1)
            finally:
                _stop_process_tree(process)

        output = output_path.read_text(encoding="utf-8").strip()
        if not started:
            exit_detail = f" (exit {return_code})" if return_code is not None else ""
            raise RuntimeError(
                "scripts.bundle_pyinstaller._smoke_test_gui bundled GUI did not reach its startup "
                f"event{exit_detail}.\nExecutable: {executable}\n{output}"
            )


def _stop_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop the smoke-test process group, including a one-file bootloader child."""
    if os.name == "nt":
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=5)


def _log_contains_event(log_path: Path, expected_event: str) -> bool:
    """Return whether a JSON-lines log contains the expected structured event."""
    if not log_path.is_file():
        return False
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == expected_event:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
