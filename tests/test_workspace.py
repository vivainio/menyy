from __future__ import annotations

from typing import Any

import pytest

from menyy import workspace


def test_launch_uses_herdr_when_available(monkeypatch: Any) -> None:
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("TMUX", "also-present")
    monkeypatch.setattr(
        workspace.herdr,
        "workspace_launch",
        lambda dir_: calls.append(("herdr", dir_)),
    )
    monkeypatch.setattr(
        workspace.tmux,
        "workspace_launch",
        lambda dir_: calls.append(("tmux", dir_)),
    )

    workspace.launch("/repo")

    assert calls == [("herdr", "/repo")]


def test_launch_uses_tmux_outside_herdr(monkeypatch: Any) -> None:
    calls: list[tuple[str, str | None]] = []
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.setenv("TMUX", "present")
    monkeypatch.setattr(
        workspace.tmux,
        "workspace_launch",
        lambda dir_: calls.append(("tmux", dir_)),
    )

    workspace.launch("/repo")

    assert calls == [("tmux", "/repo")]


def test_launch_requires_workspace_manager(monkeypatch: Any) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.delenv("TMUX", raising=False)

    with pytest.raises(SystemExit, match="requires Herdr or tmux"):
        workspace.launch("/repo")
