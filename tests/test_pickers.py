from __future__ import annotations

import subprocess
from typing import Any

from menyy import pickers


def _fake_run(listing: str, fzf_out: str = "", fzf_rc: int = 0, gh_rc: int = 0) -> Any:
    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["zh", "gh"]:
            return subprocess.CompletedProcess(cmd, gh_rc, listing, "")
        return subprocess.CompletedProcess(cmd, fzf_rc, fzf_out, "")

    return run


def test_my_prs_returns_number(monkeypatch: Any) -> None:
    line = "12\tFix thing\tfix-branch\tOPEN\n"
    monkeypatch.setattr(pickers.subprocess, "run", _fake_run(line, fzf_out=line))
    assert pickers.my_prs() == "12"


def test_my_prs_empty_prints_message(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(pickers.subprocess, "run", _fake_run(""))
    monkeypatch.setattr(pickers.time, "sleep", lambda _: None)
    assert pickers.my_prs() is None
    assert "No open PRs" in capsys.readouterr().err


def test_my_prs_gh_failure(monkeypatch: Any) -> None:
    monkeypatch.setattr(pickers.subprocess, "run", _fake_run("", gh_rc=1))
    monkeypatch.setattr(pickers.time, "sleep", lambda _: None)
    assert pickers.my_prs() is None


def test_my_prs_cancelled(monkeypatch: Any) -> None:
    line = "12\tFix\tb\tOPEN\n"
    monkeypatch.setattr(pickers.subprocess, "run", _fake_run(line, fzf_rc=130))
    assert pickers.my_prs() is None
