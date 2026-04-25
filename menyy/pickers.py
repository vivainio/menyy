from __future__ import annotations

import os
import subprocess


def zoxide() -> str | None:
    """Pick a directory from zoxide; return absolute path or None on cancel."""
    listing = subprocess.run(
        ["zoxide", "query", "-l"],
        stdout=subprocess.PIPE, text=True, check=True,
    ).stdout
    home = os.path.expanduser("~")
    display = "\n".join(
        ("~" + line[len(home):]) if line.startswith(home) else line
        for line in listing.splitlines()
    )
    picked = subprocess.run(
        ["fzf", "--no-sort", "+i", "--prompt", "zoxide> "],
        input=display, stdout=subprocess.PIPE, text=True,
    )
    if picked.returncode != 0:
        return None
    selection = picked.stdout.strip()
    if not selection:
        return None
    if selection.startswith("~"):
        selection = home + selection[1:]
    return selection
