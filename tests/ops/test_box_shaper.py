"""The box bottleneck hunter's rails (libs/ops/box_shaper.py, desks/mt5/ops/CPU_SHAPE.json)."""
from __future__ import annotations

import copy
import json
import os
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
    out = bs.run_once(rules_path=rules_path, report_path=report_path)
    assert out["verdict"] == "MEASURED" and out["n_processes"] > 0
    doc = json.loads(report_path.read_text())
    assert {"top", "judge", "memecoin", "actions", "refused", "ram", "disk_free_gb"} <= set(doc)
    assert doc["line"].startswith("CPU SHAPE ") and "box " in doc["line"]
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
    assert h[-1] == {"at": "t1", "from": "base", "mode": "boost", "phase": "plan",
                     "starved": False, "judge_share_before": 0.21, "judge_share_after": None}
    h = bs.log_switch(h, at="t2", mode="boost", phase="plan", starved=False, judge_share=0.35)
    assert len(h) == 2 and h[-1]["judge_share_after"] == 0.35


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


def test_a_stop_goes_through_the_desks_tree_kill_and_refuses_a_reused_pid(
        monkeypatch: pytest.MonkeyPatch) -> None:
    psutil = pytest.importorskip("psutil")
    import subprocess
    import sys

    from libs.ops import proctree
    calls: list[int] = []
    real = proctree.kill_tree

    def spy(pid: int, **kw: Any) -> dict[str, Any]:
        calls.append(pid)
        return real(pid, **kw)

    monkeypatch.setattr(proctree, "kill_tree", spy)
    monkeypatch.setattr(bs, "IS_WINDOWS", True)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        ct = int(psutil.Process(child.pid).create_time())
        stale = bs.Action(child.pid, "python", "other", "dedupe", "stop", f"{child.pid}:{ct - 5}",
                          "stopped")
        bs.apply([stale], N)
        assert not stale.applied and "reused" in str(stale.error) and calls == []
        good = bs.Action(child.pid, "python", "other", "dedupe", "stop", f"{child.pid}:{ct}",
                         "stopped")
        bs.apply([good], N)
        assert good.applied and calls == [child.pid]
        assert child.wait(timeout=10) is not None
    finally:
        if child.poll() is None:
            child.kill()
