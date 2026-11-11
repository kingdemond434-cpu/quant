"""process_health: the derived contract for uncontracted tasks (Hourly pass idea 589).

An UNCONTRACTED task that stopped running read as a note, never a fault. Now each one must have
RUN within 2 x its own cadence (scheduler "Repeat: Every", else the box manifest trigger), or it
reads STALE -- and a date format may withhold an alarm, never invent one.
"""

from __future__ import annotations

import importlib.util
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


def test_stale_only_when_every_reading_says_so() -> None:
    old = NOW - timedelta(hours=5)
    task = {"Repeat: Every": "0 Hour(s), 30 Minute(s)", "Last Run Time": _dm(old)}
    verdict, why = ph.derived_contract(task, "", NOW)
    assert verdict == "STALE" and "60 min" in why
    # "11/05/..." also parses month-first (5 Nov vs 11 May); one fresh reading withholds it
    ambiguous = datetime(2026, 11, 5, 14, 50).astimezone()
    now = datetime(2026, 11, 5, 15, 0).astimezone()
    task = {"Repeat: Every": "", "Last Run Time": "05/11/2026 14:50:00"}
    assert ph.derived_contract(task, "every 10 minutes", now)[0] == "OK"
    assert ambiguous < now


def test_fresh_run_is_ok_and_floor_applies() -> None:
    task = {"Last Run Time": _dm(NOW - timedelta(minutes=15))}
    # a 1-minute task 15 min since its run is inside the 20 min floor
    assert ph.derived_contract(task, "every 1 minute", NOW)[0] == "OK"
    task = {"Last Run Time": _dm(NOW - timedelta(minutes=25))}
    assert ph.derived_contract(task, "every 1 minute", NOW)[0] == "STALE"


def test_never_ran_unparseable_and_no_cadence() -> None:
    never = {"Last Run Time": "30/11/1999 00:00:00"}
    assert ph.derived_contract(never, "every 1 hour", NOW)[0] == "STALE"
    assert ph.derived_contract({"Last Run Time": "N/A"}, "every 1 hour", NOW)[0] == "STALE"
    assert ph.derived_contract({"Last Run Time": "garbage"}, "every 1 hour", NOW) is None
    assert ph.derived_contract({"Last Run Time": _dm(NOW)}, "at startup", NOW) is None
    future = {"Last Run Time": _dm(NOW + timedelta(hours=3))}
    assert ph.derived_contract(future, "every 1 hour", NOW) is None


VERBOSE_HDR = (
    '"HostName","TaskName","Next Run Time","Status","Last Run Time","Last Result",'
    '"Scheduled Task State","Repeat: Every"\r\n'
)


def test_build_turns_a_stopped_uncontracted_task_into_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime.now().astimezone()
    stopped, fresh = _dm(now - timedelta(hours=6)), _dm(now - timedelta(minutes=3))
    brief = (
        '"TaskName","Next Run Time","Status"\r\n'
        '"\\Q-Stopped","N/A","Ready"\r\n"\\Q-Fresh","N/A","Ready"\r\n'
        '"\\Q-Boot","N/A","Ready"\r\n"\\Q-Resident","N/A","Running"\r\n'
    )
    verbose = VERBOSE_HDR + (
        f'"B","\\Q-Stopped","N/A","Ready","{stopped}","0","Enabled","0 Hour(s), 15 Minute(s)"\r\n'
        f'"B","\\Q-Fresh","N/A","Ready","{fresh}","0","Enabled","Disabled"\r\n'
        f'"B","\\Q-Boot","N/A","Ready","{stopped}","0","Enabled","Disabled"\r\n'
        f'"B","\\Q-Resident","N/A","Running","{stopped}","267009","Enabled","Disabled"\r\n'
    )

    def run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, verbose if "/v" in cmd else brief, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", dict)
    man = tmp_path / ph.MANIFEST
    man.parent.mkdir(parents=True)
    man.write_text(
        'TASK name="Q-Fresh" trigger="every 1 hour" runs="x"\n'
        'TASK name="Q-Boot" trigger="at startup" runs="x"\n'
        'TASK name="Q-Resident" trigger="at startup + every 10 minutes" runs="x"\n',
        encoding="utf-8",
    )
    doc = ph.build()
    by = {r["name"]: r for r in doc["processes"]}
    assert by["Q-Stopped"]["verdict"] == "STALE" and "auto-contract" in by["Q-Stopped"]["why"]
    assert by["Q-Fresh"]["verdict"] == "OK" and "auto-contract" in by["Q-Fresh"]["why"]
    assert by["Q-Boot"]["verdict"] == "UNCONTRACTED"
    assert by["Q-Resident"]["verdict"] == "UNCONTRACTED"  # running: nothing to judge
    assert doc["status"] == "ATTENTION"
