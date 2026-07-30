from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _run_json(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["herdr", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.exit("menyy: herdr not found in PATH")
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        sys.exit(f"menyy: herdr {' '.join(args)} failed: {message}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"menyy: herdr returned invalid JSON: {result.stdout.strip()}")
    if not isinstance(value, dict):
        sys.exit("menyy: herdr returned an unexpected response")
    return value


def _result(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        sys.exit("menyy: herdr response has no result object")
    return result


def _workspaces() -> list[dict[str, Any]]:
    workspaces = _result(_run_json(["workspace", "list"])).get("workspaces")
    if not isinstance(workspaces, list):
        sys.exit("menyy: herdr response has no workspace list")
    return [workspace for workspace in workspaces if isinstance(workspace, dict)]


def focus_workspace(workspace_id: str) -> None:
    _run_json(["workspace", "focus", workspace_id])


def _start_agent(args: list[str]) -> None:
    if not os.environ.get("MENYY_POPUP"):
        _run_json(args)
        return
    try:
        subprocess.Popen(
            ["herdr", *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        sys.exit("menyy: herdr not found in PATH")


def workspace_launch(dir_: str | None = None) -> None:
    """Focus a project workspace, or create it and start Claude."""
    cwd = str(Path(dir_ or os.getcwd()).expanduser().resolve())
    label = Path(cwd).name
    for workspace in _workspaces():
        if workspace.get("label") == label:
            workspace_id = workspace.get("workspace_id")
            if isinstance(workspace_id, str):
                focus_workspace(workspace_id)
                return

    created = _result(_run_json(["workspace", "create", "--cwd", cwd, "--label", label, "--focus"]))
    root_pane = created.get("root_pane")
    if not isinstance(root_pane, dict) or not isinstance(root_pane.get("pane_id"), str):
        sys.exit("menyy: herdr did not return the new workspace's root pane")

    agent_args = [
        "agent",
        "start",
        label,
        "--kind",
        "claude",
        "--pane",
        root_pane["pane_id"],
    ]
    check = subprocess.run(
        ["claude", "conversation", "list", "--limit", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if check.returncode == 0 and check.stdout.strip():
        agent_args.extend(["--", "--continue"])
    _start_agent(agent_args)


def _agent_present(target: str) -> bool:
    try:
        result = subprocess.run(
            ["herdr", "agent", "get", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        sys.exit("menyy: herdr not found in PATH")
    return result.returncode == 0


def _wait_for_agent_exit(target: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while _agent_present(target):
        if time.monotonic() >= deadline:
            sys.exit("menyy: agent did not exit after Ctrl+D")
        time.sleep(0.1)


def _resume_args(agent: dict[str, Any]) -> list[str]:
    kind = agent.get("agent")
    session = agent.get("agent_session")
    if kind == "codex":
        if isinstance(session, dict) and isinstance(session.get("value"), str):
            return ["resume", session["value"]]
        return ["resume", "--last"]
    if kind == "claude":
        if isinstance(session, dict) and isinstance(session.get("value"), str):
            return ["--resume", session["value"]]
        return ["--continue"]
    sys.exit(f"menyy: restart/resume is unsupported for {kind or 'unknown agent'}")


def _restart_name(agent: dict[str, Any], kind: str, pane_id: str) -> str:
    name = agent.get("name")
    if isinstance(name, str) and name:
        return name
    suffix = re.sub(r"[^a-z0-9_-]", "-", pane_id.lower()).strip("-")
    return f"{kind}-{suffix}"[:32]


def _restart_pane(agent: dict[str, Any], pane_id: str) -> str:
    process_info = _result(_run_json(["pane", "process-info", "--pane", pane_id])).get(
        "process_info"
    )
    if not isinstance(process_info, dict):
        return pane_id
    shell_pid = process_info.get("shell_pid")
    foreground = process_info.get("foreground_processes")
    agent_is_pane_root = (
        isinstance(shell_pid, int)
        and isinstance(foreground, list)
        and any(
            isinstance(process, dict) and process.get("pid") == shell_pid for process in foreground
        )
    )
    if not agent_is_pane_root:
        return pane_id

    cwd = agent.get("foreground_cwd") or agent.get("cwd") or os.getcwd()
    created = _result(
        _run_json(
            [
                "pane",
                "split",
                pane_id,
                "--direction",
                "right",
                "--cwd",
                str(cwd),
                "--no-focus",
            ]
        )
    ).get("pane")
    if not isinstance(created, dict) or not isinstance(created.get("pane_id"), str):
        sys.exit("menyy: Herdr did not return the replacement pane")
    return created["pane_id"]


def restart_agent() -> None:
    """Restart and resume the Codex or Claude agent in the originating pane."""
    target = os.environ.get("HERDR_ACTIVE_PANE_ID") or os.environ.get("HERDR_PANE_ID")
    if not target:
        sys.exit("menyy: Herdr did not report the originating pane")

    agent = _result(_run_json(["agent", "get", target])).get("agent")
    if not isinstance(agent, dict):
        sys.exit("menyy: Herdr returned no agent for the current pane")
    pane_id = agent.get("pane_id")
    kind = agent.get("agent")
    if not isinstance(pane_id, str) or not pane_id:
        sys.exit("menyy: current Herdr agent has no pane ID")
    if not isinstance(kind, str) or not kind:
        sys.exit("menyy: Herdr did not identify the current agent")
    name = _restart_name(agent, kind, pane_id)
    resume_args = _resume_args(agent)
    restart_pane = _restart_pane(agent, pane_id)

    _run_json(["agent", "send-keys", target, "ctrl+c"])
    time.sleep(1.0)
    if _agent_present(pane_id):
        _run_json(["agent", "send-keys", target, "ctrl+d"])
    _wait_for_agent_exit(pane_id)
    _run_json(
        [
            "agent",
            "start",
            name,
            "--kind",
            kind,
            "--pane",
            restart_pane,
            "--",
            *resume_args,
        ]
    )
