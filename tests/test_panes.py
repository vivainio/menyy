from __future__ import annotations

from typing import Any

from menyy import panes


def test_kill_idle_shells_uses_herdr_when_available(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("TMUX", "also-present")
    monkeypatch.setattr(panes.herdr, "kill_idle_shells", lambda: calls.append("herdr"))
    monkeypatch.setattr(panes.tmux, "kill_idle_shells", lambda: calls.append("tmux"))

    panes.kill_idle_shells()

    assert calls == ["herdr"]


def test_kill_idle_shells_uses_tmux_outside_herdr(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.setenv("TMUX", "present")
    monkeypatch.setattr(panes.tmux, "kill_idle_shells", lambda: calls.append("tmux"))

    panes.kill_idle_shells()

    assert calls == ["tmux"]


def test_kill_idle_shells_requires_terminal_manager(monkeypatch: Any) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.delenv("TMUX", raising=False)

    panes.kill_idle_shells()
