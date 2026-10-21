"""process_health reads the scheduler with `schtasks /fo csv`, parsed by the csv module.

MEASURED 2026-10-20 on the trading box: the PowerShell probe (Get-ScheduledTask, CIM underneath)
timed out at 45 s under load and the verbose schtasks fallback at 20 s, so every one of the 73
rows read SCHEDULER_UNMEASURED. `schtasks /query /fo csv` returns there in about 6 s. These pin
the new probe: brief inventory first, verbose run history second, both on the 45 s bound, and an
unread inventory still UNMEASURED -- never NOT_SCHEDULED, and an unread result never a clean 0.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_under_test", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

BRIEF = (
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\MT5-Gateway","20/10/2026 19:00:00","Running"\r\n'
    '"\\MT5-Hourly","20/10/2026 19:05:00","Ready"\r\n'
    '"\\MT5-Old","N/A","Disabled"\r\n'
    '"\\Odd, ""quoted"" name","N/A","Ready"\r\n'
    "\r\n"
    "Folder: \\Microsoft\\Windows\r\n"
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
        assert kw.get("timeout") == (90 if "/v" in cmd else 45), kw
        answer = verbose if "/v" in cmd else brief
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(cmd, 0, answer, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    return calls


def test_the_timeout_is_kept_at_45_seconds() -> None:
    assert ph.SCHTASKS_TIMEOUT_S == 45


def test_the_verbose_query_has_its_own_90_second_bound() -> None:
    # Measured 28.3 s for the verbose read on the trading box (2026-10-20); 45 s was under 1.6x.
    assert ph.SCHTASKS_VERBOSE_TIMEOUT_S == 90


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


def _build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, contracts: dict[str, tuple[str, int, str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    (tmp_path / "fresh.json").write_text("{}", "utf-8")
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: dict(contracts))
    doc = ph.build()
    return doc, {r["name"]: r for r in doc["processes"]}


CONTRACTS = {
    "MT5-Hourly": ("fresh.json", 120, "hourly"),
    "MT5-Gateway": ("fresh.json", 120, "gateway"),
    "MT5-Vanished": ("fresh.json", 120, "deleted by hand"),
}


def test_full_read_judges_failures_and_absences(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake(monkeypatch, BRIEF, VERBOSE)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert by["MT5-Hourly"]["verdict"] == "FAILING"  # 0x80070002, printed signed
    assert by["MT5-Gateway"]["verdict"] == "OK"  # 267009 = running
    assert by["MT5-Old"]["verdict"] == "DISABLED"
    assert by["MT5-Vanished"]["verdict"] == "NOT_SCHEDULED"
    assert doc["counts"].get("SCHEDULER_UNMEASURED", 0) == 0


def test_verbose_timeout_keeps_the_inventory_and_never_reads_a_clean_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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


@pytest.mark.parametrize(
    "failure", [subprocess.TimeoutExpired(["schtasks"], 45), FileNotFoundError("schtasks")]
)
def test_an_unread_inventory_stays_unmeasured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: BaseException
) -> None:
    calls = _fake(monkeypatch, failure, VERBOSE)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert doc["scheduler_status"].startswith("UNMEASURED: ")
    assert type(failure).__name__ in doc["scheduler_status"]
    assert len(calls) == 1, "verbose must not be tried when the inventory itself failed"
    assert {r["verdict"] for r in by.values()} == {"SCHEDULER_UNMEASURED"}
    assert doc["status"] == "UNMEASURED"


def test_a_nonzero_exit_is_unmeasured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "ERROR: Access is denied.")

    monkeypatch.setattr(ph.subprocess, "run", run)
    rows, status = ph._tasks()
    assert rows == [] and status.startswith("UNMEASURED: ") and "Access is denied" in status


# AUDIT HOLD 2026-10-14 (PUBLISH_SYNC_SCHTASKS_55cd0c44a): output schtasks printed but this
# parser could not read was returned as [], which `_tasks()` reported as "OK schtasks" and
# `build()` then turned into NOT_SCHEDULED for every contracted organ. Each shape probed there
# is pinned below as UNMEASURED.

GERMAN_BRIEF = (
    '"Aufgabenname","Nächste Laufzeit","Status"\r\n'
    '"\\MT5-Gateway","20.10.2026 19:00:00","Wird ausgeführt"\r\n'
)
ACCESS_LEVEL_INFO = (
    "INFO: There are no scheduled tasks presently available at your access level.\r\n"
)
MICROSOFT_ONLY = (
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","N/A","Ready"\r\n'
)


@pytest.mark.parametrize(
    "brief, needle",
    [
        (GERMAN_BRIEF, "no TaskName header"),
        (ACCESS_LEVEL_INFO, "no TaskName header"),
        (MICROSOFT_ONLY, "no non-Microsoft task"),
    ],
    ids=["localised-header", "access-level-info-at-exit-0", "zero-non-microsoft-rows"],
)
def test_an_unparseable_or_empty_inventory_is_unmeasured_not_unscheduled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, brief: str, needle: str
) -> None:
    calls = _fake(monkeypatch, brief, VERBOSE)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert doc["scheduler_status"].startswith("UNMEASURED: ")
    assert needle in doc["scheduler_status"]
    assert len(calls) == 1, "verbose must not be tried when the inventory itself was unread"
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0
    assert {r["verdict"] for r in by.values()} == {"SCHEDULER_UNMEASURED"}
    assert doc["status"] == "UNMEASURED"


def test_the_parser_refuses_text_with_no_header_and_accepts_empty_text() -> None:
    with pytest.raises(ph.SchtasksUnreadable):
        ph.parse_schtasks_csv(ACCESS_LEVEL_INFO)
    assert ph.parse_schtasks_csv("") == []
    assert ph.parse_schtasks_csv(MICROSOFT_ONLY) == []


def test_a_verbose_dump_without_last_result_is_unmeasured_not_a_clean_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    for rec in csv.reader(io.StringIO(VERBOSE)):
        writer.writerow([c for i, c in enumerate(rec) if i != 6])  # drop "Last Result"
    no_result = buf.getvalue()
    assert "Last Result" not in no_result and "Last Run Time" in no_result
    _fake(monkeypatch, BRIEF, no_result)
    doc, by = _build(monkeypatch, tmp_path, CONTRACTS)
    assert doc["scheduler_status"].startswith("OK schtasks (brief")
    assert "lacks Last Result" in doc["scheduler_status"]
    for name in ("MT5-Hourly", "MT5-Gateway"):
        assert by[name]["last_result_code"] is None
        assert by[name]["last_result"].startswith("UNMEASURED")


@pytest.mark.parametrize("raw", [None, "", "  ", "n/a", "N/A", "Nicht zutreffend", "1.0"])
def test_an_unreadable_result_code_is_none_never_zero(raw: Any) -> None:
    assert ph._normalise_code(raw) is None


@pytest.mark.parametrize(
    "raw, code",
    [
        ("0x1", 1),
        ("0x0", 0),
        ("0x800710E0", 0x800710E0),
        ("-2147020576", 0x800710E0),
        ("267009", 267009),
    ],
)
def test_hex_and_signed_codes_read_as_check_desk_health_reads_them(raw: str, code: int) -> None:
    assert ph._normalise_code(raw) == code


@pytest.mark.parametrize(
    "last_result", [None, "", "N/A", "1.0"], ids=["no-column", "blank", "n/a", "float"]
)
def test_an_unreadable_code_on_a_fresh_artifact_is_unmeasured_not_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, last_result: str | None
) -> None:
    row: dict[str, str] = {
        "TaskName": "\\MT5-Hourly",
        "Status": "Ready",
        "Scheduled Task State": "Enabled",
    }
    if last_result is not None:
        row["Last Result"] = last_result
    monkeypatch.setattr(ph, "_tasks", lambda: ([row], "OK schtasks"))
    doc, by = _build(monkeypatch, tmp_path, {"MT5-Hourly": ("fresh.json", 120, "hourly")})
    assert by["MT5-Hourly"]["last_result_code"] is None
    assert by["MT5-Hourly"]["last_result"].startswith("UNMEASURED")
    assert by["MT5-Hourly"]["verdict"] == "SCHEDULER_UNMEASURED"
    assert doc["status"] == "ATTENTION"


def test_a_hex_failure_code_reads_failing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ph,
        "_tasks",
        lambda: (
            [
                {
                    "TaskName": "\\MT5-Hourly",
                    "Status": "Ready",
                    "Scheduled Task State": "Enabled",
                    "Last Result": "0x1",
                },
            ],
            "OK schtasks",
        ),
    )
    _doc, by = _build(monkeypatch, tmp_path, {"MT5-Hourly": ("fresh.json", 120, "hourly")})
    assert by["MT5-Hourly"]["verdict"] == "FAILING" and by["MT5-Hourly"]["last_result_code"] == 1


@pytest.mark.parametrize(
    "scheduler",
    [
        ([], "UNMEASURED: INFO: There are no scheduled tasks presently available"),
        ([], "UNMEASURED: schtasks /fo csv OSError: boom"),
    ],
    ids=["info-at-rc0", "oserror"],
)
def test_no_contracts_and_an_unread_scheduler_is_an_unmeasured_headline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scheduler: tuple[list[dict[str, str]], str]
) -> None:
    # `_contracts()` swallows a failed organ_contract import as {}, so this is one import
    # failure away from a board of zero rows that used to read "status": "OK".
    monkeypatch.setattr(ph, "_tasks", lambda: scheduler)
    doc, _by = _build(monkeypatch, tmp_path, {})
    assert doc["n_processes"] == 0
    assert doc["status"] == "UNMEASURED"


@pytest.mark.parametrize(
    "state, status, verdict",
    [
        ("Deaktiviert", "Deaktiviert", "DISABLED"),
        ("Désactivé", "", "DISABLED"),
        ("", "Deshabilitado", "DISABLED"),
        ("Aktiviert", "Bereit", "OK"),
        ("Aktiviert", "Wird ausgeführt", "OK"),
        ("Gesperrt", "Bereit", "SCHEDULER_UNMEASURED"),  # a state this file has never seen
        ("", "Could not start", "SCHEDULER_UNMEASURED"),  # a failed start is not a live state
        ("", "", "SCHEDULER_UNMEASURED"),  # no state read at all
    ],
)
def test_the_task_state_is_read_in_any_locale_and_unknown_is_unmeasured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state: str, status: str, verdict: str
) -> None:
    monkeypatch.setattr(
        ph,
        "_tasks",
        lambda: (
            [
                {
                    "TaskName": "\\MT5-Hourly",
                    "Status": status,
                    "Scheduled Task State": state,
                    "Last Result": "0",
                },
            ],
            "OK schtasks",
        ),
    )
    _doc, by = _build(monkeypatch, tmp_path, {"MT5-Hourly": ("fresh.json", 120, "hourly")})
    assert by["MT5-Hourly"]["verdict"] == verdict, by["MT5-Hourly"]["why"]
    if verdict == "SCHEDULER_UNMEASURED":
        assert "not recognised" in by["MT5-Hourly"]["why"]


def test_a_localised_running_state_excuses_an_overlap_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        ph,
        "_tasks",
        lambda: (
            [
                {
                    "TaskName": "\\MT5-Gateway",
                    "Status": "Wird ausgeführt",
                    "Scheduled Task State": "Aktiviert",
                    "Last Result": "-2147020576",
                },
            ],
            "OK schtasks",
        ),
    )
    _doc, by = _build(monkeypatch, tmp_path, {"MT5-Gateway": ("fresh.json", 120, "gateway")})
    assert by["MT5-Gateway"]["verdict"] == "OK"
