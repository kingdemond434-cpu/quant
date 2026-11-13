"""PROCESS SUPERVISOR: an allowlisted, non-trading box process that overstays its bound is stopped,
with proof of identity, so no one is ever asked to approve a PID again (zuck 2026-11-13 17:07Z).

WHY. On 11-13 the box gate's status reporter (scripts/merge_pipeline_watch.py, run by
Quant-WorkflowGate) ran past its task's 30-min limit and zuck was asked to type "stop PIDs 24004
and 10336". A PID is not an identity: Windows reuses them. And a person typing it is not
recovery.

WHAT IT STOPS. Only processes that match an ALLOWLIST entry in every respect at once:
    1. the image name is one the entry names (python.exe, gh.exe, ...);
    2. the command line carries the entry's member script as a path (".../merge_pipeline_watch.py");
    3. an ANCESTOR's command line carries the entry's task root script (workflow_gate.ps1), so
       the process belongs to that task's run and not to a person's shell running the same file;
    4. it is older than the member's bound (a bound well past its own budget and timeouts);
    5. no process in its chain matches the TRADING DENY list (terminal64, deadman, allocator,
       executor, gateway, e8/ftmo/fusion, ...): a money process is never a candidate, whatever
       an allowlist entry says, and an entry whose own markers match the deny list is refused;
    6. it is not this supervisor or one of its ancestors.
The identity read at selection (pid + create_time) is re-checked immediately before every
signal; psutil also refuses to signal a reused PID. Nothing else on the box is touched.

HOW IT STOPS. Gracefully first. Windows gives a console-less process no SIGTERM, so "graceful"
here is the order: the member's DESCENDANTS (the gh or git call it is stuck in) are ended first,
which hands the member an error on its own call path. Its own handler then runs, and the watcher
writes its WATCH_BLIND report and exits. The member gets --grace-s to do that. Only then is it
terminated, and only after a further bounded wait is it killed. Every step, including what was
spared and why, goes to desks/mt5/reports/PROCESS_SUPERVISOR.json.

RESTART. Every allowlisted task is a repeating scheduled task, so its own next trigger is the
restart (Quant-WorkflowGate: 10 min). No second scheduler, no new task: the supervisor runs
inside the existing MT5-ReapGitWriters pass (every 15 min, scripts/reap_hung_git_writers.py).

PRIVILEGE. It adds no privilege. It runs with the account MT5-ReapGitWriters already has, and
its authority is narrowed in code to the allowlist above, which tests pin. A process that is not
allowlisted is never signalled, whatever its age.

DRILL. `--drill` builds a fake gate tree (a "workflow_gate.ps1" root, a "merge_pipeline_watch.py"
member, a stuck "gh" child), supervises ONLY that tree with a 1 s bound, and passes when the
member and its child are gone and nothing else was signalled. CI runs it; the box can too.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: A money process is never a candidate: these markers anywhere in a process's chain spare it.
TRADING_DENY = (
    "terminal64", "metatrader", "mt5_bridge", "deadman", "allocator", "executor", "gateway",
    "e8_", "ftmo", "fusion", "order", "risk_units", "account_state", "pf_allocator",
    "tick_recorder", "sshd",
)  # fmt: skip


@dataclass(frozen=True)
class Member:
    """One script a task runs, and how long one run of it may live."""

    script: str
    max_age_s: float
    images: tuple[str, ...] = ("python.exe", "python", "python3", "python3.14", "pythonw.exe")


@dataclass(frozen=True)
class Entry:
    """One allowlisted non-trading task: its root script and the members it may run."""

    task: str
    lane: str
    root: str
    members: tuple[Member, ...]
    restart: str = "next trigger"


#: THE ALLOWLIST. Bounds sit past each member's own budget and timeouts, and the sum stays under
#: the task's 30-min ExecutionTimeLimit, so a member is stopped before the task is killed whole.
ALLOWLIST: tuple[Entry, ...] = (
    Entry(
        task="Quant-WorkflowGate",
        lane="ops",
        root="workflow_gate.ps1",
        members=(
            # the watcher's budget is 300 s plus 45 s per call
            Member("merge_pipeline_watch.py", 10 * 60),
            Member("live_first_ci.py", 8 * 60),  # 60 s per gh call
            Member("adopt_rows.py", 8 * 60),
            Member("memecoin_gate.py", 8 * 60),
            Member("audit_gate.py", 20 * 60),  # the sweep stops on its own budget before this
        ),
    ),
)
LANES_ALLOWED = ("ops", "data", "research")


def denied(text: str) -> str | None:
    low = text.lower()
    return next((m for m in TRADING_DENY if m in low), None)


def check_allowlist(entries: Iterable[Entry]) -> list[str]:
    """Why an allowlist is unsafe; empty when every entry is non-trading and well formed."""
    bad = []
    for e in entries:
        if e.lane not in LANES_ALLOWED:
            bad.append(f"{e.task}: lane {e.lane!r} is not a non-trading lane")
        for text in (e.task, e.root, *(m.script for m in e.members)):
            hit = denied(text)
            if hit:
                bad.append(f"{e.task}: {text!r} matches the trading deny list ({hit})")
        if not e.members:
            bad.append(f"{e.task}: no members")
    return bad


def _arg_is(cmd: Sequence[str], script: str) -> bool:
    s = script.lower()
    return any(a.replace("\\", "/").lower().rstrip('"').endswith("/" + s) or a.lower() == s
               for a in cmd)  # fmt: skip


def _cmd(p: Any) -> list[str]:
    try:
        return list(p.cmdline() or [])
    except Exception:
        return []


@dataclass
class Verdict:
    pid: int
    name: str
    cmd: str
    created: float
    task: str = ""
    member: str = ""
    age_s: float = 0.0
    action: str = "spared"
    why: str = ""
    steps: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "pid": self.pid, "name": self.name, "cmd": self.cmd[:300],
            "created": datetime.fromtimestamp(self.created, UTC).isoformat(timespec="seconds"),
            "task": self.task, "member": self.member, "age_s": round(self.age_s, 1),
            "action": self.action, "why": self.why, "steps": self.steps,
        }  # fmt: skip


def _psutil() -> Any:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return None
    return psutil


def classify(ps: Any, p: Any, entries: Sequence[Entry], protected: set[int],
             now: float) -> Verdict | None:  # fmt: skip
    """A Verdict when `p` is a member of an allowlisted task (stopped or spared, with why);
    None when it is no member at all (not examined further, never signalled)."""
    try:
        name = (p.name() or "").lower()
        created = p.create_time()
    except Exception:
        return None
    cmd = _cmd(p)
    for e in entries:
        for m in e.members:
            if name not in m.images or not _arg_is(cmd, m.script):
                continue
            v = Verdict(p.pid, name, " ".join(cmd), created, e.task, m.script, now - created)
            try:
                chain = p.parents()
            except Exception:
                chain = []
            texts = [" ".join(cmd)] + [" ".join(_cmd(a)) for a in chain]
            hit = next((h for h in (denied(t) for t in texts) if h), None)
            if hit:
                v.why = f"a process in its chain matches the trading deny list ({hit})"
            elif p.pid in protected:
                v.why = "this supervisor or one of its ancestors"
            elif not any(_arg_is(_cmd(a), e.root) for a in chain):
                v.why = f"no ancestor runs {e.root}: not this task's run"
            elif v.age_s <= m.max_age_s:
                v.why = f"within its bound ({v.age_s:.0f} s of {m.max_age_s:.0f} s)"
            else:
                v.action = "stop"
                v.why = f"past its bound ({v.age_s:.0f} s of {m.max_age_s:.0f} s)"
            return v
    return None


def _same(ps: Any, pid: int, created: float) -> Any:
    """The process again, only if it is still the SAME one (pid and create_time)."""
    try:
        p = ps.Process(pid)
        if p.status() == getattr(ps, "STATUS_ZOMBIE", "zombie"):
            return None  # dead, only not yet reaped (POSIX; Windows has no zombies)
        return p if abs(p.create_time() - created) < 0.01 else None
    except Exception:
        return None


def stop(ps: Any, v: Verdict, grace_s: float, hard_s: float) -> None:
    """Descendants first, then a grace period for the member's own error path, then terminate,
    then kill. Each signal re-checks identity."""
    p = _same(ps, v.pid, v.created)
    if p is None:
        v.action, v.why = "gone", v.why + "; exited before it was signalled"
        return
    try:
        kids = [(k.pid, k.create_time(), k.name()) for k in p.children(recursive=True)]
    except Exception:
        kids = []
    for pid, created, name in reversed(kids):  # deepest first
        k = _same(ps, pid, created)
        if k is None:
            continue
        try:
            k.kill()
            v.steps.append(f"ended child {name} pid={pid}")
        except Exception as exc:
            v.steps.append(f"child {name} pid={pid}: {type(exc).__name__}")
    if kids:
        gone, _ = ps.wait_procs([p], timeout=grace_s)
        if gone:
            v.action = "stopped (exited on its own after its stuck call ended)"
            return
    for how in ("terminate", "kill"):
        q = _same(ps, v.pid, v.created)
        if q is None:
            v.action = "stopped"
            return
        try:
            getattr(q, how)()
            v.steps.append(how)
        except Exception as exc:
            v.steps.append(f"{how}: {type(exc).__name__}")
        gone, _ = ps.wait_procs([q], timeout=hard_s)
        if gone:
            v.action = "stopped"
            return
    v.action = "FAILED"
    v.why += "; still alive after terminate and kill"


def supervise(
    *,
    apply: bool,
    entries: Sequence[Entry] = ALLOWLIST,
    grace_s: float = 30.0,
    hard_s: float = 10.0,
    within: Callable[[Any], bool] | None = None,
) -> dict[str, Any]:
    """One pass. `within` limits the pass to some processes (the drill's own tree)."""
    rec: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "apply": apply, "status": "MEASURED", "examined": [], "stopped": [], "failed": [],
        "allowlist": [{"task": e.task, "lane": e.lane, "root": e.root,
                       "members": {m.script: m.max_age_s for m in e.members},
                       "restart": e.restart} for e in entries],
    }  # fmt: skip
    bad = check_allowlist(entries)
    if bad:
        rec["status"], rec["why"] = "REFUSED", "; ".join(bad)
        return rec
    ps = _psutil()
    if ps is None:
        rec["status"], rec["why"] = "UNMEASURED", "psutil is not importable: nothing signalled"
        return rec
    protected = {os.getpid()}
    with contextlib.suppress(Exception):
        protected |= {a.pid for a in ps.Process(os.getpid()).parents()}
    now = time.time()
    for p in ps.process_iter():
        if within is not None and not within(p):
            continue
        v = classify(ps, p, entries, protected, now)
        if v is None:
            continue
        if v.action == "stop":
            if apply:
                stop(ps, v, grace_s, hard_s)
            else:
                v.action = "would stop"
        rec["examined"].append(v.row())
        if v.action.startswith("stopped") or v.action == "gone":
            rec["stopped"].append(v.row())
        elif v.action == "FAILED":
            rec["failed"].append(v.row())
    over = [r for r in rec["examined"] if r["action"] == "would stop"]
    rec["verdict"] = ("FAILED" if rec["failed"] else "RECOVERED" if rec["stopped"]
                      else "OVERDUE" if over else "CLEAR")  # fmt: skip
    return rec


# ---------------------------------------------------------------------------------------- drill

_HANG = "import sys,time\nwhile True: time.sleep(1)\n"


def drill(timeout_s: float = 60.0) -> dict[str, Any]:
    """A simulated reporter hang: root "workflow_gate.ps1" -> member "merge_pipeline_watch.py"
    -> stuck "gh" child. Only this tree is supervised, with a 1 s bound. PASS when the member
    and its child are gone, the root is untouched, and nothing outside the tree was signalled."""
    ps = _psutil()
    if ps is None:
        return {"drill": "UNMEASURED", "why": "psutil is not importable"}
    tmp = Path(tempfile.mkdtemp(prefix="supervisor_drill_"))
    py = sys.executable
    member_src = (
        "import subprocess,sys,time\n"
        f"subprocess.Popen([sys.executable, '-c', {_HANG!r}, {str(tmp / 'gh')!r}])\n"
        "try:\n    time.sleep(3600)\nexcept BaseException:\n    pass\n"
    )
    root_src = (
        "import subprocess,sys,time\n"
        f"m = subprocess.Popen([sys.executable, '-c', {member_src!r}, {str(tmp / 'merge_pipeline_watch.py')!r}])\n"  # noqa: E501
        "m.wait()\ntime.sleep(3600)\n"
    )
    root = subprocess.Popen([py, "-c", root_src, str(tmp / "workflow_gate.ps1")])
    try:
        deadline = time.time() + 20
        tree: list[Any] = []
        while time.time() < deadline:
            try:
                tree = ps.Process(root.pid).children(recursive=True)
            except Exception:
                tree = []
            if len(tree) >= 2:
                break
            time.sleep(0.2)
        time.sleep(1.5)  # past the drill's 1 s bound
        ids = {root.pid} | {k.pid for k in tree}
        born = {}
        for k in tree:
            with contextlib.suppress(Exception):
                born[k.pid] = k.create_time()
        members = tuple(Member(m.script, 1.0, (*m.images, Path(py).name.lower()))
                        for m in ALLOWLIST[0].members)  # fmt: skip
        entry = Entry(ALLOWLIST[0].task, ALLOWLIST[0].lane, ALLOWLIST[0].root, members)
        rec = supervise(apply=True, entries=(entry,), grace_s=5.0, hard_s=5.0,
                        within=lambda p: p.pid in ids)  # fmt: skip
        left = [pid for pid, c in born.items() if _same(ps, pid, c)]
        root_alive = root.poll() is None
        ok = (rec.get("verdict") == "RECOVERED" and not left and root_alive
              and all(r["pid"] in ids for r in rec["examined"]))  # fmt: skip
        return {"drill": "PASS" if ok else "FAIL", "tree": sorted(ids), "left_alive": left,
                "root_untouched": root_alive, "pass": rec}  # fmt: skip
    finally:
        with contextlib.suppress(Exception):
            for k in ps.Process(root.pid).children(recursive=True):
                k.kill()
        root.kill()
        root.wait(timeout=10)
