"""The work-seeking lane: units run on events and input changes, under a lease, checkpointed;
the hourly clock is their watchdog. Principal 2026-10-06: "cadence must never be the primary
driver"."""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import department_resident as dr  # noqa: E402
import hourly_cycle as hc  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def lane(monkeypatch, tmp_path):
    """A desk of its own: state, locks, one input file and two units in one department."""
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "RESIDENT_STATE", tmp_path / "resident")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "DESK", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "in.json").write_text("{}", encoding="utf-8")
    units = {
        "feeder": {"dept": "discovery", "kind": "judge_feeder", "inputs": ("data/in.json",),
                   "events": ("CANDIDATES_COMPILED",), "min_gap_s": 60, "watchdog_s": 3600,
                   "timeout_s": 30},
        "producer": {"dept": "discovery", "kind": "producer", "inputs": ("data/none.json",),
                     "events": ("GAUNTLET_SWEPT",), "min_gap_s": 60, "watchdog_s": 3600,
                     "timeout_s": 30},
    }
    monkeypatch.setattr(dr, "RESIDENT_UNITS", units)
    monkeypatch.setattr(dr, "_events_since", lambda _s, _k: [])
    return tmp_path


def _ck(unit: str, **kw) -> None:
    dr._write_json(dr.checkpoint_path(unit), {"unit": unit, **kw})


def test_every_unit_is_a_real_core_leg_of_a_real_resident_department() -> None:
    """A unit nobody's lane runs, or one the hourly clock does not know, would be a second lane
    or a dead one. Every unit is a CORE leg (so it WAS timer-only) of a department that has a
    resident, and the lane runs it through that leg's own `_costed` boundary."""
    for unit, spec in dr.RESIDENT_UNITS.items():
        assert unit in hc.CORE_LEGS, unit
        assert spec["dept"] in hc.DEPARTMENTS, unit
        assert spec["kind"] in ("judge_feeder", "producer")
        assert f'_costed("{unit}"' in Path(hc.__file__).read_text("utf-8"), unit
        assert hc.in_plan(unit, f"legs:{unit}") and not hc.in_plan(unit, "legs:other")


def test_readiness_ranks_event_over_input_over_watchdog(lane) -> None:
    spec = dr.RESIDENT_UNITS["feeder"]
    # never ran: the input exists, so the input change is the reason
    assert dr.unit_readiness("feeder", spec, {}, now=NOW, events=[])[0] == 2
    fin = (NOW - timedelta(minutes=10)).isoformat()
    wm, _ = dr.input_watermark(spec)
    done = {"status": "ok", "started_at": fin, "finished_at": fin, "consumed_watermark": wm}
    prio, why = dr.unit_readiness("feeder", spec, done, now=NOW, events=[])
    assert prio == 0 and why.startswith("idle")
    ev = [{"kind": "CANDIDATES_COMPILED", "at": (NOW - timedelta(minutes=1)).isoformat()}]
    assert dr.unit_readiness("feeder", spec, done, now=NOW, events=ev)[0] == 3
    old = {**done, "finished_at": (NOW - timedelta(hours=2)).isoformat(),
           "started_at": (NOW - timedelta(hours=2)).isoformat()}
    assert dr.unit_readiness("feeder", spec, old, now=NOW, events=[])[0] == 1


def test_a_live_lease_and_the_min_gap_hold_a_unit(lane) -> None:
    spec = dr.RESIDENT_UNITS["feeder"]
    running = {"status": "running", "pid": 1, "started_at": (NOW - timedelta(hours=1)).isoformat(),
               "lease_until": (NOW + timedelta(minutes=5)).isoformat()}
    assert dr.unit_readiness("feeder", spec, running, now=NOW, events=[])[0] == 0
    just = {"status": "ok", "started_at": (NOW - timedelta(seconds=10)).isoformat(),
            "finished_at": NOW.isoformat()}
    prio, why = dr.unit_readiness("feeder", spec, just, now=NOW, events=[])
    assert prio == 0 and why.startswith("min gap")


def test_pick_takes_the_highest_priority_ready_unit(lane, monkeypatch) -> None:
    unit, ready = dr.pick_unit("discovery", now=NOW)
    assert unit == "feeder" and ready["producer"][0] == 1     # never ran: watchdog only
    monkeypatch.setattr(dr, "_events_since", lambda _s, _k: [
        {"kind": "GAUNTLET_SWEPT", "at": NOW.isoformat()}])
    unit, ready = dr.pick_unit("discovery", now=NOW)
    assert unit == "producer" and ready["producer"][0] == 3   # the event pre-empts


def _fake_cycle(tmp_path: Path, rc: int = 0) -> Path:
    script = tmp_path / "fake_cycle.py"
    script.write_text(
        "import json, os, sys\n"
        f"open({str(tmp_path / 'ran.jsonl')!r}, 'a').write(json.dumps({{'plan': "
        "os.environ.get('HOURLY_PLAN'), 'budget': os.environ.get('HOURLY_BUDGET_S')}) + '\\n')\n"
        f"sys.exit({rc})\n", encoding="utf-8")
    return script


def test_run_unit_leases_runs_the_one_leg_and_checkpoints_the_watermark(lane, monkeypatch):
    monkeypatch.setattr(dr, "CYCLE", _fake_cycle(lane))
    monkeypatch.setenv("HOURLY_BUDGET_S", "99")
    res = dr.run_unit("feeder", trigger="test", dept="discovery")
    assert res["status"] == "ok" and res["runs"] == 1 and res["lease_until"] is None
    ran = [json.loads(x) for x in (lane / "ran.jsonl").read_text().splitlines()]
    assert ran == [{"plan": "legs:feeder", "budget": None}]       # unbounded: never rotated out
    assert res["consumed_watermark"] == dr.input_watermark(dr.RESIDENT_UNITS["feeder"])[0]
    # consumed: no longer READY on input, only by watchdog later
    prio, _why = dr.unit_readiness("feeder", dr.RESIDENT_UNITS["feeder"], dr.read_checkpoint(
        "feeder"), now=datetime.now(UTC) + timedelta(minutes=5), events=[])
    assert prio == 0


def test_a_failed_unit_leaves_its_input_unconsumed(lane, monkeypatch):
    monkeypatch.setattr(dr, "CYCLE", _fake_cycle(lane, rc=1))
    res = dr.run_unit("feeder", trigger="test")
    assert res["status"] == "exit" and res["failures"] == 1
    assert "consumed_watermark" not in res


def test_a_unit_leased_by_another_process_is_not_run_twice(lane, monkeypatch):
    monkeypatch.setattr(dr, "CYCLE", _fake_cycle(lane))
    held = dr.claim_unit_lease("feeder")
    try:
        assert dr.run_unit("feeder")["status"] == "leased_elsewhere"
    finally:
        held.close()


def test_the_lane_drains_ready_work_then_idles(lane, monkeypatch):
    monkeypatch.setattr(dr, "CYCLE", _fake_cycle(lane))
    monkeypatch.setattr(dr, "write_census", lambda path=None: {})
    stop = threading.Event()
    n = dr.feeder_lane("discovery", stop, poll_s=1, max_units=2)
    assert n == 2
    beat = json.loads(dr.lane_path("discovery").read_text())
    assert beat["status"] == "stopped" and beat["units_done"] == 2


def test_ownership_needs_a_live_lane_and_a_fresh_ok_checkpoint(lane):
    assert dr.resident_owns("feeder", now=NOW)[0] is False            # no lane, no checkpoint
    dr._write_json(dr.lane_path("discovery"), {"status": "idle", "beat_at": NOW.isoformat()})
    assert dr.resident_owns("feeder", now=NOW)[0] is False            # never ran
    _ck("feeder", status="ok", finished_at=(NOW - timedelta(minutes=20)).isoformat())
    assert dr.resident_owns("feeder", now=NOW)[0] is True
    _ck("feeder", status="exit", finished_at=(NOW - timedelta(minutes=20)).isoformat())
    assert dr.resident_owns("feeder", now=NOW)[0] is False            # failed: watchdog runs it
    _ck("feeder", status="ok", finished_at=(NOW - timedelta(hours=3)).isoformat())
    assert dr.resident_owns("feeder", now=NOW)[0] is False            # too old
    _ck("feeder", status="ok", finished_at=(NOW - timedelta(minutes=1)).isoformat())
    dr._write_json(dr.lane_path("discovery"),
                   {"status": "idle", "beat_at": (NOW - timedelta(hours=1)).isoformat()})
    assert dr.resident_owns("feeder", now=NOW)[0] is False            # dead lane


def test_the_core_clock_skips_an_owned_unit_and_runs_it_otherwise(monkeypatch):
    monkeypatch.setattr(hc, "HOURLY_PLAN", "core")
    monkeypatch.setattr(hc, "_rotation", lambda: None)
    unit = next(iter(dr.RESIDENT_UNITS))
    monkeypatch.setattr(dr, "resident_owns", lambda _u, now=None: (True, "lane alive"))
    ran: list[str] = []
    out = hc._costed(unit, lambda: ran.append("x") or {"status": "OK"})
    assert out["status"] == "RESIDENT_OWNED" and ran == []
    # under the lane's own plan the unit always runs: that pass IS the lane
    monkeypatch.setattr(hc, "HOURLY_PLAN", f"legs:{unit}")
    assert hc._resident_owned(unit)[0] is False


def test_census_classifies_every_leg_and_publishes_unit_state(lane, monkeypatch):
    monkeypatch.setattr(dr, "DESK", DESK)              # the real registry, the fake state
    doc = dr.build_census(now=NOW)
    c = doc["counts"]
    assert c["legs"] == sum(c.get(k, 0) for k in ("resident_work_seeking", "resident_pass",
                                                  "timer_only", "own_task"))
    assert c["resident_work_seeking"] == 0             # the fixture's units are not real legs
    assert set(doc["units"]) == {"feeder", "producer"}
    assert doc["units"]["feeder"]["status"] == "never_ran"
    assert doc["residents"]["discovery"]["lane"] == "UNMEASURED"
    assert "health" in doc["timer_only_legs"]


def test_census_cli_writes_the_report(tmp_path, monkeypatch):
    out = tmp_path / "RESIDENT_ORGANS.json"
    monkeypatch.setattr(dr, "CENSUS_OUT", out)
    monkeypatch.setattr(dr, "RESIDENT_STATE", tmp_path / "resident")
    assert dr.main(["--census"]) == 0
    doc = json.loads(out.read_text())
    assert doc["counts"]["resident_work_seeking"] == len(dr.RESIDENT_UNITS)
    assert set(doc["timer_only_legs"]).isdisjoint(dr.RESIDENT_UNITS)
    assert os.path.basename(str(out)) == "RESIDENT_ORGANS.json"
