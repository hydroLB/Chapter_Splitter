"""Unit tests for runtime cancellation helpers."""

from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from types import FrameType

import pytest

from chapter_splitter.core.errors import CancellationError
from chapter_splitter.core.runtime import CancellationToken, register_signal_handlers


def test_cancellation_token_requires_reason() -> None:
    """Verify cancellation requires a reason.

    Purpose:
        Ensure cancellation diagnostics are always actionable.
    Ties To:
        Covers chapter_splitter.core.runtime.CancellationToken.cancel.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        None.
    Raises:
        - None.
    """
    token = CancellationToken()
    with pytest.raises(CancellationError):
        token.cancel("", "tests.unit.test_runtime")


def test_cancellation_token_check_raises_when_cancelled() -> None:
    """Verify check raises after cancellation is requested.

    Purpose:
        Provide a consistent cancellation guard across long-running operations.
    Ties To:
        Covers chapter_splitter.core.runtime.CancellationToken.check.
    Inputs:
        - None.
    Outputs:
        - None.
    Side Effects:
        Cancels the token.
    Raises:
        - None.
    """
    token = CancellationToken()
    token.cancel("stop", "tests.unit.test_runtime")
    assert token.is_cancelled() is True
    with pytest.raises(CancellationError):
        token.check("tests.unit.test_runtime")


def test_register_signal_handlers_installs_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify register_signal_handlers installs handlers and triggers shutdown.

    Purpose:
        Ensure CLI and GUI boundaries share a consistent shutdown path.
    Ties To:
        Covers chapter_splitter.core.runtime.register_signal_handlers.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches signal.signal to capture handlers.
    Raises:
        - None.
    """
    token = CancellationToken()
    logger = logging.getLogger("tests.unit.test_runtime")
    called: list[str] = []

    captured: dict[int, Callable[[int, FrameType | None], None]] = {}

    def fake_signal(sig: int, handler: Callable[[int, FrameType | None], None]) -> object:
        captured[sig] = handler
        return object()

    monkeypatch.setattr(signal, "signal", fake_signal)

    register_signal_handlers(
        token=token,
        logger=logger,
        on_shutdown=lambda: called.append("shutdown"),
        location="tests.unit.test_runtime",
    )
    assert signal.SIGINT in captured
    captured[signal.SIGINT](signal.SIGINT, None)
    assert token.is_cancelled() is True
    assert called == ["shutdown"]


def test_register_signal_handlers_surfaces_registration_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify registration errors surface as CancellationError.

    Purpose:
        Ensure failures to register signal handlers fail fast and clearly.
    Ties To:
        Covers exception handling in register_signal_handlers.
    Inputs:
        - monkeypatch: Pytest monkeypatch fixture.
    Outputs:
        - None.
    Side Effects:
        Patches signal.signal to raise.
    Raises:
        - None.
    """
    token = CancellationToken()
    logger = logging.getLogger("tests.unit.test_runtime")

    def fake_signal(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(signal, "signal", fake_signal)
    with pytest.raises(CancellationError):
        register_signal_handlers(
            token=token,
            logger=logger,
            on_shutdown=lambda: None,
            location="tests.unit.test_runtime",
        )
