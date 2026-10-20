"""The judge's fair CPU share under the principal's 2026-10-20 constraints.

Three rules are pinned here:
  1. judge priority == the lowest miner priority, NEVER above any miner, never above NORMAL,
     strictly below live clocks, and only judge processes are ever changed;
  2. MT5-FrontierAudit is one instance at a time, its organs run sequentially, its schedule and
     organ list are unchanged (so audit work per day is unchanged);
  3. a stale GAUNTLET_BACKPRESSURE input reads UNMEASURED and ALARMS; the backpressure core is
     republished cheaply; the cadence apply skips, retries, records and never hangs.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gauntlet_backpressure as gb  # noqa: E402
import judging_throughput as jt  # noqa: E402

from scripts import judge_priority as jp  # noqa: E402
from scripts import run_sharded_gauntlet as rsg  # noqa: E402

BN, N, IDLE, AN, HIGH = jp.BELOW_NORMAL, jp.NORMAL, jp.IDLE, jp.ABOVE_NORMAL, jp.HIGH
R = jp.CLASS_RANK


def _p(pid, ppid, name, cmd, nice, created=None):
    # start time follows pid in the fixtures: a parent (lower pid) always predates its child
    return {"pid": pid, "ppid": ppid, "name": name, "cmdline": cmd, "nice": nice,
            "cpu_cores": 0.5, "create_time": float(pid if created is None else created)}


def _box(miner_nice=BN, judge_nice=BN, e8_nice=N, term_nice=BN, gw_nice=N, extra=()):
    py = r"C:\Program Files\Python314\python.exe"
    return [
        _p(10, 1, "python.exe", [py, "-u", r"scripts\run_sharded_gauntlet.py"], judge_nice),
        _p(11, 10, "python.exe",
           [py, "-u", r"C:\opt\quant\desks\mt5\scripts\run_sharded_gauntlet.py", "--once"],
           judge_nice),
        _p(12, 11, "python.exe", [py, "-c", "from multiprocessing.spawn import spawn_main"],
           judge_nice),
        _p(20, 1, "python.exe", [py, r"research\department_resident.py", "--dept", "fx"],
           miner_nice),
        _p(21, 1, "python.exe", [py, r"research\scout_swarm.py"], miner_nice),
        _p(30, 1, "cmd.exe", ["cmd.exe", "/c", r"C:\opt\quant\ops\run_frontier_audit.cmd"], BN),
        _p(31, 30, "python.exe", [py, "-u", r"desks\mt5\research\world_model.py", "--apply"], BN),
        _p(40, 1, "python.exe", [py, r"desks\mt5\prop\e8_executor.py"], e8_nice),
        _p(41, 1, "terminal64.exe", [r"C:\MT5\terminal64.exe"], term_nice),
        _p(42, 1, "python.exe", [py, r"research\gateway_resident.py"], gw_nice),
        _p(50, 1, "python.exe", [py, r"scripts\warm_gauntlet_cache.py"], IDLE),
        *extra,
    ]


# ------------------------------------------------------------------ 1. the priority-equality rule
def test_classification_follows_command_line_then_ancestry() -> None:
    cls = {r["pid"]: r["cls"] for r in jp.classify(_box())}
    assert cls[10] == cls[11] == cls[12] == "judge"       # pool child inherits the judge
    assert cls[20] == cls[21] == "miner"
    assert cls[30] == cls[31] == "audit"                  # organ under the audit cmd
    assert cls[40] == cls[41] == cls[42] == "live"        # E8, terminal64, the gateway
    assert cls[50] == "judge_warm"


def test_only_an_interpreter_is_the_judge_and_a_reused_parent_is_no_parent() -> None:
    py = "python.exe"
    extra = [
        # probe G: git and an editor with the judge's file in argv are not the judge
        _p(60, 1, "git.exe", ["git", "diff", r"desks\mt5\scripts\external_gauntlet.py"], N),
        _p(61, 1, "code.exe", ["code", r"scripts\run_sharded_gauntlet.py"], N),
        # probe H: an orphan miner whose dead parent's pid (11) was reused by the judge's sweep
        # child AFTER the orphan started: born at t=5, the "parent" at t=11
        _p(62, 11, py, [py, r"research\scout_swarm.py"], N, created=5.0),
    ]
    cls = {r["pid"]: r["cls"] for r in jp.classify(_box(extra=extra))}
    assert cls[60] == cls[61] == "other"
    assert cls[62] == "miner"


@pytest.mark.parametrize("miners", [[R[BN]], [R[N]], [R[BN], R[N]], [R[N], R[AN]],
                                    [R[HIGH]], [R[AN], R[HIGH]]])
@pytest.mark.parametrize("lives", [[], [R[N]], [R[BN]], [R[AN]]])
@pytest.mark.parametrize("registered", [None, R[N], R[AN], R[HIGH]])
@pytest.mark.parametrize("unreadable", [0, 1])
def test_the_judge_is_never_above_any_miner(miners, lives, registered, unreadable) -> None:
    t = jp.judge_target(miners, lives, registered_live=registered, unreadable=unreadable)
    assert t["status"] == "MEASURED"
    assert t["rank"] <= min(miners), "the judge may never sit above any miner"
    assert t["rank"] <= jp.JUDGE_CEILING_RANK
    assert t["rank"] >= R[BN], "the rule never pushes the judge below where it already is"
    assert t["above_any_miner"] is False
    for live in [*lives, *([registered] if registered is not None else [])]:
        if live > R[BN]:
            assert t["rank"] < live, "every live class, registered or observed, preempts it"
    if unreadable or registered is None:
        assert t["rank"] == R[BN], "an unreadable row or registration refuses any raise"


def test_the_live_cap_fails_closed_on_every_audit_probe() -> None:
    reg = jp.registered_live_rank()
    assert reg == R[N], "install_e8_tasks.ps1 registers E8 at Priority 4 = NORMAL"
    # A: E8 not running at the census -- the registered class still caps the judge
    box = [r for r in _box(miner_nice=N, term_nice=AN, gw_nice=AN) if r["pid"] != 40]
    assert jp.census(box)["target"]["rank"] == R[BN]
    # C: E8's command line unreadable -> not "a miner at NORMAL" but an unreadable row
    box = _box(miner_nice=N, term_nice=AN, gw_nice=AN, e8_nice=AN)
    box[7]["cmdline"] = None
    t = jp.census(box, registered_live=R[HIGH])["target"]
    assert t["rank"] == R[BN] and t["unreadable_rows"] == 1
    # D: E8's priority unreadable -> no raise
    box = _box(miner_nice=N, term_nice=AN, gw_nice=AN, e8_nice=None)
    assert jp.census(box, registered_live=R[HIGH])["target"]["rank"] == R[BN]
    # terminal64 at BELOW_NORMAL is a live class too: a NORMAL judge would sit above it
    box = _box(miner_nice=N, term_nice=BN, gw_nice=AN, e8_nice=AN)
    assert jp.census(box, registered_live=R[HIGH])["target"]["rank"] == R[BN]
    # ...and the gateway likewise
    box = _box(miner_nice=N, term_nice=AN, gw_nice=N, e8_nice=AN)
    assert jp.census(box, registered_live=R[HIGH])["target"]["rank"] == R[BN]
    # the registration unreadable -> no raise
    box = _box(miner_nice=N, term_nice=AN, gw_nice=AN, e8_nice=AN)
    assert jp.census(box, registered_live=None)["target"]["rank"] == R[BN]
    # only when EVERY live class is provably above NORMAL may the judge rise to EQUAL
    assert jp.census(box, registered_live=R[AN])["target"]["rank"] == R[N]


def test_the_registered_class_is_read_from_the_installer(tmp_path) -> None:
    f = tmp_path / "i.ps1"
    f.write_text("Set-E8Task -Priority 4\nSet-E8Task -Priority 6\n", "utf-8")
    assert jp.registered_live_rank(f) == R[N]
    f.write_text("Set-E8Task -Priority 2\n", "utf-8")
    assert jp.registered_live_rank(f) == R[AN]
    f.write_text("nothing here\n", "utf-8")
    assert jp.registered_live_rank(f) is None
    assert jp.registered_live_rank(tmp_path / "absent.ps1") is None


def test_no_miner_or_only_idle_miners_is_unmeasured_and_keeps_the_default() -> None:
    assert jp.judge_target([])["status"] == jp.UNMEASURED
    t = jp.judge_target([R[IDLE]])
    assert t["status"] == jp.UNMEASURED and t["idle_miners"] == 1
    flags, reading = jp.sweep_creationflags([])
    assert flags == BN and reading["target"]["status"] == jp.UNMEASURED


def _raisable_box(**kw):
    return _box(miner_nice=N, term_nice=AN, gw_nice=AN, e8_nice=AN, **kw)


def test_census_verdict_and_equalise_touch_only_the_judge() -> None:
    c = jp.census(_raisable_box(judge_nice=BN), registered_live=R[AN])
    assert c["target"]["rank"] == R[N] and c["verdict"] == "JUDGE_BELOW_MINERS"
    calls: list[tuple[int, int]] = []
    ch = jp.equalise(c["rows"], c["target"]["rank"], apply=True,
                     setter=lambda pid, k, row: calls.append((pid, k)))
    assert sorted(p for p, _ in calls) == [10, 11, 12]
    assert all(k == N for _, k in calls)
    assert all(x["applied"] for x in ch)
    calls.clear()
    jp.equalise(c["rows"], c["target"]["rank"], apply=False, setter=lambda *a: calls.append(a))
    assert calls == []


def test_apply_refuses_a_pid_that_is_no_longer_the_censused_process(monkeypatch) -> None:
    class Proc:
        def __init__(self, pid):
            self.pid = pid
            self.set_to = None

        def create_time(self):
            return 999.0                       # a different process now holds the pid

        def cmdline(self):
            return ["python", "something_else.py"]

        def nice(self, v=None):
            self.set_to = v

    import types
    made: list[Proc] = []
    fake = types.SimpleNamespace(Process=lambda pid: made.append(Proc(pid)) or made[-1])
    monkeypatch.setitem(sys.modules, "psutil", fake)
    c = jp.census(_raisable_box(), registered_live=R[AN])
    ch = jp.equalise(c["rows"], c["target"]["rank"], apply=True)
    assert ch and not any(x["applied"] for x in ch)
    assert all("pid reused" in x["error"] for x in ch)
    assert all(p.set_to is None for p in made)


def test_a_judge_above_the_miners_is_brought_down_to_equal() -> None:
    c = jp.census(_box(miner_nice=BN, judge_nice=N, e8_nice=N))
    assert c["verdict"] == "JUDGE_ABOVE_MINERS" and c["target"]["rank"] == R[BN]
    calls: list[tuple[int, int]] = []
    jp.equalise(c["rows"], c["target"]["rank"], apply=True,
                setter=lambda pid, k, row: calls.append((pid, k)))
    assert {k for _, k in calls} == {BN}


def test_today_on_paper_is_already_equal() -> None:
    c = jp.census(_box())
    assert c["verdict"] == "EQUAL"
    assert jp.equalise(c["rows"], c["target"]["rank"], apply=True, setter=lambda *a: 1 / 0) == []


def test_duplicates_count_distinct_parents_not_pool_workers() -> None:
    py = "python.exe"
    extra = [_p(60 + i, 100 + i, py, [py, r"research\scout_swarm.py"], BN) for i in range(3)]
    pool = [_p(70 + i, 20, py, [py, "-c", "from multiprocessing.spawn import spawn_main"], BN)
            for i in range(5)]
    dups = jp.census(_box(extra=[*extra, *pool]))["duplicates"]
    swarm = next(d for d in dups if d["command"].startswith("scout_swarm.py"))
    assert swarm["distinct_parents"] == 4
    assert not [d for d in dups if "spawn_main" in d["command"]]


def test_the_launcher_takes_its_class_from_the_rule_and_falls_back(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rsg, "JUDGE_PRIORITY_DECISION", tmp_path / "jp.json")
    monkeypatch.setattr(jp, "registered_live_rank", lambda *a, **k: R[AN])
    monkeypatch.setattr(jp, "snapshot", lambda *a, **k: _raisable_box())
    assert rsg._judge_flags() == N
    doc = json.loads((tmp_path / "jp.json").read_text("utf-8"))
    assert doc["launcher"]["value"]["target"]["class"] == "NORMAL"
    # with the repository's real registration (E8 at NORMAL) the same box is NOT raised
    monkeypatch.setattr(jp, "registered_live_rank", lambda *a, **k: R[N])
    assert rsg._judge_flags() == BN

    def boom(*a, **k):
        raise RuntimeError("psutil refused")
    monkeypatch.setattr(jp, "snapshot", boom)
    assert rsg._judge_flags() == BN
    src = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    body = src[src.index("def _one_sweep_child"):src.index("def _judge_flags")]
    assert "flags = _judge_flags()" in body and "_record_launch_raise(flags, child.pid)" in body
    assert "ABOVE_NORMAL" not in body and "HIGH_PRIORITY" not in body


def test_a_raise_publishes_a_missed_growth_line_from_launcher_and_child(monkeypatch,
                                                                         tmp_path) -> None:
    import missed_growth as mg
    raises = tmp_path / "JUDGE_PRIORITY_RAISES.json"
    monkeypatch.setattr(jp, "RAISES", raises)
    monkeypatch.setattr(rsg, "JUDGE_PRIORITY_DECISION", tmp_path / "JUDGE_PRIORITY_SWEEP.json")
    # the launcher started the child at NORMAL: its line is written even though the child,
    # born at target, will find nothing to change
    assert rsg._record_launch_raise(N, 4321)["missed_growth_lines"] == 1
    assert rsg._record_launch_raise(BN, 4322)["missed_growth_lines"] == 0   # no raise, no line
    # once per (day, pid, create_time, by)
    assert rsg._record_launch_raise(N, 4321)["missed_growth_lines"] == 0
    # the child raising itself writes its own line
    import os
    me = os.getpid()
    rows = _raisable_box(extra=[_p(me, 1, "python.exe",
                                   ["python", "run_sharded_gauntlet.py", "--once"], BN)])
    monkeypatch.setattr(jp, "registered_live_rank", lambda *a, **k: R[AN])
    monkeypatch.setattr(jp, "snapshot", lambda *a, **k: rows)
    monkeypatch.setattr(jp, "_default_setter", lambda pid, k, row: None)
    out = rsg._equalise_self()
    assert out["changed"] and out["missed_growth_lines"] == 1
    doc = json.loads(raises.read_text("utf-8"))
    assert [x["by"] for x in doc["missed_growth"]] == ["launcher", "sweep_child"]
    assert all(x["rail"] == "judge_priority_raise" and x["verdict"] == "UNMEASURED"
               for x in doc["missed_growth"])
    # carried by the missed-growth organ exactly like the watchdog's lines
    carried = mg.organ_published_lines(raises)
    assert carried["n_lines"] == 2 and carried["verdict"] == mg.UNMEASURED
    src = (DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"judge_priority_raise": organ_published_lines(' in src


def test_the_child_never_erases_the_launchers_record(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rsg, "JUDGE_PRIORITY_DECISION", tmp_path / "jp.json")
    rsg._publish_priority("launcher", {"creationflags": N})
    rsg._publish_priority("child", {"changed": False})
    rsg._publish_priority("backpressure_core", "STARTED")
    doc = json.loads((tmp_path / "jp.json").read_text("utf-8"))
    assert set(doc) == {"launcher", "child", "backpressure_core"}
    assert doc["launcher"]["value"] == {"creationflags": N}


def test_no_miner_spawn_site_or_installer_is_lowered_or_capped() -> None:
    """Rule 2 of the principal's constraints, pinned at the source: the miners' spawn sites keep
    BELOW_NORMAL (unchanged), nothing in this change sets an affinity, and MT5-Gauntlet is never
    raised to AboveNormal by an installer."""
    for f in ("research/department_resident.py", "research/scout_swarm.py",
              "research/moat_swarms.py"):
        assert "BELOW_NORMAL_PRIORITY_CLASS" in (DESK / f).read_text("utf-8")
    jp_src = (DESK / "scripts" / "judge_priority.py").read_text("utf-8")
    assert "cpu_affinity(" not in jp_src
    for ps1 in (DESK / "scripts").glob("*.ps1"):
        text = ps1.read_text("utf-8", errors="replace")
        assert not re.search(r"MT5-Gauntlet.*AboveNormal|AboveNormal.*MT5-Gauntlet", text), ps1


# ------------------------------------------------------------ 2. FrontierAudit: one at a time
FA_INSTALLER = DESK / "scripts" / "install_frontier_audit_task.ps1"
FA_RUNNER = ROOT / "ops" / "run_frontier_audit.cmd"
MANIFEST = DESK / "ops" / "box_tasks.manifest"


def test_frontier_audit_registers_and_enforces_a_single_instance() -> None:
    inst = FA_INSTALLER.read_text("utf-8")
    assert "-MultipleInstances IgnoreNew" in inst
    ens = inst[inst.index("if ($EnsureSingleInstance)"):inst.index("if ($IfMissing -and")]
    assert "$live.Settings.MultipleInstances = 'IgnoreNew'" in ens
    assert "Set-ScheduledTask -InputObject $live" in ens
    # It changes one setting on the LIVE task: never re-registers, never rebuilds the trigger.
    for forbidden in ("Unregister-ScheduledTask", "Register-ScheduledTask",
                      "New-ScheduledTaskTrigger", "New-ScheduledTaskSettingsSet"):
        assert forbidden not in ens


def test_frontier_audit_work_per_day_is_unchanged() -> None:
    row = next(ln for ln in MANIFEST.read_text("utf-8").splitlines()
               if 'name="MT5-FrontierAudit"' in ln)
    assert 'trigger="daily 05:10"' in row                     # once a day, as before
    lines = [ln.strip() for ln in FA_RUNNER.read_text("utf-8").splitlines()
             if ln.strip() and not ln.strip().lower().startswith("rem")]
    body = lines[:lines.index(":run")]
    organs = [ln for ln in body if ln.startswith("call :run ")]
    assert len(organs) == 34                                  # every organ, every day
    # Sequential: nothing in the lane is backgrounded, so one pass is one python at a time.
    assert not [ln for ln in lines if ln.lower().startswith("start ")]


# ------------------------------------------------------- 3. backpressure: stale -> UNMEASURED+alarm
NOW = datetime(2026, 10, 20, 15, 43, tzinfo=UTC)


def _bp(tmp_path: Path, monkeypatch, *, file_at: datetime, swept_at: datetime) -> None:
    p = tmp_path / "bp.json"
    p.write_text(json.dumps({"at": file_at.isoformat(), "capacity": {"measured": {
        "swept_at": swept_at.isoformat(), "n_cells_discovered": 10, "n_judged": 4,
        "workers": 14}}, "windows": {"24h": {"testing": {"per_hour": 3.0}}}}), encoding="utf-8")
    monkeypatch.setattr(jt, "BACKPRESSURE", p)
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "none_bd.json")
    monkeypatch.setattr(jt, "BREACH_DOCKET", tmp_path / "none_breach.json")


def test_a_stale_backpressure_file_reads_unmeasured_and_alarms(tmp_path, monkeypatch) -> None:
    old = datetime(2026, 10, 3, 12, 38, tzinfo=UTC)
    _bp(tmp_path, monkeypatch, file_at=old, swept_at=old)
    q = jt.measure_queue(NOW)
    assert q["status"] == jt.UNMEASURED and q["depth"] == jt.UNMEASURED
    assert q["alarm"]["code"] == "BACKPRESSURE_STALE"
    assert q["alarm"]["severity"] == "ALARM"
    assert q["alarm"]["file_age_seconds"] > 16 * 86400


def test_a_fresh_file_over_an_old_sweep_names_the_judge(tmp_path, monkeypatch) -> None:
    _bp(tmp_path, monkeypatch, file_at=NOW - timedelta(minutes=5),
        swept_at=NOW - timedelta(hours=14))
    q = jt.measure_queue(NOW)
    assert q["status"] == jt.UNMEASURED
    assert q["alarm"]["code"] == "JUDGE_SWEEP_STALE"


def test_a_fresh_backpressure_input_is_measured_and_raises_no_alarm(tmp_path, monkeypatch) -> None:
    _bp(tmp_path, monkeypatch, file_at=NOW - timedelta(minutes=5),
        swept_at=NOW - timedelta(hours=1))
    q = jt.measure_queue(NOW)
    assert q["status"] == "MEASURED" and q["depth"] == 6
    assert "alarm" not in q


def test_the_backpressure_core_republishes_without_the_graph(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "ledger.jsonl"
    rows = [{"at": (NOW - timedelta(hours=h)).isoformat(), "cell": f"c{h}", "passed": False}
            for h in (1, 2, 30)]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    rep = tmp_path / "universal_gates_external.json"
    rep.write_text(json.dumps({"swept_at": (NOW - timedelta(hours=1)).isoformat(),
                               "n_cells_discovered": 9, "n_judged": 2}), encoding="utf-8")
    out = tmp_path / "GAUNTLET_BACKPRESSURE.json"
    old_full = {"at": "2026-10-03T12:44:22+00:00", "windows": {"7d": {"keep": 1},
                "24h": {"intake": {"born_cells": 5}}}, "messages": ["kept"]}
    out.write_text(json.dumps(old_full), encoding="utf-8")
    monkeypatch.setattr(gb, "GATE_LEDGER", ledger)
    monkeypatch.setattr(gb, "GAUNTLET_REPORT", rep)
    monkeypatch.setattr(gb, "GAUNTLET_SOURCE", tmp_path / "absent.py")
    monkeypatch.setattr(gb, "OUT", out)

    def no_graph(*a, **k):
        raise AssertionError("the core must never read the hypothesis graph")
    monkeypatch.setattr(gb, "born_cells", no_graph)
    gb.write_core(now=NOW)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["mode"] == "core" and doc["at"] == NOW.isoformat(timespec="seconds")
    assert doc["full_at"] == "2026-10-03T12:44:22+00:00"       # carried blocks say how old
    assert doc["core"]["testing_24h"]["cells_judged"] == 2   # the 30h-old row is outside
    # ONE VINTAGE PER BLOCK: the full build's windows are carried untouched
    assert doc["windows"] == old_full["windows"] and doc["messages"] == ["kept"]
    assert doc["capacity"]["measured"]["n_judged"] == 2
    # ... and the consumer now reads it as MEASURED
    monkeypatch.setattr(jt, "BACKPRESSURE", out)
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "none_bd.json")
    monkeypatch.setattr(jt, "BREACH_DOCKET", tmp_path / "none_breach.json")
    q = jt.measure_queue(NOW)
    assert q["status"] == "MEASURED" and "alarm" not in q
    assert q["gates_per_hour"] == round(2 / 24.0, 3) and q["gates_per_hour_window"] == "core_24h"
    # no temporary file is left behind, and each writer used its own name
    assert not list(tmp_path.glob("GAUNTLET_BACKPRESSURE.json*.tmp"))


def test_an_absent_ledger_publishes_unmeasured_never_zero(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gb, "GATE_LEDGER", tmp_path / "absent.jsonl")
    monkeypatch.setattr(gb, "GAUNTLET_REPORT", tmp_path / "absent.json")
    monkeypatch.setattr(gb, "GAUNTLET_SOURCE", tmp_path / "absent.py")
    out = tmp_path / "bp.json"
    monkeypatch.setattr(gb, "OUT", out)
    gb.write_core(now=NOW)
    t = json.loads(out.read_text("utf-8"))["core"]["testing_24h"]
    assert t["per_hour"] == "UNMEASURED" and t["ledger"] == "ABSENT"
    monkeypatch.setattr(jt, "BACKPRESSURE", out)
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "none_bd.json")
    monkeypatch.setattr(jt, "BREACH_DOCKET", tmp_path / "none_breach.json")
    assert jt.measure_queue(NOW)["gates_per_hour"] == jt.UNMEASURED


def test_a_core_never_replaces_a_full_build_that_landed_after_its_read(tmp_path,
                                                                       monkeypatch) -> None:
    """The core measures outside the lock, then re-reads the CURRENT file inside it: a full
    build written in between is the base it merges onto, never what it overwrites."""
    out = tmp_path / "bp.json"
    out.write_text(json.dumps({"at": "2026-10-01T00:00:00+00:00", "messages": ["old"]}), "utf-8")
    monkeypatch.setattr(gb, "OUT", out)
    monkeypatch.setattr(gb, "GATE_LEDGER", tmp_path / "absent.jsonl")
    monkeypatch.setattr(gb, "GAUNTLET_REPORT", tmp_path / "absent.json")
    monkeypatch.setattr(gb, "GAUNTLET_SOURCE", tmp_path / "absent.py")
    real = gb._core_testing

    def measured_then_full_lands(at):
        res = real(at)
        gb.write({"at": NOW.isoformat(), "mode": "full", "full_at": NOW.isoformat(),
                  "messages": ["fresh full"]}, out)
        return res
    monkeypatch.setattr(gb, "_core_testing", measured_then_full_lands)
    gb.write_core(now=NOW)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["messages"] == ["fresh full"] and doc["full_at"] == NOW.isoformat()
    assert doc["mode"] == "core"


def test_the_launcher_republishes_one_core_at_a_time(monkeypatch, tmp_path) -> None:
    started: list[list[str]] = []
    alive: set[int] = set()

    class Child:
        def __init__(self, argv, **kw):
            started.append(argv)
            self.pid = 4000 + len(started)
            alive.add(self.pid)

    monkeypatch.setattr(rsg, "BACKPRESSURE_CORE_LOCK", tmp_path / "core.json")
    is_alive = alive.__contains__
    assert rsg._republish_backpressure(popen=Child, alive=is_alive) == "STARTED"
    assert started[0][-1] == "--core" and started[0][-2].endswith("gauntlet_backpressure.py")
    assert rsg._republish_backpressure(popen=Child, alive=is_alive) == \
        "SKIPPED_PREVIOUS_RUNNING"
    alive.clear()                                   # the previous core finished
    assert rsg._republish_backpressure(popen=Child, alive=is_alive) == "STARTED"
    assert len(started) == 2
    # a recycled pid that is not a core never blocks the next one
    assert rsg._core_alive(1) is False
    # the sweep child, not the resident parent, starts it -- so an adopted release takes
    # effect on the next sweep without restarting the launcher
    src = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    once = src[src.index("def _sweep_once() -> int:"):src.index("def _publish_priority")]
    assert "_equalise_self()" in once and "_republish_backpressure()" in once


# ------------------------------------------------------------------ 3b. the cadence apply
BOX = {"is_judging_box": True}


@pytest.fixture
def cadence(tmp_path, monkeypatch):
    monkeypatch.setattr(jt, "CADENCE_STATE", tmp_path / "cadence.json")
    monkeypatch.setattr(jt.sys, "platform", "win32")
    monkeypatch.setattr(jt, "_next_run", lambda task: "10/20/2026 5:51:00 PM")
    monkeypatch.setattr(jt.time if hasattr(jt, "time") else __import__("time"), "sleep",
                        lambda s: None)
    return tmp_path / "cadence.json"


def test_cadence_retries_with_a_longer_timeout_then_records(cadence, monkeypatch) -> None:
    seen: list[float] = []

    def run(argv, **kw):
        seen.append(kw["timeout"])
        if len(seen) == 1:
            raise subprocess.TimeoutExpired(argv, kw["timeout"])
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(jt.subprocess, "run", run)
    res = jt.apply_cadence(1, BOX)
    assert res["status"] == "APPLIED"
    assert seen == list(jt.CADENCE_ATTEMPT_TIMEOUTS_S) and seen[1] > seen[0] > 20.0
    st = json.loads(cadence.read_text("utf-8"))
    assert st["status"] == "APPLIED" and st["minutes"] == 1 and st["applied_at"]


def test_cadence_already_applied_issues_no_scheduler_call(cadence, monkeypatch) -> None:
    cadence.write_text(json.dumps({"status": "APPLIED", "minutes": 1,
                                   "duration": jt.CADENCE_DURATION,
                                   "applied_at": datetime.now(UTC).isoformat()}), "utf-8")

    def run(*a, **k):
        raise AssertionError("no schtasks call when the interval is already in force")
    monkeypatch.setattr(jt.subprocess, "run", run)
    assert jt.apply_cadence(1, BOX)["status"] == "ALREADY_APPLIED"


def test_cadence_failure_writes_the_fallback_and_never_hangs(cadence, monkeypatch) -> None:
    import time

    def run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])
    monkeypatch.setattr(jt.subprocess, "run", run)
    jt._APPLY_DEADLINE[:] = [time.monotonic() + 50.0]
    try:
        res = jt.apply_cadence(1, BOX)
    finally:
        jt._APPLY_DEADLINE[:] = []
    assert res["status"] == "FAILED" and len(res["attempts"]) == 2
    st = json.loads(cadence.read_text("utf-8"))
    assert st["status"] == "FAILED" and st["wanted_minutes"] == 1 and "fallback" in st
    # a spent budget stops the retry instead of waiting on it
    jt._APPLY_DEADLINE[:] = [time.monotonic()]
    try:
        res = jt.apply_cadence(1, BOX)
    finally:
        jt._APPLY_DEADLINE[:] = []
    assert res["status"] == "FAILED" and "budget" in res["why"]


# ------------------------------------------------------------- 4. one BLAS thread per judge proc
def test_blas_single_thread_is_off_unless_the_switch_file_says_exactly_enabled(tmp_path) -> None:
    sw = tmp_path / "JUDGE_BLAS_SINGLE_THREAD.json"
    base = {"PATH": "x", "GAUNTLET_SHARDS": "14"}
    # DEFAULT: absent file -> the env is byte-identical to today
    assert rsg._blas_env(dict(base), sw) == base
    for body in ('{"enabled": false}', '{"enabled": "true"}', '{"enabled": true, "x": 1}',
                 '{"enabled": 1}', '{"enabled": 1.0}', '{"enabled": false, "enabled": true}',
                 '{"enabled": true, "enabled": true}', "[true]", "true", "not json", ""):
        sw.write_text(body, "utf-8")
        assert rsg._blas_env(dict(base), sw) == base, body
    sw.write_text('{"enabled": true}', "utf-8")
    on = rsg._blas_env(dict(base), sw)
    assert on == {**base, **dict.fromkeys(rsg.BLAS_THREAD_VARS, "1")}
    # an operator's own thread count always wins
    assert rsg._blas_env({"OPENBLAS_NUM_THREADS": "6"}, sw)["OPENBLAS_NUM_THREADS"] == "6"
    # the switch file is not shipped: the live default stays off
    assert not rsg.BLAS_SWITCH.exists()


# ------------------------------------------------- 3c. a malformed cadence state never sticks
@pytest.mark.parametrize("minutes", [True, "1", 1.0, None, [1]])
def test_a_malformed_minutes_is_not_fresh(minutes) -> None:
    st = {"status": "APPLIED", "minutes": minutes, "duration": jt.CADENCE_DURATION,
          "applied_at": datetime.now(UTC).isoformat()}
    assert jt._cadence_fresh(st, 1) is False
    assert jt._cadence_fresh({**st, "minutes": 1}, 1) is True


# ------------------------------------- 5. the watchdog and the fair share, in ONE sweep_once
def test_sweep_once_keeps_the_watchdog_and_the_fair_share_together(monkeypatch) -> None:
    import research.judging_throughput as rjt
    events: list[str] = []

    class Dog:
        def start(self):
            events.append("dog.start")
            return self

        def finish(self, rc):
            events.append(f"dog.finish({rc})")
            if fail_finish:
                raise RuntimeError("finish failed")

    monkeypatch.setattr(rsg, "SweepWatchdog", Dog)
    monkeypatch.setattr(rjt, "apply_env", lambda *a, **k: events.append("apply_env"))
    monkeypatch.setattr(rsg, "_equalise_self", lambda: events.append("equalise") or {})
    monkeypatch.setattr(rsg, "_phase", lambda name: events.append(f"phase:{name}"))
    monkeypatch.setattr(rsg, "_publish_priority", lambda k, v: events.append(f"publish:{k}"))
    monkeypatch.setattr(rsg, "_republish_backpressure",
                        lambda: events.append("republish") or "STARTED")
    fail_finish = False
    monkeypatch.setattr(rsg, "_sweep_logged", lambda: events.append("sweep") or 0)
    assert rsg._sweep_once() == 0
    assert events == ["dog.start", "apply_env", "equalise", "publish:child", "phase:plan",
                      "sweep", "dog.finish(0)", "republish", "publish:backpressure_core"]
    # a sweep that raises: the watchdog still records rc=1, the core is still republished
    events.clear()

    def boom():
        raise RuntimeError("judge crashed")
    monkeypatch.setattr(rsg, "_sweep_logged", boom)
    with pytest.raises(RuntimeError, match="judge crashed"):
        rsg._sweep_once()
    assert events[-3:] == ["dog.finish(1)", "republish", "publish:backpressure_core"]
    # a watchdog finish that raises cannot stop the republish
    events.clear()
    fail_finish = True
    monkeypatch.setattr(rsg, "_sweep_logged", lambda: 0)
    with pytest.raises(RuntimeError, match="finish failed"):
        rsg._sweep_once()
    assert events[-2:] == ["republish", "publish:backpressure_core"]


# ------------------------------------------- 6. v3 (audit HOLD of d465792f118): nothing silent
@pytest.mark.parametrize("bad", [{"pid": "abc"}, {"pid": [1]}, {"pid": 7, "started": "x"},
                                 {"pid": True}, {"pid": 1.5}, [1, 2], "x", None])
def test_a_malformed_core_pid_file_never_raises_and_is_overwritten(monkeypatch, tmp_path,
                                                                   bad) -> None:
    lock = tmp_path / "core.json"
    lock.write_text(json.dumps(bad), "utf-8")
    monkeypatch.setattr(rsg, "BACKPRESSURE_CORE_LOCK", lock)

    class Child:
        pid = 4242

        def __init__(self, argv, **kw):
            pass
    # alive(7) would say "running": a malformed file must not reach it at all
    assert rsg._republish_backpressure(popen=Child, alive=lambda pid: True) == "STARTED"
    assert json.loads(lock.read_text("utf-8"))["pid"] == 4242      # rewritten, not wedged


def test_the_republish_returns_failed_instead_of_raising(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rsg, "BACKPRESSURE_CORE_LOCK", tmp_path / "core.json")
    (tmp_path / "core.json").write_text(json.dumps({"pid": 5, "started": 0}), "utf-8")

    def alive(pid):
        raise TypeError("alive blew up")
    got = rsg._republish_backpressure(popen=None, alive=alive)
    assert got.startswith("FAILED: TypeError")


def test_a_raising_republish_never_replaces_the_sweep_rc(monkeypatch) -> None:
    import research.judging_throughput as rjt

    class Dog:
        def start(self):
            return self

        def finish(self, rc):
            pass
    monkeypatch.setattr(rsg, "SweepWatchdog", Dog)
    monkeypatch.setattr(rjt, "apply_env", lambda *a, **k: None)
    monkeypatch.setattr(rsg, "_equalise_self", lambda: {})
    monkeypatch.setattr(rsg, "_phase", lambda name: None)

    def publish(k, v):
        if k == "backpressure_core":
            raise KeyError("publish blew up")
    monkeypatch.setattr(rsg, "_publish_priority", publish)

    def republish():
        raise ValueError("republish blew up")
    for rc in (0, 3):
        monkeypatch.setattr(rsg, "_sweep_logged", lambda rc=rc: rc)
        monkeypatch.setattr(rsg, "_republish_backpressure", republish)
        assert rsg._sweep_once() == rc
        monkeypatch.setattr(rsg, "_republish_backpressure", lambda: "STARTED")
        assert rsg._sweep_once() == rc                    # the publish itself raising too


def _failing_record(*a, **k):
    raise OSError("disk full")


def test_launcher_reverts_a_raise_whose_line_cannot_be_written(monkeypatch, tmp_path) -> None:
    decision = tmp_path / "JUDGE_PRIORITY_SWEEP.json"
    monkeypatch.setattr(rsg, "JUDGE_PRIORITY_DECISION", decision)
    monkeypatch.setattr(jp, "record_raises", _failing_record)
    undone: list[dict] = []
    out = rsg._record_launch_raise(N, 4321, revert=undone.append)
    assert out["line"] == "UNMEASURED" and "disk full" in out["line_error"]
    assert out["reverted"] == [4321] and out["changed"] is False
    assert undone and undone[0]["from"] == "BELOW_NORMAL" and undone[0]["to"] == "NORMAL"
    pub = json.loads(decision.read_text("utf-8"))["launcher_line"]["value"]
    assert pub["line"] == "UNMEASURED" and pub["reverted"] == [4321]

    # neither recorded nor reverted: said, truthfully, as a standing UNMEASURED change
    def cannot(c):
        raise LookupError("pid reused")
    out = rsg._record_launch_raise(N, 4321, revert=cannot)
    assert out["changed"] is True and out["unreverted"] == [4321]
    assert out["missed_growth"][0]["verdict"] == "UNMEASURED"
    assert "could not be reverted" in out["missed_growth"][0]["why"]


def test_child_reverts_its_own_raise_when_the_line_fails(monkeypatch, tmp_path) -> None:
    import os
    me = os.getpid()
    rows = _raisable_box(extra=[_p(me, 1, "python.exe",
                                   ["python", "run_sharded_gauntlet.py", "--once"], BN)])
    monkeypatch.setattr(jp, "registered_live_rank", lambda *a, **k: R[AN])
    monkeypatch.setattr(jp, "snapshot", lambda *a, **k: rows)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(jp, "_default_setter", lambda pid, k, row: calls.append((pid, k)))
    monkeypatch.setattr(jp, "record_raises", _failing_record)
    out = rsg._equalise_self()
    assert calls == [(me, N), (me, BN)]                   # raised, then put back
    assert out["line"] == "UNMEASURED" and out["reverted"] == [me]
    assert out["changed"] is False and out["changes"][0]["reverted"] is True
    # a revert refused (pid reused): changed True, never a silent False
    calls.clear()

    def setter(pid, k, row):
        if k == BN:
            raise LookupError("pid reused")
        calls.append((pid, k))
    monkeypatch.setattr(jp, "_default_setter", setter)
    out = rsg._equalise_self()
    assert calls == [(me, N)] and out["changed"] is True and out["unreverted"] == [me]


def test_record_raises_skips_rather_than_writes_unlocked(monkeypatch, tmp_path) -> None:
    import contextlib

    import libs.research.artifact_chain as ac
    target = tmp_path / "raises.json"

    @contextlib.contextmanager
    def never(path, timeout_s=10.0):
        yield False
    monkeypatch.setattr(ac, "_locked", never)
    ch = [{"pid": 9, "from": "BELOW_NORMAL", "to": "NORMAL", "applied": True,
           "create_time": 1.0}]
    with pytest.raises(jp.LineUnrecorded):
        jp.record_raises(ch, "t", target)
    assert not target.exists()
    got = jp.account(ch, "t", lambda c: None, target)
    assert got["line"] == "UNMEASURED" and got["reverted"] == [9] and not target.exists()


def test_dedup_key_carries_create_time_and_lowerings_write_lines(tmp_path) -> None:
    target = tmp_path / "raises.json"
    up = {"pid": 9, "from": "BELOW_NORMAL", "to": "NORMAL", "applied": True}
    assert jp.record_raises([{**up, "create_time": 1.0}], "t", target) == 1
    assert jp.record_raises([{**up, "create_time": 1.0}], "t", target) == 0
    # the same pid reused by Windows the same day is a SECOND raise, not a hidden one
    assert jp.record_raises([{**up, "create_time": 2.0}], "t", target) == 1
    down = {"pid": 9, "from": "HIGH", "to": "NORMAL", "applied": True, "create_time": 3.0}
    assert jp.record_raises([down], "t", target) == 1
    lines = json.loads(target.read_text("utf-8"))["missed_growth"]
    assert [x["direction"] for x in lines] == ["raise", "raise", "lower"]
    assert lines[-1]["units"].startswith("judge CPU") and lines[-1]["verdict"] == "UNMEASURED"
    # unapplied or unchanged: no line
    assert jp.record_raises([{**down, "applied": False, "create_time": 4.0}], "t", target) == 0
    assert jp.record_raises([{**up, "to": "BELOW_NORMAL", "create_time": 5.0}], "t",
                            target) == 0


@pytest.mark.parametrize("name", [None, "", "  "])
def test_an_unnamed_row_is_unreadable_and_blocks_a_raise(name) -> None:
    rows = _raisable_box(extra=[_p(60, 1, name, None, None)])
    c = jp.census(rows, registered_live=R[HIGH])
    assert c["target"]["unreadable_rows"] >= 1
    assert c["target"]["rank"] == R[BN]


def test_a_full_build_never_overwrites_a_fresher_core(tmp_path, monkeypatch) -> None:
    out = tmp_path / "bp.json"
    full_at = NOW - timedelta(minutes=40)            # the full build measured 40 min ago ...
    core = {"at": NOW.isoformat(), "testing_24h": {"per_hour": 12.0}}
    out.write_text(json.dumps({"at": NOW.isoformat(), "mode": "core",          # ... a core
                               "capacity": {"sweep": 3}, "core": core}), "utf-8")  # since
    gb.write({"at": full_at.isoformat(), "mode": "full", "full_at": full_at.isoformat(),
              "capacity": {"sweep": 2}, "messages": ["full"]}, out)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["messages"] == ["full"] and doc["mode"] == "full"
    assert doc["capacity"] == {"sweep": 3}
    assert doc["core"]["testing_24h"] == {"per_hour": 12.0}
    # a full build newer than the core replaces both
    gb.write({"at": (NOW + timedelta(minutes=1)).isoformat(), "mode": "full",
              "capacity": {"sweep": 4}}, out)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["capacity"] == {"sweep": 4} and "core" not in doc
