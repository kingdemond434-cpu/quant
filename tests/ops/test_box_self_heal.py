"""ops/box_self_heal.py: the closed self-heal table acts on its five rules and on nothing else.

Every test drives a fake Box: no process is started, stopped or queried and no task is touched.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from box_self_heal_kit import (  # noqa: F401 -- the shared fakes; unused ones are harmless
    _REAL_SEND_ALERT,
    FAST,
    FP,
    GATE,
    GATE_PY,
    GH_PULLS,
    HEAVY,
    HOST,
    INTAKE,
    INTAKE_CMD,
    MERGE,
    MIN,
    NOW,
    ROOT,
    SVCHOST_PID,
    SYSTEM,
    FakeBox,
    FakePs,
    P,
    _dead_gate,
    _gate_fp,
    _gate_tree,
    _kw,
    bsh,
    fake_psutil,
    intake,
    rows,
    stub_pager,
    svchost,
    two_passes,
)


@pytest.fixture(autouse=True)
def _no_real_pager(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_pager(monkeypatch)


@pytest.fixture
def ps(monkeypatch: pytest.MonkeyPatch) -> FakePs:
    return fake_psutil(monkeypatch)



# ------------------------------------------------------------------------------- the table
def test_the_rule_table_is_closed_and_names_exactly_the_paste() -> None:
    assert [r.key for r in bsh.RULES] == ["independence_intake", "workflow_gate",
                                          "workflow_gate_restart", "memecoin_spot_restart"]
    assert {"MT5-IndependenceIntake", "Quant-WorkflowGate"} == bsh.ENDABLE_TASKS
    assert {"Quant-WorkflowGate", "MemecoinShadowCodex"} == bsh.RUNNABLE_TASKS
    # the paste's two job-lock lines are deferred to job_lock_health (#526), never duplicated
    assert [k for k, _ in bsh.DEFERRED] == ["merge_hypotheses", "pf_allocator"]
    assert "check_job_locks" in dict(bsh.DEFERRED)["merge_hypotheses"]



def test_schtasks_refuses_any_task_or_verb_outside_the_table() -> None:
    for verb, task in (("/End", "MT5-Gateway"), ("/Run", "MT5-IndependenceIntake"),
                       ("/Delete", "Quant-WorkflowGate"), ("/End", "E8-Executor"),
                       ("/Run", "Claude-Bridge-Watchdog")):
        with pytest.raises(ValueError):
            bsh._schtasks(verb, task)


def test_it_is_not_a_command_runner() -> None:
    """No argument chooses what runs, and the only subprocess is the literal schtasks call."""
    src = (ROOT / "ops" / "box_self_heal.py").read_text("utf-8")
    tree = ast.parse(src)
    adds = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "add_argument"]
    assert [a.args[0].value for a in adds] == ["--dry-run"]  # type: ignore[attr-defined]
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "subprocess"]
    assert len(calls) == 1
    fn = next(f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == "_schtasks")
    assert calls[0] in list(ast.walk(fn))
    for banned in ("os.system", "shell=True", "Popen", "eval(", "exec(", "os.environ[",
                   "os.getenv", "urlopen", "requests", "socket.socket", "unlink(", "rmtree"):
        assert banned not in src, banned


# ------------------------------------------------------------------------------- deny tests
@pytest.mark.parametrize("cmd,name", [
    (r'"C:\Program Files\MetaTrader 5\terminal64.exe" /portable', "terminal64.exe"),
    (r"C:\MT5\FTMO\terminal64.exe", "terminal64.exe"),
    (r"python.exe C:\opt\quant\desks\mt5\prop\e8_executor.py --enable-certified-entries",
     "python.exe"),
    (r"python.exe C:\opt\quant\desks\mt5\research\gateway_resident.py", "python.exe"),
    (r"python.exe C:\opt\quant\scripts\run_deadman_switch.py", "python.exe"),
    (r"python.exe C:\opt\quant\desks\mt5\research\allocator_trigger.py", "python.exe"),
    (r"powershell.exe -File C:\opt\quant\ops\bridge\bridge_watchdog.ps1", "powershell.exe"),
    (r"C:\Users\Administrator\.local\bin\claude.exe remote-control", "claude.exe"),
    (r"python.exe C:\opt\quant\desks\mt5\moat\moat_recorder.py", "python.exe"),
    (r"python.exe C:\opt\quant\desks\mt5\research\moat_miner.py", "python.exe"),
    (r"python.exe ftmo_follower.py", "python.exe"),
    (r"python.exe fusion_copy.py", "python.exe"),
])
def test_money_terminal_bridge_and_miners_are_denied(cmd: str, name: str) -> None:
    p = P(1, cmd, name=name)
    assert bsh.denied(p)
    assert bsh.allowlisted(p) is None


def test_denial_beats_an_allowlist_match() -> None:
    """A gateway process that also names independence_intake.py is still never stopped."""
    p = P(7, r"python.exe C:\gateway\desks\mt5\research\independence_intake.py --once")
    assert bsh.matches(bsh.RULE_BY_KEY["independence_intake"], p)
    assert bsh.allowlisted(p) is None


@pytest.mark.parametrize("cmd", [
    "python.exe some_other_script.py",
    r"python.exe C:\opt\quant\desks\mt5\research\breadth_sweep.py",
    "notepad.exe", r"cmd.exe /c merge_hypotheses", "svchost.exe -k netsvcs", FAST, HEAVY, MERGE,
])
def test_a_non_allowlisted_command_line_is_never_stopped(tmp_path: Path, cmd: str) -> None:
    """Every rule fully stalled and past budget, and the process on no rule: nothing happens."""
    victim = P(4242, cmd, name=cmd.split()[0], age_s=10 * 3600, cpu=1.0)
    fb = FakeBox(tmp_path, [victim], running={"MT5-IndependenceIntake": True,
                                              "Quant-WorkflowGate": True}, beat_age_s=2 * 3600)
    two_passes(tmp_path, fb, gap_s=10 * MIN)
    assert 4242 not in fb.killed
    assert fb.killed == []


@pytest.mark.parametrize("cmd", [
    MERGE, HEAVY, r"python.exe C:\opt\quant\desks\mt5\research\local_converter.py",
    r"python.exe C:\opt\quant\desks\mt5\research\edge_search.py",
    r"python.exe C:\opt\quant\desks\mt5\scripts\external_gauntlet.py --sweep",
    r"python.exe -m research.certification_lane",
])
def test_the_deferred_lock_jobs_are_denied_whatever_else_matches(cmd: str) -> None:
    """job_lock_health (#526) owns these; this file must never be a second killer."""
    assert bsh.denied(P(1, cmd))
    gate_child = P(2, cmd, ppid=1)
    assert bsh.allowlisted(gate_child) is None


def test_cpu_progress_vetoes_age(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(), running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb, cpu_after={3100: 400.0})
    assert fb.killed == [] and fb.ended == []
    assert rows(second, "independence_intake")[0]["verdict"] == "PROGRESSING"


def test_child_cpu_counts_as_progress(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [*intake(),
                            P(3101, "python.exe -c from multiprocessing.spawn import spawn_main",
                              ppid=3100, age_s=90 * MIN, cpu=5.0)],
                 running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb, cpu_after={3101: 300.0})
    assert fb.killed == [] and fb.ended == []
    assert rows(second, "independence_intake")[0]["verdict"] == "PROGRESSING"


def test_a_tree_with_a_denied_descendant_is_left_whole(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(5, r"C:\MT5\terminal64.exe", name="terminal64.exe", ppid=8721,
                             age_s=10 * MIN)]
    fb = FakeBox(tmp_path, tree, beat_age_s=2 * 3600)
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []
    assert "descendant" in rows(second, "workflow_gate")[0]["why"]


def test_a_target_under_a_denied_ancestor_is_never_cut_out(tmp_path: Path) -> None:
    """An intake python whose ancestor is the gateway is part of a protected tree: refused."""
    tree = [P(900, r"python.exe C:\opt\quant\desks\mt5\research\gateway_resident.py",
              age_s=9 * 3600),
            *intake(ppid=900)]
    fb = FakeBox(tmp_path, tree, running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == []
    assert any(r.get("ancestor") == 900 for r in second["rows"])


def test_the_real_stop_freezes_the_tree_before_killing_and_thaws_on_refusal(ps: FakePs) -> None:
    """Every member is suspended before any is killed; a denied late child resumes them all."""
    _root, _py, gh, target = _gate_fp(ps)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] and res["frozen_first"] and res["target_gone"]
    first_kill = next(i for i, x in enumerate(ps.log) if x.startswith("kill"))
    assert set(ps.log[:first_kill]) == {"suspend 1", "suspend 2", "suspend 3"}
    assert ps.log[first_kill:] == ["kill 3", "kill 2", "kill 1"], "deepest first, target last"
    ps2 = FakePs()
    sys.modules["psutil"] = ps2  # type: ignore[assignment]
    _root, _py, gh, target = _gate_fp(ps2)
    ps2.add(4, "terminal64.exe", r"C:\MT5\terminal64.exe", parent=gh, age_s=60)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and not any(x.startswith("kill") for x in ps2.log)
    assert ps2.suspended() == set()


def test_dry_run_decides_but_never_acts(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(),
                 running={"MT5-IndependenceIntake": True}, beat_age_s=3 * 3600)
    _, second = two_passes(tmp_path, fb, apply=False)
    assert fb.killed == [] and fb.ended == [] and fb.started == []
    verdicts = {r["verdict"] for r in second["rows"]}
    assert {"WOULD_END", "WOULD_RESTART"} <= verdicts


# ------------------------------------------------------------------------------- task rule
def test_independence_intake_hung_past_its_limit_is_ended(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(),
                 running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    assert fb.ended == ["MT5-IndependenceIntake"]
    assert [r["verdict"] for r in rows(second, "independence_intake")][:2] == ["ATTEMPT",
                                                                                "ENDED"]
    # the process survived /End in the fake table, so its tree is stopped too
    assert fb.killed == [3100]


def test_independence_intake_within_its_limit_is_left_alone(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(age_s=10 * MIN),
                 running={"MT5-IndependenceIntake": True})
    two_passes(tmp_path, fb)
    assert fb.ended == [] and fb.killed == []


def test_a_running_task_with_no_owner_is_ended_only_after_two_passes(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], running={"MT5-IndependenceIntake": True})
    first, _second = two_passes(tmp_path, fb)
    assert rows(first, "independence_intake")[0]["verdict"] == "OBSERVING"
    assert fb.ended == ["MT5-IndependenceIntake"]


# ------------------------------------------------------------------------------- gate rules
def test_a_wedged_gate_run_is_stopped_and_its_task_ended(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True},
                 beat_age_s=2 * 3600)
    _, _second = two_passes(tmp_path, fb)
    assert fb.killed == [8720]
    assert fb.ended == ["Quant-WorkflowGate"]
    assert fb.started == [], "a live run is judged by the wedge rule, not restarted beside"


def test_a_gate_tree_holding_anything_but_gh_git_python_is_refused(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(9000, "notepad.exe x", name="notepad.exe", ppid=8720,
                              age_s=10 * MIN)]
    fb = FakeBox(tmp_path, tree, beat_age_s=2 * 3600)
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []
    assert rows(second, "workflow_gate")[0]["verdict"] == "REFUSED"


def test_an_orphaned_gate_gh_seen_in_the_tree_is_stopped(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), beat_age_s=60)
    kw = {"report": tmp_path / "r.json", "ledger": tmp_path / "l.jsonl",
          "state": tmp_path / "s.json"}
    bsh.run(box=fb.box(), now=NOW, **kw)                 # sees the tree (cpu baselined)
    fb.killed.clear()
    fb.table = [p for p in fb.table if p.pid == 14604]   # the gate and python are gone
    bsh.run(box=fb.box(), now=NOW + 5 * MIN, **kw)       # baselines the orphan
    bsh.run(box=fb.box(), now=NOW + 10 * MIN, **kw)
    assert fb.killed == [14604]


def test_an_unrelated_gh_is_never_an_orphan(tmp_path: Path) -> None:
    """gh run by the bridge or a person was never inside a gate tree: never touched."""
    fb = FakeBox(tmp_path, [P(77, GH_PULLS, name="gh.exe", ppid=3, cpu=0.1)], beat_age_s=60)
    two_passes(tmp_path, fb)
    assert fb.killed == []


def test_a_stale_gate_heartbeat_restarts_with_backoff_and_a_daily_cap(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = {"report": tmp_path / "r.json", "ledger": tmp_path / "l.jsonl",
          "state": tmp_path / "s.json"}
    doc = bsh.run(box=fb.box(), now=base, **kw)
    assert fb.ended == ["Quant-WorkflowGate"] and fb.started == ["Quant-WorkflowGate"]
    assert rows(doc, "workflow_gate_restart")[-1]["verdict"] == "STARTED"
    doc = bsh.run(box=fb.box(), now=base + 10 * MIN, **kw)
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "BACKOFF"
    assert len(fb.started) == 1
    t = base
    for wait in (30 * MIN, 60 * MIN, 120 * MIN):         # backoff doubles: 30, 60, 120 min
        doc = bsh.run(box=fb.box(), now=t + wait - 60, **kw)
        assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "BACKOFF"
        t += wait + 1
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == bsh.MAX_RESTARTS_PER_DAY == 4
    doc = bsh.run(box=fb.box(), now=t + 8 * 3600, **kw)  # same UTC day, long after any backoff
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"
    assert len(fb.started) == 4
    doc = bsh.run(box=fb.box(), now=base + 24 * 3600, **kw)   # a new UTC day
    assert len(fb.started) == 5
    assert rows(doc, "workflow_gate_restart")[-1]["verdict"] == "STARTED"


def test_a_fresh_gate_heartbeat_is_left_alone_and_an_absent_one_is_refused(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], beat_age_s=5 * MIN)
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "FRESH"
    fb.beat.unlink()
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"
    assert fb.started == []


def test_a_fresh_beat_from_runs_refused_by_a_held_mutex_is_still_a_dead_sweep(
        tmp_path: Path) -> None:
    """rc 4 + mutex_held_runs keeps the beat fresh while nothing merges; with no gate run alive
    (the holder died) that is a dead sweep, and with a live holder the wedge rule judges it."""
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(NOW - 60, tz=UTC).isoformat(),
                                   "rc": 4, "mutex_held_runs": 5}), "utf-8")
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert fb.started == ["Quant-WorkflowGate"]
    assert rows(doc, "workflow_gate_restart")[-1]["verdict"] == "STARTED"
    (tmp_path / "b").mkdir()
    fb2 = FakeBox(tmp_path / "b", _gate_tree(age_s=10 * MIN), beat_age_s=None)
    fb2.beat.write_text(json.dumps({"at": datetime.fromtimestamp(NOW - 60, tz=UTC).isoformat(),
                                    "rc": 4, "mutex_held_runs": 5}), "utf-8")
    doc = bsh.run(box=fb2.box(), now=NOW, report=tmp_path / "r2.json",
                  ledger=tmp_path / "l2.jsonl", state=tmp_path / "s2.json")
    assert fb2.started == []
    held = rows(doc, "workflow_gate_restart")[0]
    assert held["verdict"] == "RUN_IN_PROGRESS" and held["mutex_held_runs"] == 5


def test_it_pages_when_it_acts_and_once_a_day_when_it_gives_up(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    sent: list[tuple[str, str]] = []
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = {"report": tmp_path / "r.json", "ledger": tmp_path / "l.jsonl",
          "state": tmp_path / "s.json", "alert": lambda t, b: sent.append((t, b))}
    bsh.run(box=fb.box(), now=base, **kw)
    assert len(sent) == 1 and "STARTED" in sent[0][1]
    bsh.run(box=fb.box(), now=base + 60, **kw)                 # BACKOFF: RED, no page
    assert len(sent) == 1
    t = base
    for wait in (30 * MIN, 60 * MIN, 120 * MIN):
        t += wait + 1
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(sent) == 4
    bsh.run(box=fb.box(), now=t + 3600, **kw)                  # the cap: one give-up page
    assert len(sent) == 5 and "attempts already today" in sent[-1][1]
    bsh.run(box=fb.box(), now=t + 7200, **kw)                  # ...and not again today
    assert len(sent) == 5
    bsh.run(apply=False, box=fb.box(), now=base + 24 * 3600, **kw)   # a dry run never pages
    assert len(sent) == 5


def test_a_failing_pager_never_loses_the_pass(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], beat_age_s=6 * 3600)

    def boom(t: str, b: str) -> None:
        raise OSError("ntfy down")

    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json", alert=boom)
    assert fb.started == ["Quant-WorkflowGate"] and "ntfy down" in doc["paged"]["error"]
    assert json.loads((tmp_path / "r.json").read_text())["paged"]["error"]


# ------------------------------------------------------------------------------- the report
def test_a_quiet_pass_is_ok_and_the_report_carries_the_table(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], beat_age_s=60)
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert doc["status"] == "OK" and doc["n_red"] == 0
    on_disk = json.loads((tmp_path / "r.json").read_text())
    assert on_disk["schema"] == "box_self_heal/1"
    assert [r["key"] for r in on_disk["rules"]] == [r.key for r in bsh.RULES]
    assert not (tmp_path / "l.jsonl").exists(), "the ledger holds RED rows only"


def test_an_unreadable_process_table_is_red_and_acts_on_nothing(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [])
    box = fb.box()
    box.procs = lambda: None
    doc = bsh.run(box=box, now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert doc["status"] == "RED" and fb.killed == [] and fb.ended == []


def test_the_watchdog_never_stops_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    me = intake(31337, cpu=1.0)
    monkeypatch.setattr(bsh.os, "getpid", lambda: 31337)
    fb = FakeBox(tmp_path, me, running={"MT5-IndependenceIntake": True})
    two_passes(tmp_path, fb)
    assert 31337 not in fb.killed


# ------------------------------------------------------------------------------- wiring
def test_desk_health_and_the_organ_contract_read_the_report() -> None:
    contract = (ROOT / "ops" / "organ_contract.py").read_text("utf-8")
    assert '"Quant-BoxSelfHeal"' in contract and "BOX_SELF_HEAL.json" in contract
    health = (ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py").read_text("utf-8")
    assert "def check_box_self_heal" in health and "check_box_self_heal()" in health


def test_the_installer_registers_system_every_five_minutes_and_trusts_the_gate_repo() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "'Quant-BoxSelfHeal'" in code
    assert '-UserId "SYSTEM"' in code and "-RunLevel Highest" in code
    assert "New-TimeSpan -Minutes 5" in code and "IgnoreNew" in code
    assert "ops\\box_self_heal.py" in code
    assert "safe.directory" in code and "C:/ProgramData/QuantBox/gate-repo" in code
    assert "--system" in code and "--global" not in code
    assert "IfMissing" in code


def _desk_health() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_box_self_heal_desk_health", ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("age_min,status,expect", [
    (3, "OK", "OK"), (45, "OK", "PROBLEM"), (3, "RED", "PROBLEM"), (None, "OK", "PROBLEM"),
])
def test_desk_health_is_red_when_the_watchdog_is_stale_absent_or_acted(
        tmp_path: Path, age_min: float | None, status: str, expect: str) -> None:
    dh = _desk_health()
    dh._FINDINGS.clear()
    path = tmp_path / "BOX_SELF_HEAL.json"
    now = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)
    if age_min is not None:
        at = datetime.fromtimestamp(now.timestamp() - age_min * 60, tz=UTC).isoformat()
        path.write_text(json.dumps({"at": at, "status": status, "rows": [
            {"level": "RED", "rule": "merge_hypotheses", "verdict": "STOPPED", "why": "x"}]
            if status == "RED" else []}), "utf-8")
    dh.check_box_self_heal(path, now)
    levels = {f["level"] for f in dh._FINDINGS}
    assert (expect in levels) and (expect != "OK" or "PROBLEM" not in levels)


# =============================================================================================
# REGRESSIONS FOR THE AUDIT HOLD OF 7a01c1b09. Each failed against that head.
# =============================================================================================
# --- MUST-FIX 1: the thaw is unconditional, and the freeze window is short ------------------
@pytest.mark.parametrize("who,method,exc", [
    ("gh", "suspend", OSError(299, "Only part of a ReadProcessMemory request was completed")),
    ("gh", "cmdline", RuntimeError("cmdline() read a half-built PEB")),
    ("gh", "name", RuntimeError("name() failed")),
    ("py", "children", OSError(299, "WinError 299")),
    ("gh", "kill", OSError(5, "kill refused")),
    ("gh", "create_time", ValueError("odd")),
])
def test_any_exception_mid_stop_resumes_every_process_it_froze(
        ps: FakePs, who: str, method: str, exc: BaseException) -> None:
    _root, _py, _gh, target = _gate_fp(ps, **{who: {method: exc}})
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] is False and res["target_gone"] is False
    assert ps.suspended() == set(), f"left suspended: {ps.suspended()} ({ps.log})"
    assert 1 not in ps.dead, "the target is never killed after a failure"


def test_a_freeze_that_overruns_its_window_resumes_and_stops_nothing(ps: FakePs) -> None:
    _gate_fp(ps)
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    ticks = iter([0.0, 0.0, bsh.FREEZE_MAX_S + 1, bsh.FREEZE_MAX_S + 2, 99.0, 99.0])
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES, None, clock=lambda: next(ticks))
    assert not res["ok"] and "freeze took over" in res["why"]
    assert ps.suspended() == set() and not ps.dead


def test_the_task_limit_is_far_above_a_passes_worst_case() -> None:
    """A SYSTEM task killed at its limit mid-freeze leaves the tree suspended, so the limit is at
    least twice the worst case: five schtasks calls, two 10 s waits, one page."""
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    m = __import__("re").search(r"-ExecutionTimeLimit \(New-TimeSpan -Minutes (\d+)\)", src)
    assert m, "the installer names its ExecutionTimeLimit in minutes"
    worst = 5 * bsh.SCHTASKS_TIMEOUT_S + 2 * 10 + 60
    assert int(m.group(1)) * 60 >= 2 * worst
    assert int(m.group(1)) * 60 < bsh.STALE_AFTER_S, "a hung pass still reads stale"
    assert bsh.FREEZE_MAX_S <= 10


# --- MUST-FIX 2: a recycled ppid never pulls a stranger into a tree ---------------------------
SUPERVISOR = r"python.exe C:\opt\quant\desks\mt5\research\research_supervisor.py --resident"


def test_descendants_and_ancestors_require_a_child_to_be_younger_than_its_parent() -> None:
    gate = P(8720, GATE, name="powershell.exe", age_s=10 * MIN)
    stranger = P(8800, SUPERVISOR, ppid=8720, age_s=9 * 3600)        # its real parent died
    kid = P(8721, GATE_PY, ppid=8720, age_s=9 * MIN)
    grandkid_of_stranger = P(8801, GH_PULLS, name="gh.exe", ppid=8800, age_s=MIN)
    table = [gate, stranger, kid, grandkid_of_stranger]
    assert {p.pid for p in bsh.descendants(8720, table)} == {8721}
    assert bsh.ancestors(8800, table) == set(), "a NEWER process is never an ancestor"
    assert bsh.ancestors(8721, table) == {8720}


def test_a_stranger_with_a_recycled_gate_ppid_is_never_stopped_as_an_orphan(
        tmp_path: Path) -> None:
    """research_supervisor was STOPPED: its stale ppid named a later gate run, so the gate tree
    took it in, and when that run ended it read as the gate's orphan."""
    fb = FakeBox(tmp_path, [P(8720, GATE, name="powershell.exe", age_s=10 * MIN, cpu=4.0),
                            P(8800, SUPERVISOR, ppid=8720, age_s=9 * 3600, cpu=1.0)],
                 beat_age_s=60)
    kw = _kw(tmp_path)
    bsh.run(box=fb.box(), now=NOW, **kw)
    fb.table = [p for p in fb.table if p.pid == 8800]                # the gate run ended
    for k in range(1, 4):
        bsh.run(box=fb.box(), now=NOW + k * 5 * MIN, **kw)
    assert fb.killed == []
    assert "8800" not in json.dumps(json.loads((tmp_path / "s.json").read_text())["gate_tree"])


def test_a_live_child_older_than_the_target_is_neither_frozen_nor_killed(ps: FakePs) -> None:
    root, _py, _gh, target = _gate_fp(ps)
    old = ps.add(9, "python.exe", SUPERVISOR, parent=root, age_s=9 * 3600)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"]
    assert old.pid not in ps.dead and f"suspend {old.pid}" not in ps.log


# --- MUST-FIX 3: what cannot be read is never touched; the target is re-read live -------------
@pytest.mark.parametrize("name,cmd", [("python.exe", ""), ("", INTAKE), ("gh.exe", "   ")])
def test_an_unreadable_command_line_or_image_is_denied(name: str, cmd: str) -> None:
    assert bsh.denied(P(1, cmd, name=name))
    assert bsh.allowlisted(P(1, cmd, name=name)) is None


def test_a_gate_tree_with_an_unreadable_descendant_is_left_whole(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(14605, "", name="gh.exe", ppid=8721, age_s=MIN)]
    fb = FakeBox(tmp_path, tree, beat_age_s=2 * 3600)
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []
    assert "unidentifiable" in rows(second, "workflow_gate")[0]["why"]


def test_a_target_under_an_unreadable_ancestor_is_refused(tmp_path: Path) -> None:
    tree = [P(900, "", name="python.exe", age_s=9 * 3600), *_gate_tree()]
    tree[1] = P(8720, GATE, name="powershell.exe", ppid=900, age_s=2 * 3600, cpu=4.0)
    fb = FakeBox(tmp_path, tree, beat_age_s=2 * 3600)
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == []
    assert any(r.get("ancestor") == 900 for r in second["rows"])


def test_the_target_is_re_read_live_before_anything_is_frozen(ps: FakePs) -> None:
    """The table said gate; the live process now reads as something denied: refused untouched."""
    ps.add(1, "powershell.exe", r"powershell.exe -File C:\opt\quant\ops\bridge\bridge_watchdog.ps1")
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and ps.log == []


def test_an_unreadable_live_target_is_refused(ps: FakePs) -> None:
    ps.add(1, "powershell.exe", GATE, fail={"cmdline": ps.AccessDenied(1)})
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and ps.log == []


def test_the_live_target_must_still_match_its_rule(ps: FakePs) -> None:
    ps.add(1, "powershell.exe", r"powershell.exe -File C:\Users\x\other.ps1")
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    rule = bsh.RULE_BY_KEY["workflow_gate"]
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES,
                         lambda q: None if bsh.matches(rule, q) else "not the gate")
    assert not res["ok"] and "not the gate" in res["why"] and ps.log == []


# --- MUST-FIX 4: the intake is its exact script argument with --once, under its task --------
@pytest.mark.parametrize("cmd", [
    r"python.exe -m pytest desks\mt5\tests\test_independence_intake.py -q",
    r"python.exe -m pytest -k independence_intake.py --once",
    r"python.exe C:\opt\quant\scripts\check.py desks\mt5\research\independence_intake.py --once",
    r"python.exe C:\opt\quant\desks\mt5\research\independence_intake.py --budget-s 600",
    r"python.exe C:\opt\quant\desks\mt5\research\independence_intake.py.bak --once",
    r"python.exe C:\opt\quant\desks\mt5\research\old_independence_intake.py --once",
    r"python.exe -c import independence_intake.py --once",
])
def test_only_the_intake_script_itself_with_once_matches(cmd: str) -> None:
    assert not bsh.matches(bsh.RULE_BY_KEY["independence_intake"], P(1, cmd))


def test_the_installed_intake_command_line_matches() -> None:
    rule = bsh.RULE_BY_KEY["independence_intake"]
    assert bsh.matches(rule, P(1, INTAKE))
    assert bsh.matches(rule, P(1, r"py.exe -I -u desks/mt5/research/independence_intake.py --once"))
    argv = ("C:\\Program Files\\Python314\\python.exe", "-W", "ignore",
            "C:\\opt\\quant\\desks\\mt5\\research\\independence_intake.py", "--once")
    assert bsh.matches(rule, bsh.Proc(1, 0, "python.exe", " ".join(argv), 0.0, 0.0, argv))


def test_a_pytest_run_naming_the_intake_is_never_stopped(tmp_path: Path) -> None:
    py = P(3100, r"python.exe -m pytest desks\mt5\tests\test_independence_intake.py "
                 r"desks\mt5\research\independence_intake.py --once", age_s=96 * MIN, cpu=3.0)
    fb = FakeBox(tmp_path, [py], running={"MT5-IndependenceIntake": True})
    two_passes(tmp_path, fb)
    assert fb.killed == []


def test_an_intake_not_under_its_tasks_cmd_is_never_stopped(tmp_path: Path) -> None:
    """A hand run (an operator's powershell, an agent's shell) is not the task's run."""
    fb = FakeBox(tmp_path, [P(3099, "powershell.exe -NoExit", name="powershell.exe",
                              age_s=2 * 3600),
                            P(3100, INTAKE, ppid=3099, age_s=96 * MIN, cpu=3.0)],
                 running={"MT5-IndependenceIntake": True})
    two_passes(tmp_path, fb)
    assert fb.killed == []


# --- MUST-FIX 5: the gate is exactly -File C:\ProgramData\QuantBox\bin\workflow_gate.ps1 ------
@pytest.mark.parametrize("cmd,want", [
    (GATE, True),
    (r'pwsh.exe -NoProfile -file "c:\programdata\QUANTBOX\bin\workflow_gate.ps1"', True),
    (r"powershell.exe -File C:/ProgramData/QuantBox/bin/./workflow_gate.ps1", True),
    (r"powershell.exe -File C:\Users\Administrator\workflow_gate.ps1", False),
    (r"powershell.exe -File C:\ProgramData\QuantBox\bin\workflow_gate.ps1.bak", False),
    (r'powershell.exe -Command "& C:\ProgramData\QuantBox\bin\workflow_gate.ps1"', False),
    (r"powershell.exe Get-Content C:\ProgramData\QuantBox\bin\workflow_gate.ps1", False),
    (r"powershell.exe -File C:\opt\quant\ops\box\workflow_gate.ps1", False),
    (r"powershell.exe -File", False),
])
def test_the_gate_identity_is_the_exact_file_argument(cmd: str, want: bool) -> None:
    assert bsh.matches(bsh.RULE_BY_KEY["workflow_gate"], P(1, cmd, name="powershell.exe")) is want


# --- MUST-FIX 6: every attempt counts, failed or not; a repeated failure pages once a day ----
def test_a_failed_start_is_an_attempt_under_the_backoff_and_the_cap(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    calls: list[float] = []
    box = fb.box()
    box.run_task = lambda t: (calls.append(1), {"rc": 1, "out": "access denied"})[1]
    sent: list[str] = []
    kw = _kw(tmp_path, alert=lambda t, b: sent.append(b))
    for k in range(0, 24 * 12 - 6):                       # every 5 minutes, the whole UTC day
        bsh.run(box=box, now=base + k * 5 * MIN, **kw)
    assert len(calls) == bsh.MAX_RESTARTS_PER_DAY == 4
    assert sum("START_FAILED" in b for b in sent) == 1, "a repeated failure pages once a day"
    assert sum("attempts already today" in b for b in sent) == 1


def test_a_failed_stop_is_an_attempt_and_is_not_retried_every_pass(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True}, beat_age_s=60)
    box = fb.box()
    tries: list[int] = []
    box.kill = lambda p, t, a=None, v=None: (tries.append(p.pid),
                                             {"ok": False, "target_gone": False})[1]
    kw = _kw(tmp_path)
    for k in range(8):                                    # 40 minutes of passes
        bsh.run(box=box, now=NOW + k * 5 * MIN, **kw)
    assert tries == [8720, 8720], "once, then again only after the 30 min backoff"
    assert fb.ended == [], "the gate task is never /Ended while its run is alive"


def test_a_failed_end_is_an_attempt(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], running={"MT5-IndependenceIntake": True})
    box = fb.box()
    ends: list[str] = []
    box.end_task = lambda t: (ends.append(t), {"rc": 1})[1]
    kw = _kw(tmp_path)
    for k in range(6):
        bsh.run(box=box, now=NOW + k * 5 * MIN, **kw)
    assert ends == ["MT5-IndependenceIntake"]


# --- MUST-FIX 7: the attempt is durable before the action; a lost history fails closed --------
def test_the_attempt_is_on_disk_before_the_run(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    box = fb.box()
    seen: dict[str, Any] = {}

    def run_task(t: str) -> dict[str, Any]:
        seen["state"] = json.loads((tmp_path / "s.json").read_text())
        seen["ledger"] = (tmp_path / "l.jsonl").read_text()
        return {"rc": 0}

    box.run_task = run_task
    bsh.run(box=box, now=base, **_kw(tmp_path))
    assert seen["state"]["attempts"]["workflow_gate_restart"] == [base]
    assert '"ATTEMPT"' in seen["ledger"]


def test_a_corrupt_state_rebuilds_the_attempts_from_the_ledger(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    kw = _kw(tmp_path)
    t = base
    for wait in (0, 30 * MIN + 1, 60 * MIN + 1, 120 * MIN + 1):
        t += wait
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == 4
    (tmp_path / "s.json").write_text("{torn", "utf-8")
    doc = bsh.run(box=fb.box(), now=t + 6 * 3600, **kw)
    assert len(fb.started) == 4, "the cap survives a corrupt state"
    assert doc["attempt_history"] == "ledger"
    (tmp_path / "s.json").write_text("[]", "utf-8")            # valid JSON, not a state
    bsh.run(box=fb.box(), now=t + 7 * 3600, **kw)
    assert len(fb.started) == 4


def test_an_absent_state_also_rebuilds_from_the_ledger(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    kw = _kw(tmp_path)
    bsh.run(box=fb.box(), now=base, **kw)
    (tmp_path / "s.json").replace(tmp_path / "gone.json")
    bsh.run(box=fb.box(), now=base + 10 * MIN, **kw)
    assert len(fb.started) == 1, "the backoff survives a deleted state"


def test_an_unreadable_state_and_ledger_act_on_nothing_and_page_once(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True},
                 beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    (tmp_path / "s.json").write_text("{torn", "utf-8")
    (tmp_path / "l.jsonl").mkdir()                    # exists, and cannot be read as a file
    sent: list[str] = []
    kw = _kw(tmp_path, alert=lambda t, b: sent.append(b))
    docs = [bsh.run(box=fb.box(), now=base + k * 5 * MIN, **kw) for k in range(6)]
    assert fb.killed == [] and fb.ended == [] and fb.started == []
    assert len(sent) == 1 and "unreadable" in sent[0]
    assert all(d["attempt_history"] == "UNREADABLE" for d in docs)


# --- v4 should-fix 4: an UNREADABLE marker is not sticky once the ledger reads again ---------
def test_a_readable_ledger_clears_a_previous_unreadable_marker(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    (tmp_path / "l.jsonl").mkdir()
    first = bsh.run(box=fb.box(), now=base, **_kw(tmp_path))
    assert first["attempt_history"] == "UNREADABLE" and fb.started == []
    assert json.loads((tmp_path / "s.json").read_text("utf-8"))["history"] == "UNREADABLE"
    (tmp_path / "l.jsonl").rmdir()                    # the ledger is readable again (empty)
    later = bsh.run(box=fb.box(), now=base + 5 * MIN, **_kw(tmp_path))
    assert later["attempt_history"] == "ledger(cleared_unreadable)"
    assert fb.started == ["Quant-WorkflowGate"], "a readable ledger is the history again"
    assert json.loads((tmp_path / "s.json").read_text("utf-8"))["history"] == "known"


def test_a_cleared_marker_still_counts_the_attempts_the_ledger_proves(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    (tmp_path / "s.json").write_text(json.dumps({"history": "UNREADABLE"}), "utf-8")
    (tmp_path / "l.jsonl").write_text("".join(
        json.dumps({"rule": "workflow_gate_restart", "verdict": "ATTEMPT", "attempt": True,
                    "ts": base - k * 60}) + "\n" for k in range(1, 5)), "utf-8")
    doc = bsh.run(box=fb.box(), now=base, **_kw(tmp_path))
    assert doc["attempt_history"] == "ledger(cleared_unreadable)"
    assert fb.started == [], "four ledgered attempts today: the cap holds"


def test_an_attempt_that_cannot_be_recorded_is_not_made(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)

    def no(*a: Any, **k: Any) -> None:
        raise OSError(28, "No space left on device")

    real_write = bsh._write_json
    monkeypatch.setattr(bsh, "_append_ledger", no)
    monkeypatch.setattr(bsh, "_write_json",
                        lambda path, doc: no() if path.name == "s.json" else real_write(path, doc))
    doc = bsh.run(box=fb.box(), now=base, **_kw(tmp_path))
    assert fb.started == [] and fb.ended == []
    assert any("could not be recorded" in r["why"] for r in doc["rows"])
