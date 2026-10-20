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


def _p(pid, ppid, name, cmd, nice):
    return {"pid": pid, "ppid": ppid, "name": name, "cmdline": cmd, "nice": nice,
            "cpu_cores": 0.5}


def _box(miner_nice=BN, judge_nice=BN, e8_nice=N, extra=()):
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
        _p(41, 1, "terminal64.exe", [r"C:\MT5\terminal64.exe"], BN),
        _p(50, 1, "python.exe", [py, r"scripts\warm_gauntlet_cache.py"], IDLE),
        *extra,
    ]


# ------------------------------------------------------------------ 1. the priority-equality rule
def test_classification_follows_command_line_then_ancestry() -> None:
    cls = {r["pid"]: r["cls"] for r in jp.classify(_box())}
    assert cls[10] == cls[11] == cls[12] == "judge"       # pool child inherits the judge
    assert cls[20] == cls[21] == "miner"
    assert cls[30] == cls[31] == "audit"                  # organ under the audit cmd
    assert cls[40] == cls[41] == "live"
    assert cls[50] == "judge_warm"


@pytest.mark.parametrize("miners", [[R[BN]], [R[N]], [R[BN], R[N]], [R[N], R[AN]],
                                    [R[HIGH]], [R[AN], R[HIGH]]])
@pytest.mark.parametrize("lives", [[], [R[N]], [R[BN]], [R[AN]]])
def test_the_judge_is_never_above_any_miner(miners, lives) -> None:
    t = jp.judge_target(miners, lives)
    assert t["status"] == "MEASURED"
    assert t["rank"] <= min(miners), "the judge may never sit above any miner"
    assert t["rank"] <= jp.JUDGE_CEILING_RANK
    assert t["rank"] >= R[BN], "the rule never pushes the judge below where it already is"
    assert t["above_any_miner"] is False
    if lives and min(lives) > R[BN]:
        assert t["rank"] < min(lives), "a live clock always preempts the judge"


def test_equal_priority_is_the_answer_when_nothing_caps_it() -> None:
    assert jp.judge_target([R[BN], R[BN]])["rank"] == R[BN]
    assert jp.judge_target([R[N], R[N]])["rank"] == R[N]          # raised to EQUAL
    assert jp.judge_target([R[N], R[N]], [R[N]])["rank"] == R[BN]  # E8 at NORMAL keeps its edge
    assert jp.judge_target([R[BN], R[N]])["rank"] == R[BN]        # the LOWEST miner binds


def test_no_miner_or_only_idle_miners_is_unmeasured_and_keeps_the_default() -> None:
    assert jp.judge_target([])["status"] == jp.UNMEASURED
    t = jp.judge_target([R[IDLE]])
    assert t["status"] == jp.UNMEASURED and t["idle_miners"] == 1
    flags, reading = jp.sweep_creationflags([])
    assert flags == BN and reading["target"]["status"] == jp.UNMEASURED


def test_census_verdict_and_equalise_touch_only_the_judge() -> None:
    c = jp.census(_box(miner_nice=N, judge_nice=BN, e8_nice=AN))
    assert c["target"]["rank"] == R[N] and c["verdict"] == "JUDGE_BELOW_MINERS"
    calls: list[tuple[int, int]] = []
    ch = jp.equalise(c["rows"], c["target"]["rank"], apply=True,
                     setter=lambda pid, k: calls.append((pid, k)))
    assert sorted(p for p, _ in calls) == [10, 11, 12]
    assert all(k == N for _, k in calls)
    assert all(x["applied"] for x in ch)
    # dry run: nothing is set
    calls.clear()
    jp.equalise(c["rows"], c["target"]["rank"], apply=False, setter=lambda *a: calls.append(a))
    assert calls == []


def test_a_judge_above_the_miners_is_brought_down_to_equal() -> None:
    c = jp.census(_box(miner_nice=BN, judge_nice=N, e8_nice=N))
    assert c["verdict"] == "JUDGE_ABOVE_MINERS" and c["target"]["rank"] == R[BN]
    calls: list[tuple[int, int]] = []
    jp.equalise(c["rows"], c["target"]["rank"], apply=True,
                setter=lambda pid, k: calls.append((pid, k)))
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
    monkeypatch.setattr(jp, "snapshot", lambda *a, **k: _box(miner_nice=N, e8_nice=AN))
    assert rsg._judge_flags() == N
    doc = json.loads((tmp_path / "jp.json").read_text("utf-8"))
    assert doc["target"]["class"] == "NORMAL"

    def boom(*a, **k):
        raise RuntimeError("psutil refused")
    monkeypatch.setattr(jp, "snapshot", boom)
    assert rsg._judge_flags() == BN
    src = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    body = src[src.index("def _one_sweep_child"):src.index("def _judge_flags")]
    assert "flags = _judge_flags()" in body
    assert "ABOVE_NORMAL" not in body and "HIGH_PRIORITY" not in body


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
    assert doc["windows"]["24h"]["testing"]["cells_judged"] == 2  # the 30h-old row is outside
    assert doc["windows"]["7d"] == {"keep": 1} and doc["messages"] == ["kept"]
    assert doc["capacity"]["measured"]["n_judged"] == 2
    # ... and the consumer now reads it as MEASURED
    monkeypatch.setattr(jt, "BACKPRESSURE", out)
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "none_bd.json")
    monkeypatch.setattr(jt, "BREACH_DOCKET", tmp_path / "none_breach.json")
    q = jt.measure_queue(NOW)
    assert q["status"] == "MEASURED" and "alarm" not in q


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
                 "true", "not json", ""):
        sw.write_text(body, "utf-8")
        assert rsg._blas_env(dict(base), sw) == base, body
    sw.write_text('{"enabled": true}', "utf-8")
    on = rsg._blas_env(dict(base), sw)
    assert on == {**base, **dict.fromkeys(rsg.BLAS_THREAD_VARS, "1")}
    # an operator's own thread count always wins
    assert rsg._blas_env({"OPENBLAS_NUM_THREADS": "6"}, sw)["OPENBLAS_NUM_THREADS"] == "6"
    # the switch file is not shipped: the live default stays off
    assert not rsg.BLAS_SWITCH.exists()
