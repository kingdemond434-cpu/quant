"""ops/box_self_heal.py: the closed self-heal table acts on its five rules and on nothing else.

Every test drives a fake Box: no process is started, stopped or queried and no task is touched.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import socket
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_bsh() -> Any:
    """By path: `desks/mt5/ops` is a regular package that shadows the repo's `ops` in the suite."""
    name = "_quant_ops_box_self_heal"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / "box_self_heal.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bsh = _load_bsh()
NOW = datetime(2026, 10, 29, 18, 0, tzinfo=UTC).timestamp()
HOST = socket.gethostname()
MIN = 60.0


def P(pid: int, cmd: str, *, name: str = "python.exe", ppid: int = 1, age_s: float = 3 * 3600,
      cpu: float = 10.0) -> bsh.Proc:
    return bsh.Proc(pid, ppid, name, cmd, NOW - age_s, cpu)


MERGE = (r'"C:\Program Files\Python314\python.exe" '
         r"C:\opt\quant\desks\mt5\research\merge_hypotheses.py")
HEAVY = r"python.exe -W ignore C:\opt\quant\desks\mt5\research\pf_allocator.py --mode heavy"
FAST = r"python.exe -W ignore C:\opt\quant\desks\mt5\research\pf_allocator.py --mode fast"
INTAKE = (r'"C:\Program Files\Python314\python.exe" -W ignore '
          r"C:\opt\quant\desks\mt5\research\independence_intake.py --once --budget-s 600")
GATE = (r"powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass "
        r'-File "C:\ProgramData\QuantBox\bin\workflow_gate.ps1"')
GATE_PY = (r"python.exe -I -u C:\ProgramData\QuantBox\gate-repo\.github\scripts\audit_gate.py "
           r"--repo kingdemond434-cpu/quant --base claude/llm-auto-upgrade-verify-gcjac3 "
           r"--sweep --box")
GH_PULLS = r"gh.exe api repos/kingdemond434-cpu/quant/pulls?state=open&per_page=100"


class FakeBox:
    def __init__(self, tmp: Path, procs: list[bsh.Proc], *, running: dict[str, bool] | None = None,
                 beat_age_s: float | None = 60.0) -> None:
        self.table = procs
        self.running = running or {}
        self.killed: list[int] = []
        self.ended: list[str] = []
        self.started: list[str] = []
        self.beat = tmp / "workflow_gate.json"
        if beat_age_s is not None:
            self.beat.write_text(json.dumps({"at": datetime.fromtimestamp(
                NOW - beat_age_s, tz=UTC).isoformat(), "rc": 0}), "utf-8")

    def box(self) -> bsh.Box:
        def kill(p: bsh.Proc, procs: Sequence[bsh.Proc],
                 allowed: frozenset[str] | None = None) -> dict[str, Any]:
            self.killed.append(p.pid)
            return {"ok": True, "killed": [p.pid]}

        def end(t: str) -> dict[str, Any]:
            self.ended.append(t)
            return {"rc": 0}

        def run(t: str) -> dict[str, Any]:
            self.started.append(t)
            return {"rc": 0}

        return bsh.Box(procs=lambda: list(self.table),
                       task_running=lambda t: self.running.get(t, False),
                       end_task=end, run_task=run, kill=kill, host=HOST,
                       gate_beat=self.beat, windows=True)


def two_passes(tmp: Path, fb: FakeBox, *, cpu_after: dict[int, float] | None = None,
               apply: bool = True, gap_s: float = 5 * MIN) -> tuple[dict, dict]:
    """Pass 1 baselines CPU; pass 2 (gap_s later) judges progress. Returns both reports."""
    kw = {"report": tmp / "r.json", "ledger": tmp / "l.jsonl", "state": tmp / "s.json"}
    first = bsh.run(apply=apply, box=fb.box(), now=NOW, **kw)
    if cpu_after:
        fb.table = [bsh.Proc(p.pid, p.ppid, p.name, p.cmdline, p.create_time,
                             cpu_after.get(p.pid, p.cpu_s)) for p in fb.table]
    second = bsh.run(apply=apply, box=fb.box(), now=NOW + gap_s, **kw)
    return first, second


def rows(doc: dict, rule: str) -> list[dict]:
    return [r for r in doc["rows"] if r["rule"] == rule]


# ------------------------------------------------------------------------------- the table
def test_the_rule_table_is_closed_and_names_exactly_the_paste() -> None:
    assert [r.key for r in bsh.RULES] == ["independence_intake", "workflow_gate",
                                          "workflow_gate_restart"]
    assert {"MT5-IndependenceIntake", "Quant-WorkflowGate"} == bsh.ENDABLE_TASKS
    assert {"Quant-WorkflowGate"} == bsh.RUNNABLE_TASKS
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
    p = P(7, r"python.exe C:\opt\quant\desks\mt5\research\gateway.py independence_intake.py")
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
    fb = FakeBox(tmp_path, [P(3100, INTAKE, age_s=96 * MIN, cpu=3.0)],
                 running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb, cpu_after={3100: 400.0})
    assert fb.killed == [] and fb.ended == []
    assert rows(second, "independence_intake")[0]["verdict"] == "PROGRESSING"


def test_child_cpu_counts_as_progress(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [P(3100, INTAKE, age_s=96 * MIN, cpu=3.0),
                            P(3101, "python.exe -c from multiprocessing.spawn import spawn_main",
                              ppid=3100, cpu=5.0)],
                 running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb, cpu_after={3101: 300.0})
    assert fb.killed == [] and fb.ended == []
    assert rows(second, "independence_intake")[0]["verdict"] == "PROGRESSING"


def test_a_tree_with_a_denied_descendant_is_left_whole(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(5, r"C:\MT5\terminal64.exe", name="terminal64.exe", ppid=8721)]
    fb = FakeBox(tmp_path, tree, beat_age_s=2 * 3600)
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []
    assert "descendant" in rows(second, "workflow_gate")[0]["why"]


def test_a_target_under_a_denied_ancestor_is_never_cut_out(tmp_path: Path) -> None:
    """An intake python whose ancestor is the gateway is part of a protected tree: refused."""
    tree = [P(900, r"python.exe C:\opt\quant\desks\mt5\research\gateway_resident.py",
              age_s=9 * 3600),
            P(3100, INTAKE, ppid=900, age_s=96 * MIN, cpu=3.0)]
    fb = FakeBox(tmp_path, tree, running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    assert fb.killed == []
    assert any(r.get("ancestor") == 900 for r in second["rows"])


def test_the_real_stop_freezes_the_tree_before_killing_and_thaws_on_refusal(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Every member is suspended before any is killed; a denied late child resumes them all."""
    log: list[str] = []

    class FP:
        def __init__(self, pid: int, name: str, cmd: str, kids: list[FP] | None = None) -> None:
            self.pid, self._name, self._cmd, self.kids = pid, name, cmd, kids or []

        def create_time(self) -> float:
            return NOW - 3600

        def children(self, recursive: bool = False) -> list[FP]:
            out: list[FP] = []
            for k in self.kids:
                out += [k, *k.children(recursive=True)]
            return out

        def name(self) -> str:
            return self._name

        def cmdline(self) -> list[str]:
            return self._cmd.split()

        def suspend(self) -> None:
            log.append(f"suspend {self.pid}")

        def resume(self) -> None:
            log.append(f"resume {self.pid}")

        def kill(self) -> None:
            log.append(f"kill {self.pid}")

    import types
    gh = FP(3, "gh.exe", GH_PULLS)
    py = FP(2, "python.exe", GATE_PY, [gh])
    root = FP(1, "powershell.exe", GATE, [py])
    table = {1: root, 2: py, 3: gh}
    fake = types.SimpleNamespace(
        Process=lambda pid: table[pid], NoSuchProcess=LookupError, AccessDenied=PermissionError,
        wait_procs=lambda procs, timeout: (procs, []))
    monkeypatch.setitem(sys.modules, "psutil", fake)
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] and res["frozen_first"]
    first_kill = next(i for i, x in enumerate(log) if x.startswith("kill"))
    assert set(log[:first_kill]) == {"suspend 1", "suspend 2", "suspend 3"}
    assert log[first_kill:] == ["kill 3", "kill 2", "kill 1"], "deepest first, target last"
    log.clear()
    gh.kids = [FP(4, "terminal64.exe", r"C:\MT5\terminal64.exe")]
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and not any(x.startswith("kill") for x in log)
    assert {x for x in log if x.startswith("resume")} == {"resume 1", "resume 2", "resume 3",
                                                          "resume 4"}


def test_dry_run_decides_but_never_acts(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [P(3100, INTAKE, age_s=96 * MIN, cpu=3.0)],
                 running={"MT5-IndependenceIntake": True}, beat_age_s=3 * 3600)
    _, second = two_passes(tmp_path, fb, apply=False)
    assert fb.killed == [] and fb.ended == [] and fb.started == []
    verdicts = {r["verdict"] for r in second["rows"]}
    assert {"WOULD_END", "WOULD_RESTART"} <= verdicts


# ------------------------------------------------------------------------------- task rule
def test_independence_intake_hung_past_its_limit_is_ended(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [P(3100, INTAKE, age_s=96 * MIN, cpu=3.0)],
                 running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    assert fb.ended == ["MT5-IndependenceIntake"]
    assert rows(second, "independence_intake")[0]["verdict"] == "ENDED"
    # the process survived /End in the fake table, so its tree is stopped too
    assert fb.killed == [3100]


def test_independence_intake_within_its_limit_is_left_alone(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [P(3100, INTAKE, age_s=10 * MIN, cpu=3.0)],
                 running={"MT5-IndependenceIntake": True})
    two_passes(tmp_path, fb)
    assert fb.ended == [] and fb.killed == []


def test_a_running_task_with_no_owner_is_ended_only_after_two_passes(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], running={"MT5-IndependenceIntake": True})
    first, _second = two_passes(tmp_path, fb)
    assert rows(first, "independence_intake")[0]["verdict"] == "OBSERVING"
    assert fb.ended == ["MT5-IndependenceIntake"]


# ------------------------------------------------------------------------------- gate rules
def _gate_tree(age_s: float = 2 * 3600) -> list[bsh.Proc]:
    return [P(8720, GATE, name="powershell.exe", age_s=age_s, cpu=4.0),
            P(8721, GATE_PY, ppid=8720, age_s=age_s, cpu=2.0),
            P(14604, GH_PULLS, name="gh.exe", ppid=8721, age_s=age_s, cpu=0.5)]


def test_a_wedged_gate_run_is_stopped_and_its_task_ended(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True},
                 beat_age_s=2 * 3600)
    _, _second = two_passes(tmp_path, fb)
    assert fb.killed == [8720]
    assert fb.ended == ["Quant-WorkflowGate"]
    assert fb.started == [], "a live run is judged by the wedge rule, not restarted beside"


def test_a_gate_tree_holding_anything_but_gh_git_python_is_refused(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(9000, "notepad.exe x", name="notepad.exe", ppid=8720)]
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
    me = P(31337, INTAKE, age_s=96 * MIN, cpu=1.0)
    monkeypatch.setattr(bsh.os, "getpid", lambda: 31337)
    fb = FakeBox(tmp_path, [me], running={"MT5-IndependenceIntake": True})
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
