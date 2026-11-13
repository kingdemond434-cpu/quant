"""process_health: the derived contract for uncontracted tasks (Hourly pass idea 589).

An UNCONTRACTED task that stopped running read as a note, never a fault. Now each one must have
RUN within 2 x its own cadence (scheduler "Repeat: Every", else the box manifest trigger), or it
reads STALE -- and a date format may withhold an alarm, never invent one.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_derived", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

NOW = datetime(2026, 11, 20, 15, 0, 0).astimezone()


def _dm(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M:%S")


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("0 Hour(s), 10 Minute(s)", 10.0),
        ("1 Hour(s), 0 Minute(s)", 60.0),
        ("0 Hour(s), 0 Minute(s)", None),
        ("Disabled", None),
        ("every 15 minutes, at :05", 15.0),
        ("every 1 hour", 60.0),
        ("every 6 hours", 360.0),
        ("hourly at :40", 60.0),
        ("daily 04:20", 1440.0),
        ("at startup + every 10 minutes (keep-alive of a 24/7 resident)", 10.0),
        ("at logon + every 5 minutes", 5.0),
        ("hourly; window 12:00-22:59 Europe/Dublin", 1440.0),
        ("at startup", None),
        ("at system start-up (resident)", None),
        ("UNDECLARED", None),
        ("legacy compatibility only", None),
        ("", None),
    ],
)
def test_interval_from_scheduler_or_manifest(text: str, minutes: float | None) -> None:
    assert ph.interval_min(text) == minutes


def test_every_manifest_trigger_parses_or_is_deliberately_none() -> None:
    triggers = ph.manifest_triggers(ROOT)
    assert len(triggers) > 50
    for name, trig in triggers.items():
        got = ph.interval_min(trig)
        low = trig.lower()
        if "every" in low or low.startswith(("hourly", "daily")):
            assert got is not None, (name, trig)


def _dc(
    task: dict[str, str],
    trigger: str,
    code: int | None,
    now: datetime,
    prev: dict[str, Any] | None = None,
) -> tuple[tuple[str, str] | None, dict | None]:
    return ph.derived_contract(task, trigger, code, now, prev)


def _seen(hours_ago: float, now: datetime = NOW) -> dict[str, Any]:
    return {"first_seen": (now - timedelta(hours=hours_ago)).isoformat()}


def test_old_success_is_a_derived_breach_not_plain_stale() -> None:
    task = {
        "Repeat: Every": "0 Hour(s), 30 Minute(s)",
        "Last Run Time": _dm(NOW - timedelta(hours=5)),
    }
    (verdict, why), entry = _dc(task, "", 0, NOW)
    assert verdict == ph.DERIVED_VERDICT == "STALE_DERIVED" and "60 min" in why
    assert entry is not None and entry["last_ok_run"] == task["Last Run Time"]
    assert ph.DERIVED_VERDICT not in _never_stale().RESTARTABLE


def test_runs_every_hour_but_killed_at_limit_breaches_with_cause() -> None:
    # MT5-TapeFeatures: it RUNS every hour, killed at its limit (267014) every time.
    killed = {"Last Run Time": _dm(NOW - timedelta(minutes=10))}
    (verdict, why), _ = _dc(killed, "every 1 hour", 267014, NOW, _seen(3))
    assert verdict == "STALE_DERIVED" and "no successful run" in why
    assert "terminated by the scheduler" in why
    # ...and a remembered success inside the limit keeps it OK
    prev = {**_seen(3), "last_ok_run": _dm(NOW - timedelta(minutes=70))}
    assert _dc(killed, "every 1 hour", 267014, NOW, prev)[0][0] == "OK"


def test_first_observation_never_breaches_instantly() -> None:
    never = {"Last Run Time": "30/11/1999 00:00:00"}
    (verdict, why), entry = _dc(never, "daily 04:20", 267011, NOW)
    assert verdict == "UNCONTRACTED" and "watching since" in why
    assert entry is not None and entry["first_seen"]
    # a whole limit of watching with no success: now it is late
    assert _dc(never, "daily 04:20", 267011, NOW, _seen(49))[0][0] == "STALE_DERIVED"
    assert _dc({"Last Run Time": "N/A"}, "every 1 hour", None, NOW, _seen(3))[0][0] == (
        "STALE_DERIVED"
    )


def test_ambiguous_dates_withhold_never_invent() -> None:
    now = datetime(2026, 11, 5, 15, 0).astimezone()
    task = {"Last Run Time": "05/11/2026 14:50:00"}  # 5 Nov or 11 May: one reading is fresh
    assert _dc(task, "every 10 minutes", 0, now)[0][0] == "OK"


def test_box_format_with_am_pm_parses() -> None:
    now = datetime(2026, 11, 11, 4, 30).astimezone()
    (verdict, _), _ = _dc({"Last Run Time": "11/11/2026 4:00:01 AM"}, "every 1 hour", 0, now)
    assert verdict == "OK"


def test_fresh_run_is_ok_and_floor_applies() -> None:
    task = {"Last Run Time": _dm(NOW - timedelta(minutes=15))}
    assert _dc(task, "every 1 minute", 0, NOW)[0][0] == "OK"  # inside the 20 min floor
    task = {"Last Run Time": _dm(NOW - timedelta(minutes=25))}
    assert _dc(task, "every 1 minute", 0, NOW)[0][0] == "STALE_DERIVED"


def test_windowed_task_says_it_is_judged_per_day() -> None:
    task = {"Last Run Time": _dm(NOW - timedelta(hours=60))}
    (verdict, why), _ = _dc(task, "hourly; window 12:00-22:59 Europe/Dublin", 0, NOW)
    assert verdict == "STALE_DERIVED" and "judged per day" in why


def test_no_cadence_or_unreadable_time_derives_nothing() -> None:
    assert _dc({"Last Run Time": "garbage"}, "every 1 hour", 0, NOW) == (None, None)
    assert _dc({"Last Run Time": _dm(NOW)}, "at startup", 0, NOW) == (None, None)
    future = {"Last Run Time": _dm(NOW + timedelta(hours=3))}
    assert _dc(future, "every 1 hour", 0, NOW) == (None, None)


def _never_stale() -> Any:
    spec = importlib.util.spec_from_file_location("ns_for_589", ROOT / "ops" / "never_stale.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VERBOSE_HDR = (
    '"HostName","TaskName","Next Run Time","Status","Last Run Time","Last Result",'
    '"Scheduled Task State","Repeat: Every"\r\n'
)


def _board(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    verbose_rows: str,
    brief_rows: str,
    manifest: str = "",
) -> dict[str, Any]:
    brief = '"TaskName","Next Run Time","Status"\r\n' + brief_rows
    verbose = VERBOSE_HDR + verbose_rows

    def run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, verbose if "/v" in cmd else brief, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", dict)
    man = tmp_path / ph.MANIFEST
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(manifest, encoding="utf-8")
    return ph.build()


def test_build_end_to_end_and_never_stale_never_starts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime.now().astimezone()
    stopped, fresh = _dm(now - timedelta(hours=6)), _dm(now - timedelta(minutes=3))
    brief = (
        '"\\Q-Stopped","N/A","Ready"\r\n"\\Q-Fresh","N/A","Ready"\r\n'
        '"\\Q-Boot","N/A","Ready"\r\n"\\Q-Resident","N/A","Running"\r\n'
    )
    verbose = (
        f'"B","\\Q-Stopped","N/A","Ready","{stopped}","0","Enabled","0 Hour(s), 15 Minute(s)"\r\n'
        f'"B","\\Q-Fresh","N/A","Ready","{fresh}","0","Enabled","Disabled"\r\n'
        f'"B","\\Q-Boot","N/A","Ready","{stopped}","0","Enabled","Disabled"\r\n'
        f'"B","\\Q-Resident","N/A","Running","{stopped}","267009","Enabled","Disabled"\r\n'
    )
    manifest = (
        'TASK name="Q-Fresh" trigger="every 1 hour" runs="x"\n'
        'TASK name="Q-Boot" trigger="at startup" runs="x"\n'
        'TASK name="Q-Resident" trigger="at startup + every 10 minutes" runs="x"\n'
    )
    doc = _board(monkeypatch, tmp_path, verbose, brief, manifest)
    by = {r["name"]: r for r in doc["processes"]}
    assert (
        by["Q-Stopped"]["verdict"] == "STALE_DERIVED" and "auto-contract" in by["Q-Stopped"]["why"]
    )
    assert by["Q-Fresh"]["verdict"] == "OK" and "auto-contract" in by["Q-Fresh"]["why"]
    assert by["Q-Boot"]["verdict"] == "UNCONTRACTED"
    assert by["Q-Resident"]["verdict"] == "UNCONTRACTED"  # running: neutral
    assert doc["status"] == "ATTENTION"
    assert [r["name"] for r in doc["derived_contract"]["newly_stale"]] == ["Q-Stopped"]
    assert doc["derived_contract"]["state"] == "written"
    state = json.loads((tmp_path / ph.DERIVED_STATE).read_text(encoding="utf-8"))["tasks"]
    assert "breached_at" not in state["Q-Stopped"] and "Q-Boot" not in state
    # the page FAILED: nothing is marked, so the next pass retries it
    failed = ph.page_newly_stale(doc, lambda *_a: {"armed": 2, "delivered": 0})
    assert "retried" in failed
    doc2 = _board(monkeypatch, tmp_path, verbose, brief, manifest)
    assert [r["name"] for r in doc2["derived_contract"]["newly_stale"]] == ["Q-Stopped"]
    # delivered: marked, and the next pass is quiet
    assert "marked written" in ph.page_newly_stale(doc2, lambda *_a: {"armed": 1, "delivered": 1})
    doc3 = _board(monkeypatch, tmp_path, verbose, brief, manifest)
    assert doc3["derived_contract"]["newly_stale"] == []
    # never_stale --apply starts nothing for it (Auditor M1)
    ns = _never_stale()
    rep = tmp_path / "process_health.json"
    rep.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ns, "HEALTH", rep)
    monkeypatch.setattr(ns, "ROOT", tmp_path)
    started: list[str] = []
    monkeypatch.setattr(ns, "_start", lambda task: (started.append(task), (True, "x"))[1])
    monkeypatch.setattr(ns, "_capital_faults", list)
    out = ns.run(apply=True)
    assert "Q-Stopped" not in started
    assert not any(a.get("task") == "Q-Stopped" for a in out.get("acted", []))


def test_brief_only_read_records_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    brief = '"TaskName","Next Run Time","Status"\r\n"\\Q-A","N/A","Ready"\r\n'

    def run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if "/v" in cmd:
            raise subprocess.TimeoutExpired(cmd, 90)
        return subprocess.CompletedProcess(cmd, 0, brief, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", dict)
    monkeypatch.setattr(ph, "_spawn_retry", lambda *_a: None, raising=False)
    doc = ph.build()
    assert doc["derived_contract"]["state"].startswith("not written")
    assert not (tmp_path / ph.DERIVED_STATE).exists()


def test_page_newly_stale_once_with_cause(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    sent: list[tuple[str, str]] = []

    def send(title: str, body: str) -> dict[str, Any]:
        sent.append((title, body))
        return {"armed": 1, "delivered": 1}

    assert ph.page_newly_stale({"derived_contract": {"newly_stale": []}}, send) == "nothing new"
    new = [{"name": "MT5-TapeFeatures", "why": "auto-contract: ...; last result: terminated"}]
    got = ph.page_newly_stale({"derived_contract": {"newly_stale": new}}, send)
    assert got.startswith("armed 1, delivered 1")
    assert "MT5-TapeFeatures" in sent[0][0] and "terminated" in sent[0][1]

    def boom(*_a: Any) -> dict[str, Any]:
        raise OSError("down")

    assert ph.page_newly_stale({"derived_contract": {"newly_stale": new}}, boom).startswith("not")


def test_a_retired_manifest_row_gets_no_derived_contract(tmp_path: Path) -> None:
    man = tmp_path / ph.MANIFEST
    man.parent.mkdir(parents=True)
    man.write_text(
        'TASK name="Q-Live" trigger="every 1 hour" runs="x.py" installer="NONE"\n'
        'TASK name="Q-Gone" trigger="hourly" runs="retired 2026-11-11: reason" installer="NONE"\n'
        'TASK name="Q-Order" runs="y.py" trigger="every 5 minutes"\n',
        encoding="utf-8",
    )
    got = ph.manifest_triggers(tmp_path)
    assert got == {"Q-Live": "every 1 hour", "Q-Gone": "", "Q-Order": "every 5 minutes"}
    assert ph.manifest_triggers(ROOT)["MT5-CycleMidnight"] == ""  # retired by the CRO 2026-11-11
