#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${1:-$ROOT_DIR/.venv}"
PYTHON_BIN="$VENV_DIR/bin/python"

die() {
  echo "bootstrap-venv: $*" >&2
  exit 1
}

supports_project_python() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
}

if [[ -x "$PYTHON_BIN" ]]; then
  supports_project_python "$PYTHON_BIN" || die "$PYTHON_BIN must use Python 3.11 or newer"
  exit 0
fi

if [[ -e "$VENV_DIR" && ! -d "$VENV_DIR" ]]; then
  die "$VENV_DIR exists but is not a directory"
fi

for candidate in python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    candidate_path="$(command -v "$candidate")"
    if supports_project_python "$candidate_path"; then
      if [[ -d "$VENV_DIR" ]]; then
        echo "bootstrap-venv: repairing incomplete environment at $VENV_DIR"
        "$candidate_path" -m venv --clear "$VENV_DIR"
      else
        echo "bootstrap-venv: creating $VENV_DIR with $candidate_path"
        "$candidate_path" -m venv "$VENV_DIR"
      fi
      [[ -x "$PYTHON_BIN" ]] || die "virtual environment creation did not produce $PYTHON_BIN"
      exit 0
    fi
  fi
done

die "Python 3.11 or newer is required; install it and retry"
