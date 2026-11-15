from __future__ import annotations

import os
import sys

from menyy import herdr, herdr_app, tmux


def restart() -> None:
    """Restart and resume the agent in the pane that opened Menyy."""
    try:
        if herdr_app.is_active():
            herdr_app.restart_agent()
            return
        if os.environ.get("HERDR_ACTIVE_PANE_ID") or os.environ.get("HERDR_ENV"):
            herdr.restart_agent()
            return
        if os.environ.get("TMUX"):
            tmux.restart_agent()
            return
        sys.exit("menyy: agent restart requires Herdr or tmux")
    except SystemExit as error:
        print(error, file=sys.stderr)
