from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def snapshot_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(state).expanduser() / "menyy" / "tmux-snapshot.json"


def save() -> None:
    fmt = "#{session_name}\t#{window_index}\t#{window_name}\t#{pane_current_path}\t#{pane_current_command}"
    result = subprocess.run(
        ["tmux", "list-windows", "-a", "-F", fmt],
        stdout=subprocess.PIPE, text=True, check=True,
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
        exists = subprocess.run(
            ["tmux", "has-session", "-t", name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
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
