"""process_health reads the scheduler with `schtasks /fo csv`, parsed by the csv module.

MEASURED 2026-10-20 on the trading box: the PowerShell probe (Get-ScheduledTask, CIM underneath)
timed out at 45 s under load and the verbose schtasks fallback at 20 s, so every one of the 73
rows read SCHEDULER_UNMEASURED. `schtasks /query /fo csv` returns there in about 6 s. These pin
the new probe: brief inventory first, verbose run history second, both on the 45 s bound, and an
unread inventory still UNMEASURED -- never NOT_SCHEDULED, and an unread result never a clean 0.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("process_health_under_test",
                                               ROOT / "ops" / "process_health.py")
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

BRIEF = (
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\MT5-Gateway","20/10/2026 19:00:00","Running"\r\n'
    '"\\MT5-Hourly","20/10/2026 19:05:00","Ready"\r\n'
    '"\\MT5-Old","N/A","Disabled"\r\n'
    '"\\Odd, ""quoted"" name","N/A","Ready"\r\n'
    '\r\n'
    'Folder: \\Microsoft\\Windows\r\n'
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","N/A","Ready"\r\n'
)

VERBOSE = (
    '"HostName","TaskName","Next Run Time","Status","Logon Mode","Last Run Time","Last Result",'
    '"Author","Task To Run","Scheduled Task State"\r\n'
    '"BOX","\\MT5-Gateway","20/10/2026 19:00:00","Running","Interactive only",'
    '"20/10/2026 18:00:00","267009","quant","cmd /c ""a, b""","Enabled"\r\n'
    # a second trigger of the same task: schtasks /v prints the task again; first row wins
    '"BOX","\\MT5-Gateway","20/10/2026 19:30:00","Running","Interactive only",'
    '"20/10/2026 18:00:00","1","quant","cmd","Enabled"\r\n'
    '"BOX","\\MT5-Hourly","20/10/2026 19:05:00","Ready","Interactive only",'
    '"20/10/2026 18:05:00","-2147024894","quant","py","Enabled"\r\n'
    '"HostName","TaskName","Next Run Time","Status","Logon Mode","Last Run Time","Last Result",'
    '"Author","Task To Run","Scheduled Task State"\r\n'
    '"BOX","\\MT5-Old","N/A","Disabled","Interactive only","N/A","0","quant","py","Disabled"\r\n'
)


def _fake(monkeypatch: pytest.MonkeyPatch, brief: Any, verbose: Any) -> list[list[str]]:
    """Answer the two schtasks queries; an Exception instance is raised instead."""
    calls: list[list[str]] = []

    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        assert cmd[0] == "schtasks", f"the probe ran {cmd[0]!r}; it must be schtasks only"
        assert kw.get("timeout") == 45, kw
        answer = verbose if "/v" in cmd else brief
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(cmd, 0, answer, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    return calls


def test_the_timeout_is_kept_at_45_seconds() -> None:
    assert ph.SCHTASKS_TIMEOUT_S == 45


def test_brief_csv_parses_folders_quotes_and_drops_microsoft() -> None:
    rows = ph.parse_schtasks_csv(BRIEF)
    names = [r["TaskName"] for r in rows]
    assert names == ["\\MT5-Gateway", "\\MT5-Hourly", "\\MT5-Old", '\\Odd, "quoted" name']
    assert rows[2]["Status"] == "Disabled"


def test_verbose_csv_keeps_one_row_per_task_and_commas_in_commands() -> None:
    rows = {r["TaskName"]: r for r in ph.parse_schtasks_csv(VERBOSE)}
    assert set(rows) == {"\\MT5-Gateway", "\\MT5-Hourly", "\\MT5-Old"}
    assert rows["\\MT5-Gateway"]["Last Result"] == "267009"
    assert rows["\\MT5-Gateway"]["Task To Run"] == 'cmd /c "a, b"'


def test_both_queries_answer_and_the_run_history_is_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake(monkeypatch, BRIEF, VERBOSE)
    rows, status = ph._tasks()
    assert status == "OK schtasks"
    assert ["schtasks", "/query", "/fo", "csv"] in calls
    assert ["schtasks", "/query", "/fo", "csv", "/v"] in calls
    by = {r["TaskName"]: r for r in rows}
    assert by["\\MT5-Hourly"]["Last Result"] == "-2147024894"
    assert "ResultUnmeasured" not in by["\\MT5-Hourly"]
    # present in the inventory, absent from the verbose dump: its history is NOT read
    assert by['\\Odd, "quoted" name']["ResultUnmeasured"]


def _build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
           contracts: dict[str, tuple[str, int, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    (tmp_path / "fresh.json").write_text("{}", "utf-8")
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: dict(contracts))
    doc = ph.build()
    return doc, {r["name"]: r for r in doc["processes"]}


CONTRACTS = {"MT5-Hourly": ("fresh.json", 120, "hourly"),
             "MT5-Gateway": ("fresh.json", 120, "gateway"),
             "MT5-Vanished": ("fresh.json", 120, "deleted by hand")}


def test_full_read_judges_failures_and_absences(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    _fake(monkeypatch, BRIEF, VERBOSE)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert by["MT5-Hourly"]["verdict"] == "FAILING"       # 0x80070002, printed signed
    assert by["MT5-Gateway"]["verdict"] == "OK"           # 267009 = running
    assert by["MT5-Old"]["verdict"] == "DISABLED"
    assert by["MT5-Vanished"]["verdict"] == "NOT_SCHEDULED"
    assert doc["counts"].get("SCHEDULER_UNMEASURED", 0) == 0


def test_verbose_timeout_keeps_the_inventory_and_never_reads_a_clean_zero(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake(monkeypatch, BRIEF, subprocess.TimeoutExpired(["schtasks", "/v"], 45))
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert doc["scheduler_status"].startswith("OK schtasks (brief")
    assert "TimeoutExpired" in doc["scheduler_status"]
    # the inventory still judges: absent organ, disabled task
    assert by["MT5-Vanished"]["verdict"] == "NOT_SCHEDULED"
    assert by["MT5-Old"]["verdict"] == "DISABLED"
    # the result code was not read, and is not published as 0
    for name in ("MT5-Hourly", "MT5-Gateway"):
        assert by[name]["last_result_code"] is None
        assert by[name]["last_result"].startswith("UNMEASURED")
        assert by[name]["verdict"] == "OK" and "not read" in by[name]["why"]
    assert doc["counts"].get("SCHEDULER_UNMEASURED", 0) == 0


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired(["schtasks"], 45),
                                     FileNotFoundError("schtasks")])
def test_an_unread_inventory_stays_unmeasured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                       failure: BaseException) -> None:
    calls = _fake(monkeypatch, failure, VERBOSE)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert doc["scheduler_status"].startswith("UNMEASURED: ")
    assert type(failure).__name__ in doc["scheduler_status"]
    assert len(calls) == 1, "verbose must not be tried when the inventory itself failed"
    assert {r["verdict"] for r in by.values()} == {"SCHEDULER_UNMEASURED"}
    assert doc["status"] == "ATTENTION"


def test_a_nonzero_exit_is_unmeasured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "ERROR: Access is denied.")
    monkeypatch.setattr(ph.subprocess, "run", run)
    rows, status = ph._tasks()
    assert rows == [] and status.startswith("UNMEASURED: ") and "Access is denied" in status
