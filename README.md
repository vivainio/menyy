# menyy

A hotkey-driven nested menu backed by [fzf](https://github.com/junegunn/fzf), configured in TOML. Designed to live in a tmux popup and replace muscle-memory keystrokes for the dozens of small commands you'd otherwise alias.

## Install

```sh
pip install menyy
# or
uv tool install menyy
```

Requires `fzf` on `$PATH`.

## Use

Run `menyy`. Type a hotkey to enter a submenu or fire an action. Type `/` (configurable) to flat-search every action.

The picker is case-sensitive, so `s` and `S` are distinct hotkeys.

### tmux popup

Add to `~/.tmux.conf`:

```tmux
bind m display-popup -E -d "#{pane_current_path}" -e MENYY_POPUP=1 -y 0% -w 90% -h 80% "menyy"
```

`prefix m` opens menyy in a centered floating window. `MENYY_POPUP=1` is what makes `keep_open` actions pause for Enter so output stays visible — outside the popup it's a no-op.

## Configuration

User config lives at `$XDG_CONFIG_HOME/menyy/actions.toml` (default `~/.config/menyy/actions.toml`). If absent, all built-in modules are loaded; if present, only the modules listed in `include` are loaded.

```toml
include = ["git", "tmux", "fs"]
search_key = "/"

[g.p]
label = "git push"
run = "git push"
```

### Action fields

- **`label`** — display name in the menu (defaults to the key).
- **`run`** — shell command to execute. `{}` is replaced with the value from `pick`/`prompt`.
- **`call`** — Python function to invoke instead of shelling out. Format: `"module:function"`. The picked/prompted value (if any) is passed as the single positional arg.
- **`pick`** — shell command whose stdout becomes the value. Typically pipes into `fzf`.
- **`pick_call`** — Python function (`"module:function"`) whose return value becomes the picked value. Returning `None` or empty string cancels the action. Use when shell pipelines get unwieldy.
- **`prompt`** — shows a prompt on the tty and reads a line of input.
- **`post`** — post-action: currently `"copy"` captures stdout and sends it to the clipboard.
- **`keep_open`** — if `true` *and* `$MENYY_POPUP` is set, wait for Enter after the action runs. Use for informational commands (`git status`, `git log`) so the output stays visible when running inside a tmux popup. No-op outside the popup.
- **`hide`** — drop the entry from the menu (useful for shadowing built-ins).

A node is a submenu if any of its values is a table; otherwise it's an action.

### Examples

Run a shell command:

```toml
[g.s]
label = "git status"
run = "git status"
```

Pick from a list, then act on the selection:

```toml
[g.b]
label = "checkout branch"
pick = "git branch --format='%(refname:short)' | fzf"
run = "git checkout {}"
```

Prompt for free-form input:

```toml
[t.r]
label = "rename window"
prompt = "new window name"
run = "tmux rename-window {}"
```

Capture stdout to clipboard:

```toml
[f.c]
label = "copy file path"
pick = "find . -maxdepth 4 -type f | fzf"
run = "printf '%s' {}"
post = "copy"
```

Call Python directly (no shell):

```toml
[t.w]
label = "start/switch tmux workspace"
call = "menyy.tmux:workspace_launch"
```

Override or hide a built-in by re-defining the same key:

```toml
[t.k]
hide = true
```

## Built-in modules

- **defaults** — top-level fall-throughs.
- **git** — common git operations, branch picker, recent-branches.
- **tmux** — kill panes, switch session, save/restore session snapshot, workspace launch (with `claude --continue` for resumed sessions), zoxide-driven session start.
- **fs** — open file manager, copy file path (relative or absolute).

`menyy --list-builtins` lists them; `menyy --show-config` dumps the resolved tree.

## Tmux session snapshots

`t.S` snapshots all running sessions (windows + cwds) to `$XDG_STATE_HOME/menyy/tmux-snapshot.json`. `t.R` restores them, skipping any session that's already running, and re-launches `claude` windows with `--continue`.
