from __future__ import annotations

from typing import Any

from menyy import tmux


def test_restart_agent_resumes_codex_in_originating_pane(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    commands = iter(["codex", "bash"])
    monkeypatch.setenv("TMUX_PANE", "%7")
    monkeypatch.setattr(tmux, "_pane_command", lambda target: next(commands))
    monkeypatch.setattr(tmux.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda args, **kwargs: calls.append(args),
    )

    tmux.restart_agent()

    assert calls == [
        ["tmux", "send-keys", "-t", "%7", "C-c"],
        ["tmux", "send-keys", "-t", "%7", "C-d"],
        ["tmux", "send-keys", "-t", "%7", "codex resume --last", "Enter"],
    ]


def test_restart_agent_resumes_claude_in_originating_pane(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    commands = iter(["claude", "zsh"])
    monkeypatch.setenv("TMUX_PANE", "%8")
    monkeypatch.setattr(tmux, "_pane_command", lambda target: next(commands))
    monkeypatch.setattr(tmux.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda args, **kwargs: calls.append(args),
    )

    tmux.restart_agent()

    assert calls[-1] == ["tmux", "send-keys", "-t", "%8", "claude --continue", "Enter"]
