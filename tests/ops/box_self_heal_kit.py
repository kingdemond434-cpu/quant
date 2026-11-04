"""Shared fakes and fixtures for the box self-heal tests (test_box_self_heal*.py).

Split out of tests/ops/test_box_self_heal.py (2026-11-04) so each file fits the independent
reviewer whole. Every fake here stands in for the machine: no process is started, stopped or
queried and no task is touched. The two fixtures (the autouse pager stub and `ps`) are imported
by name into each test module, which is how pytest finds them.
"""
from __future__ import annotations

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
#: the real pager entry point (an autouse fixture stubs `bsh._send_alert` in every test)
_REAL_SEND_ALERT = bsh._send_alert
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
        # Spot reads Running unless a test says otherwise, so its rule stays out of the others.
        self.running = {bsh.MEMECOIN_SPOT_TASK: True, **(running or {})}
        self.spot = tmp / "spot.json"
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
                       gate_beat=self.beat, spot_status=self.spot, windows=True,
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


def stub_pager(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pager is never called for real; each test module wraps this in an autouse fixture."""
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


def fake_psutil(monkeypatch: pytest.MonkeyPatch) -> FakePs:
    """A FakePs installed as `psutil`; each test module wraps this in its `ps` fixture."""
    fake = FakePs()
    monkeypatch.setitem(sys.modules, "psutil", fake)
    return fake


def _gate_fp(ps: FakePs, **fail: dict[str, BaseException]) -> tuple[FP, FP, FP, bsh.Proc]:
    root = ps.add(1, "powershell.exe", GATE, age_s=3600, fail=fail.get("root"))
    py = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=3500, fail=fail.get("py"))
    gh = ps.add(3, "gh.exe", GH_PULLS, parent=py, age_s=3400, fail=fail.get("gh"))
    return root, py, gh, bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)


def _gate_tree(age_s: float = 2 * 3600) -> list[bsh.Proc]:
    return [P(8720, GATE, name="powershell.exe", age_s=age_s, cpu=4.0),
            P(8721, GATE_PY, ppid=8720, age_s=age_s, cpu=2.0),
            P(14604, GH_PULLS, name="gh.exe", ppid=8721, age_s=age_s, cpu=0.5)]


def _kw(tmp: Path, **extra: Any) -> dict[str, Any]:
    return {"report": tmp / "r.json", "ledger": tmp / "l.jsonl", "state": tmp / "s.json",
            **extra}


def _dead_gate(tmp: Path, base: float) -> FakeBox:
    fb = FakeBox(tmp, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    return fb
