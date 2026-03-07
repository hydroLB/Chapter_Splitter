"""Unit tests for system viewer utilities."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from chapter_splitter.core import IoError
from chapter_splitter.utils import open_path_in_default_viewer


def test_open_path_in_default_viewer_times_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that viewer launch enforces a timeout.

    Summary:
        Ensure open_path_in_default_viewer does not block longer than the configured timeout when
        the underlying viewer call hangs.
    Ties to other methods:
        Covers chapter_splitter.utils.viewer.open_path_in_default_viewer.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Temporary directory fixture.
    Outputs:
        - None.
    Side effects:
        Creates a temporary file and patches webbrowser.open.
    Error handling:
        - None.
    """
    target = tmp_path / "sample.pdf"
    target.write_bytes(b"%PDF-1.4\n%EOF\n")

    def _slow_open(_url: str, *, new: int, autoraise: bool) -> bool:  # noqa: ARG001
        time.sleep(0.05)
        return True

    def _slow_native(_path: Path, _location: str) -> bool:  # noqa: ARG001
        time.sleep(0.05)
        return True

    monkeypatch.setattr("chapter_splitter.utils.viewer._open_path_native", _slow_native)

    with pytest.raises(IoError):
        open_path_in_default_viewer(
            target,
            timeout_seconds=0.001,
            rate_limiter=None,
            location="tests.unit.test_viewer.test_open_path_in_default_viewer_times_out",
        )


def test_open_path_in_default_viewer_rejects_non_finite_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify non-finite viewer timeouts are rejected.

    Summary:
        Prevent hangs or unpredictable behavior when timeout values are NaN or infinity.
    Ties to other methods:
        Covers chapter_splitter.utils.viewer.open_path_in_default_viewer.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
        - tmp_path: Temporary directory fixture.
    Outputs:
        - None.
    Side effects:
        Creates a temporary file and patches webbrowser.open.
    Error handling:
        - None.
    """
    import math

    target = tmp_path / "sample.pdf"
    target.write_bytes(b"%PDF-1.4\n%EOF\n")

    def _open_should_not_run(_url: str, *, new: int, autoraise: bool) -> bool:  # noqa: ARG001
        raise AssertionError("webbrowser.open should not be called for invalid timeout values")

    def _native_should_not_run(_path: Path, _location: str) -> bool:  # noqa: ARG001
        raise AssertionError("_open_path_native should not be called for invalid timeout values")

    monkeypatch.setattr("chapter_splitter.utils.viewer.webbrowser.open", _open_should_not_run)
    monkeypatch.setattr("chapter_splitter.utils.viewer._open_path_native", _native_should_not_run)

    with pytest.raises(IoError):
        open_path_in_default_viewer(
            target,
            timeout_seconds=math.nan,
            rate_limiter=None,
            location="tests.unit.test_viewer.test_open_path_in_default_viewer_rejects_non_finite_timeout",
        )
    with pytest.raises(IoError):
        open_path_in_default_viewer(
            target,
            timeout_seconds=math.inf,
            rate_limiter=None,
            location="tests.unit.test_viewer.test_open_path_in_default_viewer_rejects_non_finite_timeout",
        )
