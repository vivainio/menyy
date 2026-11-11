from __future__ import annotations

import os
import subprocess
import sys
import time


def zoxide() -> str | None:
    """Pick a directory from zoxide; return absolute path or None on cancel."""
    listing = subprocess.run(
        ["zoxide", "query", "-l"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout
    home = os.path.expanduser("~")
    display = "\n".join(
        ("~" + line[len(home) :]) if line.startswith(home) else line
        for line in listing.splitlines()
    )
    picked = subprocess.run(
        ["fzf", "--no-sort", "+i", "--prompt", "zoxide> "],
        input=display,
        stdout=subprocess.PIPE,
        text=True,
    )
    if picked.returncode != 0:
        return None
    selection = picked.stdout.strip()
    if not selection:
        return None
    if selection.startswith("~"):
        selection = home + selection[1:]
    return selection


def my_prs() -> str | None:
    """Pick one of my open PRs in the current repo; return its number or None."""
    listing = subprocess.run(
        ["zh", "gh", "pr", "list", "--author", "@me", "--state", "open"],
        stdout=subprocess.PIPE,
        text=True,
    )
    if listing.returncode != 0:
        time.sleep(2)
        return None
    if not listing.stdout.strip():
        print("No open PRs authored by you in this repo.", file=sys.stderr)
        time.sleep(2)
        return None
    picked = subprocess.run(
        ["fzf", "--no-sort", "--prompt", "my PRs> "],
        input=listing.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )
    if picked.returncode != 0:
        return None
    number = picked.stdout.split("\t", 1)[0].strip()
    return number or None
