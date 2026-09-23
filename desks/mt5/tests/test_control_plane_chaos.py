"""CONTINUOUS OPS CHAOS, with fakes: every failure the spec names is detected, repaired or
quarantined inside the component's declared SLA, and none of it needs a process or a second."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from libs.ops.control_plane import actuators as act  # noqa: E402
from libs.ops.control_plane import edges, fingerprints, lease, reconciler  # noqa: E402
from libs.ops.control_plane import watermarks as wm  # noqa: E402
from libs.ops.control_plane.edges import Edge  # noqa: E402
from libs.ops.control_plane.specs import Registry, spec  # noqa: E402

TICKS = {"t": 0.0}


def _clock() -> float:
    return TICKS["t"]


def _sleep(s: float) -> None:
    TICKS["t"] += s


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    TICKS["t"] = 0.0
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "lineage.sqlite")
    monkeypatch.setattr(lease, "ACK_LOG", tmp_path / "acks.jsonl")
    monkeypatch.setattr(fingerprints, "LEDGER", tmp_path / "fp.jsonl")
    locks = tmp_path / "locks"
    locks.mkdir()
    worker = spec("resident:dept_korea", kind="resident", host="box", cadence_s=600,
                  timeout_s=1_800, criticality="required", schedule="MT5-Forest-Korea",
                  restart_action="restart:task:MT5-Forest-Korea")
    return {"root": tmp_path, "locks": locks, "wm": tmp_path / "wm",
            "lineage": tmp_path / "lineage.sqlite", "worker": worker,
            "now": datetime.now(tz=UTC)}


def _alive(w, cid="resident:dept_korea", stem="dept_korea", value=1):
    (w["locks"] / f"{stem}.lock").write_text(f"{os.getpid()} now\n", encoding="utf-8")
    wm.progress(cid, "sources_scanned", value, root=w["wm"])


def _observe(w, s, now=None):
    return reconciler.observe(s, now=now or w["now"], root=w["root"], locks=w["locks"],
                              watermark_root=w["wm"], lineage=w["lineage"])


def _reconcile(w, reg, runner, apply=True):
    return reconciler.reconcile(registry=reg, root=w["root"], apply=apply, budget_s=120,
                                locks=w["locks"], watermark_root=w["wm"], lineage=w["lineage"],
                                runner=runner, sleeper=_sleep, clock=_clock,
                                census={"executables": 1, "executables_unclaimed": [],
                                        "coverage": 1.0})


def test_kill_a_regional_worker_detect_and_repair_inside_sla(world):
    w = world
    _alive(w)
    assert _observe(w, w["worker"]).state == "HEALTHY"
    (w["locks"] / "dept_korea.lock").unlink()                        # the kill
    o = _observe(w, w["worker"])
    assert o.state == "BROKEN"                                       # detected on the next pass

    def keepalive(argv, t, cwd):
        assert tuple(argv[:2]) == ("schtasks", "/Run")
        (w["locks"] / "dept_korea.lock").write_text(f"{os.getpid()} now\n", encoding="utf-8")
        wm.progress("resident:dept_korea", "sources_scanned", 2, root=w["wm"])
        return {"rc": 0, "tail": "started"}

    doc = _reconcile(w, Registry([w["worker"]]), keepalive)
    rep = doc["repairs"][0]
    assert rep["result"] == "REPAIRED" and rep["seconds"] <= act.RESTART_WINDOW_S
    assert rep["seconds"] + 0 <= w["worker"].repair_sla_s
    assert doc["failed_required_repairs"] == []
    assert _observe(w, w["worker"]).state == "HEALTHY"


def test_pid_alive_but_progress_frozen_is_stalled_not_healthy(world):
    w = world
    _alive(w)
    later = w["now"] + timedelta(seconds=w["worker"].max_silence_s + 1)
    o = _observe(w, w["worker"], now=later)
    assert o.state == "STALLED" and "beyond its" in o.why
    assert o.details["alive"] is True                                # the PID was never the point
    assert w["worker"].max_silence_s <= w["worker"].detection_sla_s


def test_delete_a_schedule_and_the_desk_knows(world):
    w = world
    unscheduled = spec("resident:dept_korea", kind="resident", host="box", cadence_s=600,
                       timeout_s=1_800, criticality="required", schedule="UNMEASURED")
    reg = Registry([unscheduled])
    doc = _reconcile(w, reg, lambda a, t, c: {"rc": 0}, apply=False)
    assert doc["invariants"]["schedule_coverage"]["ok"] is False
    assert doc["first_broken_invariant"]["invariant"] == "schedule_coverage"
    assert reg.problems(w["root"])                                   # the registry names it too
    from libs.ops.control_plane import scheduler_gen
    v = scheduler_gen.validate(Registry([w["worker"]]), live={})
    assert v["missing"] == ["MT5-Forest-Korea"]


def test_api_hang_is_a_failed_repair_not_a_quiet_zero(world):
    w = world
    a = act.restart_resident("resident:dept_korea", "MT5-Forest-Korea", "dept_korea",
                             window_s=10)
    rec = act.run_actuator(a, {"locks": w["locks"], "watermark_root": w["wm"]},
                           runner=lambda argv, t, cwd: {"rc": None, "tail": "hung",
                                                        "timeout": True},
                           sleeper=_sleep, clock=_clock)
    assert rec["result"] == "FAILED" and "timeout" in rec["why"]
    doc = _reconcile(w, Registry([w["worker"]]),
                     lambda argv, t, cwd: {"rc": None, "tail": "hung", "timeout": True})
    assert doc["failed_required_repairs"] == ["resident:dept_korea"]
    assert doc["DESK_CLOSED_AND_HEALTHY"] is False


def test_corrupt_an_artifact_and_it_reads_unleased_not_fresh(world):
    w = world
    art = w["root"] / "reports" / "FOREST_KOREA.json"
    lease.write_report(art, {"n": 1}, "leg:forest_korea", ttl="hourly", root=w["root"])
    assert lease.staleness([art], root=w["root"])["reports/FOREST_KOREA.json"]["verdict"] == "VALID"
    art.write_bytes(b"{ this is not json")
    art.with_name(art.name + ".envelope.json").write_bytes(b"\x00\x01garbage")
    v = lease.staleness([art], root=w["root"])["reports/FOREST_KOREA.json"]
    assert v["verdict"] == "UNLEASED" and "mtime is not a lease" in v["why"]


def test_feed_an_old_report_and_it_cannot_certify_this_epoch(world):
    w = world
    at = w["now"]
    epoch = reconciler.epoch_id(at)
    old_env = {"epoch_id": reconciler.epoch_id(at - timedelta(hours=1)),
               "created_at": (at - timedelta(minutes=30)).isoformat(timespec="seconds")}
    ok, why = reconciler.epoch_compatible(old_env, epoch, at.isoformat(timespec="seconds"))
    assert ok is False and "cannot certify a later one" in why
    fresh_env = {"epoch_id": epoch, "created_at": at.isoformat(timespec="seconds")}
    assert reconciler.epoch_compatible(fresh_env, epoch, at.isoformat())[0] is True


def test_change_a_schema_and_the_envelope_says_so(world):
    w = world
    art = w["root"] / "R.json"
    env = lease.write_report(art, {"v": 1}, "leg:x", ttl="hourly", root=w["root"])
    assert env["schema_version"] == lease.SCHEMA_VERSION
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["_envelope"]["schema_version"] = "0"
    art.write_text(json.dumps(doc), encoding="utf-8")
    seen = lease.read_envelope(art)
    assert seen["schema_version"] != lease.SCHEMA_VERSION
    # a consumer comparing versions refuses the object rather than guessing at its shape
    assert seen["content_hash"] == env["content_hash"]


def test_fill_a_queue_faster_than_it_drains_is_a_stalled_drain(world):
    w = world
    cid = "leg:external_gauntlet"
    judge = spec(cid, kind="leg", host="box", cadence_s=600, timeout_s=600,
                 criticality="required", schedule="MT5-Gauntlet")
    for i in range(1, 6):
        wm.progress("leg:compile_candidates", "candidates_compiled", i * 100, root=w["wm"])
    wm.progress(cid, "trial_id", 10, root=w["wm"])
    later = w["now"] + timedelta(seconds=judge.max_silence_s + 1)
    producer = wm.advancing("leg:compile_candidates", judge.max_silence_s, later, w["wm"])
    drain = wm.advancing(cid, judge.max_silence_s, later, w["wm"])
    assert producer["state"] == "STALLED" and drain["state"] == "STALLED"
    wm.progress("leg:compile_candidates", "candidates_compiled", 600, root=w["wm"])
    # the producer keeps filling, the drain stands still: the drain is the STALLED component
    assert wm.advancing("leg:compile_candidates", judge.max_silence_s, root=w["wm"])["state"] \
        == "ADVANCING"
    o = reconciler.observe(judge, now=later, root=w["root"], locks=w["locks"],
                           watermark_root=w["wm"], lineage=w["lineage"])
    assert o.state == "STALLED"
    # and a regressing counter is recorded, never silently rewound
    row = wm.progress(cid, "trial_id", 3, root=w["wm"])
    assert row["value"] == 10 and row["regressions"] == 1


def test_break_a_forward_identity_and_enrolment_must_prove_the_clock(world):
    w = world
    a = act.Actuator("enrolment", ("python", "shadow_forward.py"), window_s=5,
                     postconditions=(act.CLOCK_ACCRUING,))
    census = {"n": 3}
    rec = act.run_actuator(a, {"certificates_without_clocks": lambda: census,
                               "certs_before": {"n": 3}},
                           runner=lambda argv, t, cwd: {"rc": 0, "tail": "enrolled"},
                           sleeper=_sleep, clock=_clock)
    assert rec["result"] == "UNPROVEN" and "did not fall" in rec["why"]
    fp = fingerprints.record("shadow_spec.params=None broke enrolment", "leg:enrol_clocks",
                             path=w["root"] / "fp.jsonl")
    fingerprints.record("shadow_spec.params=None broke enrolment", "leg:enrol_clocks",
                        path=w["root"] / "fp.jsonl")
    debt = fingerprints.debt(w["root"] / "fp.jsonl", w["root"])
    assert [d["fingerprint"] for d in debt] == [fp["fingerprint"]]
    fingerprints.record("shadow_spec.params=None broke enrolment", "leg:enrol_clocks",
                        invariant_test="desks/mt5/tests/test_control_plane_chaos.py::"
                                       "test_break_a_forward_identity_and_enrolment_must_prove_the_clock",
                        path=w["root"] / "fp.jsonl")
    assert fingerprints.debt(w["root"] / "fp.jsonl", ROOT) == []
    census["n"] = 2
    rec2 = act.run_actuator(a, {"certificates_without_clocks": lambda: census,
                                "certs_before": {"n": 3}},
                            runner=lambda argv, t, cwd: {"rc": 0, "tail": ""},
                            sleeper=_sleep, clock=_clock)
    assert rec2["result"] == "REPAIRED"


def test_two_processes_with_write_authority_over_one_artifact(world):
    w = world
    art = w["root"] / "reports" / "pf_allocation.json"
    lease.write_report(art, {"book": 1}, "leg:pf_allocator", ttl="hourly", root=w["root"])
    lease.write_report(art, {"book": 2}, "leg:rogue_allocator", ttl="hourly", root=w["root"])
    e = Edge("leg:pf_allocator", "task:MT5-Gateway", "reports/pf_allocation.json", "a->g")
    r = edges.observe(e, path=w["lineage"])
    assert r["state"] == "WRONG_PRODUCER" and r["producer_seen"] == "leg:rogue_allocator"
    assert "two components hold write authority" in r["why"]


def test_reboot_mid_write_leaves_the_last_good_lease_readable(world):
    w = world
    art = w["root"] / "reports" / "META_CONTROLLER.json"
    env = lease.write_report(art, {"epoch": 1}, "leg:meta_controller", ttl="hourly",
                             root=w["root"])
    # the reboot: a torn temp file beside the artifact, the artifact itself intact
    (art.with_suffix(".json.tmp")).write_bytes(b'{"epoch": 2, "_envelope": {"produ')
    (art.with_name(art.name + ".envelope.json.tmp")).write_bytes(b"{")
    seen = lease.read_envelope(art)
    assert seen["producer_run_id"] == env["producer_run_id"]
    assert lease.staleness([art], root=w["root"])["reports/META_CONTROLLER.json"]["verdict"] \
        == "VALID"
    # and a torn ARTIFACT falls back to its sidecar rather than reading as fresh-by-mtime
    art.write_bytes(b'{"epoch": 2, "_envelope": {"produ')
    assert lease.read_envelope(art)["producer_run_id"] == env["producer_run_id"]
