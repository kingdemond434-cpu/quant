"""The reconciler: postconditions decide repairs, only the reconciler assigns HEALTHY, epochs
are immutable, and a required failure is fail-closed."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.control_plane import actuators as act
from libs.ops.control_plane import edges, lease, reconciler
from libs.ops.control_plane import watermarks as wm
from libs.ops.control_plane.specs import Registry, spec

TICKS = {"t": 0.0}


def _clock() -> float:
    return TICKS["t"]


def _sleep(s: float) -> None:
    TICKS["t"] += s


def _resident(cid: str = "resident:dept_x", task: str = "MT5-X") -> object:
    return spec(cid, kind="resident", host="box", cadence_s=600, timeout_s=1_800,
                criticality="required", schedule=task, restart_action=f"restart:task:{task}")


def test_restart_with_rc_zero_and_no_lock_is_not_repaired(tmp_path: Path):
    TICKS["t"] = 0.0
    a = act.restart_resident("resident:dept_x", "MT5-X", "dept_x", window_s=30)
    ctx = {"locks": tmp_path, "watermark_root": tmp_path / "wm"}
    rec = act.run_actuator(a, ctx, runner=lambda argv, t, cwd: {"rc": 0, "tail": "ok"},
                           sleeper=_sleep, clock=_clock)
    assert rec["rc"] == 0 and rec["result"] == "UNPROVEN" and rec["repaired"] is False
    assert rec["proofs"][0]["postcondition"] == "new_live_lock_holder"
    assert rec["proofs"][0]["proved"] is False and "holds no pid" in rec["proofs"][0]["why"]
    assert rec["seconds"] >= 30                                   # it waited the whole window


def test_restart_is_repaired_only_when_lock_and_watermark_both_prove(tmp_path: Path):
    TICKS["t"] = 0.0
    locks = tmp_path / "locks"
    locks.mkdir()
    wroot = tmp_path / "wm"
    a = act.restart_resident("resident:dept_x", "MT5-X", "dept_x", window_s=30)
    wm.progress("resident:dept_x", "passes", 1, root=wroot)
    before = wm.read("resident:dept_x", wroot)

    def runner(argv, t, cwd):
        (locks / "dept_x.lock").write_text(f"{os.getpid()} now\n", encoding="utf-8")
        wm.progress("resident:dept_x", "passes", 2, root=wroot)
        return {"rc": 0, "tail": "started"}

    ctx = {"locks": locks, "watermark_root": wroot, "watermark_before": before,
           "pid_before": 424242}
    rec = act.run_actuator(a, ctx, runner=runner, sleeper=_sleep, clock=_clock)
    assert rec["result"] == "REPAIRED" and rec["repaired"] is True
    assert {p["postcondition"] for p in rec["proofs"]} == {"new_live_lock_holder",
                                                             "watermark_advanced"}
    # rc != 0 with a proven postcondition is STILL repaired: the world, not the code, decides
    rec2 = act.run_actuator(a, {**ctx, "pid_before": None},
                            runner=lambda argv, t, cwd: {"rc": 1, "tail": "eh"},
                            sleeper=_sleep, clock=_clock)
    assert rec2["result"] == "REPAIRED"
    # and the SAME pid still holding the slot is not a restart
    rec3 = act.run_actuator(a, {**ctx, "pid_before": os.getpid()},
                            runner=lambda argv, t, cwd: {"rc": 0, "tail": ""},
                            sleeper=_sleep, clock=_clock)
    assert rec3["result"] == "UNPROVEN" and "SAME pid" in rec3["why"]


def test_an_actuator_without_postconditions_can_never_repair(tmp_path: Path):
    a = act.Actuator("bare", ("true",))
    rec = act.run_actuator(a, runner=lambda argv, t, cwd: {"rc": 0, "tail": ""},
                           sleeper=_sleep, clock=_clock)
    assert rec["result"] == "UNPROVEN" and "no postcondition" in rec["why"]
    assert act.run_actuator(a, apply=False)["result"] == "DRY_RUN"


def test_only_the_reconciler_assigns_healthy(tmp_path: Path):
    wroot = tmp_path / "wm"
    locks = tmp_path / "locks"
    locks.mkdir()
    s = _resident()
    (locks / "dept_x.lock").write_text(f"{os.getpid()} now\n", encoding="utf-8")
    now = datetime.now(tz=UTC)
    # a component writing "HEALTHY" into its own watermark changes nothing: no watermark = DEGRADED
    o = reconciler.observe(s, now=now, root=tmp_path, locks=locks, watermark_root=wroot,
                           lineage=tmp_path / "l.sqlite")
    assert o.state == "DEGRADED" and "no watermark" in o.why
    wm.progress("resident:dept_x", "passes", 3, root=wroot, status="HEALTHY")
    o = reconciler.observe(s, now=now, root=tmp_path, locks=locks, watermark_root=wroot,
                           lineage=tmp_path / "l.sqlite")
    assert o.state == "HEALTHY"
    stalled = reconciler.observe(s, now=now + timedelta(seconds=s.max_silence_s + 1),
                                 root=tmp_path, locks=locks, watermark_root=wroot,
                                 lineage=tmp_path / "l.sqlite")
    assert stalled.state == "STALLED"
    (locks / "dept_x.lock").unlink()
    dead = reconciler.observe(s, now=now, root=tmp_path, locks=locks, watermark_root=wroot,
                              lineage=tmp_path / "l.sqlite")
    assert dead.state == "BROKEN"
    unsched = reconciler.observe(spec("exe:z"), now=now, root=tmp_path)
    assert unsched.state == "DECLARED"
    q = reconciler.observe(s, now=now, root=tmp_path, locks=locks, watermark_root=wroot,
                           quarantine={"resident:dept_x": "operator hold"})
    assert q.state == "QUARANTINED" and q.why == "operator hold"


def test_epoch_ids_are_immutable_and_stale_reports_cannot_certify():
    at = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    e1, e2 = reconciler.epoch_id(at), reconciler.epoch_id(at)
    assert e1 == e2 and e1 != reconciler.epoch_id(at + timedelta(hours=1))
    started = at.isoformat(timespec="seconds")
    old = {"epoch_id": "E-older", "created_at": (at - timedelta(minutes=5)).isoformat()}
    ok, why = reconciler.epoch_compatible(old, e1, started)
    assert ok is False and "BEFORE this epoch began" in why
    same = {"epoch_id": e1, "created_at": (at - timedelta(days=1)).isoformat()}
    assert reconciler.epoch_compatible(same, e1, started)[0] is True
    newer = {"epoch_id": "E-other", "created_at": (at + timedelta(minutes=5)).isoformat()}
    assert reconciler.epoch_compatible(newer, e1, started)[0] is True
    assert reconciler.epoch_compatible(None, e1, started)[0] is None


def test_first_broken_invariant_is_named_and_unmeasured_never_passes():
    inv = {n: {"ok": True, "measured": {}, "why": ""} for n in reconciler.INVARIANTS}
    assert reconciler.first_broken(inv) is None
    inv["forward"] = {"ok": None, "measured": {}, "why": "UNMEASURED"}
    assert reconciler.first_broken(inv)["invariant"] == "forward"
    inv["freshness"] = {"ok": False, "measured": {}, "why": "expired"}
    assert reconciler.first_broken(inv)["invariant"] == "freshness"     # first in order


def test_reconcile_pass_is_fail_closed_on_a_required_repair(tmp_path: Path, monkeypatch):
    TICKS["t"] = 0.0
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "l.sqlite")
    monkeypatch.setattr(lease, "ACK_LOG", tmp_path / "acks.jsonl")
    from libs.ops.control_plane import fingerprints as fp
    monkeypatch.setattr(fp, "LEDGER", tmp_path / "fp.jsonl")
    reg = Registry([_resident()])
    locks = tmp_path / "locks"
    locks.mkdir()
    doc = reconciler.reconcile(registry=reg, root=tmp_path, apply=True, budget_s=60,
                               locks=locks, watermark_root=tmp_path / "wm",
                               lineage=tmp_path / "l.sqlite",
                               runner=lambda argv, t, cwd: {"rc": 0, "tail": "ok"},
                               sleeper=_sleep, clock=_clock,
                               census={"executables": 1, "executables_unclaimed": [],
                                       "coverage": 1.0})
    assert doc["plan"][0]["component_id"] == "resident:dept_x"
    assert doc["repairs"][0]["result"] == "UNPROVEN" and doc["repairs"][0]["rc"] == 0
    assert doc["failed_required_repairs"] == ["resident:dept_x"]
    assert doc["DESK_CLOSED_AND_HEALTHY"] is False
    assert doc["invariants"]["runtime_coverage"]["ok"] is False
    assert doc["first_broken_invariant"]["invariant"] == "runtime_coverage"
    assert set(doc["invariants"]) == set(reconciler.INVARIANTS)
    assert fp.census(tmp_path / "fp.jsonl")                  # the failure left a fingerprint
    assert doc["slas"]["rows"][0]["sla_s"] == 2 * 2_400
