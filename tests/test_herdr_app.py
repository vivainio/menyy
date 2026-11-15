from __future__ import annotations

from typing import Any

from menyy import herdr_app


def test_is_active_requires_desktop_env(monkeypatch: Any) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.delenv("HERDR_ACTIVE_PANE_ID", raising=False)
    monkeypatch.setenv("HC_TERMINAL_ID", "t1")
    assert herdr_app.is_active()
    monkeypatch.setenv("HERDR_ENV", "1")
    assert not herdr_app.is_active()


def test_workspace_launch_selects_existing_space(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(herdr_app, "_spaces", lambda: [{"id": "sp1", "folder": "/repo/menyy"}])
    monkeypatch.setattr(herdr_app, "_app", lambda args: calls.append(args) or {})

    herdr_app.workspace_launch("/repo/menyy")

    assert calls == [["do", "space.select", "--id", "sp1"]]


def test_workspace_launch_creates_space(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(herdr_app, "_spaces", lambda: [])
    monkeypatch.setattr(herdr_app, "_app", lambda args: calls.append(args) or {})

    class NoConversation:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(herdr_app.subprocess, "run", lambda *a, **k: NoConversation())

    herdr_app.workspace_launch("/repo/menyy")

    assert calls == [
        [
            "do",
            "space.new",
            "--name",
            "menyy",
            "--folder",
            "/repo/menyy",
            "--argv",
            '["claude"]',
        ]
    ]


def test_kill_idle_shells_closes_only_idle_panes(monkeypatch: Any) -> None:
    app_calls: list[list[str]] = []
    monkeypatch.setenv("HC_TERMINAL_ID", "t1")
    terminals = [
        {"address": "t1", "state": "live"},
        {"address": "t2", "state": "live"},
        {"address": "t3", "state": "live"},
        {"address": "t4", "state": "live", "status": "working"},
    ]
    foreground = {"t2": "/opt/homebrew/bin/nu", "t3": "vim"}

    def fake_app(args: list[str]) -> Any:
        app_calls.append(args)
        return {"agent": "t1"} if args == ["status"] else {}

    def fake_hc(args: list[str]) -> Any:
        if args[0] == "ls":
            return {"terminals": terminals}
        return {"foreground": {"argv": [foreground[args[1]]]}}

    monkeypatch.setattr(herdr_app, "_app", fake_app)
    monkeypatch.setattr(herdr_app, "_hc", fake_hc)
    monkeypatch.setattr(herdr_app, "_close_terminal", lambda address: app_calls.append([address]))

    herdr_app.kill_idle_shells()

    assert ["t2"] in app_calls
    assert [c for c in app_calls if c[0] in ("t1", "t3", "t4")] == []


def test_close_terminal_closes_sole_space_with_confirmation(monkeypatch: Any) -> None:
    calls: list[list[str]] = []
    spaces = [
        {"id": "sp1", "tabs": [{"terminals": [{"terminal": "t1", "pane": "p1"}]}]},
        {
            "id": "sp2",
            "tabs": [
                {"terminals": [{"terminal": "t2", "pane": "p2"}, {"terminal": "t3", "pane": "p3"}]}
            ],
        },
    ]
    monkeypatch.setattr(herdr_app, "_spaces", lambda: spaces)
    monkeypatch.setattr(herdr_app, "_app", lambda args: calls.append(args) or {})

    herdr_app._close_terminal("t1")
    herdr_app._close_terminal("t3")

    assert calls == [
        ["do", "space.close", "--id", "sp1", "--confirmed", "true"],
        ["do", "pane.close", "--pane", "p3"],
    ]
