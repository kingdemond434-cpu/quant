"""ops/box/apply_installers.py: merged installers applied by the SYSTEM adopter, once per version,
never a credential installer (zuck 2026-11-17 19:56Z: no more one-time admin installs)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "apply_installers", ROOT / "ops/box/apply_installers.py"
)
assert _spec and _spec.loader
ai = importlib.util.module_from_spec(_spec)
sys.modules["apply_installers"] = ai
_spec.loader.exec_module(ai)

PLAIN = "param([switch]$IfMissing)\nRegister-ScheduledTask -TaskName X\n"


def _tree(tmp: Path, files: dict[str, str], rows: list[dict[str, Any]]) -> Path:
    for rel, text in files.items():
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text(text, "utf-8")
    (tmp / "m.json").write_text(json.dumps({"installers": rows}), "utf-8")
    return tmp


@pytest.fixture(autouse=True)
def _all_tracked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "_tracked", lambda rel: True)


def test_the_repo_manifest_rows_all_pass_on_this_tree() -> None:
    rows = ai.load_rows()
    assert rows, "the manifest lists at least one installer"
    for row in rows:
        assert ai.refusal(row) is None, row


@pytest.mark.parametrize(
    ("row", "text", "why"),
    [
        ({"path": "desks/mt5/scripts/x.sh", "args": [], "principal": "system"}, PLAIN, ".ps1"),
        ({"path": "libs/x.ps1", "args": [], "principal": "system"}, PLAIN, "outside"),
        ({"path": "ops/box/../x.ps1", "args": [], "principal": "system"}, PLAIN, ".ps1"),
        ({"path": "ops/box/x.ps1", "args": ["-IfMissing; calc"], "principal": "system"}, PLAIN,
         "switches"),
        ({"path": "ops/box/x.ps1", "args": ["C:\\x"], "principal": "system"}, PLAIN, "switches"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "admin"}, PLAIN, "principal"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "system"},
         "Start-Process Autologon64.exe\n", "credential"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "system"},
         "gh auth refresh -s workflow\n", "credential"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "system"},
         "$p = Read-Host | ConvertTo-SecureString\n", "credential"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "system"},
         "Get-Content data\\secrets\\k\n", "credential"),
        ({"path": "ops/box/x.ps1", "args": [], "principal": "desk_user"}, PLAIN, "-User"),
    ],
)  # fmt: skip
def test_refusals(tmp_path: Path, row: dict[str, Any], text: str, why: str) -> None:
    rel = (
        row["path"] if row["path"].endswith(".ps1") and ".." not in row["path"] else "ops/box/x.ps1"
    )
    _tree(tmp_path, {rel: text}, [row])
    got = ai.refusal(row, tmp_path)
    assert got and why in got, got


def test_an_untracked_installer_never_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "_tracked", lambda rel: False)
    _tree(tmp_path, {"ops/box/x.ps1": PLAIN}, [])
    assert "tracked" in (ai.refusal({"path": "ops/box/x.ps1", "args": [], "principal": "system"},
                                    tmp_path) or "")  # fmt: skip


def test_a_desk_user_installer_with_a_user_parameter_passes(tmp_path: Path) -> None:
    text = "param(\n    [string] $User = '',\n    [switch] $AtStartup\n)\n"
    _tree(tmp_path, {"ops/bridge/w.ps1": text}, [])
    row = {"path": "ops/bridge/w.ps1", "args": ["-AtStartup"], "principal": "desk_user"}
    assert ai.refusal(row, tmp_path) is None


def _fake_run(calls: list[list[str]], rc: int = 0) -> Any:
    def run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, rc, "ok", "")

    return run


def test_each_version_runs_once_and_a_new_version_runs_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {"path": "desks/mt5/scripts/i.ps1", "args": ["-IfMissing"], "principal": "system"}
    _tree(tmp_path, {"desks/mt5/scripts/i.ps1": PLAIN}, [row])
    ledger, calls = tmp_path / "logs" / "l.jsonl", []
    monkeypatch.setattr(ai.subprocess, "run", _fake_run(calls))
    first = ai.apply(ledger, tmp_path, tmp_path / "m.json")
    assert [r["action"] for r in first] == ["applied"] and first[0]["rc"] == 0
    assert calls[0][-2:] == [str(tmp_path / "desks/mt5/scripts/i.ps1"), "-IfMissing"]
    assert "-NonInteractive" in calls[0]
    again = ai.apply(ledger, tmp_path, tmp_path / "m.json")
    assert [r["action"] for r in again] == ["skip"] and len(calls) == 1
    (tmp_path / "desks/mt5/scripts/i.ps1").write_text(PLAIN + "# v2\n", "utf-8")
    third = ai.apply(ledger, tmp_path, tmp_path / "m.json")
    assert [r["action"] for r in third] == ["applied"] and len(calls) == 2


def test_a_failed_run_is_retried_next_adoption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {"path": "ops/box/i.ps1", "args": [], "principal": "system"}
    _tree(tmp_path, {"ops/box/i.ps1": PLAIN}, [row])
    ledger, calls = tmp_path / "l.jsonl", []
    monkeypatch.setattr(ai.subprocess, "run", _fake_run(calls, rc=1))
    ai.apply(ledger, tmp_path, tmp_path / "m.json")
    ai.apply(ledger, tmp_path, tmp_path / "m.json")
    assert len(calls) == 2


def test_refusals_are_ledgered_and_nothing_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {"path": "ops/box/i.ps1", "args": [], "principal": "system"}
    _tree(tmp_path, {"ops/box/i.ps1": "cmdkey /add:x\n"}, [row])
    ledger, calls = tmp_path / "l.jsonl", []
    monkeypatch.setattr(ai.subprocess, "run", _fake_run(calls))
    res = ai.apply(ledger, tmp_path, tmp_path / "m.json")
    assert res[0]["action"] == "refused" and not calls
    assert json.loads(ledger.read_text("utf-8").splitlines()[0])["action"] == "refused"


def test_a_desk_user_row_without_an_auto_logon_account_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {"path": "ops/bridge/w.ps1", "args": [], "principal": "desk_user"}
    _tree(tmp_path, {"ops/bridge/w.ps1": "param([string] $User)\n"}, [row])
    calls: list[list[str]] = []
    monkeypatch.setattr(ai.subprocess, "run", _fake_run(calls))
    monkeypatch.setattr(ai, "desk_user", lambda: None)
    res = ai.apply(tmp_path / "l.jsonl", tmp_path, tmp_path / "m.json")
    assert res[0]["action"] == "refused" and not calls
    monkeypatch.setattr(ai, "desk_user", lambda: "BOX\\desk")
    res = ai.apply(tmp_path / "l.jsonl", tmp_path, tmp_path / "m.json")
    assert res[0]["action"] == "applied" and calls[0][-2:] == ["-User", "BOX\\desk"]


def test_the_system_adopter_runs_the_apply_step_as_admin_only() -> None:
    heal = (ROOT / "ops" / "box" / "box_selfheal.ps1").read_text("utf-8")
    assert "{ Invoke-InstallerApply }" in heal
    body = heal.split("function Invoke-InstallerApply {", 1)[1].split("\n}\n", 1)[0]
    assert body.lstrip().startswith("if (-not (Test-RunnerIsAdmin))")
    assert "apply_installers.py" in body and "--apply" in body
