"""The box bottleneck hunter's rails (libs/ops/box_shaper.py, desks/mt5/ops/CPU_SHAPE.json)."""
from __future__ import annotations

import contextlib
import copy
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from libs.ops import box_shaper as bs
from libs.ops.box_shaper import Proc

REPO = Path(__file__).resolve().parents[2]
RULES: dict[str, Any] = json.loads((REPO / "desks/mt5/ops/CPU_SHAPE.json").read_text("utf-8"))
N = 18


def _box() -> list[Proc]:
    """The 2026-10-29 reading, reduced to one process per kind."""
    runtime = r"C:\opt\quant-research-runtime\.venv\Scripts\python.exe"
    procs = [
        Proc(10, "pythonw.exe", exe=r"C:\Program Files\Python314\pythonw.exe",
             cmdline="pythonw.exe -u -W ignore research/pf_allocator.py --mode heavy",
             cpu_pct=3162, priority="BelowNormal", affinity=list(range(N))),
        Proc(11, "terminal64.exe",
             exe=r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe",
             cpu_pct=139, priority="Normal", affinity=list(range(N))),
        Proc(12, "terminal64.exe",
             exe=r"C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
             cpu_pct=76, priority="High", affinity=list(range(N))),
        Proc(13, "MsMpEng.exe", cpu_pct=232, affinity=list(range(N))),
        Proc(14, "node.exe", exe=r"C:\opt\memecoin-codex-stage\node.exe", cmdline="node bot.js",
             cpu_pct=900, priority="Normal", affinity=list(range(N))),
        Proc(20, "python.exe", exe=runtime,
             cmdline=r"python.exe -u C:\opt\quant\desks\mt5\scripts\run_sharded_gauntlet.py",
             cpu_pct=32, priority="BelowNormal", affinity=list(range(N))),
        Proc(21, "python.exe", ppid=20, exe=runtime, cmdline="python.exe -u -c shard_worker(3)",
             cpu_pct=40, priority="BelowNormal", affinity=list(range(N))),
        Proc(30, "python.exe", cmdline=r"python.exe C:\opt\quant\desks\mt5\moat\moat_recorder.py",
             cpu_pct=900, priority="BelowNormal", affinity=list(range(N))),
        Proc(31, "python.exe", cmdline=r"python.exe C:\opt\quant\desks\mt5\moat\moat_miner.py",
             create_time=100, cpu_pct=900, priority="BelowNormal", affinity=list(range(N))),
        Proc(32, "python.exe", cmdline="python.exe something_else.py", create_time=200,
             cpu_pct=700, priority="Normal", affinity=list(range(N))),
    ]
    bs.classify(procs, RULES["groups"])
    return procs


def _by_pid(procs: list[Proc]) -> dict[int, Proc]:
    return {p.pid: p for p in procs}


def test_the_committed_rules_file_is_inside_the_rails() -> None:
    bs.validate_rules(RULES)


def test_groups_money_first_and_the_whole_judge_tree() -> None:
    g = {p.pid: p.group for p in _box()}
    assert g[11] == g[12] == "money"
    assert g[20] == g[21] == "judge"
    assert g[14] == "memecoin"
    assert g[30] == "protected"
    assert g[13] == "system"
    assert g[31] == "mining"
    assert g[10] == g[32] == "other"


def test_the_three_owner_rules() -> None:
    out = bs.plan(_box(), RULES, N, judge_starved=False)
    got = {(a.pid, a.kind): a.after for a in out.actions}
    assert got[(14, "affinity")] == hex(1 << 17)          # 10% of 18 cores = one core, the top one
    assert got[(14, "priority")] == "BelowNormal"
    assert got[(10, "affinity")] == "0xff"
    assert (10, "priority") not in got                    # the allocator's class is untouched
    assert got[(11, "priority")] == "AboveNormal"         # Normal terminal raised
    assert (12, "priority") not in got                    # High terminal is never lowered


def test_nothing_on_the_money_path_judge_or_writers_is_ever_capped_or_lowered() -> None:
    procs = _box()
    rules = copy.deepcopy(RULES)
    rules["rules"].append({"name": "bad", "match": "python", "affinity": "0x1",
                           "priority": "Idle"})
    rules["rules"].append({"name": "bad2", "match": "terminal64", "affinity": "0x1"})
    out = bs.plan(procs, rules, N, judge_starved=True)
    groups = _by_pid(procs)
    for a in out.actions:
        if groups[a.pid].group in bs.RAISE_ONLY:
            assert a.kind == "priority"
            assert bs.PRIORITY_ORDER.index(str(a.after)) > bs.PRIORITY_ORDER.index(
                str(groups[a.pid].priority))
        assert groups[a.pid].group != "system"
    refused = {(r["pid"], r["rule"]) for r in out.refused}
    assert (11, "bad2") in refused and (30, "bad") in refused and (21, "bad") in refused
    # mining never below BelowNormal
    assert (31, "bad") in refused
    assert not any(a.pid == 31 and a.kind == "priority" for a in out.actions)


def test_rules_above_abovenormal_are_refused_at_load() -> None:
    for prio in ("High", "RealTime"):
        rules = copy.deepcopy(RULES)
        rules["rules"][0]["priority"] = prio
        with pytest.raises(ValueError):
            bs.validate_rules(rules)
    rules = copy.deepcopy(RULES)
    rules["priority_ceiling"] = "High"
    with pytest.raises(ValueError):
        bs.validate_rules(rules)


def test_share_cap_needs_two_passes_and_a_starved_judge() -> None:
    first = bs.plan(_box(), RULES, N, judge_starved=False)
    assert not any(a.rule == "share_cap" for a in first.actions)
    heavy = first.heavy
    assert any(k.startswith("32:") for k in heavy) and any(k.startswith("31:") for k in heavy)
    second = bs.plan(_box(), RULES, N, judge_starved=False, previous_heavy=heavy)
    # an unlisted process is never throttled on size alone: "other" waits for a starved judge too
    assert not any(a.rule == "share_cap" for a in second.actions)
    assert {r["pid"] for r in second.refused if r["rule"] == "share_cap"} == {31, 32}
    starved = bs.plan(_box(), RULES, N, judge_starved=True, previous_heavy=heavy)
    cap_masks = {a.pid: str(a.after) for a in starved.actions if a.rule == "share_cap"}
    assert set(cap_masks) == {31, 32}
    assert bin(int(cap_masks[31], 16)).count("1") >= RULES["mining_floor_cores"]


def test_judge_starved_is_measured_not_assumed() -> None:
    procs = _box()
    s = bs.summarize(procs, N, 100.0, RULES["judge_starved"])
    assert s["judge"]["starved"] is True
    assert s["judge"]["share_of_busy"] < 0.5
    assert bs.summarize(procs, N, None, RULES["judge_starved"])["judge"]["starved"] is False
    assert s["memecoin"]["share_of_box"] == round(900 / 1800, 4)


@pytest.mark.skipif(os.name == "nt", reason="off-Windows behaviour")
def test_a_pass_off_windows_plans_but_applies_nothing() -> None:
    out = bs.plan(_box(), RULES, N, judge_starved=False)
    assert out.actions
    bs.apply(out.actions, N)
    assert not any(a.applied for a in out.actions)


def test_run_once_writes_the_report_and_refuses_a_bad_rules_file(tmp_path: Path) -> None:
    bad = tmp_path / "CPU_SHAPE.json"
    bad.write_text(json.dumps({"rules": [{"name": "x", "match": "y", "priority": "High"}]}))
    report = tmp_path / "BOX_BOTTLENECKS.json"
    out = bs.run_once(rules_path=bad, report_path=report)
    assert out["verdict"] == "RULES_REFUSED"
    assert json.loads(report.read_text())["verdict"] == "RULES_REFUSED"


def test_secrets_never_reach_the_report() -> None:
    p = Proc(1, "x", cmdline="bot.py --api-key sk-abc123 --token=xyz")
    assert "sk-abc123" not in bs._short_cmd(p) and "xyz" not in bs._short_cmd(p)
    t = Proc(2, "terminal64.exe", cmdline="terminal64.exe /login:5551234 /server:FTMO-Demo2 "
             "/account=778899")
    out = bs._short_cmd(t)
    assert "5551234" not in out and "FTMO-Demo2" not in out and "778899" not in out


def test_stall_watch_runs_the_shaper_with_no_arguments() -> None:
    text = (REPO / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8")
    assert "& py -3 -m libs.ops.box_shaper 2>$null" in text
    assert "Stop-Process" not in text.split("CPU SHAPE AND BOTTLENECK HUNT")[1].split(
        "THE PAGER ON ITS OWN CLOCK")[0]


def test_a_real_pass_measures_this_host_and_writes_the_report(tmp_path: Path) -> None:
    pytest.importorskip("psutil")
    rules = copy.deepcopy(RULES)
    rules["window_s"] = 0.5
    rules_path = tmp_path / "CPU_SHAPE.json"
    rules_path.write_text(json.dumps(rules))
    report_path = tmp_path / "BOX_BOTTLENECKS.json"
    phase_path = tmp_path / "JUDGE_SWEEP_PHASE.json"
    phase_path.write_text(json.dumps({"phase": "done", "pid": os.getpid()}))
    out = bs.run_once(rules_path=rules_path, report_path=report_path, phase_path=phase_path,
                      adopt_heartbeat_path=tmp_path / "ADOPTION_HEARTBEAT.json")
    assert out["verdict"] == "MEASURED" and out["n_processes"] > 0
    doc = json.loads(report_path.read_text())
    assert {"top", "judge", "memecoin", "actions", "refused", "ram", "disk_free_gb",
            "share_cap_moved", "judge_phase_status"} <= set(doc)
    assert doc["line"].startswith("CPU SHAPE ") and "box " in doc["line"]
    assert doc["judge_phase_status"] == "done"
    assert doc["health"]["verdict"] in ("GREEN", "WATCH", "RED")


def _applied(out: bs.Plan) -> bs.Plan:
    for a in out.actions:
        a.applied, a.error = True, None
    return out


def test_hand_tasks_retire_only_on_positive_proof() -> None:
    procs = _box()
    out = bs.plan(procs, RULES, N, judge_starved=False)
    # measured over the cap (900% of 1800%) before this pass narrowed it: not proven
    ok, why = bs.memecoin_cap_holds(procs, RULES, _applied(out), 0.5)
    assert not ok and "above" in why
    ok, _ = bs.memecoin_cap_holds(procs, RULES, _applied(out), 0.05)
    assert ok
    failed = bs.plan(procs, RULES, N, judge_starved=False)
    next(a for a in failed.actions if a.rule == "memecoin_cap").error = "AccessDenied"
    ok, why = bs.memecoin_cap_holds(procs, RULES, failed, 0.05)
    assert not ok and "did not land" in why
    no_meme = [p for p in procs if p.group != "memecoin"]
    ok, why = bs.memecoin_cap_holds(no_meme, RULES, bs.Plan(), 0.0)
    assert not ok and "no memecoin process" in why
    # already on the narrowed mask at BelowNormal: no action needed, and that holds
    m = next(p for p in procs if p.group == "memecoin")
    m.affinity, m.priority = [17], "BelowNormal"
    quiet = bs.plan(procs, RULES, N, judge_starved=False)
    assert not any(a.rule == "memecoin_cap" for a in quiet.actions)
    assert bs.memecoin_cap_holds(procs, RULES, quiet, 0.05)[0]


def test_stall_watch_retires_hand_tasks_only_when_the_cap_holds() -> None:
    text = (REPO / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8")
    assert "$cpuShape.memecoin_cap_holds -eq $true" in text
    assert "hand tasks not disabled this pass" in text


def test_the_allocator_wall_time_is_carried_pass_to_pass() -> None:
    rule = next(r for r in RULES["rules"] if r["name"] == "pf_allocator_heavy")
    assert rule["track_wall"] is True
    procs = _box()
    alloc = next(p for p in procs if p.pid == 10)
    alloc.create_time = 1_000.0
    first = bs.track_wall(procs, rule["match"], None, now=4_600.0)
    assert first["running"][0]["wall_s"] == 3_600 and first["running"][0]["cores"] == N
    gone = bs.track_wall([p for p in procs if p.pid != 10], rule["match"], first, now=5_200.0)
    assert gone["running"] == []
    assert gone["finished"][0]["wall_s_at_least"] == 3_600


# ------------------------------------------------------------------------------------ judge reserve
RES = RULES["judge_reserve"]
FLOOR = RULES["mining_floor_cores"]


def _reserve_box() -> list[Proc]:
    procs = _box()
    procs.append(Proc(33, "python.exe", cmdline="python.exe quiet_helper.py", create_time=300,
                      cpu_pct=5, priority="Normal", affinity=[0, 1]))
    bs.classify(procs, RULES["groups"])
    return procs


def test_the_committed_masks_keep_the_mining_floor_and_the_owner_split() -> None:
    reserve, side, note = bs.reserve_masks(RES, N, FLOOR, boost=False)
    assert bs.cpus_to_mask(reserve) == "0xff00" and bs.cpus_to_mask(side) == "0x300ff"
    reserve, side, note = bs.reserve_masks(RES, N, FLOOR, boost=True)
    assert bs.cpus_to_mask(reserve) == "0xfff0" and bs.cpus_to_mask(side) == "0x3000f"
    assert len(side) == FLOOR and note is None
    # a boost that would breach the floor falls back to the base, and says so
    reserve, side, note = bs.reserve_masks({**RES, "boost_mask": "0xFFFF"}, N, FLOOR, boost=True)
    assert bs.cpus_to_mask(reserve) == "0xff00" and note and "floor" in note
    # a reserve the box cannot afford above the floor reserves nothing
    reserve, side, note = bs.reserve_masks(RES, 12, 10, boost=False)
    assert reserve == [] and len(side) == 12 and note


def test_the_base_reserve_moves_only_mining_and_other_python() -> None:
    procs = _reserve_box()
    actions, _moved, meta = bs.plan_reserve(procs, RES, N, boost=False, floor_cores=FLOOR,
                                           skip_pids=set(), previous_moved={})
    assert meta["mode"] == "base"
    assert {a.pid for a in actions} == {31, 32}       # mining + other python on all cores
    assert all(a.after == "0x300ff" for a in actions)
    # never: terminals, judge, protected recorder, memecoin node, the exempt allocator,
    # and a process already off the reserve (33)
    assert not {a.pid for a in actions} & {10, 11, 12, 13, 14, 20, 21, 30, 33}


def test_a_serial_phase_boosts_then_the_shaper_widens_back_what_it_narrowed() -> None:
    procs = _reserve_box()
    boost, moved, meta = bs.plan_reserve(procs, RES, N, boost=True, floor_cores=FLOOR,
                                         skip_pids=set(), previous_moved={})
    assert meta["mode"] == "boost" and {a.after for a in boost} == {"0x3000f"}
    for p in procs:                                   # the boost landed
        if p.pid in moved_pids(boost):
            p.affinity = bs.mask_to_cpus("0x3000f", N)
    back, _moved2, meta2 = bs.plan_reserve(procs, RES, N, boost=False, floor_cores=FLOOR,
                                          skip_pids=set(), previous_moved=moved)
    assert meta2["mode"] == "base"
    assert {(a.pid, a.after) for a in back} == {(31, "0x300ff"), (32, "0x300ff")}
    # a process the reservation never touched is never widened (33 stays on 0-1)
    assert 33 not in moved_pids(back)


def moved_pids(actions: list[bs.Action]) -> set[int]:
    return {a.pid for a in actions}


def test_the_judge_phase_is_believed_only_while_its_writer_lives() -> None:
    doc = {"phase": "collect_and_cut", "pid": 4242}
    assert bs.judge_phase(doc, lambda pid: True) == ("collect_and_cut", 4242)
    assert bs.judge_phase(doc, lambda pid: False) == (None, 4242)
    assert bs.judge_phase(None, lambda pid: True) == (None, None)
    assert bs.judge_phase({"phase": "plan"}, lambda pid: True) == (None, None)


def test_every_switch_is_logged_with_the_judge_share_before_and_after() -> None:
    h = bs.log_switch([], at="t0", mode="base", phase=None, starved=False, judge_share=0.20)
    h = bs.log_switch(h, at="t1", mode="boost", phase="plan", starved=False, judge_share=0.21)
    assert {k: h[-1][k] for k in ("at", "from", "mode", "phase", "starved",
                                  "judge_share_before", "judge_share_after")} == {
        "at": "t1", "from": "base", "mode": "boost", "phase": "plan", "starved": False,
        "judge_share_before": 0.21, "judge_share_after": None}
    h = bs.log_switch(h, at="t2", mode="boost", phase="plan", starved=False, judge_share=0.35)
    assert len(h) == 2 and h[-1]["judge_share_after"] == 0.35


def test_every_switch_logs_mining_share_and_its_donation() -> None:
    h = bs.log_switch([], at="t0", mode="base", phase=None, starved=False, judge_share=0.20,
                      mining_share=0.40, side_cores=10)
    h = bs.log_switch(h, at="t1", mode="boost", phase="plan", starved=False, judge_share=0.21,
                      mining_share=0.40, side_cores=6)
    assert h[-1]["mining_share_before"] == 0.40 and h[-1]["side_cores"] == 6
    h = bs.log_switch(h, at="t2", mode="boost", phase="plan", starved=False, judge_share=0.35,
                      mining_share=0.28, side_cores=6)
    assert h[-1]["mining_share_after"] == 0.28 and h[-1]["mining_donation"] == 0.12


def test_the_reserve_holds_only_when_every_move_landed() -> None:
    procs = _reserve_box()
    actions, _, meta = bs.plan_reserve(procs, RES, N, boost=False, floor_cores=FLOOR,
                                       skip_pids=set(), previous_moved={})
    assert not bs.reserve_holds(actions, meta)[0]          # planned, not applied
    for a in actions:
        a.applied = True
    assert bs.reserve_holds(actions, meta)[0]
    actions[0].error = "AccessDenied"
    assert not bs.reserve_holds(actions, meta)[0]
    assert not bs.reserve_holds([], {"reserve_mask": None})[0]


def test_stall_watch_retires_the_core_trial_only_when_the_reserve_holds() -> None:
    text = (REPO / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8")
    assert "$cpuShape.judge_reserve_holds -eq $true" in text
    assert "Disable-ScheduledTask -TaskName 'Quant-JudgeCoreTrial'" in text


# ------------------------------------------------------------------------------------ red check
def test_red_only_after_more_than_two_low_passes_with_runnable_work() -> None:
    h = None
    seen = []
    for _ in range(4):
        h = bs.health(h, measured=True, runnable=True, judge_share=0.05, min_share=0.15)
        seen.append(h["verdict"])
    assert seen == ["WATCH", "WATCH", "RED", "RED"]
    # a clean pass resets the count
    h = bs.health(h, measured=True, runnable=True, judge_share=0.30, min_share=0.15)
    assert h["verdict"] == "GREEN" and h["judge_low_strikes"] == 0


def test_a_judge_with_no_runnable_work_never_counts_against_the_floor() -> None:
    h = None
    for _ in range(5):
        h = bs.health(h, measured=True, runnable=False, judge_share=0.0, min_share=0.15)
    assert h is not None and h["verdict"] == "GREEN"
    assert bs.judge_runnable("done", ["done"]) is False
    assert bs.judge_runnable(None, ["done"]) is False
    assert bs.judge_runnable("rule_shards", ["done"]) is True


def test_red_after_more_than_two_unmeasured_passes_and_measured_resets_it() -> None:
    h = None
    seen = []
    for _ in range(3):
        h = bs.health(h, measured=False, runnable=False, judge_share=None, min_share=0.15)
        seen.append(h["verdict"])
    assert seen == ["UNMEASURED", "UNMEASURED", "RED"]
    h = bs.health(h, measured=True, runnable=False, judge_share=None, min_share=0.15)
    assert h["verdict"] == "GREEN" and h["unmeasured_strikes"] == 0


def test_unmeasured_passes_are_counted_across_runs_in_the_report(tmp_path: Path) -> None:
    bad = tmp_path / "CPU_SHAPE.json"
    bad.write_text(json.dumps({"rules": [{"name": "x", "match": "y", "priority": "High"}]}))
    report = tmp_path / "BOX_BOTTLENECKS.json"
    verdicts = [bs.run_once(rules_path=bad, report_path=report)["health"]["verdict"]
                for _ in range(3)]
    assert verdicts == ["UNMEASURED", "UNMEASURED", "RED"]


def test_stall_watch_carries_the_health_verdict_and_counts_an_unrunnable_shaper() -> None:
    text = (REPO / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8")
    assert "cpu_shape = $cpuShapeVerdict" in text and "cpu_shape_why = $cpuShapeWhy" in text
    assert "$cpuShapeUnrun -gt 2" in text
    assert "cpu_shape_unrunnable = $cpuShapeUnrun" in text


def test_desk_health_reads_a_red_hunter_as_a_problem(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util
    script = REPO / "desks/mt5/scripts/check_desk_health.py"
    spec = importlib.util.spec_from_file_location("_quant_desk_health_cpu_shape", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(mod, "DESK", tmp_path)
    for verdict, level in (("RED", "PROBLEM"), ("GREEN", "OK"), ("UNMEASURED", "UNKNOWN")):
        (tmp_path / "data" / "stall_watch.json").write_text(json.dumps(
            {"checked_at": "t", "cpu_shape": verdict, "cpu_shape_why": "w"}))
        mod._FINDINGS.clear()
        mod.check_cpu_shape()
        assert [f["level"] for f in mod._FINDINGS] == [level]


# ------------------------------------------------------------------- audit fixes, 2026-10-29
def test_a_share_cap_pin_is_released_once_the_judge_is_no_longer_starved() -> None:
    """MF1: a 9-core miner pinned to 0x3000F must not stay on six cores after starvation."""
    full = list(range(N))
    base_side = bs.mask_to_cpus("0x300FF", N)
    boost_side = bs.mask_to_cpus("0x3000F", N)
    miner = Proc(31, "python.exe", cmdline="python.exe moat_miner.py", create_time=100,
                 cpu_pct=900, affinity=full)
    bs.classify([miner], RULES["groups"])
    rules = {**RULES, "rules": []}
    out = bs.plan([miner], rules, N, judge_starved=True, previous_heavy=[miner.key])
    pin = [a for a in out.actions if a.rule == "share_cap"]
    assert pin and pin[0].after == "0x3000f"
    record = {miner.key: str(pin[0].after)}
    miner.affinity = bs.mask_to_cpus("0x3000F", N)
    miner.cpu_pct = 600
    # still starved: the pin stands and stays recorded
    acts, keep = bs.release_share_cap([miner], record, judge_starved=True, side_now=boost_side,
                                      side_base=base_side, n_cpu=N, skip_pids=set())
    assert acts == [] and keep == record
    # starvation over but a serial-phase boost on: nothing wider allowed yet, record kept
    acts, keep = bs.release_share_cap([miner], record, judge_starved=False,
                                      side_now=boost_side, side_base=base_side, n_cpu=N,
                                      skip_pids=set())
    assert acts == [] and miner.key in keep
    # the boost ends: widened back to the side mask, record dropped
    acts, keep = bs.release_share_cap([miner], keep, judge_starved=False, side_now=base_side,
                                      side_base=base_side, n_cpu=N, skip_pids=set())
    assert [(a.pid, a.after, a.rule) for a in acts] == [(31, "0x300ff", "share_cap_release")]
    assert keep == {}
    # plan alone would never have done it: outside starvation it plans nothing for the miner
    assert not [a for a in bs.plan([miner], rules, N, judge_starved=False).actions
                if a.pid == 31]


def test_an_unknown_judge_phase_is_an_unmeasured_strike_not_no_work() -> None:
    """MF2: absent / unreadable / pid-less is UNKNOWN (RED after 2); dead / done is no work."""
    alive = {4242}.__contains__
    wait = ["done"]
    assert bs.phase_status(None, "absent", alive, wait)[2] == "absent"
    assert bs.phase_status(None, "unreadable", alive, wait)[2] == "unreadable"
    assert bs.phase_status({}, "ok", alive, wait)[2] == "no_pid"
    assert bs.phase_status({"phase": "plan"}, "ok", alive, wait)[2] == "no_pid"
    assert bs.phase_status({"phase": "plan", "pid": 1}, "ok", alive, wait)[2] == "dead"
    assert bs.phase_status({"phase": "done", "pid": 4242}, "ok", alive, wait)[2] == "done"
    assert bs.phase_status({"phase": "plan", "pid": 4242}, "ok", alive, wait) == (
        "plan", 4242, "live")
    h = None
    seen = []
    for _ in range(3):
        h = bs.health(h, measured=True, runnable=False, judge_share=0.0, min_share=0.15,
                      phase_known=False, phase_status="absent")
        seen.append(h["verdict"])
    assert h is not None and seen == ["UNMEASURED", "UNMEASURED", "RED"]
    assert "unknown" in h["why"]
    # a known answer resets it; dead pid / done is GREEN, saying which case
    h = bs.health(h, measured=True, runnable=False, judge_share=0.0, min_share=0.15,
                  phase_known=True, phase_status="dead")
    assert h["verdict"] == "GREEN" and h["phase_unknown_strikes"] == 0
    assert h["why"].startswith("no runnable work")
    h = bs.health(h, measured=True, runnable=True, judge_share=0.30, min_share=0.15,
                  phase_known=True, phase_status="live")
    assert h["verdict"] == "GREEN" and h["why"].startswith("at/above floor")


def test_an_absent_phase_file_reads_unknown_in_the_report(tmp_path: Path) -> None:
    pytest.importorskip("psutil")
    rules = copy.deepcopy(RULES)
    rules["window_s"] = 0.5
    rules_path = tmp_path / "CPU_SHAPE.json"
    rules_path.write_text(json.dumps(rules))
    out = bs.run_once(rules_path=rules_path, report_path=tmp_path / "B.json",
                      phase_path=tmp_path / "absent.json",
                      adopt_heartbeat_path=tmp_path / "absent2.json")
    assert out["judge_phase_status"] == "absent"
    assert out["health"]["verdict"] == "UNMEASURED" and out["health"]["phase_unknown_strikes"] == 1


def _adopt_box() -> list[Proc]:
    full = list(range(N))
    procs = [
        Proc(500, "powershell.exe", ppid=4, cmdline=(
            r"powershell.exe -NoProfile -File C:\opt\quant\desks\mt5\scripts\Adopt-And-Seal.ps1"),
             create_time=1, cpu_pct=5, priority="Normal", affinity=full),
        Proc(501, "powershell.exe", ppid=500, cmdline="powershell.exe -File Adopt-Release.ps1",
             create_time=2, cpu_pct=5, priority="Normal", affinity=full),
        Proc(502, "python.exe", ppid=501, cmdline="python.exe -m libs.ops.adopt_guard pre",
             create_time=3, cpu_pct=900, priority="BelowNormal",
             affinity=bs.mask_to_cpus("0x3000F", N)),
        Proc(503, "git.exe", ppid=502, cmdline="git.exe checkout -- libs", create_time=4,
             cpu_pct=700, priority="Normal", affinity=full),
        Proc(504, "py.exe", ppid=500, cmdline="py -3 -m libs.ops.release seal", create_time=5,
             cpu_pct=13, priority="Normal", affinity=full),
    ]
    bs.classify(procs, RULES["groups"])
    return procs


def test_the_adopt_tree_is_raised_and_never_narrowed() -> None:
    """Rule 23: Adopt-And-Seal and every py/python/git under it ride with the money path."""
    procs = _adopt_box()
    assert {p.group for p in procs} == {"adopt"}
    out = bs.plan(procs, RULES, N, judge_starved=True,
                  previous_heavy=[p.key for p in procs])
    raised = {a.pid for a in out.actions if a.kind == "priority" and a.after == "AboveNormal"}
    assert raised == {500, 501, 502, 503, 504}
    assert not [a for a in out.actions if a.kind == "affinity"]          # never share-capped
    actions, moved, _ = bs.plan_reserve(procs, RES, N, boost=True, floor_cores=FLOOR,
                                        skip_pids=set(), previous_moved={})
    assert actions == [] and moved == {}                                  # never on the side
    # narrowed earlier while it read as other: widened back to every core
    p502 = _by_pid(procs)[502]
    actions, _, _ = bs.plan_reserve(procs, RES, N, boost=True, floor_cores=FLOOR,
                                    skip_pids=set(), previous_moved={p502.key: "0x3000f"})
    assert [(a.pid, a.after) for a in actions] == [(502, "0x3ffff")]
    acts, keep = bs.release_share_cap(procs, {p502.key: "0x3000f"}, judge_starved=True,
                                      side_now=[0], side_base=[0], n_cpu=N, skip_pids=set())
    assert [(a.pid, a.after) for a in acts] == [(502, "0x3ffff")] and keep == {}
    with pytest.raises(ValueError):
        bs.validate_rules({"rules": [{"name": "x", "group": "adopt", "affinity": "0xF"}]})


def test_an_adopt_run_past_fifteen_minutes_with_no_seal_or_refusal_is_red() -> None:
    now = bs._parse_ts("2026-10-29T15:00:00Z")
    assert now is not None
    running = {"started_at": "2026-10-29T14:40:00.1234567Z", "finished_at": None, "pid": 14000,
               "stage": "started"}
    why = bs.adopt_overdue(running, now, 900, lambda pid: True)
    assert why and "14000" in why and "20 min" in why and "pid alive" in why
    assert bs.adopt_overdue({**running, "started_at": "2026-10-29T14:50:00Z"}, now, 900) is None
    assert bs.adopt_overdue({**running, "finished_at": "2026-10-29T14:59:00Z"}, now, 900) is None
    assert bs.adopt_overdue(None, now, 900) is None
    h = bs.health(None, measured=True, runnable=False, judge_share=0.0, min_share=0.15,
                  adopt_why=why)
    assert h["verdict"] == "RED" and "release path stalled" in h["why"]
    h = bs.health(None, measured=False, runnable=False, judge_share=None, min_share=0.15,
                  adopt_why=why)
    assert h["verdict"] == "RED"


# ------------------------------------------------------------------------------------ dedupe
def _dupes() -> list[Proc]:
    loop = r"python.exe C:\opt\quant\desks\mt5\research\some_loop.py"
    procs = [
        Proc(40, "python.exe", ppid=400, exe="py.exe", cmdline=loop, create_time=10),
        Proc(41, "python.exe", ppid=401, exe="py.exe", cmdline=loop, create_time=20),
        # pool siblings: one launcher, one command line -- never duplicates
        Proc(50, "python.exe", ppid=500, exe="py.exe", cmdline="python.exe pool_child.py",
             create_time=5),
        Proc(51, "python.exe", ppid=500, exe="py.exe", cmdline="python.exe pool_child.py",
             create_time=6),
        # parent and child with one command line -- never duplicates
        Proc(60, "python.exe", ppid=1, exe="py.exe", cmdline="python.exe nest.py", create_time=1),
        Proc(61, "python.exe", ppid=60, exe="py.exe", cmdline="python.exe nest.py", create_time=2),
        # protected writer and memecoin doubled: reported nowhere, stopped never
        Proc(70, "python.exe", ppid=700, exe="py.exe", cmdline="python.exe moat_recorder.py"),
        Proc(71, "python.exe", ppid=701, exe="py.exe", cmdline="python.exe moat_recorder.py"),
        Proc(80, "node.exe", ppid=800, exe=r"C:\memecoin\node.exe", cmdline="node bot.js"),
        Proc(81, "node.exe", ppid=801, exe=r"C:\memecoin\node.exe", cmdline="node bot.js"),
    ]
    for p in procs:     # one working directory and environment: the same loop (SF3)
        p.cwd, p.env_sig = r"C:\opt\quant", "env-a"
    bs.classify(procs, RULES["groups"])
    return procs


def test_dedupe_is_deny_by_default_and_reports_only_true_duplicates() -> None:
    assert RULES["dedupe"]["allow"] == []
    stops, seen = bs.plan_dedupe(_dupes(), RULES["dedupe"], previous_duplicates=["41:20"])
    assert stops == []
    assert [(d["keep"], d["duplicate"], d["allowed"]) for d in seen] == [("40:10", "41:20", False)]


def test_an_allowed_duplicate_is_stopped_only_on_its_second_sighting_and_the_oldest_kept() -> None:
    cfg = {"allow": ["some_loop.py"]}
    first, seen = bs.plan_dedupe(_dupes(), cfg)
    assert first == [] and seen[0]["allowed"] is True
    second, _ = bs.plan_dedupe(_dupes(), cfg, previous_duplicates=[seen[0]["duplicate"]])
    assert [(a.pid, a.kind, a.before) for a in second] == [(41, "stop", "41:20")]


def test_no_allow_pattern_reaches_a_protected_group() -> None:
    cfg = {"allow": ["moat_recorder", "node bot.js", "memecoin"]}
    procs = _dupes()
    _, seen = bs.plan_dedupe(procs, cfg)
    keys = [d["duplicate"] for d in seen]
    stops, _ = bs.plan_dedupe(procs, cfg, previous_duplicates=keys)
    assert {a.pid for a in stops} <= {41}
    assert not any(d["duplicate"].startswith(("71:", "81:")) for d in seen)


def test_a_too_broad_allow_pattern_is_refused() -> None:
    rules = copy.deepcopy(RULES)
    rules["dedupe"]["allow"] = ["py"]
    with pytest.raises(ValueError):
        bs.validate_rules(rules)


def _chain(psutil: Any, pid: int) -> list[str]:
    return [f"{x.pid}:{int(x.create_time())}" for x in psutil.Process(pid).parents()]


def test_a_stop_kills_the_verified_process_and_refuses_a_reused_pid(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """#482 SF1: the psutil.Process that passed the pid+create-time check is what is killed."""
    psutil = pytest.importorskip("psutil")
    import subprocess
    import sys

    from libs.ops import proctree
    calls: list[Any] = []
    real = proctree.kill_verified_tree

    def spy(root: Any, **kw: Any) -> dict[str, Any]:
        calls.append(root)
        return real(root, **kw)

    monkeypatch.setattr(proctree, "kill_verified_tree", spy)
    monkeypatch.setattr(proctree, "kill_tree", lambda *a, **k: pytest.fail("pid-only kill"))
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        ct = int(psutil.Process(child.pid).create_time())
        up = _chain(psutil, child.pid)
        stale = bs.Action(child.pid, "python", "other", "dedupe", "stop", f"{child.pid}:{ct - 5}",
                          "stopped", ancestors=up)
        bs.apply([stale], N)
        assert not stale.applied and "reused" in str(stale.error) and calls == []
        good = bs.Action(child.pid, "python", "other", "dedupe", "stop", f"{child.pid}:{ct}",
                         "stopped", ancestors=up)
        bs.apply([good], N)
        assert good.applied and len(calls) == 1
        assert isinstance(calls[0], psutil.Process) and calls[0].pid == child.pid
        assert child.wait(timeout=10) is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_a_verified_kill_never_falls_back_to_a_bare_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """#482 SF1: no taskkill /PID or os.kill by number once the process object failed."""
    psutil = pytest.importorskip("psutil")
    import subprocess

    from libs.ops import proctree

    class _Denied:
        pid = 999999

        def children(self, recursive: bool = False) -> list[Any]:
            return []

        def kill(self) -> None:
            raise psutil.AccessDenied(self.pid)

        def is_running(self) -> bool:
            return True
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("taskkill fallback"))
    monkeypatch.setattr("libs.ops.proctree.os.kill", lambda *a: pytest.fail("os.kill fallback"))
    out = proctree.kill_verified_tree(_Denied(), verified={}, timeout=0.1)
    assert out["root_gone"] is False and "AccessDenied" in out["note"]


def test_a_stop_is_refused_when_its_tree_holds_a_guarded_process() -> None:
    """#482 S2: a tree kill never takes a money/judge/protected/memecoin/adopt process down."""
    cfg = {"allow": ["some_loop.py"]}
    for cmd in ("terminal64.exe /portable", "python.exe moat_recorder.py", "node memecoin.js",
                "python.exe run_sharded_gauntlet.py", "powershell -File Adopt-And-Seal.ps1"):
        procs = _dupes()
        procs.append(Proc(90, "x.exe", ppid=41, cmdline=cmd, create_time=30))
        bs.classify(procs, RULES["groups"])
        keys = [d["duplicate"] for d in bs.plan_dedupe(procs, cfg)[1]]
        stops, seen = bs.plan_dedupe(procs, cfg, previous_duplicates=keys)
        assert stops == [], cmd
        assert "refused" in seen[0] and "90" in seen[0]["refused"]
    # an ordinary child is carried on the action as the measured tree
    procs = _dupes()
    procs.append(Proc(91, "python.exe", ppid=41, cmdline="python.exe helper.py", create_time=31))
    bs.classify(procs, RULES["groups"])
    stops, _ = bs.plan_dedupe(procs, cfg, previous_duplicates=["41:20"])
    assert [(a.pid, a.tree) for a in stops] == [(41, ["91:31"])]


def _sleeper() -> Any:
    import subprocess
    import sys
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def test_a_stop_lands_only_when_the_root_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """#482 SF2: children killed but the root alive is NOT a stop."""
    psutil = pytest.importorskip("psutil")
    from libs.ops import proctree
    real = proctree.kill_verified_tree
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    child = _sleeper()
    try:
        key = f"{child.pid}:{int(psutil.Process(child.pid).create_time())}"
        for gone, killed in ((False, 3), (True, 1)):
            monkeypatch.setattr(proctree, "kill_verified_tree",
                                lambda root, _g=gone, _k=killed, **kw: {
                                    "pid": root.pid, "killed": _k, "root_gone": _g})
            a = bs.Action(child.pid, "python", "other", "dedupe", "stop", key, "stopped",
                          ancestors=_chain(psutil, child.pid))
            bs.apply([a], N)
            assert a.applied is gone, (gone, killed)
            assert (a.error is None) is gone
            if not gone:
                assert "root is still running" in str(a.error)
    finally:
        child.kill()
        child.wait(timeout=10)
    # the real verified kill reports root_gone only once the root has exited
    root = _sleeper()
    out = real(psutil.Process(root.pid), verified={})
    assert out["root_gone"] is True and root.wait(timeout=10) is not None


def test_a_stop_refuses_an_ancestor_the_plan_never_saw(monkeypatch: pytest.MonkeyPatch) -> None:
    """#482 MF1 at apply time: a live parent chain unlike the measured one refuses."""
    psutil = pytest.importorskip("psutil")
    from libs.ops import proctree
    monkeypatch.setattr(proctree, "kill_verified_tree",
                        lambda *a, **k: pytest.fail("must not kill"))
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    child = _sleeper()
    try:
        key = f"{child.pid}:{int(psutil.Process(child.pid).create_time())}"
        a = bs.Action(child.pid, "python", "other", "dedupe", "stop", key, "stopped",
                      ancestors=[])
        bs.apply([a], N)
        assert not a.applied and "ancestor chain changed" in str(a.error)
    finally:
        child.kill()
        child.wait(timeout=10)


def test_a_child_of_the_money_path_is_never_a_stoppable_duplicate() -> None:
    """#482 MF1 repro: the gateway's own state_pusher_loop vs an older unrelated launcher."""
    cfg = {"allow": ["state_pusher_loop.py"]}
    loop = "python.exe state_pusher_loop.py"
    procs = [
        Proc(300, "python.exe", ppid=4, exe="py.exe", cmdline="python.exe stray_launcher.py",
             create_time=1),
        Proc(301, "python.exe", ppid=300, exe="py.exe", cmdline=loop, create_time=2),
        Proc(400, "python.exe", ppid=4, exe="py.exe",
             cmdline=r"python.exe C:\opt\quant\desks\mt5\run_gateway_loop.py", create_time=3),
        Proc(401, "python.exe", ppid=400, exe="py.exe", cmdline=loop, create_time=4),
    ]
    for p in procs:
        p.cwd, p.env_sig = r"C:\opt\quant", "env-a"
    bs.classify(procs, RULES["groups"])
    # the money path is a tree (#477 third audit MF1): the gateway's child is money itself and
    # never a dedupe candidate at all
    assert _by_pid(procs)[400].group == "money" and _by_pid(procs)[401].group == "money"
    keys = [d["duplicate"] for d in bs.plan_dedupe(procs, cfg)[1]]
    stops, seen = bs.plan_dedupe(procs, cfg, previous_duplicates=keys)
    assert stops == [] and seen == []
    # the ancestor guard still holds for a guarded parent whose children are not its group:
    # a protected writer (matched by name only) launching the loop
    procs[2].cmdline = r"python.exe C:\opt\quant\desks\mt5\moat\moat_recorder.py"
    bs.classify(procs, RULES["groups"])
    assert _by_pid(procs)[400].group == "protected" and _by_pid(procs)[401].group == "other"
    keys = [d["duplicate"] for d in bs.plan_dedupe(procs, cfg)[1]]
    stops, seen = bs.plan_dedupe(procs, cfg, previous_duplicates=keys)
    assert stops == []
    assert seen[0]["duplicate"] == "401:4" and "ancestor 400" in seen[0]["refused"]
    assert "protected" in seen[0]["refused"]
    # a stop that is allowed carries its measured parent chain for the apply-time re-check
    stops, _ = bs.plan_dedupe(_dupes(), {"allow": ["some_loop.py"]},
                              previous_duplicates=["41:20"])
    assert [a.ancestors for a in stops] == [[]]


def test_different_cwd_or_env_is_not_a_duplicate() -> None:
    """#482 SF3: two loops for different accounts share a command line, not an identity."""
    cfg = {"allow": ["some_loop.py"]}
    procs = _dupes()
    _by_pid(procs)[41].env_sig = "env-b"         # e.g. another MT5 account's environment
    assert bs.plan_dedupe(procs, cfg, previous_duplicates=["41:20"]) == ([], [])
    procs = _dupes()
    _by_pid(procs)[41].cwd = r"C:\opt\quant-acct2"
    assert bs.plan_dedupe(procs, cfg, previous_duplicates=["41:20"]) == ([], [])
    procs = _dupes()
    _by_pid(procs)[41].cwd = None                # unread: reported, never stopped
    stops, seen = bs.plan_dedupe(procs, cfg, previous_duplicates=["41:20"])
    assert stops == [] and "unread" in seen[0]["refused"]


def test_read_identity_fills_only_compared_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    psutil = pytest.importorskip("psutil")
    import os as _os
    me = psutil.Process(_os.getpid())
    ct = me.create_time()
    procs = [Proc(_os.getpid(), "python.exe", exe="py.exe", cmdline="python.exe x.py",
                  create_time=ct),
             Proc(_os.getpid(), "python.exe", exe="py.exe", cmdline="python.exe x.py",
                  create_time=ct - 100),           # creation time differs: unread
             Proc(_os.getpid(), "python.exe", exe="py.exe", cmdline="python.exe solo.py",
                  create_time=ct)]
    bs.read_identity(procs)
    assert procs[0].cwd == me.cwd() and procs[0].env_sig
    assert procs[1].cwd is None and procs[2].cwd is None


def test_a_stop_refuses_a_descendant_born_after_the_measurement(
        monkeypatch: pytest.MonkeyPatch) -> None:
    psutil = pytest.importorskip("psutil")
    import subprocess
    import sys

    from libs.ops import proctree
    calls: list[int] = []
    def spy(pid: int, **kw: Any) -> dict[str, Any]:
        calls.append(pid)
        return {}

    monkeypatch.setattr(proctree, "kill_tree", spy)
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    parent = subprocess.Popen([sys.executable, "-c", (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "time.sleep(60)")])
    try:
        pr = psutil.Process(parent.pid)
        for _ in range(100):
            if pr.children():
                break
            psutil.wait_procs([], timeout=0.05)
        assert pr.children()
        a = bs.Action(parent.pid, "python", "other", "dedupe", "stop",
                      f"{parent.pid}:{int(pr.create_time())}", "stopped", tree=[])
        bs.apply([a], N)
        assert not a.applied and "tree changed" in str(a.error) and calls == []
    finally:
        kids = psutil.Process(parent.pid).children(recursive=True)
        for c in kids:
            c.kill()
        psutil.wait_procs(kids, timeout=10)
        parent.kill()
        parent.wait(timeout=10)


# ------------------------------------------------------------ second audit (#477), 2026-10-29
class _FakePsutil:
    """Just enough of psutil for run_once with an injected measurement."""
    def __init__(self) -> None:
        self.alive: set[int] = set()

    def cpu_count(self) -> int:
        return N

    def pid_exists(self, pid: int) -> bool:
        return pid in self.alive

    def virtual_memory(self) -> Any:
        class _VM:
            total = 64 * 1048576 * 1024
            available = 32 * 1048576 * 1024
        return _VM()


def _drive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
           box: list[Proc]) -> tuple[_FakePsutil, list[Any], Any]:
    """run_once against `box`; landed affinity actions are written back onto it."""
    fake = _FakePsutil()
    fake.alive = {p.pid for p in box}
    feed: list[Any] = []
    monkeypatch.setattr(bs, "psutil", fake)
    monkeypatch.setattr(bs, "measure", lambda _w: feed.pop(0))

    def _apply(actions: list[bs.Action], n_cpu: int) -> None:
        for a in actions:
            a.applied = True
            for p in box:
                if p.pid == a.pid and a.kind == "affinity":
                    p.affinity = bs.mask_to_cpus(str(a.after), n_cpu)
                elif p.pid == a.pid:
                    p.priority = str(a.after)
    monkeypatch.setattr(bs, "apply", _apply)
    rules_path = tmp_path / "CPU_SHAPE.json"
    rules_path.write_text(json.dumps(RULES))

    def run() -> dict[str, Any]:
        return bs.run_once(rules_path=rules_path, report_path=tmp_path / "B.json",
                           phase_path=tmp_path / "absent.json",
                           adopt_heartbeat_path=tmp_path / "absent2.json")
    return fake, feed, run


def test_an_unmeasured_pass_never_strands_a_pin(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    """MF1 + SF1 repro: 3 starved passes, 1 empty, then calm. Before: the miner stayed on
    0x3000f and a non-python 'other' ended on 0x300ff. Now both go back where they were."""
    full = list(range(N))
    judge = Proc(20, "python.exe", cmdline="python.exe run_sharded_gauntlet.py", create_time=1,
                 cpu_pct=50, priority="BelowNormal", affinity=full)
    miner = Proc(31, "python.exe", cmdline="python.exe moat_miner.py", create_time=100,
                 cpu_pct=900, priority="BelowNormal", affinity=full)
    other = Proc(40, "render.exe", cmdline="render.exe --big", create_time=300,
                 cpu_pct=800, priority="Normal", affinity=full)
    box = [judge, miner, other]
    _fake, feed, run = _drive(monkeypatch, tmp_path, box)

    def snap() -> list[Proc]:
        return copy.deepcopy(box)
    for _ in range(3):
        feed.append((snap(), 100.0))
        out = run()
        assert out["judge"]["starved"] is True
    assert miner.affinity is not None and other.affinity is not None
    assert bs.cpus_to_mask(miner.affinity) == "0x3000f"
    assert bs.cpus_to_mask(other.affinity) == "0x3000f"            # pinned by share_cap
    feed.append(([], None))                                         # the empty pass
    out = run()
    assert out["verdict"] == "UNMEASURED"
    assert out["share_cap_moved"] and out["judge_reserve"]["moved"]  # carried, not dropped
    miner.cpu_pct, other.cpu_pct = 300, 300
    feed.append((snap(), 40.0))
    out = run()
    assert out["judge"]["starved"] is False
    assert miner.affinity is not None and other.affinity is not None
    assert bs.cpus_to_mask(miner.affinity) == "0x300ff"            # back to the side mask
    assert bs.cpus_to_mask(other.affinity) == "0x3ffff"            # its original 18 cores
    assert out["share_cap_moved"] == {} and out["judge_reserve"]["moved"]


def test_rules_refused_carries_the_records_forward(tmp_path: Path) -> None:
    """MF1: a RULES_REFUSED pass rewrites the report without forgetting the pins."""
    report = tmp_path / "B.json"
    report.write_text(json.dumps({"generated_at": "t0",
                                  "share_cap_moved": {"40:300": {"mask": "0x3000f",
                                                                 "orig": list(range(N))}},
                                  "judge_reserve": {"moved": {"31:100": "0x3000f"},
                                                    "switches": [{"mode": "boost"}]}}))
    bad = tmp_path / "CPU_SHAPE.json"
    bad.write_text(json.dumps({"rules": [{"name": "x", "match": "y", "priority": "High"}]}))
    out = bs.run_once(rules_path=bad, report_path=report)
    assert out["verdict"] == "RULES_REFUSED"
    doc = json.loads(report.read_text())
    assert doc["share_cap_moved"] == {"40:300": {"mask": "0x3000f", "orig": list(range(N))}}
    assert doc["judge_reserve"]["moved"] == {"31:100": "0x3000f"}
    assert doc["judge_reserve"]["switches"] == [{"mode": "boost"}]


def test_a_released_non_python_process_gets_its_original_cores_back() -> None:
    """SF1: release targets the pre-pin mask for a process the reservation does not apply to."""
    side = bs.mask_to_cpus("0x300FF", N)
    p = Proc(40, "render.exe", cmdline="render.exe", create_time=300, cpu_pct=100,
             affinity=bs.mask_to_cpus("0x3000F", N), group="other")
    rec = {p.key: {"mask": "0x3000f", "orig": list(range(N))}}
    acts, keep = bs.release_share_cap([p], rec, judge_starved=False, side_now=side,
                                      side_base=side, n_cpu=N, skip_pids=set(),
                                      reserved=lambda q: bs.reserve_applies(q, RES))
    assert [(a.pid, a.after) for a in acts] == [(40, "0x3ffff")] and keep == {}


def _money_box(gateway_class: str | None) -> list[Proc]:
    full = list(range(N))
    procs = [
        Proc(11, "terminal64.exe", exe=r"C:\MT5\terminal64.exe", create_time=1,
             priority="Normal", affinity=full),
        Proc(60, "python.exe", cmdline=r"python.exe C:\opt\quant\desks\mt5\run_gateway_loop.py",
             create_time=2, priority=gateway_class, affinity=full),
        Proc(500, "powershell.exe", cmdline="powershell.exe -File Adopt-And-Seal.ps1",
             create_time=3, priority="Normal", affinity=full),
    ]
    bs.classify(procs, RULES["groups"])
    return procs


def test_the_adopt_tree_never_rises_above_the_money_path() -> None:
    """MF2: with the gateway python at default Normal, adopt must not go above it."""
    procs = _money_box("Normal")
    out = bs.plan(procs, RULES, N, judge_starved=False)
    got = {a.pid: a.after for a in out.actions if a.kind == "priority"}
    # the committed rules raise the whole money group first: gateway at AboveNormal, adopt ties
    assert got[60] == "AboveNormal" and got[11] == "AboveNormal" and got[500] == "AboveNormal"
    # with only the terminals raised (the old rules), adopt is held at the gateway's class
    old = {**RULES, "rules": [r for r in RULES["rules"] if r["name"] != "money_path_raise"]
           + [{"name": "mt5_terminals_raise", "match": "terminal64.exe",
               "priority": "AboveNormal"}]}
    out = bs.plan(_money_box("Normal"), old, N, judge_starved=False)
    assert 500 not in {a.pid for a in out.actions if a.kind == "priority"}
    assert any(r["pid"] == 500 and "lowest money-path class is Normal" in r["why"]
               for r in out.refused)
    out = bs.plan(_money_box("BelowNormal"), old, N, judge_starved=False)
    assert any(r["pid"] == 500 for r in out.refused)
    # a money class we cannot read: adopt is refused, never assumed under it
    out = bs.plan(_money_box(None), old, N, judge_starved=False)
    assert any(r["pid"] == 500 and "unreadable" in r["why"] for r in out.refused)
    assert 500 not in {a.pid for a in out.actions if a.kind == "priority"}


def test_adopt_raises_land_only_after_every_money_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """MF2: money raises are applied first; a failed one holds the adopt raise back."""
    out = bs.plan(_money_box("Normal"), RULES, N, judge_starved=False)
    order: list[int] = []

    def _apply(actions: list[bs.Action], _n: int) -> None:
        for a in actions:
            order.append(a.pid)
            if a.pid == 60:
                a.error = "AccessDenied"
            else:
                a.applied = True
    monkeypatch.setattr(bs, "apply", _apply)
    bs.apply_ordered(out.actions, N)
    adopt = [a for a in out.actions if a.pid == 500 and a.kind == "priority"]
    assert adopt and not adopt[0].applied and "money raise on pid 60" in str(adopt[0].error)
    assert 500 not in order


def test_every_throttle_carries_a_two_sided_missed_growth_line() -> None:
    """SF2: share_cap, the memecoin cap and the allocator cap each bill cost AND gain."""
    names = bs.throttle_mechanisms(RULES)
    assert {"memecoin_cap", "pf_allocator_heavy", "share_cap", "judge_reserve"} <= set(names)
    assert "money_path_raise" not in names and "adopt_release_raise" not in names
    p = Proc(40, "render.exe", create_time=300, cpu_pct=800, group="other")
    a = bs.Action(40, "render.exe", "other", "share_cap", "affinity", "0x3ffff", "0x3000f",
                  applied=True)
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[p], actions=[a], n_cpu=N, at="t1",
                                  judge_share=0.10)
    assert all(led[n]["two_sided"] and led[n]["cost"] and led[n]["gain"] for n in names)
    assert led["share_cap"]["open"][0]["share_before"] == round(800 / 1800, 4)
    p.cpu_pct = 500
    led = bs.missed_growth_ledger(led, rules=RULES, procs=[p], actions=[], n_cpu=N, at="t2",
                                  judge_share=0.30)
    ev = led["share_cap"]["closed"][0]
    assert ev["forgone_share"] == pytest.approx(300 / 1800, abs=2e-4)
    assert ev["judge_gain_share"] == pytest.approx(0.2)
    assert ev["net_share"] == round(0.2 - ev["forgone_share"], 4)
    assert led["share_cap"]["open"] == [] and led["share_cap"]["totals"]["n"] == 1
    # a widening (release) is not a throttle and opens nothing
    w = bs.Action(40, "render.exe", "other", "share_cap", "affinity", "0x3000f", "0x3ffff",
                  applied=True)
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[p], actions=[w], n_cpu=N, at="t3",
                                  judge_share=0.3)
    assert led["share_cap"]["open"] == []


#: A throttle on ANOTHER process: its cores narrowed or its class set. Re-nicing oneself
#: (`me.nice`, `os.nice`) is not one.
_THROTTLE_CALL = re.compile(r"(\w+)\.(nice|cpu_affinity)\(\s*([^)\s])")


def _throttles_without_ledger(root: Path) -> list[str]:
    bad = []
    for path in sorted((root / "libs" / "ops").glob("*.py")):
        s = path.read_text("utf-8")
        calls = [m for m in _THROTTLE_CALL.finditer(s) if m.group(1) not in ("me", "os", "self")]
        if calls and ('THROTTLE_LEDGER = "missed_growth"' not in s
                      or "def missed_growth_ledger(" not in s):
            bad.append(path.name)
    return bad


def test_every_libs_ops_throttle_is_two_sided(tmp_path: Path) -> None:
    """SF2 / growth governance G5 in spirit: any libs/ops module that throttles another process
    carries the two-sided missed_growth ledger, and the shaper's covers every CPU_SHAPE throttle.
    (scripts/check_growth_governance.py is a signed immutable evaluator: wiring this scan into it
    needs a human re-sign, so the fence lives here until then.)"""
    assert _throttles_without_ledger(REPO) == []
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[], actions=[], n_cpu=N, at="",
                                  judge_share=None)
    for name in bs.throttle_mechanisms(RULES):
        assert led[name]["two_sided"] and led[name]["cost"] and led[name]["gain"], name
    fake = tmp_path / "libs" / "ops"
    fake.mkdir(parents=True)
    (fake / "squeezer.py").write_text("def go(pr):\n    pr.cpu_affinity([0])\n")
    (fake / "self_nice.py").write_text("def go(me):\n    me.nice(10)\n")
    assert _throttles_without_ledger(tmp_path) == ["squeezer.py"]


# ------------------------------------------------------------------------------------ third audit
def _gateway_box() -> list[Proc]:
    """The gateway (money by name) and its python child state_pusher_loop.py (money by tree)."""
    full = list(range(N))
    procs = [
        Proc(20, "python.exe", cmdline="python.exe run_sharded_gauntlet.py", create_time=1,
             cpu_pct=50, priority="BelowNormal", affinity=full),
        Proc(60, "python.exe", cmdline=r"python.exe C:\opt\quant\desks\mt5\run_gateway_loop.py",
             create_time=2, cpu_pct=20, priority="AboveNormal", affinity=full),
        Proc(61, "python.exe", ppid=60, create_time=3,
             cmdline=r"python.exe C:\opt\quant\desks\mt5\scripts\state_pusher_loop.py",
             cpu_pct=900, priority="Normal", affinity=full),
        # a pid-reuse impostor: its ppid names the gateway, but it is older than the gateway
        Proc(62, "python.exe", ppid=60, create_time=0.5, cmdline="python.exe other_job.py",
             cpu_pct=900, priority="Normal", affinity=full),
    ]
    bs.classify(procs, RULES["groups"])
    return procs


def test_a_gateway_child_is_money_and_never_reserved_off_its_cores() -> None:
    """MF1 probe: state_pusher_loop.py under the gateway read as "other" and plan_reserve moved
    it 0x3ffff -> 0x3000f. The money path is a tree: its children are raise-only."""
    procs = _gateway_box()
    g = _by_pid(procs)
    assert g[61].group == "money" and g[60].group == "money"
    assert g[62].group == "other"                     # an older process is never a child
    for boost in (False, True):
        actions, moved, _ = bs.plan_reserve(procs, RES, N, boost=boost, floor_cores=FLOOR,
                                            skip_pids=set(), previous_moved={})
        assert 61 not in moved_pids(actions) and g[61].key not in moved
        assert 62 in moved_pids(actions)
    # narrowed on an earlier pass while it read as other: every core back
    g[61].affinity = bs.mask_to_cpus("0x3000F", N)
    actions, _, _ = bs.plan_reserve(procs, RES, N, boost=True, floor_cores=FLOOR,
                                    skip_pids=set(), previous_moved={g[61].key: "0x3000f"})
    assert [(a.pid, a.after) for a in actions if a.pid == 61] == [(61, "0x3ffff")]


def test_a_gateway_child_is_never_share_capped() -> None:
    """MF1 probe: a 9-core gateway child, two passes, a starved judge: never pinned."""
    procs = _gateway_box()
    out = bs.plan(procs, RULES, N, judge_starved=True, previous_heavy=[p.key for p in procs])
    assert not [a for a in out.actions if a.pid == 61 and a.kind == "affinity"]
    assert not [a for a in out.actions if a.pid == 61 and a.kind == "priority"
                and bs._rank(str(a.after)) < bs._rank("Normal")]
    assert 61 not in {int(k.split(":")[0]) for k in out.heavy}
    # raised with the money path instead
    assert any(a.pid == 61 and a.after == "AboveNormal" for a in out.actions)
    # the impostor is an ordinary other process and is capped
    assert any(a.pid == 62 and a.rule == "share_cap" for a in out.actions)
    # and a pin set before the fix is widened back to every core
    g = _by_pid(procs)[61]
    g.affinity = bs.mask_to_cpus("0x3000F", N)
    acts, keep = bs.release_share_cap(procs, {g.key: {"mask": "0x3000f", "orig": None}},
                                      judge_starved=True, side_now=[0], side_base=[0], n_cpu=N,
                                      skip_pids=set())
    assert [(a.pid, a.after) for a in acts] == [(61, "0x3ffff")] and keep == {}


def test_release_restores_the_recorded_mask_exactly() -> None:
    """SF probe :595: release gave cur | orig (0x3000f | 0x300f0 = 0x300ff), a mask the process
    never held. It restores the recorded original exactly."""
    side = bs.mask_to_cpus("0x300FF", N)
    p = Proc(40, "render.exe", cmdline="render.exe", create_time=300, cpu_pct=100,
             affinity=bs.mask_to_cpus("0x3000F", N), group="other")
    rec = {p.key: {"mask": "0x3000f", "orig": bs.mask_to_cpus("0x300F0", N)}}
    acts, keep = bs.release_share_cap([p], rec, judge_starved=False, side_now=side,
                                      side_base=side, n_cpu=N, skip_pids=set(),
                                      reserved=lambda q: bs.reserve_applies(q, RES))
    assert [(a.pid, a.after) for a in acts] == [(40, "0x300f0")] and keep == {}
    # a reserved python miner whose original cores lay inside the side gets exactly those back
    m = Proc(31, "python.exe", cmdline="python.exe moat_miner.py", create_time=100,
             cpu_pct=100, affinity=bs.mask_to_cpus("0x3000F", N), group="mining")
    rec = {m.key: {"mask": "0x3000f", "orig": bs.mask_to_cpus("0x000F3", N)}}
    acts, keep = bs.release_share_cap([m], rec, judge_starved=False, side_now=side,
                                      side_base=side, n_cpu=N, skip_pids=set(),
                                      reserved=lambda q: bs.reserve_applies(q, RES))
    assert [(a.pid, a.after) for a in acts] == [(31, "0xf3")] and keep == {}


def test_keep_unseen_drops_a_reused_pid() -> None:
    """SF probe :1040: a record survives an unread pass only for the SAME process."""
    prev = {"31:100": {"mask": "0x3000f"}, "32:200": "0x300ff", "33:300": "0x300ff"}
    ctimes = {31: 100.4, 32: 999.0}            # 32's pid now names a younger process

    def alive(pid: int) -> bool:
        return pid in (31, 32, 33)
    got = bs.keep_unseen({}, prev, set(), alive, ctimes.get)
    assert set(got) == {"31:100", "33:300"}     # 33: alive, create time unreadable -> kept
    assert bs.keep_unseen({}, prev, set(), lambda _p: False, ctimes.get) == {}


def test_an_unread_but_alive_process_is_not_billed_as_gone() -> None:
    """SF probe :771: a process psutil could not read this pass stays open in the ledger."""
    p = Proc(40, "render.exe", create_time=300, cpu_pct=800, group="other")
    a = bs.Action(40, "render.exe", "other", "share_cap", "affinity", "0x3ffff", "0x3000f",
                  applied=True)
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[p], actions=[a], n_cpu=N, at="t1",
                                  judge_share=0.10)
    led2 = bs.missed_growth_ledger(led, rules=RULES, procs=[], actions=[], n_cpu=N, at="t2",
                                   judge_share=0.30, lives=lambda k: k == p.key)
    assert led2["share_cap"]["closed"] == [] and len(led2["share_cap"]["open"]) == 1
    assert led2["share_cap"]["totals"]["n"] == 0
    led3 = bs.missed_growth_ledger(led2, rules=RULES, procs=[], actions=[], n_cpu=N, at="t3",
                                   judge_share=0.30, lives=lambda _k: False)
    ev = led3["share_cap"]["closed"][0]
    assert ev["gone"] is True and ev["forgone_share"] == round(800 / 1800, 4)


def test_a_class_set_from_an_unreadable_class_is_billed_as_a_lowering() -> None:
    """SF probe :736: _rank(None) = -1 made BelowNormal-from-unknown read as a raise."""
    a = bs.Action(14, "node.exe", "memecoin", "memecoin_cap", "priority", None, "BelowNormal",
                  applied=True)
    assert bs._narrows(a)
    p = Proc(14, "node.exe", create_time=1, cpu_pct=200, group="memecoin")
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[p], actions=[a], n_cpu=N, at="t1",
                                  judge_share=0.1)
    assert len(led["memecoin_cap"]["open"]) == 1
    assert not bs._narrows(bs.Action(14, "n", "m", "r", "priority", "Normal", "AboveNormal"))


def test_summarize_ignores_the_system_idle_process() -> None:
    """SF probe :252: pid 0's idle time counted as busy and hid a starved judge."""
    full = list(range(N))
    procs = [Proc(0, "System Idle Process", cpu_pct=1200, affinity=full),
             Proc(20, "python.exe", cmdline="run_sharded_gauntlet.py", cpu_pct=100),
             Proc(31, "python.exe", cmdline="moat_miner.py", cpu_pct=500)]
    bs.classify(procs, RULES["groups"])
    s = bs.summarize(procs, N, 95.0, RULES["judge_starved"])
    assert s["busy_cpu_pct"] == 600.0 and "system" not in s["by_group"]
    assert s["judge"]["share_of_busy"] == round(100 / 600, 4) and s["judge"]["starved"] is True


def test_a_failed_money_raise_lowers_an_adopt_tree_raised_earlier(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """P6 probe: the gateway restarted at Normal, its raise failed, and the adopt tree raised on
    an earlier pass sat at AboveNormal above it. It is lowered to the money floor."""
    procs = _money_box("Normal")
    for p in procs:
        if p.pid == 500:
            p.priority = "AboveNormal"                 # raised on an earlier pass
        if p.pid == 11:
            p.priority = "AboveNormal"
    out = bs.plan(procs, RULES, N, judge_starved=False)
    assert not [a for a in out.actions if a.pid == 500]   # nothing planned for adopt this pass

    def _apply(actions: list[bs.Action], _n: int) -> None:
        for a in actions:
            if a.pid == 60 and a.group == "money":
                a.error = "AccessDenied"
            else:
                a.applied = True
    monkeypatch.setattr(bs, "apply", _apply)
    extra = bs.apply_ordered(out.actions, N, procs)
    assert [(a.pid, a.before, a.after, a.applied) for a in extra] == [
        (500, "AboveNormal", "Normal", True)]
    # all money raises land: the adopt tree may stay where it is
    procs = _money_box("Normal")
    _by_pid(procs)[500].priority = "AboveNormal"
    out = bs.plan(procs, RULES, N, judge_starved=False)

    def _land(actions: list[bs.Action], _n: int) -> None:
        for a in actions:
            a.applied = True
    monkeypatch.setattr(bs, "apply", _land)
    assert bs.apply_ordered(out.actions, N, procs) == []
    # a money class unreadable: the adopt tree goes back to Normal, never assumed under it
    procs = _money_box(None)
    _by_pid(procs)[500].priority = "AboveNormal"
    extra = bs.apply_ordered([], N, procs)
    assert [(a.pid, a.after) for a in extra] == [(500, "Normal")]


# ------------------------------------------------------------ third audit (#482), 2026-10-29
def _parent_with_child() -> Any:
    import subprocess
    import sys
    return subprocess.Popen([sys.executable, "-c", (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "time.sleep(60)")])


def _wait_children(psutil: Any, pid: int) -> list[Any]:
    pr = psutil.Process(pid)
    for _ in range(200):
        kids: list[Any] = pr.children(recursive=True)
        if kids:
            return kids
        psutil.wait_procs([], timeout=0.05)
    raise AssertionError("child never started")


def _reap(psutil: Any, parent: Any) -> None:
    try:
        kids = psutil.Process(parent.pid).children(recursive=True)
    except psutil.Error:
        kids = []
    for c in kids:
        with contextlib.suppress(psutil.Error):
            c.kill()
    psutil.wait_procs(kids, timeout=10)
    if parent.poll() is None:
        parent.kill()
    parent.wait(timeout=10)


def test_the_verified_kill_refuses_a_child_born_after_verification() -> None:
    """#482 probe: apply checked the tree, then kill_verified_tree re-enumerated children and
    killed whatever was there -- a child born in between, never classified, went down with it.
    The kill takes the verified set and refuses (killing nothing) when the tree is not it."""
    psutil = pytest.importorskip("psutil")
    from libs.ops import proctree
    parent = _parent_with_child()
    try:
        kids = _wait_children(psutil, parent.pid)
        root = psutil.Process(parent.pid)
        # verified before the child existed: the tree changed, nothing is killed
        out = proctree.kill_verified_tree(root, verified={}, timeout=0.5)
        assert "tree changed" in str(out.get("refused")) and out["killed"] == 0
        assert root.is_running() and all(k.is_running() for k in kids)
        # the same pid with another creation time is not the verified child either
        wrong = {k.pid: k.create_time() - 5 for k in kids}
        out = proctree.kill_verified_tree(root, verified=wrong, timeout=0.5)
        assert out.get("refused") and root.is_running()
        # the set that was verified: the root and that child are killed
        good = {k.pid: k.create_time() for k in kids}
        out = proctree.kill_verified_tree(root, verified=good, timeout=10)
        assert out.get("refused") is None and out["root_gone"] is True
        assert out["killed"] == 1 + len(kids)
    finally:
        _reap(psutil, parent)


def test_a_stop_passes_its_measured_tree_with_creation_times(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """#482 probe at apply: the stop's measured descendants (keys, pid + creation time) are the
    set the kill verifies; a child whose key does not match refuses the stop."""
    psutil = pytest.importorskip("psutil")
    from libs.ops import proctree
    seen: list[Any] = []
    real = proctree.kill_verified_tree

    def spy(root: Any, **kw: Any) -> dict[str, Any]:
        seen.append(kw.get("verified"))
        return real(root, **kw)
    monkeypatch.setattr(proctree, "kill_verified_tree", spy)
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    parent = _parent_with_child()
    try:
        kids = _wait_children(psutil, parent.pid)
        pr = psutil.Process(parent.pid)
        key = f"{parent.pid}:{int(pr.create_time())}"
        up = _chain(psutil, parent.pid)
        stale = [f"{k.pid}:{int(k.create_time()) - 5}" for k in kids]
        a = bs.Action(parent.pid, "python", "other", "dedupe", "stop", key, "stopped",
                      tree=stale, ancestors=up)
        bs.apply([a], N)
        assert not a.applied and "tree changed" in str(a.error) and seen == []
        assert pr.is_running()
        a = bs.Action(parent.pid, "python", "other", "dedupe", "stop", key, "stopped",
                      tree=[f"{k.pid}:{int(k.create_time())}" for k in kids], ancestors=up)
        bs.apply([a], N)
        assert a.applied and a.error is None
        assert seen and set(seen[-1]) == {k.pid for k in kids}
    finally:
        _reap(psutil, parent)


def test_a_dedupe_stop_bills_a_two_sided_missed_growth_line() -> None:
    """#482 probe: a stopped duplicate is a throttle; its line names the share given up (the
    duplicate and the tree it took down) and the judge share gained across it."""
    assert "dedupe" in bs.throttle_mechanisms(RULES)
    dup = Proc(41, "python.exe", cmdline="python.exe some_loop.py", create_time=20,
               cpu_pct=300, group="other")
    kid = Proc(91, "python.exe", ppid=41, cmdline="python.exe helper.py", create_time=31,
               cpu_pct=60, group="other")
    stop = bs.Action(41, "python.exe", "other", "dedupe", "stop", dup.key, "stopped; kept 40:10",
                     applied=True, tree=[kid.key], died=[dup.key, kid.key])
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[dup, kid], actions=[stop], n_cpu=N,
                                  at="t1", judge_share=0.10)
    line = led["dedupe"]
    assert line["two_sided"] and line["cost"] and line["gain"]
    assert line["open"][0]["share_before"] == round(360 / 1800, 4)
    led = bs.missed_growth_ledger(led, rules=RULES, procs=[], actions=[], n_cpu=N, at="t2",
                                  judge_share=0.25, lives=lambda _k: False)
    ev = led["dedupe"]["closed"][0]
    assert ev["gone"] is True and ev["forgone_share"] == round(360 / 1800, 4)
    assert ev["judge_gain_share"] == pytest.approx(0.15)
    assert ev["net_share"] == round(0.15 - ev["forgone_share"], 4)
    # a stop that did not land opens nothing
    miss = bs.Action(41, "python.exe", "other", "dedupe", "stop", dup.key, "x", error="denied")
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[dup], actions=[miss], n_cpu=N,
                                  at="t3", judge_share=0.1)
    assert led["dedupe"]["open"] == []


# ------------------------------------------------------------------------------------ fourth audit
_MONEY_SCRIPTS = [
    # (command line, group it must read as)
    (r"python.exe C:\opt\quant\desks\mt5\prop\e8_gold.py", "money"),
    (r"python.exe C:\opt\quant\desks\mt5\prop\e8_book.py", "money"),
    (r"python.exe C:\opt\quant\scripts\run_deadman_switch.py", "money"),
    (r"python.exe C:\opt\quant\desks\mt5\research\prop_challenge_allocator.py", "money_feed"),
    (r"python.exe C:\opt\quant\desks\mt5\research\allocator_trigger.py", "money_feed"),
    (r"pythonw.exe -u research\pf_allocator.py --mode fast", "money_feed"),
]


@pytest.mark.parametrize(("cmd", "group"), _MONEY_SCRIPTS)
def test_every_money_process_is_raise_only_and_never_moved_or_capped(cmd: str,
                                                                     group: str) -> None:
    """MF1 probe: each of these read as mining/other and was reserve-moved, narrowed and
    share-capped (pf_allocator --mode fast was share-capped)."""
    full = list(range(N))
    procs = [Proc(20, "python.exe", cmdline="python.exe run_sharded_gauntlet.py", create_time=1,
                  cpu_pct=50, priority="BelowNormal", affinity=full),
             Proc(70, "python.exe", cmdline=cmd, create_time=5, cpu_pct=900, priority="Normal",
                  affinity=full),
             Proc(71, "python.exe", ppid=70, cmdline="python.exe -c from multiprocessing.spawn",
                  create_time=6, cpu_pct=900, priority="Normal", affinity=full)]
    bs.classify(procs, RULES["groups"])
    g = _by_pid(procs)
    assert g[70].group == group and g[71].group == group        # the child rides with it
    assert group in bs.RAISE_ONLY
    for boost in (False, True):
        actions, moved, _ = bs.plan_reserve(procs, RES, N, boost=boost, floor_cores=FLOOR,
                                            skip_pids=set(), previous_moved={})
        assert actions == [] and moved == {}
    out = bs.plan(procs, RULES, N, judge_starved=True, previous_heavy=[p.key for p in procs])
    assert not [a for a in out.actions if a.pid in (70, 71) and a.kind == "affinity"]
    assert not [a for a in out.actions if a.pid in (70, 71) and a.kind == "priority"
                and bs._rank(str(a.after)) < bs._rank("Normal")]
    assert not [k for k in out.heavy if k.split(":")[0] in ("70", "71")]
    raised = {a.pid for a in out.actions if a.kind == "priority" and a.after == "AboveNormal"}
    # the order path is raised; the allocators are protected but not raised over the judge
    assert (70 in raised) is (group == "money")


def test_pf_allocator_heavy_stays_the_one_pinned_allocator() -> None:
    """MF1: only --mode heavy keeps its committed 0xFF pin (D-20261029-011); fast is money_feed."""
    procs = _box()
    heavy = _by_pid(procs)[10]
    assert heavy.group == "other"
    out = bs.plan(procs, RULES, N, judge_starved=False)
    assert any(a.pid == 10 and a.rule == "pf_allocator_heavy" for a in out.actions)
    rule = next(r for r in RULES["rules"] if r["name"] == "pf_allocator_heavy")
    assert "D-20261029-011" in rule["why"]


def test_an_orphaned_gateway_child_stays_money_while_it_lives(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """MF2 probe: the gateway dies, its state_pusher_loop child lives on with a dead ppid. The
    tree is built from live roots only, so it read "other" and was moved, narrowed and capped.
    Money membership is sticky by key while key_lives holds."""
    full = list(range(N))
    judge = Proc(20, "python.exe", cmdline="python.exe run_sharded_gauntlet.py", create_time=1,
                 cpu_pct=50, priority="BelowNormal", affinity=full)
    gw = Proc(60, "python.exe", cmdline=r"python.exe C:\opt\quant\desks\mt5\run_gateway_loop.py",
              create_time=2, cpu_pct=20, priority="AboveNormal", affinity=full)
    child = Proc(61, "python.exe", ppid=60, create_time=3,
                 cmdline=r"python.exe C:\opt\quant\desks\mt5\scripts\state_pusher_loop.py",
                 cpu_pct=900, priority="AboveNormal", affinity=full)
    box = [judge, gw, child]
    fake, feed, run = _drive(monkeypatch, tmp_path, box)
    feed.append((copy.deepcopy(box), 100.0))
    out = run()
    assert child.key in out["money_keys"]
    # the gateway dies: the child is an orphan whose ppid names nothing
    box.remove(gw)
    fake.alive.discard(60)
    for _ in range(3):                         # starved passes: reserve, cap and share_cap
        feed.append((copy.deepcopy(box), 100.0))
        out = run()
        assert out["judge"]["starved"] is True
        assert child.key in out["money_keys"]
        assert not [a for a in out["actions"] if a["pid"] == 61 and a["kind"] == "affinity"]
        assert bs.cpus_to_mask(child.affinity or []) == "0x3ffff"
    # pure: classify with and without the sticky key
    alone = [copy.deepcopy(child)]
    bs.classify(alone, RULES["groups"])
    assert alone[0].group == "other"           # what the live-roots tree alone says
    bs.classify(alone, RULES["groups"], {child.key})
    assert alone[0].group == "money" and alone[0].money_root is False
    # a dead key or a reused pid is never sticky
    assert bs.sticky_money_keys([child.key, "77:5"], {}, lambda p: p == 77,
                                lambda p: 9.0) == set()
    assert bs.sticky_money_keys([child.key], {}, lambda p: p == 61, lambda p: 3.2) == {child.key}


def test_the_adopt_floor_is_the_money_roots_and_never_below_normal(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MF3 probe: a money child at Idle dragged the adopt tree to Idle when a raise failed."""
    procs = _money_box("Normal")
    procs.append(Proc(62, "python.exe", ppid=60, create_time=4, cmdline="python.exe helper.py",
                      priority="Idle"))
    bs.classify(procs, RULES["groups"])
    g = _by_pid(procs)
    assert g[62].group == "money" and not g[62].money_root and g[60].money_root
    g[500].priority = "AboveNormal"
    money = bs.Action(60, "python.exe", "money", "money_path_raise", "priority", "Normal",
                      "AboveNormal", error="AccessDenied")
    extra = bs.adopt_floor_actions(procs, [money])
    assert [(a.pid, a.after, a.rule) for a in extra] == [(500, "Normal", "adopt_under_money")]
    assert extra[0].key == g[500].key
    # a money ROOT below Normal still never takes the adopt tree under Normal
    g[60].priority = "Idle"
    assert [(a.pid, a.after) for a in bs.adopt_floor_actions(procs, [money])] == [(500, "Normal")]
    g[500].priority = "Normal"
    assert bs.adopt_floor_actions(procs, [money]) == []
    # the plan-time clamp: same roots, same floor
    old = {**RULES, "rules": [r for r in RULES["rules"] if r["name"] != "money_path_raise"]}
    out = bs.plan(procs, old, N, judge_starved=False)
    assert any(r["pid"] == 500 and "Normal" in r["why"] for r in out.refused)


def test_lowering_the_adopt_tree_bills_a_two_sided_line() -> None:
    """MF3: adopt_under_money takes class from a process, so it is billed cost and gain."""
    assert "adopt_under_money" in bs.throttle_mechanisms(RULES)
    p = Proc(500, "powershell.exe", create_time=3, cpu_pct=90, group="adopt")
    a = bs.Action(500, "powershell.exe", "adopt", "adopt_under_money", "priority",
                  "AboveNormal", "Normal", applied=True, key=p.key)
    led = bs.missed_growth_ledger(None, rules=RULES, procs=[p], actions=[a], n_cpu=N, at="t1",
                                  judge_share=0.2)
    line = led["adopt_under_money"]
    assert line["two_sided"] and line["open"][0]["share_before"] == round(90 / 1800, 4)
    p.cpu_pct = 45
    led = bs.missed_growth_ledger(led, rules=RULES, procs=[p], actions=[], n_cpu=N, at="t2",
                                  judge_share=0.25)
    ev = led["adopt_under_money"]["closed"][0]
    assert ev["forgone_share"] == round(45 / 1800, 4)
    assert ev["judge_gain_share"] == pytest.approx(0.05)


def test_apply_never_writes_to_a_reused_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """SF1 probe: priority and affinity writes went to a bare psutil.Process(pid). Each write is
    checked against the measured key first, as the stop path is."""
    psutil = pytest.importorskip("psutil")
    import subprocess
    import sys
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        pr = psutil.Process(child.pid)
        ct = int(pr.create_time())
        cores = sorted(pr.cpu_affinity())
        mask = bs.cpus_to_mask(cores)
        stale = bs.Action(child.pid, "python", "other", "share_cap", "affinity", mask, mask,
                          key=f"{child.pid}:{ct - 5}")
        nokey = bs.Action(child.pid, "python", "other", "share_cap", "affinity", mask, mask)
        prio = bs.Action(child.pid, "python", "other", "memecoin_cap", "priority", "Normal",
                         "BelowNormal", key=f"{child.pid}:{ct - 5}")
        good = bs.Action(child.pid, "python", "other", "share_cap", "affinity", mask, mask,
                         key=f"{child.pid}:{ct}")
        bs.apply([stale, nokey, prio, good], max(cores) + 1)
        assert not stale.applied and "reused" in str(stale.error)
        assert not prio.applied and "reused" in str(prio.error)
        assert not nokey.applied and "no measured key" in str(nokey.error)
        assert good.applied and good.error is None
    finally:
        child.kill()
        child.wait(timeout=10)


# ------------------------------------------------------------ fourth audit (#482), 2026-10-29
@pytest.mark.parametrize("cmd", [c for c, _g in _MONEY_SCRIPTS])
def test_a_duplicate_whose_child_is_a_money_process_is_never_stopped(cmd: str) -> None:
    """MF1 through #482: a duplicate whose child is e8_gold, the deadman or an allocator."""
    cfg = {"allow": ["some_loop.py"]}
    procs = _dupes()
    procs.append(Proc(90, "python.exe", ppid=41, cmdline=cmd, create_time=30))
    bs.classify(procs, RULES["groups"])
    assert _by_pid(procs)[90].group in bs.NEVER_IN_A_STOPPED_TREE
    keys = [d["duplicate"] for d in bs.plan_dedupe(procs, cfg)[1]]
    stops, seen = bs.plan_dedupe(procs, cfg, previous_duplicates=keys)
    assert stops == [] and "descendant 90" in seen[0]["refused"]


def test_an_orphaned_money_child_is_never_a_dedupe_candidate() -> None:
    """MF2 through #482: the sticky money key keeps an orphan out of dedupe."""
    cfg = {"allow": ["state_pusher_loop.py"]}
    loop = "python.exe state_pusher_loop.py"
    procs = [Proc(300, "python.exe", ppid=4, exe="py.exe", cmdline="python.exe stray.py",
                  create_time=1),
             Proc(301, "python.exe", ppid=300, exe="py.exe", cmdline=loop, create_time=2),
             Proc(401, "python.exe", ppid=400, exe="py.exe", cmdline=loop, create_time=4)]
    for p in procs:
        p.cwd, p.env_sig = r"C:\opt\quant", "env-a"
    bs.classify(procs, RULES["groups"], {"401:4"})       # its gateway (400) has died
    assert _by_pid(procs)[401].group == "money"
    keys = [d["duplicate"] for d in bs.plan_dedupe(procs, cfg)[1]]
    assert bs.plan_dedupe(procs, cfg, previous_duplicates=keys) == ([], [])


def test_a_partial_stop_bills_only_what_died() -> None:
    """SF3 probe: children killed under a denied root opened no line; a denied child that still
    lives was billed as forgone when the root died."""
    dup = Proc(41, "python.exe", cmdline="python.exe some_loop.py", create_time=20,
               cpu_pct=300, group="other")
    k1 = Proc(91, "python.exe", ppid=41, create_time=31, cpu_pct=60, group="other")
    k2 = Proc(92, "python.exe", ppid=41, create_time=32, cpu_pct=90, group="other")
    procs = [dup, k1, k2]
    # root denied, both children killed: not a landed stop, but 150% of a core died
    a = bs.Action(41, "python.exe", "other", "dedupe", "stop", dup.key, "stopped",
                  error="the duplicate's root is still running", tree=[k1.key, k2.key],
                  died=[k1.key, k2.key])
    led = bs.missed_growth_ledger(None, rules=RULES, procs=procs, actions=[a], n_cpu=N,
                                  at="t1", judge_share=0.1)
    ev = led["dedupe"]["open"][0]
    assert ev["share_before"] == round(150 / 1800, 4) and ev["landed"] is False
    led = bs.missed_growth_ledger(led, rules=RULES, procs=[dup], actions=[], n_cpu=N, at="t2",
                                  judge_share=0.2)
    ev = led["dedupe"]["closed"][0]
    assert ev["gone"] is True and ev["forgone_share"] == round(150 / 1800, 4)
    # root died, one child denied and alive: only the root and the dead child are billed
    b = bs.Action(41, "python.exe", "other", "dedupe", "stop", dup.key, "stopped", applied=True,
                  tree=[k1.key, k2.key], died=[dup.key, k1.key])
    led = bs.missed_growth_ledger(None, rules=RULES, procs=procs, actions=[b], n_cpu=N,
                                  at="t1", judge_share=0.1)
    assert led["dedupe"]["open"][0]["share_before"] == round(360 / 1800, 4)
    led = bs.missed_growth_ledger(led, rules=RULES, procs=[k2], actions=[], n_cpu=N, at="t2",
                                  judge_share=0.2)
    assert led["dedupe"]["closed"][0]["forgone_share"] == round(360 / 1800, 4)


def test_the_verified_kill_reports_which_processes_died() -> None:
    """SF3: kill_verified_tree names the dead by key, so a partial stop is billed exactly."""
    psutil = pytest.importorskip("psutil")
    from libs.ops import proctree
    parent = _parent_with_child()
    try:
        kids = _wait_children(psutil, parent.pid)
        root = psutil.Process(parent.pid)
        rkey = f"{root.pid}:{int(root.create_time())}"
        kkeys = {f"{k.pid}:{int(k.create_time())}" for k in kids}
        out = proctree.kill_verified_tree(root, verified={k.pid: k.create_time() for k in kids},
                                          timeout=10)
        assert out["root_gone"] is True and set(out["dead"]) == kkeys | {rkey}
    finally:
        _reap(psutil, parent)


def test_the_dedupe_why_names_the_verified_kill() -> None:
    why = RULES["dedupe"]["why"]
    assert "kill_verified_tree" in why and "proctree.kill_tree" not in why
