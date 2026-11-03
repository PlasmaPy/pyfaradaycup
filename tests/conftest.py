"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _wide_plain_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make rich print plain text without wrapping lines.

    When printing to something other than a terminal, rich wraps lines
    at 80 columns unless ``COLUMNS`` is set, which would split long paths
    in messages that tests look for. ``FORCE_COLOR`` would add color
    codes, and ``NO_COLOR`` is removed so that tests run the same way
    everywhere.
    """
    monkeypatch.setenv("COLUMNS", "1000")
    for name in ("FORCE_COLOR", "NO_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE"):
        monkeypatch.delenv(name, raising=False)
