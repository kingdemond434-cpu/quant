"""The fence for "a long job on a short trigger" (BACKLOG 2026-09-29).

A task whose measured run is longer than its trigger interval leaves the scheduler's own evidence:
under IgnoreNew the next trigger is REFUSED (0x800710E0), and a run past its ExecutionTimeLimit is
KILLED (0x41306). process_health publishes every such task in `cadence_overruns`, except a 24/7
resident's keep-alive refusal, which is the watchdog finding the resident alive.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_cadence_under_test", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)


def _row(name: str, code: int | None, every: int | None = 5, state: str = "Enabled") -> dict:
    return {"name": name, "state": state, "last_result_code": code,
            "repeat_every_min": every, "last_run": "11/11/2026 11:11:01 AM"}


def test_a_refused_trigger_on_a_periodic_job_is_an_overrun() -> None:
    out = ph.cadence_overruns([_row("MT5-LongJob", 2147946720, every=5),
                               _row("MT5-Fine", 0)], frozenset(), True)
    assert out["status"] == "MEASURED"
    assert [o["name"] for o in out["overruns"]] == ["MT5-LongJob"]
    assert out["overruns"][0]["evidence"].startswith("REFUSED_STILL_RUNNING")
    assert out["overruns"][0]["repeat_every_min"] == 5


def test_a_resident_keepalive_refusal_is_not_an_overrun_but_a_kill_is() -> None:
    residents = frozenset({"MT5-Dept-Intel", "MT5-Gauntlet"})
    out = ph.cadence_overruns([_row("MT5-Dept-Intel", 2147946720, every=10),
                               _row("MT5-Gauntlet", 267014)], residents, True)
    assert out["resident_keepalive"] == ["MT5-Dept-Intel"]
    assert [o["name"] for o in out["overruns"]] == ["MT5-Gauntlet"]
    assert out["overruns"][0]["evidence"].startswith("KILLED_AT_LIMIT")


def test_an_unread_run_history_is_unmeasured_never_clean() -> None:
    out = ph.cadence_overruns([_row("MT5-LongJob", 2147946720)], frozenset(), False)
    assert out["status"] == "UNMEASURED" and out["overruns"] == []


def test_components_and_absent_organs_are_not_judged() -> None:
    out = ph.cadence_overruns([_row("X (rotation)", 2147946720, state="COMPONENT"),
                               _row("Y", 267014, state="ABSENT")], frozenset(), True)
    assert out["overruns"] == []


def test_the_manifest_names_the_residents_and_the_repeat_is_parsed() -> None:
    residents = ph.resident_tasks()
    assert {"MT5-Gauntlet", "MT5-Dept-Intel", "MT5-Forest-China"} <= residents
    assert "MT5-AllocatorFast" not in residents
    assert ph.repeat_minutes("0 Hour(s), 10 Minute(s)") == 10
    assert ph.repeat_minutes("1 Hour(s), 0 Minute(s)") == 60
    assert ph.repeat_minutes("Disabled") is None
    assert ph.repeat_minutes("") is None
