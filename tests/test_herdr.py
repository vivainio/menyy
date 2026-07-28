from __future__ import annotations

from typing import Any

from menyy import herdr


def test_workspace_launch_focuses_existing_workspace(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        herdr,
        "_workspaces",
        lambda: [{"workspace_id": "w1", "label": "menyy"}],
    )
    monkeypatch.setattr(herdr, "_run_json", lambda args: calls.append(args) or {"result": {}})

    herdr.workspace_launch("/home/v/menyy")

    assert calls == [["workspace", "focus", "w1"]]


def test_workspace_launch_creates_workspace_and_starts_claude(
    monkeypatch: Any,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(herdr, "_workspaces", lambda: [])
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or {
                "result": {
                    "root_pane": {"pane_id": "w1:p1"},
                }
            }
        ),
    )

    class ConversationCheck:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(herdr.subprocess, "run", lambda *args, **kwargs: ConversationCheck())

    herdr.workspace_launch("/home/v/menyy")

    assert calls == [
        [
            "workspace",
            "create",
            "--cwd",
            "/home/v/menyy",
            "--label",
            "menyy",
            "--focus",
        ],
        [
            "agent",
            "start",
            "menyy",
            "--kind",
            "claude",
            "--pane",
            "w1:p1",
        ],
    ]


def test_workspace_launch_detaches_agent_start_in_popup(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("MENYY_POPUP", "1")
    monkeypatch.setattr(herdr, "_workspaces", lambda: [])
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: {
            "result": {
                "root_pane": {"pane_id": "w1:p1"},
            }
        },
    )

    class ConversationCheck:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(herdr.subprocess, "run", lambda *args, **kwargs: ConversationCheck())
    monkeypatch.setattr(
        herdr.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append(args),
    )

    herdr.workspace_launch("/home/v/menyy")

    assert calls == [
        [
            "herdr",
            "agent",
            "start",
            "menyy",
            "--kind",
            "claude",
            "--pane",
            "w1:p1",
        ]
    ]
