"""A HUNG research task is ended and run again, box-natively (principal 2026-11-24: the box never
needs his words to unstick a producer). Audit 11-20 conditions: research allow-list only, output
older than HUNG_FACTOR x its limit while the task reads Running, `schtasks /End` on that task only,
the same re-run bounds, every End logged, and no live task can ever be ended."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import desk_self_heal as heal  # noqa: E402
import run_desk_self_heal as rheal  # noqa: E402

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)
DOCKET = "desks/mt5/data/hypotheses/external_survivors.json"


def _write(root: Path, rel: str, age_h: float) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({}), encoding="utf-8")
    t = (NOW - timedelta(hours=age_h)).timestamp()
    os.utime(p, (t, t))


def _run(tmp_path: Path, *, running: bool, now: datetime = NOW, end_ok: bool = True):
    calls: list[tuple[str, str]] = []
    doc = rheal.run(root=tmp_path, apply=True, out=tmp_path / "out.json",
                    ledger_path=tmp_path / "ledger.json", now=now,
                    run_task=lambda t: calls.append(("run", t)) or True,
                    task_running=lambda t: running,
                    end_task=lambda t: calls.append(("end", t)) or end_ok)
    return doc, calls


def _docket(calls):
    return [c for c in calls if c[1] == "MT5-MergeDocket"]


def test_merge_docket_is_a_watched_research_lane():
    assert "MT5-MergeDocket" in heal.RESEARCH_TASKS
    assert heal.research_task("MT5-MergeDocket")


def test_hung_running_task_is_ended_then_run_and_logged(tmp_path):
    _write(tmp_path, DOCKET, age_h=22)
    doc, calls = _run(tmp_path, running=True)
    assert _docket(calls) == [("end", "MT5-MergeDocket"), ("run", "MT5-MergeDocket")]
    assert {"task": "MT5-MergeDocket", "at": NOW.isoformat(timespec="seconds"),
            "ended": True} in doc["ended"]
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert any(r["task"] == "MT5-MergeDocket" for r in ledger[rheal.END_KEY])


def test_idle_but_not_hung_is_run_only(tmp_path):
    _write(tmp_path, DOCKET, age_h=4)          # past 3h limit, under 2x
    _, calls = _run(tmp_path, running=True)
    assert _docket(calls) == [("run", "MT5-MergeDocket")]


def test_hung_but_not_running_is_run_only(tmp_path):
    _write(tmp_path, DOCKET, age_h=22)
    doc, calls = _run(tmp_path, running=False)
    assert _docket(calls) == [("run", "MT5-MergeDocket")]
    assert not doc["ended"]


def test_failed_end_does_not_launch_a_second_copy(tmp_path):
    _write(tmp_path, DOCKET, age_h=22)
    doc, calls = _run(tmp_path, running=True, end_ok=False)
    assert _docket(calls) == [("end", "MT5-MergeDocket")]
    assert doc["ended"][0]["ended"] is False


def test_end_obeys_the_rerun_bounds(tmp_path):
    _write(tmp_path, DOCKET, age_h=22)
    _, first = _run(tmp_path, running=True)
    _, inside_gap = _run(tmp_path, running=True, now=NOW + timedelta(minutes=30))
    assert len(_docket(first)) == 2 and not _docket(inside_gap)
    ends = 0
    for h in range(0, 24, 3):
        _, calls = _run(tmp_path, running=True, now=NOW + timedelta(hours=h))
        ends += sum(1 for c in _docket(calls) if c[0] == "end")
    assert ends <= rheal.RERUN_MAX_PER_DAY


def test_no_live_task_can_ever_be_ended(tmp_path, monkeypatch):
    live = ["MT5-E8-Executor", "MT5-FTMO-Executor", "MT5-Follower", "MT5-Gateway",
            "MT5-AdoptRelease", "MT5-Dept-LiveBridge", "MT5-Forest-E8", "MT5-Fusion-Executor"]
    forged = [heal.Finding(f"lane {t}", False, "idle", fixable=True, task=t, hung=True)
              for t in live]
    monkeypatch.setattr(heal, "audit", lambda root, now: forged)
    _, calls = _run(tmp_path, running=True)
    assert not [c for c in calls if c[0] == "end"]
    assert not any(heal.research_task(t) for t in live)
    # the actuator itself refuses before any scheduler call, on every OS
    monkeypatch.setattr(rheal.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert not any(rheal._end_task(t) for t in live)


def test_a_lanes_file_cannot_make_a_live_task_hung_and_ended(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    _write(tmp_path, "desks/mt5/reports/X.json", age_h=50)
    _write(tmp_path, heal.LANES_FILE, 0)
    (tmp_path / heal.LANES_FILE).write_text(json.dumps([
        {"lane": "x", "path": "desks/mt5/reports/X.json", "max_age_h": 1,
         "task": "MT5-E8-Executor"}]), encoding="utf-8")
    _, calls = _run(tmp_path, running=True)
    assert not any(t == "MT5-E8-Executor" for _, t in calls)



def _stall(root: Path, incidents: dict, *, at_h: float = 0.05) -> None:
    p = root / "desks/mt5/reports/JUDGE_STALL.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": (NOW - timedelta(hours=at_h)).isoformat(),
                             "incidents": incidents}), encoding="utf-8")
    t = (NOW - timedelta(hours=min(at_h, 0.05))).timestamp()
    os.utime(p, (t, t))


def _throughput(root: Path, gap_h: float) -> None:
    p = root / "desks/mt5/reports/JUDGING_THROUGHPUT.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rate": {"first_judged_per_day": 6734.0, "verdicts": {
        "last_verdict_at": (NOW - timedelta(hours=gap_h)).isoformat()}}}), encoding="utf-8")


def _gauntlet(calls):
    return [c for c in calls if c[1] == heal.JUDGE_TASK]


def _ends(calls):
    return [c for c in _gauntlet(calls) if c[0] == "end"]


def test_a_5h_verdict_gap_with_a_healthy_heartbeat_is_never_ended(tmp_path):
    """Audit MF-1: the ledger appends only when a verdict changes; healthy gaps ran 5.5-31h."""
    _throughput(tmp_path, 5.0)
    _stall(tmp_path, {"no_verdict": {"open": True, "why": "no new verdict for 5.0h"},
                      "resident_dead": {"open": False}, "sweep_dead": {"open": False},
                      "phase_overrun": {"open": False, "phase": "build_shards"}})
    _, calls = _run(tmp_path, running=True)
    assert not _ends(calls) and ("run", "MT5-Gauntlet") in calls


def test_a_stale_heartbeat_is_ended_then_run(tmp_path):
    _stall(tmp_path, {"resident_dead": {"open": True, "why": "heartbeat 42 min old"}})
    doc, calls = _run(tmp_path, running=True)
    assert _gauntlet(calls) == [("end", "MT5-Gauntlet"), ("run", "MT5-Gauntlet")]
    assert any(r["task"] == "MT5-Gauntlet" for r in doc["ended"])


def test_a_stale_reading_never_ends_anything(tmp_path):
    """Audit MF-2: every input the End reads carries a fresh `at`, or nothing is ended."""
    _throughput(tmp_path, 40.0)
    _stall(tmp_path, {"resident_dead": {"open": True}}, at_h=3.0)
    _, calls = _run(tmp_path, running=True)
    assert not _ends(calls)


def test_merge_and_publish_inside_its_limit_is_never_ended(tmp_path):
    """Audit MF-3: 10-18 the resident died mid merge_and_publish; only an overrun is hung."""
    _stall(tmp_path, {"phase_overrun": {"open": False, "phase": "merge_and_publish",
                                        "hours": 2.0}})
    _, calls = _run(tmp_path, running=True)
    assert not _ends(calls)
    over = tmp_path / "overrun"
    _stall(over, {"phase_overrun": {"open": True, "phase": "merge_and_publish",
                                    "hours": 3.5}})
    _, calls = _run(over, running=True)
    assert _ends(calls) == [("end", "MT5-Gauntlet")]


def test_the_judge_is_research_and_never_live_shaped():
    assert heal.research_task("MT5-Gauntlet")
    assert not heal._LIVE_TASK.search("MT5-Gauntlet")
