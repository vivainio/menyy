from __future__ import annotations

import json
import os
import subprocess
import sys
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
