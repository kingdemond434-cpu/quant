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


SYSTEM = "NT AUTHORITY\\SYSTEM"
SVCHOST_PID = 1000


def P(pid: int, cmd: str, *, name: str = "python.exe", ppid: int = SVCHOST_PID,
      age_s: float = 3 * 3600, cpu: float = 10.0, user: str | None = SYSTEM) -> bsh.Proc:
    return bsh.Proc(pid, ppid, name, cmd, NOW - age_s, cpu, (), user)


def svchost() -> bsh.Proc:
    """Task Scheduler's host: the ancestor scheduler_owned requires for a task's own process."""
    return bsh.Proc(SVCHOST_PID, 4, "svchost.exe", "svchost.exe -k netsvcs",
                    NOW - 30 * 24 * 3600, 0.0, (), SYSTEM)


MERGE = (r'"C:\Program Files\Python314\python.exe" '
         r"C:\opt\quant\desks\mt5\research\merge_hypotheses.py")
HEAVY = r"python.exe -W ignore C:\opt\quant\desks\mt5\research\pf_allocator.py --mode heavy"
FAST = r"python.exe -W ignore C:\opt\quant\desks\mt5\research\pf_allocator.py --mode fast"
INTAKE = (r'"C:\Program Files\Python314\python.exe" -W ignore '
          r"C:\opt\quant\desks\mt5\research\independence_intake.py --once --budget-s 600")
INTAKE_CMD = (r'cmd.exe /d /s /c ""C:\Program Files\Python314\python.exe" -W ignore '
              r'"C:\opt\quant\desks\mt5\research\independence_intake.py" --once --budget-s 600 '
              r'>> "C:\opt\quant\desks\mt5\logs\IndependenceIntake.log" 2>&1"')


def intake(pid: int = 3100, *, age_s: float = 96 * MIN, cpu: float = 3.0, ppid: int = SVCHOST_PID,
           cmd: str = INTAKE) -> list[bsh.Proc]:
    """The intake as its task runs it: the task's cmd.exe, and the python under it."""
    return [P(pid - 1, INTAKE_CMD, name="cmd.exe", ppid=ppid, age_s=age_s + 1, cpu=0.0),
            P(pid, cmd, ppid=pid - 1, age_s=age_s, cpu=cpu)]


GATE = (r"powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass "
        r'-File "C:\ProgramData\QuantBox\bin\workflow_gate.ps1"')
GATE_PY = (r"python.exe -I -u C:\ProgramData\QuantBox\gate-repo\.github\scripts\audit_gate.py "
           r"--repo kingdemond434-cpu/quant --base claude/llm-auto-upgrade-verify-gcjac3 "
           r"--sweep --box")
GH_PULLS = r"gh.exe api repos/kingdemond434-cpu/quant/pulls?state=open&per_page=100"


class FakeBox:
    def __init__(self, tmp: Path, procs: list[bsh.Proc], *, running: dict[str, bool] | None = None,
                 beat_age_s: float | None = 60.0) -> None:
        self.table = ([svchost(), *procs] if not any(p.pid == SVCHOST_PID for p in procs)
                      else list(procs))
        self.running = running or {}
        self.killed: list[int] = []
        self.ended: list[str] = []
        self.started: list[str] = []
        self.beat = tmp / "workflow_gate.json"
        #: account -> SID, as LookupAccountNameW would answer on the box (SIDs pass through).
        self.sids: dict[str, str] = {"box\\administrator": "S-1-5-21-7-7-7-500",
                                     "box\\svc-gate": "S-1-5-21-7-7-7-1001"}
        if beat_age_s is not None:
            self.beat.write_text(json.dumps({"at": datetime.fromtimestamp(
                NOW - beat_age_s, tz=UTC).isoformat(), "rc": 0}), "utf-8")

    def box(self) -> bsh.Box:
        def kill(p: bsh.Proc, procs: Sequence[bsh.Proc],
                 allowed: frozenset[str] | None = None,
                 verify: Any = None) -> dict[str, Any]:
            self.killed.append(p.pid)
            gone = {p.pid} | {d.pid for d in bsh.descendants(p.pid, self.table)}
            self.table = [q for q in self.table if q.pid not in gone]
            return {"ok": True, "target_gone": True, "killed": sorted(gone)}

        def end(t: str) -> dict[str, Any]:
            self.ended.append(t)
            return {"rc": 0}

        def run(t: str) -> dict[str, Any]:
            self.started.append(t)
            return {"rc": 0}

        return bsh.Box(procs=lambda: list(self.table),
                       task_running=lambda t: self.running.get(t, False),
                       end_task=end, run_task=run, kill=kill, host=HOST,
                       gate_beat=self.beat, windows=True,
                       secure=self.secure, task_principal=lambda t: self.principal,
                       sid_of=self.sid_of)

    #: by default the admin-only state check passes; a test sets this to a reason to simulate a
    #: writable store.
    secure_reason: str | None = None
    #: the task's registered principal, as schtasks exports it (a name or a SID).
    principal: str | None = SYSTEM.lower()

    def sid_of(self, account: str | None) -> str | None:
        got = self.sids.get((account or "").strip().lower())
        return got or bsh._account_sid(account)

    def secure(self, path: Path) -> str | None:
        return self.secure_reason


@pytest.fixture(autouse=True)
def _no_real_pager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bsh, "_send_alert", lambda t, b: {"armed": 0, "test": True})


def two_passes(tmp: Path, fb: FakeBox, *, cpu_after: dict[int, float] | None = None,
               apply: bool = True, gap_s: float = 5 * MIN) -> tuple[dict, dict]:
    """Pass 1 baselines CPU; pass 2 (gap_s later) judges progress. Returns both reports."""
    kw = {"report": tmp / "r.json", "ledger": tmp / "l.jsonl", "state": tmp / "s.json"}
    first = bsh.run(apply=apply, box=fb.box(), now=NOW, **kw)
    if cpu_after:
        fb.table = [bsh.Proc(p.pid, p.ppid, p.name, p.cmdline, p.create_time,
                             cpu_after.get(p.pid, p.cpu_s), p.argv, p.user) for p in fb.table]
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


class FakePs:
    """A stand-in for psutil: a live table that suspend/resume/kill act on, with failures
    injectable per process and per method. Nothing real is touched."""

    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass

    def __init__(self) -> None:
        self.table: dict[int, FP] = {}
        self.dead: set[int] = set()
        self.log: list[str] = []

    def add(self, pid: int, name: str, cmd: str, *, parent: FP | None = None,
            age_s: float = 3600.0, fail: dict[str, BaseException] | None = None) -> FP:
        fp = FP(self, pid, name, cmd, parent.pid if parent else 0, NOW - age_s, fail or {})
        self.table[pid] = fp
        if parent is not None:
            parent.kids.append(fp)
        return fp

    def Process(self, pid: int) -> FP:
        if pid in self.dead or pid not in self.table:
            raise self.NoSuchProcess(pid)
        return self.table[pid]

    def wait_procs(self, procs: list[FP], timeout: float) -> tuple[list[FP], list[FP]]:
        return ([p for p in procs if p.pid in self.dead],
                [p for p in procs if p.pid not in self.dead])

    def suspended(self) -> set[int]:
        """Pids suspended and neither resumed nor killed since."""
        out: set[int] = set()
        for x in self.log:
            verb, pid = x.split()
            if verb == "suspend":
                out.add(int(pid))
            else:
                out.discard(int(pid))
        return out


class FP:
    def __init__(self, ps: FakePs, pid: int, name: str, cmd: str, ppid: int, ct: float,
                 fail: dict[str, BaseException]) -> None:
        self.ps, self.pid, self._name, self._cmd, self._ppid = ps, pid, name, cmd, ppid
        self._ct, self.fail, self.kids = ct, fail, []

    def _check(self, method: str) -> None:
        if method in self.fail:
            raise self.fail[method]
        if self.pid in self.ps.dead:
            raise self.ps.NoSuchProcess(self.pid)

    def create_time(self) -> float:
        self._check("create_time")
        return self._ct

    def ppid(self) -> int:
        self._check("ppid")
        return self._ppid

    def name(self) -> str:
        self._check("name")
        return self._name

    def cmdline(self) -> list[str]:
        self._check("cmdline")
        return bsh._argv(bsh.Proc(self.pid, 0, self._name, self._cmd, 0.0, 0.0))

    def children(self, recursive: bool = False) -> list[FP]:
        self._check("children")
        out: list[FP] = []
        for k in self.kids:
            if k.pid in self.ps.dead:
                continue
            out += [k, *(k.children(recursive=True) if recursive else [])]
        return out

    def suspend(self) -> None:
        self._check("suspend")
        self.ps.log.append(f"suspend {self.pid}")

    def resume(self) -> None:
        if "resume" in self.fail:
            raise self.fail["resume"]
        self.ps.log.append(f"resume {self.pid}")

    def kill(self) -> None:
        self._check("kill")
        self.ps.log.append(f"kill {self.pid}")
        self.ps.dead.add(self.pid)


@pytest.fixture
def ps(monkeypatch: pytest.MonkeyPatch) -> FakePs:
    fake = FakePs()
    monkeypatch.setitem(sys.modules, "psutil", fake)
    return fake


def _gate_fp(ps: FakePs, **fail: dict[str, BaseException]) -> tuple[FP, FP, FP, bsh.Proc]:
    root = ps.add(1, "powershell.exe", GATE, age_s=3600, fail=fail.get("root"))
    py = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=3500, fail=fail.get("py"))
    gh = ps.add(3, "gh.exe", GH_PULLS, parent=py, age_s=3400, fail=fail.get("gh"))
    return root, py, gh, bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)


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
def _kw(tmp: Path, **extra: Any) -> dict[str, Any]:
    return {"report": tmp / "r.json", "ledger": tmp / "l.jsonl", "state": tmp / "s.json",
            **extra}


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
def _dead_gate(tmp: Path, base: float) -> FakeBox:
    fb = FakeBox(tmp, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    return fb


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


# --- SHOULD-FIX ------------------------------------------------------------------------------
def test_a_denied_live_child_is_seen_before_anything_is_frozen(ps: FakePs) -> None:
    _root, _py, gh, target = _gate_fp(ps)
    ps.add(4, "terminal64.exe", r"C:\MT5\terminal64.exe", parent=gh, age_s=60)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and ps.log == [], "nothing is suspended when a denied child is visible"


def test_a_vanished_child_never_reports_a_live_target_stopped(ps: FakePs) -> None:
    _gate_fp(ps, gh={"name": FakePs.NoSuchProcess(3)})
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] is False and res["target_gone"] is False
    assert ps.suspended() == set() and 1 not in ps.dead


def test_a_target_still_alive_after_the_kill_is_stop_failed_and_the_gate_not_ended(
        tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True}, beat_age_s=60)
    box = fb.box()
    box.kill = lambda p, t, a=None, v=None: {"ok": True, "target_gone": True}   # but it is not
    _, second = (bsh.run(box=box, now=NOW, **_kw(tmp_path)),
                 bsh.run(box=box, now=NOW + 5 * MIN, **_kw(tmp_path)))
    assert "STOP_FAILED" in [r["verdict"] for r in rows(second, "workflow_gate")]
    assert fb.ended == []


def test_an_exiting_child_is_progress_not_a_stall(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(14700, "git.exe fetch", name="git.exe", ppid=8721, age_s=MIN,
                             cpu=50.0)]
    fb = FakeBox(tmp_path, tree, running={"Quant-WorkflowGate": True}, beat_age_s=60)
    kw = _kw(tmp_path)
    bsh.run(box=fb.box(), now=NOW, **kw)
    fb.table = [p for p in fb.table if p.pid != 14700]       # git finished: -50 s of tree cpu
    doc = bsh.run(box=fb.box(), now=NOW + 5 * MIN, **kw)
    assert fb.killed == []
    assert rows(doc, "workflow_gate")[0]["verdict"] == "PROGRESSING"


@pytest.mark.parametrize("cmd", [
    r"python.exe C:\opt\quant\desks\mt5\research\promoter.py --reconcile",
    r"python.exe C:\opt\quant\desks\mt5\research\shadow_forward.py",
    r"python.exe C:\opt\quant\desks\mt5\research\scalp_shadow.py",
    r"python.exe C:\opt\quant\desks\mt5\scripts\certifier_launcher.py",
    r"python.exe C:\opt\quant\desks\mt5\research\hourly_cycle.py",
])
def test_the_research_organs_other_owners_run_are_denied(cmd: str) -> None:
    assert bsh.denied(P(1, cmd))


def test_a_gate_tree_using_the_credential_manager_and_sh_is_still_a_gate_tree(
        tmp_path: Path) -> None:
    tree = [*_gate_tree(),
            P(14610, "git.exe fetch", name="git.exe", ppid=8721, age_s=MIN, cpu=0.1),
            P(14611, "git-credential-manager.exe get", name="git-credential-manager.exe",
              ppid=14610, age_s=MIN, cpu=0.1),
            P(14612, "sh.exe -c hook", name="sh.exe", ppid=14610, age_s=MIN, cpu=0.1)]
    fb = FakeBox(tmp_path, tree, running={"Quant-WorkflowGate": True}, beat_age_s=60)
    two_passes(tmp_path, fb)
    assert fb.killed == [8720] and fb.ended == ["Quant-WorkflowGate"]


def test_an_intake_stop_publishes_a_two_sided_missed_growth_line(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(), running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    lines = second["missed_growth"]
    assert len(lines) == 1
    line = lines[0]
    assert line["rail"] == "box_self_heal_intake_stop" and line["verdict"] == "UNMEASURED"
    assert line["cost"]["intake_wall_s_discarded"] == pytest.approx(96 * MIN + 5 * MIN)
    assert line["benefit"]["slot_s_freed_past_budget"] > 0
    third = bsh.run(box=fb.box(), now=NOW + 10 * MIN, **_kw(tmp_path))
    assert len(third["missed_growth"]) == 1, "the history persists, one line per stop"


def test_the_installer_runs_the_admin_only_copy_never_the_repo_tree() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    for name in ("box_self_heal.py", "process_health.py", "alert_channels.py"):
        assert f"'{name}'" in code or f"\\{name}'" in code, name
    assert "C:\\ProgramData\\QuantBox" in code and "Join-Path $Root 'bin'" in code
    # install_unattended.ps1's ACL pattern: owner, no junction, nothing writable but admin/SYSTEM
    for marker in ("'S-1-5-32-544'", "'S-1-5-18'", "ReparsePoint", "more than read",
                   "SetAccessRuleProtection"):
        assert marker in code, marker
    action = next(x for x in code.splitlines() if "New-ScheduledTaskAction" in x)
    nxt = code[code.index(action):code.index(action) + 400]
    assert "$Installed" in nxt and "$Script" not in nxt.split("$Installed")[0]


def test_the_installed_copy_loads_only_its_admin_only_siblings(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bsh, "_IN_REPO", False)
    monkeypatch.setattr(bsh, "_HERE", tmp_path)
    assert bsh._dep("process_health.py", "ops/process_health.py") is None, \
        "never falls back to the repo tree"
    (tmp_path / "process_health.py").write_text("STATE_RUNNING = frozenset({'x'})\n", "utf-8")
    assert bsh._dep("process_health.py", "ops/process_health.py") == tmp_path / "process_health.py"


def test_the_watchdog_has_one_registry_organ_and_an_attestation_row() -> None:
    """ops/ is outside the birth fence's executable areas, so the organ is declared by hand; the
    manifest is protected, so until its line lands the organ is no second registration of it."""
    name = "_box_self_heal_components"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "desks" / "mt5" / "ops" / "components.py")
    assert spec and spec.loader
    c = sys.modules.get(name) or importlib.util.module_from_spec(spec)
    if name not in sys.modules:
        sys.modules[name] = c
        spec.loader.exec_module(c)
    organ = next(s for s in c.explicit_specs()
                 if s.component_id == "executable:ops/box_self_heal.py")
    assert organ.schedule == "Quant-BoxSelfHeal" and organ.cadence_s == bsh.CADENCE_S
    assert organ.code_paths[0] == "ops/box_self_heal.py"
    assert "desks/mt5/reports/BOX_SELF_HEAL.json" in organ.outputs
    gaps = c.task_canonical_gaps()
    assert not any("Quant-BoxSelfHeal" in g for v in gaps.values() for g in v), gaps
    att = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert any(r.get("organ") == organ.component_id for r in att["organs"])


# =============================================================================================
# REGRESSIONS FOR THE AUDIT HOLD OF 5b3504f50 (v3). Each failed against that head.
# =============================================================================================
# --- MF-A: the state store is admin-only, and an insecure or empty one cannot drive action ----
def test_admin_only_fails_closed_off_windows_and_for_an_absent_path(tmp_path: Path) -> None:
    assert bsh.admin_only(tmp_path) is not None                 # linux: cannot be proven
    assert bsh.admin_only(tmp_path / "nope") is not None        # absent


def test_a_writable_state_dir_refuses_all_action_and_keeps_nothing(tmp_path: Path) -> None:
    """A planted state in a user-writable dir named some_admin_job.py as a former gate member and
    got it STOPPED; an empty one reset the cap. If the dir is not provably admin-only, the pass
    reads nothing, keeps nothing and stops nothing."""
    # a state that WOULD stop a planted orphan and WOULD look like an empty cap
    (tmp_path / "s.json").write_text(json.dumps({
        "gate_tree": {"777:0.0": 0.0},
        "cpu": {"777:0.0": {"at": NOW - 10 * MIN, "cpu_s": 0.0, "members": {"777:0.0": 0.0}}},
        "attempts": {}}), "utf-8")
    victim = P(777, r"python.exe C:\opt\quant\scripts\some_admin_job.py", name="python.exe",
               age_s=3 * 3600, cpu=0.0)
    fb = FakeBox(tmp_path, [victim], beat_age_s=60)
    fb.secure_reason = "C:\\ProgramData\\QuantBox\\state grants S-1-5-32-545 more than read"
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert fb.killed == [] and fb.ended == [] and fb.started == []
    assert doc["state_dir_secure"] is False
    assert any(r["verdict"] == "REFUSED" and r.get("history") == "INSECURE" for r in doc["rows"])
    # the state on disk is untouched: the pass never wrote it back
    assert json.loads((tmp_path / "s.json").read_text())["gate_tree"] == {"777:0.0": 0.0}


def test_an_empty_state_cannot_lower_the_cap_below_the_ledger(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = _kw(tmp_path)
    t = base
    for wait in (0, 30 * MIN + 1, 60 * MIN + 1, 120 * MIN + 1):
        t += wait
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == 4
    # a state that erased the attempts, but the admin-only ledger still proves four
    (tmp_path / "s.json").write_text(json.dumps({"attempts": {}, "cpu": {}}), "utf-8")
    doc = bsh.run(box=fb.box(), now=t + 6 * 3600, **kw)
    assert len(fb.started) == 4
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"
    assert doc["attempt_history"] == "state+ledger"


# --- MF-B: the live tree is walked level by level, each child against ITS OWN parent ----------
def test_a_recycled_pid_grandchild_is_excluded_from_the_live_kill(ps: FakePs) -> None:
    """psutil children(recursive=True) compares every descendant with the ROOT only, so a Z that
    adopted a recycled pid (older than its apparent parent) came along. Level by level drops it."""
    root = ps.add(1, "powershell.exe", GATE, age_s=3600)                 # target, ct oldest
    child = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=1800)    # legit, younger
    ps.add(7, "python.exe", r"python.exe C:\opt\quant\scripts\some_admin_job.py",
           parent=child, age_s=3000)                                     # OLDER than its parent 2
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] and 7 not in ps.dead
    assert set(ps.dead) == {1, 2}, "only the target and its real child are killed"


# --- MF-C: each copied file is pinned to its committed sha256 -------------------------------
def test_the_installer_pins_match_the_files_at_head() -> None:
    import subprocess as _sp
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    pat = r"'([\w.]+\.py)' = @\{ src = .*?sha256 = '([0-9a-f]{64})'"
    pinned = dict(__import__("re").findall(pat, src))
    assert set(pinned) == {"box_self_heal.py", "process_health.py", "alert_channels.py"}
    paths = {"box_self_heal.py": "ops/box_self_heal.py",
             "process_health.py": "ops/process_health.py",
             "alert_channels.py": "libs/ops/alert_channels.py"}
    srcs = dict(__import__("re").findall(r"'([\w.]+\.py)' = @\{ src = '([\w/.]+)'", src))
    assert srcs == paths, "each pin names the repo-relative blob it is read from"
    for name, rel in paths.items():
        blob = _sp.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True).stdout
        import hashlib
        assert pinned[name] == hashlib.sha256(blob).hexdigest(), f"{name} pin drifted from HEAD"


# --- SF-1: a PATH python is trusted only from an admin-only directory -----------------------
def test_the_installer_only_trusts_a_path_python_from_an_admin_only_directory() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "function Test-DirAdminOnly" in code
    assert "refusing PATH python" in code and "C:\\Program Files\\Python314\\python.exe" in code


# --- SF-2: the two identities must be a SYSTEM task run, not any matching string -------------
def test_scheduler_owned_requires_system_and_a_task_scheduler_ancestor(tmp_path: Path) -> None:
    box = FakeBox(tmp_path, []).box()
    sv = svchost()
    gate = P(8720, GATE, name="powershell.exe", ppid=SVCHOST_PID, user=SYSTEM)
    assert bsh.scheduler_owned(gate, [sv, gate], box, "Quant-WorkflowGate") is None
    hand = P(8720, GATE, name="powershell.exe", ppid=4242, user="BOX\\Administrator")
    shell = P(4242, "powershell.exe -NoExit", name="powershell.exe", age_s=4 * 3600)
    why = bsh.scheduler_owned(hand, [shell, hand], box, "Quant-WorkflowGate")
    assert why and "SYSTEM" in why and "S-1-5-21-7-7-7-500" in why
    orphan_owner = P(8720, GATE, name="powershell.exe", ppid=9, user=SYSTEM)
    assert bsh.scheduler_owned(orphan_owner, [orphan_owner], box, "Quant-WorkflowGate")


def test_a_gate_run_not_launched_by_the_scheduler_is_not_stopped(tmp_path: Path) -> None:
    """A -Command wrapper or a hand run owned by a user, with no svchost ancestor."""
    shell = P(4242, "powershell.exe -NoExit", name="powershell.exe", age_s=4 * 3600,
              user="BOX\\Administrator")
    gate = P(8720, GATE, name="powershell.exe", ppid=4242, age_s=2 * 3600, cpu=4.0,
             user="BOX\\Administrator")
    fb = FakeBox(tmp_path, [shell, gate], running={"Quant-WorkflowGate": True},
                 beat_age_s=2 * 3600)
    two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []


def test_a_command_flag_before_file_never_matches_the_gate() -> None:
    cmd = (r'powershell.exe -Command "Start-Process" -File '
           r"C:\ProgramData\QuantBox\bin\workflow_gate.ps1")
    assert not bsh.matches(bsh.RULE_BY_KEY["workflow_gate"], P(1, cmd, name="powershell.exe"))


# --- SF-3: a partial kill names what died -----------------------------------------------------
def test_an_access_denied_mid_kill_names_the_members_already_killed(ps: FakePs) -> None:
    root = ps.add(1, "powershell.exe", GATE, age_s=3600, fail={"kill": ps.AccessDenied(1)})
    py = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=3500)
    ps.add(3, "gh.exe", GH_PULLS, parent=py, age_s=3400)
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)   # 3 and 2 die, the root refuses
    assert not res["ok"]
    assert "PARTIALLY" in res["why"] and set(res["killed"]) == {2, 3}


# --- SF-4: a torn line in the MIDDLE of the ledger is skipped, not fatal ---------------------
def test_a_torn_middle_ledger_line_is_skipped_not_the_whole_history(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = _kw(tmp_path)
    t = base
    for wait in (0, 30 * MIN + 1):
        t += wait
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == 2
    lines = (tmp_path / "l.jsonl").read_text("utf-8").splitlines()
    lines.insert(1, "{ this is torn")                   # a crash left half a line mid-file
    (tmp_path / "l.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    (tmp_path / "s.json").write_text("{corrupt", "utf-8")
    doc = bsh.run(box=fb.box(), now=t + 10 * MIN, **kw)
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "BACKOFF"   # both attempts counted
    assert "torn_lines_skipped" in doc["attempt_history"]


# --- SF-5: future-dated attempts (a backward clock) are clamped to now -----------------------
def test_future_dated_attempts_count_at_now_not_tomorrow(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 12, 0, tzinfo=UTC).timestamp()
    future = base + 2 * 86400
    futures = [future, future + 60, future + 120, future + 180]
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    (tmp_path / "s.json").write_text(json.dumps({
        "attempts": {"workflow_gate_restart": futures}, "cpu": {}}), "utf-8")
    doc = bsh.run(box=fb.box(), now=base, **_kw(tmp_path))
    assert fb.started == [], "four future-dated attempts still fill today's cap"
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"


# --- SF-6 / v4 NEW-MF3: only PURE-DATA images (git, gh, git-remote-*, git-credential-manager,
# conhost) are judged by their image alone; every other image by its WHOLE command line ---------
@pytest.mark.parametrize("cmd,name", [
    (r"git.exe fetch origin claude/miner-x", "git.exe"),
    (r"git.exe fetch origin claude/miner-experiment", "git.exe"),
    (r"gh.exe pr checkout claude/fusion-rework", "gh.exe"),
    (r"git.exe -C C:\gate-repo log --oneline e8_branch", "git.exe"),
    (r"git-remote-https.exe origin https://github.com/x/quant claude/miner-x",
     "git-remote-https.exe"),
    (r"git-credential-manager.exe get claude/miner-x", "git-credential-manager.exe"),
    (r"conhost.exe 0xffffffff -ForceV1 miner", "conhost.exe"),
])
def test_a_data_argument_named_like_a_denied_job_is_not_denied(cmd: str, name: str) -> None:
    assert bsh.denied(P(1, cmd, name=name)) is None


@pytest.mark.parametrize("cmd,name", [
    (r"python run.py --role gateway", "python.exe"),
    (r"python -m desks.mt5.cli executor --live", "python.exe"),
    (r"python desk.py --account FTMO", "python.exe"),
    (r"python follower.py --broker fusion", "python.exe"),
    (r"python -mdesks.mt5.gateway cfg.json", "python.exe"),
    (r"powershell -Command Invoke-Desk -Name gateway", "powershell.exe"),
    (r"powershell -File run.ps1 -Role gateway", "powershell.exe"),
    (r'sh.exe -c "python C:\opt\quant\desks\mt5\gateway.py"', "sh.exe"),
    (r'python.exe "C:\opt\quant\run.py --role gateway', "python.exe"),     # unbalanced quote
    (r"python.exe build.py --note merge_hypotheses-rerun", "python.exe"),
])
def test_a_money_organ_anywhere_on_a_non_data_command_line_is_denied(cmd: str, name: str
                                                                        ) -> None:
    """v4 NEW-MF3: the v3 code-token haystack let each of these through."""
    assert bsh.denied(P(1, cmd, name=name)) is not None


def test_sh_is_not_a_data_image_and_an_unparseable_line_is_one_token() -> None:
    assert "sh" not in bsh._DATA_ARG_IMAGES
    line = r'python.exe "C:\opt\quant\run.py --role gateway'
    assert bsh._argv(P(1, line)) == [line]
    # a git line that cannot be parsed is judged by all of it (fail-safe), not by its image
    assert bsh.denied(P(1, r'git.exe fetch "origin claude/miner-x', name="git.exe"))


@pytest.mark.parametrize("cmd,name", [
    (r"python.exe C:\opt\quant\desks\mt5\research\pf_allocator.py", "python.exe"),
    (r"python.exe launcher.py C:\x\gateway_resident.py", "python.exe"),
    (r"powershell.exe -File C:\opt\quant\ops\bridge\bridge_watchdog.ps1", "powershell.exe"),
    (r"some_unknown.exe --flag moat_recorder deep", "some_unknown.exe"),
])
def test_code_tokens_and_unknown_images_still_deny(cmd: str, name: str) -> None:
    assert bsh.denied(P(1, cmd, name=name)) is not None


def test_a_python_launcher_running_a_denied_script_is_denied() -> None:
    # fail-safe: a later argument that names code is identity too
    assert bsh.denied(P(1, r"py.exe -I runner.py gateway.py --live", name="py.exe"))


# --- v4 NEW-MF1: a fresh install (folder only, no files) acts and then persists ---------------
_ADMIN_ACL = ("S-1-5-18", [(0, 0x1F01FF, "S-1-5-18"), (0, 0x1F01FF, "S-1-5-32-544"),
                           (0, 0x1200A9, "S-1-5-32-545")])


def _real_admin_only(monkeypatch: pytest.MonkeyPatch,
                     acl: Any = lambda p: _ADMIN_ACL) -> list[str]:
    """The REAL admin_only, with only the Windows ACL read stubbed."""
    seen: list[str] = []
    monkeypatch.setattr(bsh, "_on_windows", lambda: True)
    monkeypatch.setattr(bsh, "_acl_entries", lambda p: (seen.append(Path(p).name), acl(p))[1])
    return seen


def test_a_fresh_install_with_only_the_folder_acts_and_then_persists(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _real_admin_only(monkeypatch)
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    sd = tmp_path / "state"
    sd.mkdir()                                       # what the installer creates: the folder
    kw = {"report": tmp_path / "r.json", "ledger": sd / "box_self_heal.jsonl",
          "state": sd / "box_self_heal_state.json"}
    box = fb.box()
    box.secure = bsh.admin_only
    doc = bsh.run(box=box, now=base, **kw)
    assert seen == ["state"], "a fresh folder: only the folder's ACL is proven"
    assert doc["state_dir_secure"] is True and doc["attempt_history"] == "fresh"
    assert fb.started == ["Quant-WorkflowGate"], "the fresh pass acts"
    assert json.loads(kw["state"].read_text("utf-8"))["history"] == "known"
    assert any(json.loads(x).get("verdict") == "ATTEMPT"
               for x in kw["ledger"].read_text("utf-8").splitlines())
    seen.clear()
    later = bsh.run(box=box, now=base + 5 * MIN, **kw)
    assert seen == ["state", "box_self_heal_state.json", "box_self_heal.jsonl"]
    assert later["state_dir_secure"] is True and later["attempt_history"] == "state+ledger"
    assert len(fb.started) == 1, "the persisted attempt holds the backoff"


def test_a_writable_folder_or_an_existing_writable_file_is_still_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    users_write = ("S-1-5-18", [*_ADMIN_ACL[1], (0, 0x2, "S-1-5-32-545")])
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    for bad in ("state", "box_self_heal.jsonl.1"):
        _real_admin_only(monkeypatch, lambda p, bad=bad: users_write if Path(p).name == bad
                         else _ADMIN_ACL)
        root = tmp_path / bad
        sd = root / "state"
        sd.mkdir(parents=True)
        (sd / "box_self_heal.jsonl.1").write_text("", "utf-8")
        fb = _dead_gate(root, base)
        box = fb.box()
        box.secure = bsh.admin_only
        doc = bsh.run(box=box, now=base, report=root / "r.json",
                      ledger=sd / "box_self_heal.jsonl", state=sd / "box_self_heal_state.json")
        assert doc["state_dir_secure"] is False and fb.started == [], bad
        assert not (sd / "box_self_heal_state.json").exists()


# --- v4 should-fix 1: the repo report cannot silence a page -----------------------------------
def test_a_planted_paged_once_in_the_report_does_not_suppress_a_page(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    box = fb.box()
    box.run_task = lambda t: {"rc": 1, "out": "access denied"}
    day = datetime.fromtimestamp(base, tz=UTC).strftime("%Y-%m-%d")
    (tmp_path / "r.json").write_text(json.dumps({"paged_once": {
        "workflow_gate_restart:START_FAILED": day, "workflow_gate_restart:CAPPED": day}}),
        "utf-8")
    sent: list[str] = []
    bsh.run(box=box, now=base, **_kw(tmp_path, alert=lambda t, b: sent.append(b)))
    assert sent and "START_FAILED" in sent[0], "the planted report key is ignored"


# --- v4 should-fix 2: SYSTEM never writes into the repo through a junction or symlink ---------
def test_a_symlinked_report_folder_is_not_written_through(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "reports").symlink_to(target, target_is_directory=True)
    doc = bsh.run(box=fb.box(), now=base, **{**_kw(tmp_path),
                                             "report": tmp_path / "reports" / "r.json"})
    assert doc["report_refused"] and "symlink" in doc["report_refused"]
    assert list(target.iterdir()) == []
    assert bsh.redirected(tmp_path / "plain" / "r.json") is None


def test_a_hard_linked_report_is_not_written_through(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", "utf-8")
    (tmp_path / "r.json").hardlink_to(victim)
    assert "hard links" in (bsh.redirected(tmp_path / "r.json") or "")


def test_a_planted_tmp_symlink_is_never_written_through(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", "utf-8")
    (tmp_path / "r.json.tmp").symlink_to(victim)
    bsh._write_json(tmp_path / "r.json", {"a": 1})
    assert victim.read_text("utf-8") == "keep"
    assert json.loads((tmp_path / "r.json").read_text("utf-8")) == {"a": 1}


# --- v4 should-fix 3: only https channel URLs are opened -------------------------------------
@pytest.mark.parametrize("cfg,ok", [
    ({"kind": "webhook", "url": "https://hooks.example/x"}, True),
    ({"kind": "webhook", "url": "http://hooks.example/x"}, False),
    ({"kind": "webhook", "url": "file:///C:/Windows/win.ini"}, False),
    ({"kind": "webhook"}, False),
    ({"kind": "hc", "url": "HTTPS://hc-ping.com/abc"}, True),
    ({"kind": "hc", "url": "ftp://hc-ping.com/abc"}, False),
    ({"kind": "ntfy", "topic": "box"}, True),
    ({"kind": "telegram", "token": "t", "chat_id": "1"}, True),
])
def test_only_https_channels_are_fired(tmp_path: Path, cfg: dict[str, Any], ok: bool) -> None:
    assert (bsh._https_channel(cfg, tmp_path / "hb.json") is not None) is ok


def test_an_hc_channel_without_a_url_needs_an_https_heartbeat(tmp_path: Path) -> None:
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({"url": "http://hc-ping.com/abc"}), "utf-8")
    assert bsh._https_channel({"kind": "hc"}, hb) is None
    hb.write_text(json.dumps({"url": "https://hc-ping.com/abc"}), "utf-8")
    assert bsh._https_channel({"kind": "hc"}, hb) == {"kind": "hc",
                                                       "url": "https://hc-ping.com/abc"}


# --- v4 should-fix 9: owner and principal are compared as SIDs --------------------------------
def test_a_principal_exported_as_a_sid_matches_its_account_by_sid(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [])
    fb.principal = "S-1-5-21-7-7-7-1001"             # schtasks /XML exported the SID
    box = fb.box()
    sv = svchost()
    gate = P(8720, GATE, name="powershell.exe", user="BOX\\svc-gate")
    assert bsh.scheduler_owned(gate, [sv, gate], box, "Quant-WorkflowGate") is None
    other = P(8720, GATE, name="powershell.exe", user="BOX\\Administrator")
    assert bsh.scheduler_owned(other, [sv, other], box, "Quant-WorkflowGate")
    localized = P(8720, GATE, name="powershell.exe", user="NT-AUTORITÄT\\SYSTEM")
    fb.sids["nt-autorität\\system"] = "S-1-5-18"
    assert bsh.scheduler_owned(localized, [sv, localized], box, "Quant-WorkflowGate") is None
    unknown = P(8720, GATE, name="powershell.exe", user="BOX\\nobody")
    assert "no SID" in (bsh.scheduler_owned(unknown, [sv, unknown], box, "Quant-WorkflowGate")
                        or "")


def test_task_principal_returns_the_exported_userid_verbatim(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bsh, "_schtasks", lambda *a, **k: {
        "rc": 0, "out": "<Principal><UserId>S-1-5-18</UserId></Principal>"})
    assert bsh._task_principal("Quant-WorkflowGate") == "S-1-5-18"
    assert bsh._account_sid("s-1-5-18") == "S-1-5-18"
    assert bsh._account_sid("NT AUTHORITY\\SYSTEM") == "S-1-5-18"
    assert bsh._account_sid("") is None


# --- v4 NEW-MF2: the installer writes each copy from the committed blob, not the CRLF tree ----
def test_the_installer_writes_each_copy_from_git_cat_file_blob() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert 'cat-file blob "HEAD:{1}"' in code and "BaseStream.CopyTo" in code
    assert "Copy-Item" not in code, "nothing is copied from the working tree"
    assert "git.exe is not on PATH" in code and "the blob is missing" in code
    assert "[string]$RepoRoot" in code and "rev-parse --show-toplevel" in code
    assert "Get-FileHash -LiteralPath $dst" in code


def test_a_crlf_checkout_differs_from_the_pin_but_its_blob_matches(tmp_path: Path) -> None:
    """The box checks out with core.autocrlf=true: the working-tree bytes are CRLF and can never
    match the pin; `git cat-file blob HEAD:<path>` is the LF blob, which does."""
    import hashlib
    import subprocess as _sp

    def git(*a: str, cwd: Path) -> bytes:
        return _sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd,
                       check=True, capture_output=True).stdout

    rel = "ops/box_self_heal.py"
    blob = git("show", f"HEAD:{rel}", cwd=ROOT)
    pin = hashlib.sha256(blob).hexdigest()
    origin = tmp_path / "origin"
    (origin / "ops").mkdir(parents=True)
    git("init", "-q", cwd=origin)
    (origin / rel).write_bytes(blob)
    git("add", rel, cwd=origin)
    git("commit", "-q", "-m", "x", cwd=origin)
    box = tmp_path / "box"
    git("-c", "core.autocrlf=true", "clone", "-q", "-c", "core.autocrlf=true", str(origin),
        str(box), cwd=tmp_path)
    tree = (box / rel).read_bytes()
    assert b"\r\n" in tree and hashlib.sha256(tree).hexdigest() != pin
    assert hashlib.sha256(git("cat-file", "blob", f"HEAD:{rel}", cwd=box)).hexdigest() == pin


# --- v4 should-fix 7: the interpreter's code folders are admin-only, the probe is isolated ----
def test_the_installer_checks_the_interpreters_lib_and_site_packages() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "@('Lib', 'Lib\\site-packages', 'DLLs')" in code
    assert '& $Python -I -c "import psutil"' in code
