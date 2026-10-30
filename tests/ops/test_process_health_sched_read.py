"""process_health's scheduler read survives a slow scheduler (2026-10-29).

MEASURED on the trading box, three hourly passes running: `schtasks /query /fo csv` took 34.5 s
idle and went past its 45 s bound (and the detached retry's 180 s) under load, so all 73 tasks
read SCHEDULER_UNMEASURED. These pin the fix: the inventory comes from the task XML files (no
schtasks, no Schedule service); every scheduler read goes through ops/last_good.read_through, so a
read that fails serves the last good read WITH ITS AGE inside 6 h; and a read that stays
UNMEASURED for more than two consecutive runs turns its rows and the headline RED.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_sched_read_under_test", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)
lg = ph._lg()

#: A task definition as Windows writes it: UTF-16 LE with a BOM, the 2004/02 task namespace.
TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>BOX\\quant</Author>
    <URI>\\MT5-Hourly</URI>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition><Interval>PT1H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>2026-09-12T00:05:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <Enabled>{enabled}</Enabled>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\\Program Files\\Python314\\python.exe</Command>
      <Arguments>-u C:\\opt\\quant\\ops\\process_health.py</Arguments>
    </Exec>
  </Actions>
</Task>
"""

VERBOSE = (
    '"HostName","TaskName","Next Run Time","Status","Last Run Time","Last Result",'
    '"Scheduled Task State"\r\n'
    '"BOX","\\MT5-Hourly","29/10/2026 15:05:00","Ready","29/10/2026 14:05:00","0","Enabled"\r\n'
    '"BOX","\\MT5-Gateway","N/A","Ready","29/10/2026 14:00:00","1","Enabled"\r\n'
)


def _xml(enabled: str = "true") -> bytes:
    return TASK_XML.replace("{enabled}", enabled).encode("utf-16")


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    tasks = tmp_path / "Tasks"
    (tasks / "Microsoft" / "Windows" / "Defrag").mkdir(parents=True)
    (tasks / "Microsoft" / "Windows" / "Defrag" / "ScheduledDefrag").write_bytes(_xml())
    (tasks / "MT5-Hourly").write_bytes(_xml())
    (tasks / "MT5-Gateway").write_bytes(_xml())
    (tmp_path / "fresh.json").write_text("{}", "utf-8")
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "OUT", tmp_path / "reports" / "process_health.json")
    monkeypatch.setattr(ph, "TASKS_DIR", tasks)
    monkeypatch.setattr(ph, "sched_cache_path", lambda: tmp_path / "logs" / "sched_cache.json")
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Hourly": ("fresh.json", 120, "hourly"), "MT5-Gateway": ("fresh.json", 120, "gw")})
    monkeypatch.setattr(ph, "memory_snapshot", lambda: {"host": "T", "free_phys_mb": 1,
                                                        "total_phys_mb": 2,
                                                        "commit_charge_mb": 3})
    monkeypatch.setattr(ph, "account_key_file", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "account_key_backup", lambda: {"state": "ok"})
    return tmp_path


def _sched(monkeypatch: pytest.MonkeyPatch, *, brief: Any = None,
           verbose: Any = None) -> list[str]:
    """None times out; a string answers; an Exception instance is raised."""
    calls: list[str] = []

    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        assert cmd[0] == "schtasks", cmd
        which = "/v" if "/v" in cmd else "brief"
        calls.append(which)
        answer = verbose if which == "/v" else brief
        if answer is None:
            raise subprocess.TimeoutExpired(cmd, kw["timeout"])
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(cmd, 0, answer, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    return calls


def _age_cache(box: Path, key: str, hours: float) -> None:
    path = box / "logs" / "sched_cache.json"
    doc = json.loads(path.read_text("utf-8"))
    doc[key]["at"] = (datetime.now(tz=UTC) - timedelta(hours=hours)).isoformat()
    path.write_text(json.dumps(doc), "utf-8")


def _by(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in doc["processes"]}


# --- the task XML fixture ----------------------------------------------------------------------

def test_a_task_xml_file_parses_to_an_inventory_row() -> None:
    row = ph.parse_task_xml(_xml(), "\\MT5-Hourly")
    assert row["TaskName"] == "\\MT5-Hourly"
    assert row["Scheduled Task State"] == "Enabled"
    # the definition carries no run state: those columns are left for the verbose read
    assert row["Status"] == "" and row["Next Run Time"] == "" and "Last Result" not in row
    assert ph.parse_task_xml(_xml("false"), "\\X")["Scheduled Task State"] == "Disabled"


def test_a_task_xml_with_no_enabled_element_is_enabled_as_the_scheduler_reads_it() -> None:
    data = TASK_XML.replace("<Enabled>{enabled}</Enabled>", "").encode("utf-16")
    assert ph.parse_task_xml(data, "\\X")["Scheduled Task State"] == "Enabled"


def test_the_xml_walk_skips_microsoft_names_subfolders_and_keeps_an_unreadable_file(
    box: Path,
) -> None:
    (box / "Tasks" / "Desk").mkdir()
    (box / "Tasks" / "Desk" / "Nested").write_bytes(_xml("false"))
    (box / "Tasks" / "Broken").write_bytes(b"<not xml")
    rows = {r["TaskName"]: r for r in ph.read_task_xml_dir(box / "Tasks")}
    assert set(rows) == {"\\MT5-Hourly", "\\MT5-Gateway", "\\Desk\\Nested", "\\Broken"}
    assert rows["\\Desk\\Nested"]["Scheduled Task State"] == "Disabled"
    # a task file that cannot be read is still a task that exists: UNMEASURED, never dropped
    assert "task XML unreadable" in rows["\\Broken"]["TaskInfoError"]


def test_the_inventory_comes_from_xml_without_running_brief_schtasks(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    calls = _sched(monkeypatch, brief=None, verbose=VERBOSE)   # the brief read would time out
    doc = ph.build()
    assert calls == ["/v"], "the inventory must not go through schtasks when the XML is there"
    assert doc["scheduler_status"] == "OK schtasks" and doc["run_history"] == "MEASURED"
    assert doc["scheduler_reads"]["inventory"]["via"] == "task XML"
    by = _by(doc)
    assert by["MT5-Hourly"]["verdict"] == "OK" and by["MT5-Hourly"]["last_result_code"] == 0
    assert by["MT5-Gateway"]["verdict"] == "FAILING"


def test_with_no_xml_directory_the_brief_schtasks_read_still_serves(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    monkeypatch.setattr(ph, "TASKS_DIR", box / "absent")
    brief = '"TaskName","Next Run Time","Status"\r\n"\\MT5-Hourly","N/A","Ready"\r\n'
    calls = _sched(monkeypatch, brief=brief, verbose=VERBOSE)
    rows, status = ph._tasks()
    assert calls == ["brief", "/v"] and status == "OK schtasks"
    assert [r["TaskName"] for r in rows] == ["\\MT5-Hourly"]


# --- the timeout path and the cache fallback ---------------------------------------------------

def test_a_verbose_timeout_serves_the_cached_run_history_with_its_age(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _sched(monkeypatch, verbose=VERBOSE)
    assert ph.build()["run_history"] == "MEASURED"          # a good read, now cached
    _age_cache(box, "run_history", 1.5)
    _sched(monkeypatch, verbose=None)                       # then the verbose read times out
    doc = ph.build()
    assert doc["counts"].get("SCHEDULER_UNMEASURED", 0) == 0
    assert doc["run_history"] == "CACHED"
    assert doc["scheduler_status"].startswith("OK task XML; run history CACHED (90 min old)")
    assert "TimeoutExpired" in doc["scheduler_status"]
    assert doc["scheduler_reads"]["run_history"]["source"] == "cache"
    assert doc["scheduler_timeouts"], "the timeout is still recorded (and still spawns the retry)"
    by = _by(doc)
    # judged on the cached code, and labelled with its age -- FAILING stays FAILING
    assert by["MT5-Gateway"]["verdict"] == "FAILING"
    assert by["MT5-Hourly"]["verdict"] == "OK" and by["MT5-Hourly"]["last_result_code"] == 0
    assert "(90 min old)" in by["MT5-Hourly"]["why"]
    assert by["MT5-Hourly"]["last_result"].endswith("(cached read)")
    assert 89 <= by["MT5-Hourly"]["last_result_age_min"] <= 91
    assert doc["status"] == "ATTENTION"   # the cached FAILING row, judged like a live one


def test_a_cache_past_six_hours_is_not_served(monkeypatch: pytest.MonkeyPatch, box: Path) -> None:
    _sched(monkeypatch, verbose=VERBOSE)
    ph.build()
    _age_cache(box, "run_history", 7)
    _sched(monkeypatch, verbose=None)
    doc = ph.build()
    assert doc["run_history"] == "UNMEASURED" and doc["status"] == "UNMEASURED"
    assert "(brief: last run and last result UNMEASURED" in doc["scheduler_status"]
    assert _by(doc)["MT5-Hourly"]["last_result_code"] is None
    assert doc["scheduler_reads"]["run_history"]["unmeasured_runs"] == 1


def test_run_history_cache_expires_at_two_hours_while_the_inventory_keeps_six(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # auditor F1 on #491: a 3 h old last result is not served; a 3 h old inventory is
    assert ph.SCHED_HISTORY_CACHE_MAX_AGE_S == 2 * 3600 and ph.SCHED_CACHE_MAX_AGE_S == 6 * 3600
    _sched(monkeypatch, verbose=VERBOSE)
    ph.build()
    _age_cache(box, "run_history", 3)
    _age_cache(box, "inventory", 3)
    monkeypatch.setattr(ph, "TASKS_DIR", box / "absent")
    _sched(monkeypatch)                                     # every live read fails
    doc = ph.build()
    reads = doc["scheduler_reads"]
    assert reads["inventory"]["source"] == "cache" and 179 <= reads["inventory"]["age_min"] <= 181
    assert reads["run_history"]["source"] == "unmeasured"
    assert reads["run_history"]["unmeasured_runs"] == 1
    assert doc["run_history"] == "UNMEASURED"
    row = _by(doc)["MT5-Hourly"]
    assert row["last_result_code"] is None and "inside 2 h" in row["last_result"]


def test_an_xml_walk_where_every_file_is_unreadable_is_a_failed_read(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # auditor F2 on #491: an ACL change makes every file raise; that is no inventory, so the
    # counter runs and the RED clock with it -- never a "live" read of broken rows
    for name in ("MT5-Hourly", "MT5-Gateway"):
        (box / "Tasks" / name).write_bytes(b"<denied")
    with pytest.raises(ph.SchtasksUnreadable, match="none of 2 task definition"):
        ph.read_task_xml_dir(box / "Tasks")
    _sched(monkeypatch)                                     # the brief fallback times out too
    statuses = []
    for _ in range(3):
        doc = ph.build()
        statuses.append(doc["status"])
    assert statuses == ["UNMEASURED", "UNMEASURED", "RED"]
    assert doc["scheduler_reads"]["inventory"]["unmeasured_runs"] == 3
    assert "none of 2 task definition" in doc["scheduler_reads"]["inventory"]["error"]
    assert doc["red_reads"] == ["inventory"]


def test_an_xml_directory_with_no_desk_task_is_a_failed_read(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    for name in ("MT5-Hourly", "MT5-Gateway"):
        (box / "Tasks" / name).unlink()                     # only Microsoft tasks are left
    with pytest.raises(ph.SchtasksUnreadable, match="no non-Microsoft"):
        ph.read_task_xml_dir(box / "Tasks")
    _sched(monkeypatch)
    doc = ph.build()
    assert doc["scheduler_reads"]["inventory"]["source"] == "unmeasured"
    assert doc["scheduler_reads"]["inventory"]["unmeasured_runs"] == 1
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0


def test_one_readable_file_among_unreadable_ones_is_still_a_live_inventory(box: Path) -> None:
    (box / "Tasks" / "MT5-Gateway").write_bytes(b"<denied")
    rows = {r["TaskName"]: r for r in ph.read_task_xml_dir(box / "Tasks")}
    assert "TaskInfoError" not in rows["\\MT5-Hourly"]
    assert "task XML unreadable" in rows["\\MT5-Gateway"]["TaskInfoError"]


def test_an_unreadable_inventory_serves_the_cached_inventory(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _sched(monkeypatch, verbose=VERBOSE)
    ph.build()
    monkeypatch.setattr(ph, "TASKS_DIR", box / "absent")   # XML gone, brief + verbose time out
    _sched(monkeypatch)
    doc = ph.build()
    assert doc["scheduler_status"].startswith("OK task XML CACHED (")
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0
    assert "inventory from the cached read" in _by(doc)["MT5-Hourly"]["why"]


def test_a_failed_read_never_overwrites_the_last_good_value(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    assert lg.read_through(path, "k", lambda: {"v": 1}, 3600).source == "live"

    def boom() -> Any:
        raise lg.ReadFailed("slow")

    out = lg.read_through(path, "k", boom, 3600)
    assert out.source == "cache" and out.value == {"v": 1} and out.error == "slow"
    assert json.loads(path.read_text("utf-8"))["k"]["value"] == {"v": 1}


def test_a_corrupt_cache_file_is_empty_and_never_raises(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text("{not json", "utf-8")
    out = lg.read_through(path, "k", lambda: (_ for _ in ()).throw(OSError("x")), 3600)
    assert out.source == "unmeasured" and out.unmeasured_runs == 1
    assert any("cache unreadable" in n for n in out.notes)


# --- RED after two consecutive unmeasured runs -------------------------------------------------

def test_a_read_unmeasured_for_more_than_two_runs_turns_red(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    monkeypatch.setattr(ph, "TASKS_DIR", box / "absent")
    _sched(monkeypatch)                       # nothing answers, nothing cached
    seen = []
    for _ in range(3):
        doc = ph.build()
        seen.append((doc["status"], doc["scheduler_reads"]["inventory"]["unmeasured_runs"]))
    assert seen == [("UNMEASURED", 1), ("UNMEASURED", 2), ("RED", 3)]
    assert doc["red_reads"] == ["inventory"]
    by = _by(doc)
    assert {r["verdict"] for r in by.values()} == {"RED"}
    assert "3 consecutive runs" in by["MT5-Hourly"]["why"]
    assert doc["n_needing_attention"] == 2

    # one live read resets the counter: the board goes back to judging the tasks
    monkeypatch.setattr(ph, "TASKS_DIR", box / "Tasks")
    _sched(monkeypatch, verbose=VERBOSE)
    doc = ph.build()
    assert doc["red_reads"] == [] and doc["status"] == "ATTENTION"   # MT5-Gateway FAILING
    assert doc["scheduler_reads"]["inventory"]["unmeasured_runs"] == 0


def test_a_dark_run_history_turns_its_unread_rows_and_the_headline_red(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _sched(monkeypatch, verbose=None)         # inventory from XML, history never read
    statuses = [ph.build()["status"] for _ in range(3)]
    assert statuses == ["UNMEASURED", "UNMEASURED", "RED"]
    doc = ph.build()
    assert doc["red_reads"] == ["run_history"] and doc["status"] == "RED"
    assert _by(doc)["MT5-Hourly"]["verdict"] == "RED"
    assert doc["scheduler_reads"]["run_history"]["unmeasured_runs"] == 4


def test_a_served_cache_is_not_an_unmeasured_run(monkeypatch: pytest.MonkeyPatch,
                                                 box: Path) -> None:
    _sched(monkeypatch, verbose=VERBOSE)
    ph.build()
    _sched(monkeypatch, verbose=None)
    for _ in range(4):
        doc = ph.build()
    assert doc["status"] != "RED" and doc["run_history"] == "CACHED"
    assert doc["scheduler_reads"]["run_history"]["unmeasured_runs"] == 0


def test_the_detached_retry_never_counts_a_run(monkeypatch: pytest.MonkeyPatch,
                                               box: Path) -> None:
    _sched(monkeypatch, verbose=None)
    ph.build()
    monkeypatch.setattr(ph, "_BOUNDS_OVERRIDE", (180, 300))   # what retry_scheduler sets
    for _ in range(3):
        doc = ph.build()
    assert doc["scheduler_reads"]["run_history"]["unmeasured_runs"] == 1
    assert doc["status"] != "RED"


def test_the_cache_lives_in_the_gitignored_logs_directory() -> None:
    assert ph.sched_cache_path().relative_to(ph.ROOT).parts[:3] == ("desks", "mt5", "logs")
    gi = (ROOT / ".gitignore").read_text("utf-8").splitlines()
    assert "desks/mt5/logs/" in gi
