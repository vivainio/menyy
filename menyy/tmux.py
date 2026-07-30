from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def workspace_launch(dir_: str | None = None) -> None:
    dir_ = dir_ or os.getcwd()
    name = os.path.basename(os.path.abspath(dir_))
    has = (
        subprocess.run(
            ["tmux", "has-session", "-t", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    if not has:
        cmd = "claude"
        check = subprocess.run(
            ["claude", "conversation", "list", "--limit", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if check.returncode == 0 and check.stdout.strip():
            cmd = "claude --continue"
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", dir_, "-n", name, cmd], check=False
        )
    if os.environ.get("TMUX"):
        subprocess.run(["tmux", "switch-client", "-t", name], check=False)
    else:
        os.execvp("tmux", ["tmux", "attach-session", "-t", name])


IDLE_SHELLS = {"bash", "zsh", "nu", "fish", "sh", "dash", "ksh"}


def kill_idle_shells() -> None:
    fmt = (
        "#{pane_id}\t#{pane_current_command}\t#{pane_in_mode}\t"
        "#{session_name}:#{window_index}.#{pane_index}"
    )
    result = subprocess.run(
        ["tmux", "list-panes", "-a", "-F", fmt],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    current = os.environ.get("TMUX_PANE")
    killed = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        pane_id, cmd, in_mode, label = parts
        if pane_id == current:
            continue
        if in_mode != "0":
            continue
        if cmd not in IDLE_SHELLS:
            continue
        subprocess.run(["tmux", "kill-pane", "-t", pane_id], check=False)
        print(f"killed {label} ({cmd})")
        killed += 1
    print(f"killed {killed} idle shell pane(s)")


def _pane_command(target: str) -> str:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", target, "#{pane_current_command}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "pane not found"
        sys.exit(f"menyy: tmux could not inspect pane {target}: {message}")
    return result.stdout.strip()


def _wait_for_shell(target: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while _pane_command(target) not in IDLE_SHELLS:
        if time.monotonic() >= deadline:
            sys.exit("menyy: agent did not exit after Ctrl+D")
        time.sleep(0.1)


def restart_agent() -> None:
    """Restart and resume the Codex or Claude agent in the originating pane."""
    target = os.environ.get("TMUX_PANE")
    if not target:
        sys.exit("menyy: TMUX_PANE is not set")

    kind = _pane_command(target)
    commands = {
        "codex": "codex resume --last",
        "claude": "claude --continue",
    }
    command = commands.get(kind)
    if command is None:
        sys.exit(f"menyy: pane {target} is not running Codex or Claude (found {kind or 'nothing'})")

    subprocess.run(["tmux", "send-keys", "-t", target, "C-c"], check=True)
    time.sleep(0.2)
    subprocess.run(["tmux", "send-keys", "-t", target, "C-d"], check=True)
    _wait_for_shell(target)
    subprocess.run(["tmux", "send-keys", "-t", target, command, "Enter"], check=True)


def snapshot_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(state).expanduser() / "menyy" / "tmux-snapshot.json"


def save() -> None:
    fmt = (
        "#{session_name}\t#{window_index}\t#{window_name}\t"
        "#{pane_current_path}\t#{pane_current_command}"
    )
    result = subprocess.run(
        ["tmux", "list-windows", "-a", "-F", fmt],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    sessions: dict[str, list[dict[str, Any]]] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        sess, idx, name, dir_, cmd = parts
        sessions.setdefault(sess, []).append(
            {"index": int(idx), "name": name, "dir": dir_, "cmd": cmd}
        )
    data = [{"name": s, "windows": w} for s, w in sessions.items()]
    path = snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"saved {len(data)} session(s) to {path}")


def restore() -> None:
    path = snapshot_path()
    if not path.exists():
        sys.exit(f"menyy: no snapshot at {path}")
    data = json.loads(path.read_text())
    for sess in data:
        name = sess["name"]
        exists = (
            subprocess.run(
                ["tmux", "has-session", "-t", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
        if exists:
            continue
        windows = sorted(sess["windows"], key=lambda w: w["index"])
        for i, w in enumerate(windows):
            launch = "claude --continue" if w["cmd"] == "claude" else ""
            args = ["-c", w["dir"], "-n", w["name"]]
            if i == 0:
                cmd = ["tmux", "new-session", "-d", "-s", name, *args]
            else:
                cmd = ["tmux", "new-window", "-t", f"{name}:", *args]
            if launch:
                cmd.append(launch)
            subprocess.run(cmd, check=False)
        print(f"restored {name} ({len(windows)} window(s))")
