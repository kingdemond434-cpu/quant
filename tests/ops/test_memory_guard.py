from __future__ import annotations

import json
from pathlib import Path

from ops import memory_guard as mg

BOX = {"total_phys_mb": 98_298, "free_phys_mb": 44_000, "commit_charge_mb": 150_000,
       "commit_limit_mb": 251_700}


def proc(pid: int, mb: float, cmd: str, name: str = "python.exe") -> dict:
    return {"pid": pid, "name": name, "private_mb": mb, "cmdline": cmd.split(),
            "cwd": "C:\\opt\\quant"}


SCALING = r"C:\Program Files\Python314\python.exe -m libs.ops.scaling_laws"


def test_healthy_box_touches_nothing() -> None:
    d = mg.plan(BOX, [proc(1, 9_000, SCALING)], set())
    assert d["stop"] is None and d["rule"] == "CLEAR"


def test_a_leak_over_the_hard_cap_is_stopped_even_without_pressure() -> None:
    d = mg.plan(BOX, [proc(1, 9_000, "python -m judge"), proc(13224, 30_000, SCALING)], set())
    assert d["rule"] == "HARD_CAP" and d["stop"]["pid"] == 13224


def test_pressure_stops_the_largest_research_job_only() -> None:
    low = {**BOX, "free_phys_mb": 6_000}
    d = mg.plan(low, [proc(1, 3_000, "python -m a"), proc(2, 8_000, "python -m b")], set())
    assert d["rule"] == "PRESSURE" and d["stop"]["pid"] == 2


def test_small_jobs_are_never_blamed_for_pressure() -> None:
    low = {**BOX, "free_phys_mb": 6_000}
    d = mg.plan(low, [proc(1, 500, "python -m a")], set())
    assert d["stop"] is None and d["rule"] == "PRESSURE_NO_CANDIDATE"


def test_commit_near_limit_is_pressure() -> None:
    hot = {**BOX, "commit_charge_mb": 240_000}
    d = mg.plan(hot, [proc(2, 8_000, "python -m b")], set())
    assert d["rule"] == "PRESSURE"


def test_live_path_and_terminals_are_never_candidates() -> None:
    low = {**BOX, "free_phys_mb": 1_000}
    procs = [
        proc(1, 60_000, "terminal64.exe /portable", name="terminal64.exe"),
        proc(2, 60_000, r"python desks\mt5\mt5desk\gateway.py"),
        proc(3, 60_000, r"python -m desks.mt5.prop.e8_gold"),
        proc(4, 60_000, r"python desks\mt5\ftmo_allocator.py"),
        proc(5, 60_000, r"python desks\mt5\recorders\tick_recorder.py"),
        proc(6, 60_000, r"python proposals\fusion_deadman.py"),
        proc(7, 60_000, "python -m ops.memory_guard --apply"),
        proc(8, 60_000, "cmd.exe /c run_frontier_audit.cmd", name="cmd.exe"),
    ]
    d = mg.plan(low, procs, set())
    assert d["stop"] is None
    d2 = mg.plan(low, [proc(9, 60_000, SCALING)], {9})
    assert d2["stop"] is None  # our own tree


def test_requeue_cycle_caps_attempts_per_day() -> None:
    at = "2026-11-11T14:20:00+00:00"
    rows = mg.enqueue([], proc(13224, 30_000, SCALING), "HARD_CAP", "leak", at)
    rows = mg.enqueue(rows, proc(13224, 31_000, SCALING), "HARD_CAP", "leak", at)
    assert len(rows) == 1 and rows[0]["peak_mb"] == 31_000
    for _ in range(mg.MAX_ATTEMPTS):
        r = mg.next_requeue(rows, at, set())
        assert r is not None
        r["attempts"]["2026-11-11"] = r["attempts"].get("2026-11-11", 0) + 1
    assert mg.next_requeue(rows, at, set()) is None
    assert rows[0]["state"] == "GAVE_UP" and "stream" in rows[0]["gave_up_why"]


def test_running_rerun_is_not_started_twice_and_settles_done() -> None:
    at = "2026-11-11T14:20:00+00:00"
    rows = mg.enqueue([], proc(1, 30_000, SCALING), "HARD_CAP", "leak", at)
    key = rows[0]["key"]
    assert mg.next_requeue(rows, at, {key}) is None
    rows[0]["state"] = "RUNNING"
    rows = mg.settle(rows, {key}, at)
    assert rows[0]["state"] == "RUNNING"
    rows = mg.settle(rows, set(), at)
    assert rows[0]["state"] == "DONE"
    rows = mg.settle(rows, set(), "2026-11-20T00:00:00+00:00")
    assert rows == []


def test_headroom_needs_twice_the_floor() -> None:
    th = mg.thresholds(BOX)
    assert mg.headroom(BOX, th)
    assert not mg.headroom({**BOX, "free_phys_mb": 20_000}, th)


def test_dry_pass_writes_a_report_and_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REPORT", tmp_path / "MEMORY_GUARD.json")
    monkeypatch.setattr(mg, "QUEUE", tmp_path / "q.json")
    stopped: list[int] = []
    monkeypatch.setattr(mg, "stop", lambda pid: stopped.append(pid) or {"result": "STOPPED"})
    monkeypatch.setattr(mg, "_processes", lambda: [proc(13224, 10**7, SCALING)])
    monkeypatch.setattr(mg, "_own_pids", lambda: set())
    doc = mg.run_pass(apply=False)
    assert doc["verdict"] == "HARD_CAP" and doc["actions"] == [] and stopped == []
    assert not (tmp_path / "q.json").exists()
    assert json.loads((tmp_path / "MEMORY_GUARD.json").read_text("utf-8"))["verdict"] == "HARD_CAP"


def test_applied_pass_stops_and_queues(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REPORT", tmp_path / "MEMORY_GUARD.json")
    monkeypatch.setattr(mg, "QUEUE", tmp_path / "q.json")
    monkeypatch.setattr(mg, "stop", lambda pid: {"pid": pid, "result": "STOPPED"})
    monkeypatch.setattr(mg, "_processes", lambda: [proc(13224, 10**7, SCALING)])
    monkeypatch.setattr(mg, "_own_pids", lambda: set())
    doc = mg.run_pass(apply=True)
    assert doc["actions"][0]["action"] == "STOP"
    assert mg.load_queue(tmp_path / "q.json")[0]["state"] == "QUEUED"
