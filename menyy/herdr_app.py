"""Herdr desktop app backend: spaces/tabs via `herdr-app`, terminals via `hc`."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from menyy.tmux import IDLE_SHELLS

RESUME_COMMANDS = {
    "claude-code": "claude --continue",
    "codex": "codex resume --last",
}


def is_active() -> bool:
    """True in the desktop app; a classic Herdr running inside it takes precedence."""
    classic = os.environ.get("HERDR_ENV") or os.environ.get("HERDR_ACTIVE_PANE_ID")
    return bool(os.environ.get("HC_TERMINAL_ID")) and not classic


def _run(tool: str, args: list[str]) -> Any:
    try:
        result = subprocess.run([tool, *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        sys.exit(f"menyy: {tool} not found in PATH")
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        sys.exit(f"menyy: {tool} {' '.join(args)} failed: {message}")
    out = result.stdout.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"menyy: {tool} returned invalid JSON: {out}")


def _app(args: list[str]) -> Any:
    return _run("herdr-app", args)


def _hc(args: list[str]) -> Any:
    return _run("hc", [*args, "--json"])


def _spaces() -> list[dict[str, Any]]:
    spaces = _app(["ls"]).get("spaces")
    if not isinstance(spaces, list):
        sys.exit("menyy: herdr-app returned no space list")
    return [space for space in spaces if isinstance(space, dict)]


def workspace_launch(dir_: str | None = None) -> None:
    """Select the space for a project folder, or create it and start Claude."""
    cwd = str(Path(dir_ or os.getcwd()).expanduser().resolve())
    for space in _spaces():
        folder = space.get("folder")
        if isinstance(folder, str) and Path(folder).expanduser().resolve() == Path(cwd):
            _app(["do", "space.select", "--id", str(space["id"])])
            return

    argv = ["claude"]
    check = subprocess.run(
        ["claude", "conversation", "list", "--limit", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if check.returncode == 0 and check.stdout.strip():
        argv.append("--continue")
    _app(
        [
            "do",
            "space.new",
            "--name",
            Path(cwd).name,
            "--folder",
            cwd,
            "--argv",
            json.dumps(argv),
        ]
    )


def _protected_terminals() -> set[str]:
    protected = {os.environ.get("HC_TERMINAL_ID", "")}
    focused = _app(["status"]).get("agent")
    if isinstance(focused, str):
        protected.add(focused)
    return protected


def _close_terminal(address: str) -> None:
    """Close a terminal's pane, or its whole space when it is the space's last terminal."""
    for space in _spaces():
        tabs = space.get("tabs", [])
        terminals = [t for tab in tabs for t in tab.get("terminals", [])]
        for terminal in terminals:
            if terminal.get("terminal") != address:
                continue
            if len(terminals) == 1:
                _app(["do", "space.close", "--id", str(space["id"]), "--confirmed", "true"])
            else:
                _app(["do", "pane.close", "--pane", str(terminal["pane"])])
            return
    _hc(["kill", address])


def _foreground_name(info: dict[str, Any]) -> str | None:
    foreground = info.get("foreground")
    if not isinstance(foreground, dict):
        return None
    argv = foreground.get("argv")
    if isinstance(argv, list) and argv and isinstance(argv[0], str):
        return Path(argv[0]).name
    name = foreground.get("name")
    return name if isinstance(name, str) else None


def kill_idle_shells() -> None:
    protected = _protected_terminals()
    terminals = _hc(["ls"]).get("terminals", [])
    killed = 0
    for terminal in terminals:
        address = terminal.get("address")
        if not isinstance(address, str) or address in protected:
            continue
        if terminal.get("state") != "live" or terminal.get("status"):
            continue
        try:
            name = _foreground_name(_hc(["get", address]))
            if name not in IDLE_SHELLS:
                continue
            _close_terminal(address)
            killed += 1
            print(f"killed {terminal.get('where') or address} ({name})")
        except SystemExit as error:
            print(f"skipped {address}: {error.code}", file=sys.stderr)
    print(f"killed {killed} idle shell pane(s)")


def _wait_for_shell(address: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while _foreground_name(_hc(["get", address])) not in IDLE_SHELLS:
        if time.monotonic() >= deadline:
            sys.exit("menyy: agent did not exit")
        time.sleep(0.2)


def restart_agent() -> None:
    """Exit the agent in the focused terminal and resume it."""
    target = _app(["status"]).get("agent") or os.environ.get("HC_TERMINAL_ID")
    if not isinstance(target, str) or not target:
        sys.exit("menyy: Herdr did not report the originating terminal")
    info = _hc(["get", target])
    status = info.get("status")
    app = status.get("app") if isinstance(status, dict) else None
    command = RESUME_COMMANDS.get(app) if isinstance(app, str) else None
    if command is None:
        sys.exit(f"menyy: restart/resume is unsupported for {app or 'unknown agent'}")

    _hc(["keys", target, "ctrl+c"])
    time.sleep(1.0)
    if _foreground_name(_hc(["get", target])) not in IDLE_SHELLS:
        _hc(["keys", target, "ctrl+d"])
    _wait_for_shell(target)
    _hc(["send", target, command])
