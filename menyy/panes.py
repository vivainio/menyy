from __future__ import annotations

import os
import sys

from menyy import herdr, tmux


def kill_idle_shells() -> None:
    """Kill panes that are running only an idle shell, using the active terminal manager."""
    try:
        if os.environ.get("HERDR_ENV"):
            herdr.kill_idle_shells()
            return
        if os.environ.get("TMUX"):
            tmux.kill_idle_shells()
            return
        sys.exit("menyy: kill idle shells requires Herdr or tmux")
    except SystemExit as error:
        print(error, file=sys.stderr)
