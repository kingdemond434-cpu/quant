"""The judge's core share (principal 2026-11-13: 6-core floor, adaptive): rule and safety."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research import judge_core_share as jcs

DESK = Path(__file__).resolve().parents[1]
BELOW = {"status": "MEASURED", "below_pace": True, "first_terminal_per_day": 15625}
AT_PACE = {"status": "MEASURED", "below_pace": False, "first_terminal_per_day": 200000}
UNM = {"status": "UNMEASURED"}


# ------------------------------------------------------------------ the rule
def test_no_judge_work_reserves_nothing() -> None:
    d = jcs.decide(18, demand=0, reserved_now=6, miner_busy=3.0, pace_doc=BELOW)
    assert (d["reserve"], d["mode"]) == (0, "IDLE")


@pytest.mark.parametrize("pace_doc", [UNM, AT_PACE])
def test_the_floor_without_a_measured_shortfall(pace_doc: dict) -> None:
    d = jcs.decide(18, demand=18, reserved_now=0, miner_busy=1.0, pace_doc=pace_doc)
    assert (d["reserve"], d["mode"]) == (6, "FLOOR")


def test_the_floor_never_exceeds_the_judges_demand_or_the_miners_minimum() -> None:
    assert jcs.decide(18, demand=1, reserved_now=0, miner_busy=1.0,
                      pace_doc=BELOW)["reserve"] == 1           # a lone merge: one core
    assert jcs.decide(8, demand=18, reserved_now=0, miner_busy=1.0,
                      pace_doc=BELOW)["reserve"] == 4           # 8 cores keep MINER_MIN=4


def test_behind_pace_it_borrows_the_miners_idle_cores_up_to_the_ceiling() -> None:
    d = jcs.decide(18, demand=18, reserved_now=6, miner_busy=5.0, pace_doc=BELOW)
    assert d["mode"] == "BORROWING" and d["reserve"] == 12      # 7 idle -> +6, capped at 12
    d = jcs.decide(18, demand=8, reserved_now=6, miner_busy=2.0, pace_doc=BELOW)
    assert d["reserve"] == 8                                    # never above the demand


def test_it_gives_back_the_moment_the_miners_saturate() -> None:
    d = jcs.decide(18, demand=18, reserved_now=10, miner_busy=7.8, pace_doc=BELOW)
    assert (d["reserve"], d["mode"]) == (6, "GIVING_BACK")


def test_an_unread_miner_load_never_borrows() -> None:
    d = jcs.decide(18, demand=18, reserved_now=6, miner_busy=None, pace_doc=BELOW)
    assert (d["reserve"], d["mode"]) == (6, "FLOOR")


def test_a_small_slack_holds_the_current_reservation() -> None:
    d = jcs.decide(18, demand=18, reserved_now=8, miner_busy=9.0, pace_doc=BELOW)
    assert d["reserve"] == 8


def test_cores_for_takes_the_highest_cpus_for_the_judge() -> None:
    assert jcs.cores_for(18, 6) == (list(range(12, 18)), list(range(12)))
    assert jcs.cores_for(4, 9) == ([0, 1, 2, 3], [])


def test_pace_reads_the_published_rate_and_burndown() -> None:
    p = jcs.pace({"verdicts": {"first_terminal_counts": {"24h": 15625}}},
                 {"queue": {"burndown_status": "SHRINKING"}})
    assert p["status"] == "MEASURED" and p["below_pace"] is True
    p = jcs.pace({"verdicts": {"first_terminal_counts": {"24h": 200000}}},
                 {"queue": {"burndown_status": "GROWING"}})
    assert p["below_pace"] is True                              # backlog growing is behind too
    p = jcs.pace({"verdicts": {"first_terminal_counts": {"24h": 200000}}}, {})
    assert p["below_pace"] is False
    assert jcs.pace({}, {})["status"] == "UNMEASURED"


def test_judge_demand_counts_working_leaves() -> None:
    rows = [{"pid": 1, "ppid": 0, "cls": "judge"},             # the resident
            {"pid": 2, "ppid": 1, "cls": "judge"},             # the sweep, waiting on its pool
            *({"pid": 10 + i, "ppid": 2, "cls": "judge"} for i in range(18)),
            {"pid": 50, "ppid": 0, "cls": "judge_warm"},
            {"pid": 60, "ppid": 0, "cls": "miner"}]
    assert jcs.judge_demand(rows) == 19
    assert jcs.judge_demand(rows[:2]) == 1                      # the lone merge


# ------------------------------------------------------------------ the enforcer
class Box:
    """A fake process table: affinities change only through `set`."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = [
            {"pid": 100, "ppid": 0, "cls": "judge", "create_time": 1.0},
            *({"pid": 101 + i, "ppid": 100, "cls": "judge", "create_time": 2.0}
              for i in range(18)),
            {"pid": 200, "ppid": 0, "cls": "miner", "create_time": 3.0},
            {"pid": 201, "ppid": 0, "cls": "audit", "create_time": 3.0},
            {"pid": 202, "ppid": 0, "cls": "miner", "create_time": 3.0,
             "affinity_start": [0, 1, 2, 3]},
            {"pid": 300, "ppid": 0, "cls": "live", "create_time": 4.0},
            {"pid": 400, "ppid": 0, "cls": "other", "create_time": 5.0},
            {"pid": 500, "ppid": 0, "cls": "judge_warm", "create_time": 6.0}]
        self.aff = {r["pid"]: list(r.get("affinity_start") or range(18)) for r in self.rows}
        self.cpu = {r["pid"]: 0.0 for r in self.rows}
        self.calls: list[tuple[int, list[int]]] = []
        self.refuse: set[int] = set()

    def snap(self) -> list[dict[str, Any]]:
        return [{**r, "affinity": list(self.aff[r["pid"]]), "cpu_s": self.cpu[r["pid"]]}
                for r in self.rows]

    def set(self, pid: int, cores: list[int], row: dict[str, Any]) -> None:
        if pid in self.refuse:
            raise LookupError("pid reused")
        self.calls.append((pid, cores))
        self.aff[pid] = list(cores)


@pytest.fixture
def box(tmp_path: Path) -> tuple[Box, jcs.Enforcer]:
    b = Box()
    t = [0.0]

    def clock() -> float:
        t[0] += 10.0
        return t[0]

    e = jcs.Enforcer(snap=b.snap, setter=b.set, classify=lambda rows: rows, ncpu=18,
                     clock=clock, pace_reader=lambda: dict(BELOW),
                     report=tmp_path / "JUDGE_CORE_SHARE.json",
                     state=tmp_path / "state.json", owner={"pid": 100, "create_time": 1.0})
    return b, e


def test_it_confines_only_miners_and_audit(box) -> None:
    b, e = box
    doc = e.tick()
    assert doc["reserved"] == 6 and doc["reserved_cores"] == list(range(12, 18))
    assert b.aff[200] == list(range(12)) and b.aff[201] == list(range(12))
    assert b.aff[202] == [0, 1, 2, 3]                 # already off the reserved cores: untouched
    for pid in (100, 101, 300, 400, 500):
        assert b.aff[pid] == list(range(18)), pid      # judge, live, other, warmer: never touched
    touched = {pid for pid, _ in b.calls}
    assert touched == {200, 201}


def test_release_restores_the_recorded_affinity(box) -> None:
    b, e = box
    e.tick()
    st = json.loads(e.state_path.read_text("utf-8"))
    assert {v["pid"] for v in st["touched"].values()} == {200, 201}
    e.release("test")
    assert b.aff[200] == list(range(18)) and b.aff[201] == list(range(18))
    assert json.loads(e.state_path.read_text("utf-8"))["touched"] == {}


def test_judge_idle_gives_every_core_back(box) -> None:
    b, e = box
    e.tick()
    b.rows = [r for r in b.rows if r["cls"] != "judge"]
    assert e.tick()["reserved"] == 1                   # the cache warmer is judging work too
    b.rows = [r for r in b.rows if r["cls"] not in ("judge", "judge_warm")]
    doc = e.tick()
    assert doc["mode"] == "IDLE" and b.aff[200] == list(range(18))


def test_borrowing_and_giving_back_on_the_measured_load(box) -> None:
    b, e = box
    e.tick()                                           # first tick: floor (load unmeasured)
    b.cpu[200] += 10.0 * 2                             # miners busy 2 of 12 allowed cores
    doc = e.tick()
    assert doc["mode"] == "BORROWING" and doc["reserved"] == 12
    assert b.aff[200] == list(range(6))
    b.cpu[200] += 10.0 * 6                             # miners saturate their 6 cores
    doc = e.tick()
    assert doc["mode"] == "GIVING_BACK" and doc["reserved"] == 6
    assert b.aff[200] == list(range(12))


def test_every_change_publishes_a_missed_growth_line(box) -> None:
    b, e = box
    e.tick()
    b.cpu[200] += 20.0
    e.tick()
    lines = json.loads(e.report.read_text("utf-8"))["missed_growth"]
    assert [(x["from_reserved"], x["to_reserved"]) for x in lines] == [(0, 6), (6, 12)]
    assert all(x["rail"] == "judge_core_share" and x["verdict"] == "UNMEASURED" for x in lines)


def test_a_refused_pid_is_reported_and_never_recorded(box) -> None:
    b, e = box
    b.refuse.add(201)
    doc = e.tick()
    assert doc["affinity_errors"] and doc["affinity_errors"][0]["pid"] == 201
    st = json.loads(e.state_path.read_text("utf-8"))
    assert {v["pid"] for v in st["touched"].values()} == {200}


def test_switched_off_releases(box, monkeypatch) -> None:
    b, e = box
    e.tick()
    monkeypatch.setenv("JUDGE_CORE_SHARE", "0")
    doc = e.tick()
    assert doc["mode"] == "DISABLED" and b.aff[200] == list(range(18))


def test_a_live_owner_elsewhere_is_left_alone(box) -> None:
    b, e = box
    e.state_path.write_text(json.dumps({"owner": {"pid": 300, "create_time": 4.0},
                                        "touched": {}}), "utf-8")
    assert e.tick()["mode"] == "NOT_OWNER" and not b.calls


def test_release_orphaned_restores_after_a_dead_sweep(box) -> None:
    b, e = box
    e.tick()
    b.rows = [r for r in b.rows if r["pid"] != 100]    # the owning sweep died
    assert jcs.release_orphaned(e)["status"] == "RELEASED"
    assert b.aff[200] == list(range(18))
    assert jcs.release_orphaned(e)["status"] == "NOTHING_CONFINED"


def test_release_orphaned_leaves_a_live_owner(box) -> None:
    b, e = box
    e.tick()
    assert jcs.release_orphaned(e)["status"] == "OWNER_ALIVE"
    assert b.aff[200] == list(range(12))


def test_the_floor_and_ceiling_move_by_env(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_CORE_FLOOR", "8")
    monkeypatch.setenv("JUDGE_CORE_CEILING", "4")
    s = jcs.settings()
    assert (s["floor"], s["ceiling"]) == (8, 8)       # a ceiling below the floor reads as the floor


# ------------------------------------------------------------------ the wiring
def test_the_sweep_starts_and_releases_the_share() -> None:
    src = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    body = src[src.index("def _sweep_once"):src.index("PUBLISH_PRIORITY_LOCK_S")]
    assert "start_for_sweep()" in body and "share.stop()" in body
    assert body.index("start_for_sweep()") < body.index('_phase("plan")')


def test_the_hourly_organ_releases_orphans_and_missed_growth_carries_the_lines() -> None:
    jt = (DESK / "research" / "judging_throughput.py").read_text("utf-8")
    assert "release_orphaned()" in jt
    mg = (DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"judge_core_share": organ_published_lines(' in mg


def test_no_priority_class_is_changed_here() -> None:
    src = (DESK / "research" / "judge_core_share.py").read_text("utf-8")
    assert ".nice(" not in src and "PRIORITY_CLASS" not in src
