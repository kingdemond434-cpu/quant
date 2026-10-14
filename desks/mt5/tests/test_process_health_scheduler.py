"""The scheduler inventory must not hide a stalled money path behind false alarms."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "ops" / "process_health.py"
SPEC = importlib.util.spec_from_file_location("root_process_health", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ph = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ph)


def _row(doc, name):
    return next(row for row in doc["processes"] if row["name"] == name)


def test_e8_live_clock_and_book_have_measured_freshness_contracts(monkeypatch):
    contracts = ph._contracts()
    assert contracts["E8-Executor"][1] == 15
    assert contracts["E8-Book"][1] == 180
    monkeypatch.setattr(ph, "_tasks", lambda: ([
        {"TaskName": r"\E8-Executor", "Scheduled Task State": "Ready", "Last Result": "0"},
        {"TaskName": r"\E8-Book", "Scheduled Task State": "Ready", "Last Result": "0"},
    ], "OK powershell"))
    monkeypatch.setattr(ph, "_age_min", lambda path: 16.0 if path.name == "E8_EXEC.json"
                        else 120.0)

    doc = ph.build()
    assert _row(doc, "E8-Executor")["verdict"] == "STALE"
    assert _row(doc, "E8-Book")["verdict"] == "OK"


def test_unreadable_scheduler_is_not_empty_scheduler(monkeypatch):
    monkeypatch.setattr(ph, "_tasks", lambda: ([], "UNMEASURED: scheduler timed out"))
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Gateway": ("gateway.json", 10, "broker check"),
    })
    monkeypatch.setattr(ph, "_age_min", lambda path: 1.0)

    doc = ph.build()

    assert doc["scheduler_status"].startswith("UNMEASURED")
    assert _row(doc, "MT5-Gateway")["verdict"] == "SCHEDULER_UNMEASURED"
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0
    assert doc["status"] == "ATTENTION"


def test_hourly_replication_staleness_is_detected_before_live_door_expiry(monkeypatch):
    contracts = ph._contracts()
    name = "MT5-HourlyCore (replication)"
    assert contracts[name][1] == 180
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": r"\MT5-HourlyCore", "Scheduled Task State": "Running",
        "Last Result": "267009",
    }], "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {name: contracts[name]})
    monkeypatch.setattr(ph, "_age_min", lambda path: 181.0)
    row = _row(ph.build(), name)
    assert row["verdict"] == "STALE"
    assert row["state"] == "COMPONENT"
    monkeypatch.setattr(ph, "_age_min", lambda path: 1.0)
    assert _row(ph.build(), name)["verdict"] == "OK"


def test_running_gateway_with_overlap_result_and_fresh_artifact_is_healthy(monkeypatch):
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": r"\MT5-Gateway",
        "Scheduled Task State": "Running",
        "Last Result": "2147946720",  # refused a duplicate trigger while still running
    }], "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Gateway": ("gateway.json", 10, "broker check"),
    })
    monkeypatch.setattr(ph, "_age_min", lambda path: 1.0)

    assert _row(ph.build(), "MT5-Gateway")["verdict"] == "OK"


def test_parenthesised_component_uses_owner_and_its_own_artifact_clock(monkeypatch):
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": r"\MT5-Gauntlet",
        "Scheduled Task State": "Running",
        "Last Result": "267009",
    }], "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Gauntlet": ("survivors.json", 240, "certificates"),
        "MT5-Gauntlet (rotation)": ("cursor.json", 30, "docket rotation"),
    })
    monkeypatch.setattr(ph, "_age_min", lambda path: 5.0)

    component = _row(ph.build(), "MT5-Gauntlet (rotation)")
    assert component["verdict"] == "OK"
    assert component["state"] == "COMPONENT"

    monkeypatch.setattr(ph, "_age_min", lambda path: 45.0 if path.name == "cursor.json" else 5.0)
    assert _row(ph.build(), "MT5-Gauntlet (rotation)")["verdict"] == "STALE"


def test_a_blind_scheduler_still_reports_stale_and_missing_artifacts(monkeypatch):
    """2026-10-14 00:45Z: both inventory queries timed out and all 73 rows read
    SCHEDULER_UNMEASURED, hiding a 43h-stale gauntlet. Artifact age is measured regardless."""
    monkeypatch.setattr(ph, "_tasks", lambda: ([], "UNMEASURED: scheduler timed out"))
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Gauntlet": ("cursor.json", 240, "judge"),
        "MT5-Hourly": ("hourly.json", 90, "research"),
        "MT5-Gateway": ("gateway.json", 10, "broker check"),
    })
    ages = {"cursor.json": 2580.0, "hourly.json": None, "gateway.json": 1.0}
    monkeypatch.setattr(ph, "_age_min", lambda path: ages[path.name])

    doc = ph.build()

    assert _row(doc, "MT5-Gauntlet")["verdict"] == "STALE"
    assert _row(doc, "MT5-Hourly")["verdict"] == "NO_ARTIFACT"
    assert _row(doc, "MT5-Gateway")["verdict"] == "SCHEDULER_UNMEASURED"
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0


def test_per_task_fallback_measures_contracted_tasks_without_claiming_absence(monkeypatch):
    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, rc, out):
            self.returncode, self.stdout, self.stderr = rc, out, ""

    def _run(cmd, **kw):
        calls.append(cmd)
        if "/tn" not in cmd:
            raise ph.subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        name = cmd[cmd.index("/tn") + 1]
        if name == "MT5-Gateway":
            return _Proc(0, '"TaskName","Status","Last Result"\n"\\MT5-Gateway","Running","0"\n')
        return _Proc(1, "")

    monkeypatch.setattr(ph.sys, "platform", "linux")
    monkeypatch.setattr(ph.subprocess, "run", _run)
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-Gateway": ("gateway.json", 10, "broker check"),
        "MT5-Shadow": ("shadow.json", 30, "clocks"),
    })
    monkeypatch.setattr(ph, "_age_min", lambda path: 1.0)

    rows, status = ph._tasks()
    assert status.startswith("OK schtasks per task") and len(rows) == 1
    doc = ph.build()
    assert _row(doc, "MT5-Gateway")["verdict"] == "OK"
    # Not answered by a partial inventory: unmeasured, never "not scheduled".
    assert _row(doc, "MT5-Shadow")["verdict"] == "SCHEDULER_UNMEASURED"
    assert any("/tn" in c for c in calls)
