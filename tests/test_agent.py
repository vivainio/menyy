from __future__ import annotations

from typing import Any

from menyy import agent


def test_restart_uses_herdr_when_available(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("TMUX", "also-present")
    monkeypatch.setattr(agent.herdr, "restart_agent", lambda: calls.append("herdr"))
    monkeypatch.setattr(agent.tmux, "restart_agent", lambda: calls.append("tmux"))

    agent.restart()

    assert calls == ["herdr"]


def test_restart_uses_herdr_active_pane_from_popup(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w1:p1")
    monkeypatch.setattr(agent.herdr, "restart_agent", lambda: calls.append("herdr"))

    agent.restart()

    assert calls == ["herdr"]


def test_restart_uses_tmux_outside_herdr(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.setenv("TMUX", "present")
    monkeypatch.setattr(agent.tmux, "restart_agent", lambda: calls.append("tmux"))

    agent.restart()

    assert calls == ["tmux"]


def test_restart_requires_terminal_manager(monkeypatch: Any) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.delenv("TMUX", raising=False)

    agent.restart()
