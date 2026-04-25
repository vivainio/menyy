from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

BUILTINS = ["defaults", "git", "tmux", "fs"]
DEFAULT_SEARCH_KEY = "/"


def load_builtin(name: str) -> dict[str, Any]:
    data = resources.files("menyy.builtins").joinpath(f"{name}.toml").read_bytes()
    return tomllib.loads(data.decode())


def config_path() -> Path:
    env = os.environ.get("MENYY_CONFIG")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(xdg).expanduser() / "menyy" / "actions.toml"


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def strip_hidden(tree: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in tree.items():
        if isinstance(v, dict):
            if v.get("hide"):
                continue
            result[k] = strip_hidden(v)
        else:
            result[k] = v
    return result


def load_config() -> tuple[dict[str, Any], str]:
    path = config_path()
    if not path.exists():
        merged: dict[str, Any] = {}
        for name in BUILTINS:
            merged = deep_merge(merged, load_builtin(name))
        return strip_hidden(merged), DEFAULT_SEARCH_KEY

    user = tomllib.loads(path.read_text())
    includes = user.pop("include", [])
    search_key = user.pop("search_key", DEFAULT_SEARCH_KEY)
    merged = {}
    for name in includes:
        merged = deep_merge(merged, load_builtin(name))
    merged = deep_merge(merged, user)
    return strip_hidden(merged), search_key


def is_menu(node: dict[str, Any]) -> bool:
    return any(isinstance(v, dict) for v in node.values())


def menu_entries(node: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    entries = []
    for k, v in node.items():
        if isinstance(v, dict):
            entries.append((k, v.get("label", k), v))
    entries.sort(key=lambda e: e[0])
    return entries


def fzf_select(lines: list[str], one_accept: bool, prompt: str) -> str | None:
    args = ["fzf", "--no-sort", "--prompt", prompt]
    if one_accept:
        args += [
            "--bind",
            "one:accept",
            "--delimiter",
            "\t",
            "--nth",
            "1",
        ]
    try:
        result = subprocess.run(
            args,
            input="\n".join(lines),
            stdout=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        sys.exit("menyy: fzf not found in PATH")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def flatten_leaves(
    node: dict[str, Any], path: list[str] = []
) -> list[tuple[list[str], dict[str, Any]]]:
    leaves = []
    for k, v in node.items():
        if not isinstance(v, dict):
            continue
        sub = path + [v.get("label", k)]
        if is_menu(v):
            leaves.extend(flatten_leaves(v, sub))
        elif "run" in v:
            leaves.append((sub, v))
    return leaves


def run_action(action: dict[str, Any]) -> int:
    env = {**os.environ, "MENYY": f"{sys.executable} -m menyy"}
    cmd = action["run"]
    if "prompt" in action:
        with open("/dev/tty") as tty_in, open("/dev/tty", "w") as tty_out:
            tty_out.write(f"{action['prompt']}: ")
            tty_out.flush()
            value = tty_in.readline().strip()
        if not value:
            return 130
        cmd = cmd.replace("{}", value)
    elif "pick" in action:
        pick = subprocess.run(
            action["pick"], shell=True, stdout=subprocess.PIPE, text=True, env=env
        )
        if pick.returncode == 130 or not pick.stdout.strip():
            return 130
        value = pick.stdout.strip()
        cmd = cmd.replace("{}", value)
    post = action.get("post")
    if post == "copy":
        result = subprocess.run(cmd, shell=True, env=env, stdout=subprocess.PIPE, text=True)
        if result.returncode == 0:
            copy_to_clipboard(result.stdout.rstrip("\n"))
        return result.returncode
    return subprocess.run(cmd, shell=True, env=env).returncode


def run_flat_search(root: dict[str, Any]) -> int:
    leaves = flatten_leaves(root)
    if not leaves:
        sys.exit("menyy: no actions available")
    lines = [" / ".join(path) for path, _ in leaves]
    selection = fzf_select(lines, one_accept=False, prompt="search> ")
    if selection is None:
        return 130
    for path, action in leaves:
        if " / ".join(path) == selection:
            return run_action(action)
    return 1


def navigate(node: dict[str, Any], search_key: str, top_level: bool) -> int:
    entries = menu_entries(node)
    lines = [f"{k}\t{label}" for k, label, _ in entries]
    if top_level:
        lines.append(f"{search_key}\tsearch all actions")
    selection = fzf_select(lines, one_accept=True, prompt="menyy> ")
    if selection is None:
        return 130
    key = selection.split("\t", 1)[0]
    if top_level and key == search_key:
        return run_flat_search(node)
    for k, _, sub in entries:
        if k == key:
            if is_menu(sub):
                return navigate(sub, search_key, top_level=False)
            if "run" in sub:
                return run_action(sub)
            sys.exit(f"menyy: entry '{k}' has neither submenu nor 'run'")
    return 1


def copy_to_clipboard(data: str) -> None:
    import shutil

    is_wsl = bool(os.environ.get("WSL_DISTRO_NAME"))
    candidates = [
        (["wl-copy"], None),
        (["xclip", "-selection", "clipboard"], None),
        (["xsel", "--clipboard", "--input"], None),
        (["pbcopy"], None),
        (["clip.exe"], None),
    ]
    if is_wsl:
        candidates = [c for c in candidates if c[0][0] == "clip.exe"] + [
            c for c in candidates if c[0][0] != "clip.exe"
        ]
    for argv, _ in candidates:
        if shutil.which(argv[0]):
            subprocess.run(argv, input=data, text=True, check=False)
            return
    if shutil.which("tmux"):
        subprocess.run(["tmux", "load-buffer", "-"], input=data, text=True, check=False)
        return
    sys.exit("menyy: no clipboard tool found (tried wl-copy, xclip, xsel, pbcopy, clip.exe, tmux)")


def cmd_copy() -> None:
    copy_to_clipboard(sys.stdin.read())


def cmd_list_builtins() -> None:
    for name in BUILTINS:
        print(name)


def cmd_show_config() -> None:
    import json

    tree, search_key = load_config()
    print(json.dumps({"search_key": search_key, "tree": tree}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="menyy")
    parser.add_argument("--list-builtins", action="store_true")
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--copy", action="store_true", help="read stdin and copy to clipboard")
    parser.add_argument("--tmux-save", action="store_true", help="snapshot all tmux sessions")
    parser.add_argument("--tmux-restore", action="store_true", help="restore tmux sessions from snapshot")
    args = parser.parse_args()

    if args.copy:
        cmd_copy()
        return
    if args.tmux_save:
        from menyy import tmux
        tmux.save()
        return
    if args.tmux_restore:
        from menyy import tmux
        tmux.restore()
        return
    if args.list_builtins:
        cmd_list_builtins()
        return
    if args.show_config:
        cmd_show_config()
        return

    tree, search_key = load_config()
    if not tree:
        sys.exit("menyy: empty menu (no config and no builtins?)")
    sys.exit(navigate(tree, search_key, top_level=True))
