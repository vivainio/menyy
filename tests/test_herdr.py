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


def test_restart_agent_resumes_exact_codex_session(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w1:p1")
    monkeypatch.setenv("HERDR_PANE_ID", "popup:p1")
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or (
                {"result": {"process_info": {}}}
                if args[:2] == ["pane", "process-info"]
                else {
                    "result": {
                        "agent": {
                            "name": "worker",
                            "agent": "codex",
                            "pane_id": "w1:p1",
                            "agent_session": {"value": "codex-session"},
                        }
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: True)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert calls == [
        ["agent", "get", "w1:p1"],
        ["pane", "process-info", "--pane", "w1:p1"],
        ["agent", "send-keys", "w1:p1", "ctrl+c"],
        ["agent", "send-keys", "w1:p1", "ctrl+d"],
        [
            "agent",
            "start",
            "worker",
            "--kind",
            "codex",
            "--pane",
            "w1:p1",
            "--",
            "resume",
            "codex-session",
        ],
    ]


def test_restart_agent_resumes_exact_claude_session(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_PANE_ID", "w1:p2")
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or (
                {"result": {"process_info": {}}}
                if args[:2] == ["pane", "process-info"]
                else {
                    "result": {
                        "agent": {
                            "name": "reviewer",
                            "agent": "claude",
                            "pane_id": "w1:p2",
                            "agent_session": {"value": "claude-session"},
                        }
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: True)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert calls[-1] == [
        "agent",
        "start",
        "reviewer",
        "--kind",
        "claude",
        "--pane",
        "w1:p2",
        "--",
        "--resume",
        "claude-session",
    ]


def test_restart_agent_names_an_unmanaged_agent(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w11:p1")
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or (
                {"result": {"process_info": {}}}
                if args[:2] == ["pane", "process-info"]
                else {
                    "result": {
                        "agent": {
                            "agent": "codex",
                            "pane_id": "w11:p1",
                            "agent_session": {"value": "codex-session"},
                        }
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: True)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert calls[-1][2] == "codex-w11-p1"


def test_restart_agent_replaces_pane_when_agent_is_root_process(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w11:p1")

    def run_json(args: list[str]) -> dict[str, Any]:
        calls.append(args)
        if args[:2] == ["pane", "process-info"]:
            return {
                "result": {
                    "process_info": {
                        "shell_pid": 42,
                        "foreground_processes": [{"pid": 42, "name": "codex"}],
                    }
                }
            }
        if args[:2] == ["pane", "split"]:
            return {"result": {"pane": {"pane_id": "w11:p2"}}}
        return {
            "result": {
                "agent": {
                    "agent": "codex",
                    "pane_id": "w11:p1",
                    "cwd": "/repo",
                }
            }
        }

    monkeypatch.setattr(herdr, "_run_json", run_json)
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: True)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert [
        "pane",
        "split",
        "w11:p1",
        "--direction",
        "right",
        "--cwd",
        "/repo",
        "--no-focus",
    ] in calls
    assert calls[-1][calls[-1].index("--pane") + 1] == "w11:p2"


def test_restart_agent_falls_back_when_session_is_not_reported(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_PANE_ID", "w1:p1")
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or (
                {"result": {"process_info": {}}}
                if args[:2] == ["pane", "process-info"]
                else {
                    "result": {
                        "agent": {
                            "name": "worker",
                            "agent": "codex",
                            "pane_id": "w1:p1",
                        }
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: True)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert calls[-1][-2:] == ["resume", "--last"]


def test_restart_agent_does_not_send_eof_after_interrupt_exits_agent(
    monkeypatch: Any,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w1:p1")
    monkeypatch.setattr(
        herdr,
        "_run_json",
        lambda args: (
            calls.append(args)
            or (
                {"result": {"process_info": {}}}
                if args[:2] == ["pane", "process-info"]
                else {
                    "result": {
                        "agent": {
                            "name": "worker",
                            "agent": "codex",
                            "pane_id": "w1:p1",
                        }
                    }
                }
            )
        ),
    )
    monkeypatch.setattr(herdr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(herdr, "_agent_present", lambda target: False)
    monkeypatch.setattr(herdr, "_wait_for_agent_exit", lambda target: None)

    herdr.restart_agent()

    assert ["agent", "send-keys", "w1:p1", "ctrl+d"] not in calls


def test_kill_idle_shells_closes_only_idle_shell_panes(monkeypatch: Any) -> None:
    monkeypatch.setenv("HERDR_ACTIVE_PANE_ID", "w1:p1")
    monkeypatch.setattr(
        herdr,
        "_panes",
        lambda: [
            {"pane_id": "w1:p1", "terminal_title_stripped": "current"},
            {"pane_id": "w1:p2", "terminal_title_stripped": "shell"},
            {"pane_id": "w1:p3", "terminal_title_stripped": "claude"},
        ],
    )

    process_info = {
        "w1:p2": {"foreground_processes": [{"name": "bash"}]},
        "w1:p3": {"foreground_processes": [{"name": "claude"}]},
    }
    calls: list[list[str]] = []

    def fake_run_json(args: list[str]) -> dict[str, Any]:
        calls.append(args)
        if args[:2] == ["pane", "process-info"]:
            return {"result": {"process_info": process_info[args[3]]}}
        return {"result": {}}

    monkeypatch.setattr(herdr, "_run_json", fake_run_json)

    herdr.kill_idle_shells()

    assert ["pane", "process-info", "--pane", "w1:p1"] not in calls
    assert ["pane", "process-info", "--pane", "w1:p2"] in calls
    assert ["pane", "close", "w1:p2"] in calls
    assert ["pane", "close", "w1:p3"] not in calls
