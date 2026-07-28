from __future__ import annotations

import os
import sys

from menyy import herdr, tmux


def launch(dir_: str | None = None) -> None:
    """Launch a workspace using the active terminal workspace manager."""
    if os.environ.get("HERDR_ENV"):
        herdr.workspace_launch(dir_)
        return
    if os.environ.get("TMUX"):
        tmux.workspace_launch(dir_)
        return
    sys.exit("menyy: workspace launch requires Herdr or tmux")
