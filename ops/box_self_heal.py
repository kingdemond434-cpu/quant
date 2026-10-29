"""THE BOX SELF-HEAL WATCHDOG: a CLOSED rule table that clears the stuck processes zuck had to
clear by hand, and nothing else.

    python ops/box_self_heal.py              # one pass, acts (Quant-BoxSelfHeal, every 5 min)
    python ops/box_self_heal.py --dry-run    # one pass, decides and logs, acts on nothing

WHY THIS EXISTS (2026-10-29). zuck pasted this into an admin PowerShell, and said it must never be
needed again:

    stop pid N  only if its command line is merge_hypotheses   (it held .job_locks/merge_hypotheses)
    stop pid N  only if its command line is pf_allocator        (it held the allocator lock)
    stop pid N  only if its command line is gh "pulls" / the gate's python (under the gate)
    schtasks /end MT5-IndependenceIntake                         (hung past its limit)
    schtasks /end + /run Quant-WorkflowGate                       (dead since a 13:14Z crash)
    git config safe.directory C:/ProgramData/QuantBox/gate-repo

Every line of that paste is a FIXED identity plus a FIXED action, so it is a rule table, not a
judgement. This file is the table for the lines ONLY A SYSTEM PROCESS CAN DO -- ending SYSTEM or
elevated tasks and their trees, and restarting the gate -- and the evidence each rule needs before
it may fire. The two job-lock lines are NOT here (see DEFERRED below). The git
line is not an action here: it is a one-time machine config written by the installer
(desks/mt5/scripts/install_box_self_heal_task.ps1), and workflow_gate.ps1 already passes the
same exception at command scope.

WHAT IT IS NOT. It is NOT a general command runner and must never become one. It reads no command
from a file, a queue, the network, the environment or its own arguments; its only flag is
--dry-run. Every process it may stop, every task it may end or start, and every argument it passes
to schtasks is a literal in THIS file, reviewed with it (a "box runner" was refused before, and
this is deliberately not one). Adding a rule is a code change that goes through review like any
other.

THE RULES (`RULES` below is the table; tests pin it):

    independence_intake   identity: task MT5-IndependenceIntake Running + independence_intake.py
                          budget:   its installer's PT20M limit + 5 min (2x its --budget-s if more)
                          action:   schtasks /End; then its tree if it survived the /End
    workflow_gate         identity: workflow_gate.ps1 under Quant-WorkflowGate, gh/git/python kids
                          budget:   install_unattended.ps1's 30 min limit + 5 min
                          action:   end the tree (gh/git/python children only), schtasks /End
    workflow_gate_restart identity: logs/workflow_gate.json older than 30 min, no gate run alive
                          action:   schtasks /End + /Run, backoff 30/60/120 min, max 4 a UTC day

    STUCK = held/running past its budget AND (its owner pid is dead, OR it made no CPU progress
    across two passes at least PROGRESS_WINDOW_S apart). A long job that is still computing is not
    an abandoned one (job_lock's own lesson: liveness vetoes age), so CPU progress always vetoes.

DEFERRED, NOT DUPLICATED: THE JOB-LOCK LINES. A stuck lock owner is job_lock's own business, and
job_lock is growing the mechanism (#526, claude/judge-atomic-replace: `owner_progress` names an
owner WEDGED after 30 min with no tree CPU, and the hourly `job_lock_health` leg,
scripts/check_job_locks.py, stops an allowlisted research owner -- merge_hypotheses among them --
after two hours with no progress, and reclaims through job_lock). That same change lists
pf_allocator as NEVER auto-stopped: it reads the live terminal (`mt5.account_info`) and writes the
book the gateway sizes from, which is also this file's own "never touch anything that calls MT5"
rule. A second killer for the same locks, on a different clock and budget, would race the first,
so `DEFERRED` names where each of those paste lines lives and this file never reads, stops or
deletes anything by lock. Nothing in this file unlinks, rewrites or creates a lock file.

NEVER TOUCHED, by a deny list checked BEFORE any allowlist match and again on every descendant of
a tree it is about to end: the MT5 terminal (terminal64.exe, metaeditor), anything that trades or
places orders (gateway, executors, deadman, prop/E8/FTMO/Fusion), the bridge and Claude's
Remote Control session, the miners/recorders/moat, and this watchdog itself and its ancestors.
A process that is on neither list is never stopped: there is no default action.

RED-LOGGED. Every action and every refusal is a RED row in desks/mt5/reports/BOX_SELF_HEAL.json
(this pass) and appended to desks/mt5/logs/box_self_heal.jsonl (the ledger). The report carries its
own `at`, and `check_desk_health.py` and the organ contract both read it, so a watchdog that
stopped running shows RED rather than silence.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "BOX_SELF_HEAL.json"
LEDGER = DESK / "logs" / "box_self_heal.jsonl"
#: Cross-pass memory (CPU baselines, gate tree, restarts). Under logs/, which the box sync ignores.
STATE = DESK / "logs" / "box_self_heal_state.json"
#: The gate's own folder (ops/box/workflow_gate.ps1, $Root). A literal, never an argument.
QUANTBOX_LOGS = Path(r"C:\ProgramData\QuantBox\logs")
GATE_BEAT = QUANTBOX_LOGS / "workflow_gate.json"

SCHEMA = "box_self_heal/1"
VERSION = "boxheal-2026-10-29-a"
TASK_NAME = "Quant-BoxSelfHeal"
#: How often the task fires, and the age past which its own report is stale (desk health, contract).
CADENCE_S = 5 * 60
STALE_AFTER_S = 20 * 60

#: CPU progress is judged across PASSES, never inside one: a 20-second sample of a job that is
#: waiting on disk reads as wedged. Two observations at least this far apart, and less than
#: CPU_EPS_S of CPU (the whole tree) between them, is "no progress".
PROGRESS_WINDOW_S = 4 * 60
CPU_EPS_S = 2.0
#: An observation older than this is not a baseline (the watchdog itself was down).
PROGRESS_MAX_GAP_S = 30 * 60

#: Gate restarts: the first may happen once the heartbeat is GATE_STALE_S old; each later one
#: waits twice as long as the one before; never more than MAX_RESTARTS_PER_DAY per UTC day.
GATE_CADENCE_S = 10 * 60
GATE_STALE_S = 3 * GATE_CADENCE_S
RESTART_BACKOFF_S = 30 * 60
MAX_RESTARTS_PER_DAY = 4

LEDGER_ROTATE_BYTES = 5 * 1024 * 1024


# ------------------------------------------------------------------------------ the closed table
@dataclass(frozen=True)
class Rule:
    """One allowlisted thing this watchdog may act on. Literal in code; never loaded."""

    key: str
    kind: str                      # "task" | "gate" | "gate_restart"
    #: EVERY one of these must appear in the (lower-cased, whitespace-folded) command line.
    cmd_all: tuple[str, ...]
    #: The image the matched process must have (lower-case basename, extension optional).
    images: tuple[str, ...]
    task: str | None = None        # the scheduled task, for kinds "task"/"gate"/"gate_restart"
    #: The budget past which the rule may judge "stuck" (and never before).
    fallback_budget_s: int = 0
    budget_source: str = ""
    why: str = ""


_PY = ("python.exe", "python", "python3", "python3.exe", "pythonw.exe", "py.exe")
_PS = ("powershell.exe", "pwsh.exe", "powershell", "pwsh")

RULES: tuple[Rule, ...] = (
    Rule("independence_intake", "task", ("independence_intake.py",), _PY,
         task="MT5-IndependenceIntake", fallback_budget_s=20 * 60 + 5 * 60,
         budget_source="install_independence_intake_task.ps1 ExecutionTimeLimit PT20M + 5 min; "
                       "its own --budget-s if larger",
         why="registered with a 20 minute limit and found hung far past it"),
    Rule("workflow_gate", "gate", ("workflow_gate.ps1",), _PS, task="Quant-WorkflowGate",
         fallback_budget_s=30 * 60 + 5 * 60,
         budget_source="ops/box/install_unattended.ps1 ExecutionTimeLimit 30 min + 5 min",
         why="the box's auto-merge sweep (audit_gate.py --sweep --box); a wedged run holds the "
             "Global\\QuantBox-WorkflowGate mutex and every later run exits 0 having done nothing"),
    Rule("workflow_gate_restart", "gate_restart", (), (), task="Quant-WorkflowGate",
         fallback_budget_s=GATE_STALE_S,
         budget_source="3 of the gate's own 10-minute cadences",
         why="the gate crashed and its heartbeat stopped; nothing merges until it runs again"),
)
RULE_BY_KEY: dict[str, Rule] = {r.key: r for r in RULES}

#: The paste's job-lock lines, and the owner that handles each one instead of this file.
DEFERRED: tuple[tuple[str, str], ...] = (
    ("merge_hypotheses", "job_lock owner_progress + scripts/check_job_locks.py (#526): WEDGED at "
                         "30 min, auto-stopped after 2 h with no tree CPU, lock reclaimed by "
                         "job_lock"),
    ("pf_allocator", "job_lock owner_progress (#526) names it WEDGED/RED in JOB_LOCK_HEALTH.json; "
                     "never auto-stopped (it reads the live terminal and feeds the gateway's "
                     "sizing) -- an operator stop, by design"),
)

#: The ONLY tasks this file may /End, and the ONLY one it may /Run. Checked at the call.
ENDABLE_TASKS: frozenset[str] = frozenset({"MT5-IndependenceIntake", "Quant-WorkflowGate"})
RUNNABLE_TASKS: frozenset[str] = frozenset({"Quant-WorkflowGate"})

#: The images a workflow_gate tree may contain. Anything else under the gate refuses the action.
GATE_CHILD_IMAGES: frozenset[str] = frozenset({
    "gh.exe", "gh", "git.exe", "git", "git-remote-https.exe", "git-remote-https",
    "conhost.exe", *_PY, *_PS,
})

#: NEVER TOUCH. Substrings of the lower-cased command line or image; any hit refuses, whatever
#: else matched. Checked first, and again on every descendant of a tree about to be ended.
DENY: tuple[tuple[str, str], ...] = (
    ("terminal64", "the MT5 terminal"),
    ("terminal.exe", "an MT5 terminal"),
    ("metatrader", "an MT5 terminal"),
    ("metaeditor", "the MT5 editor"),
    ("gateway", "the gateway: it places and manages orders"),
    ("executor", "an executor: it trades"),
    ("deadman", "the Tier-3 deadman rail"),
    ("\\prop\\", "the prop desk (E8/FTMO/Fusion): it trades"),
    ("/prop/", "the prop desk (E8/FTMO/Fusion): it trades"),
    ("e8_", "an E8 prop process"),
    ("e8-", "an E8 prop task"),
    ("ftmo", "an FTMO process"),
    ("fusion", "the Fusion account"),
    ("order_send", "places orders"),
    ("allocator_trigger", "the resident allocator pulse that feeds the gateway"),
    ("bridge", "the bridge"),
    ("claude.exe", "Claude's Remote Control session"),
    ("claude-code", "Claude's Remote Control session"),
    ("remote-control", "Claude's Remote Control session"),
    ("remote_control", "Claude's Remote Control session"),
    ("miner", "a mining task"),
    ("mining", "a mining task"),
    ("moat", "the moat recorders and miners"),
    ("recorder", "a tape recorder"),
    ("box_self_heal", "this watchdog"),
    # The paste's job-lock lines belong to job_lock_health (#526); see DEFERRED. Denied here so
    # this file can never become a second killer racing the first.
    ("merge_hypotheses", "deferred to job_lock's own wedged-owner stop (#526)"),
    # check_job_locks.AUTO_STOP_JOBS (#526): its 2 h stop owns these research owners.
    *((s, "a job_lock_health research owner (#526 AUTO_STOP_JOBS); its 2 h stop owns it")
      for s in ("local_converter", "breadth_sweep", "session_chart_equivalents",
                "miner_candidate_compiler", "style_novelty", "orthogonal_sweep",
                "edge_search", "macro_desk", "falsifier_run", "backfill_coverage",
                "warm_gauntlet_cache")),
    # check_job_locks.NEVER_STOP (#526): the judge, the certifier, the terminal lane.
    *((s, "never stopped automatically (#526 NEVER_STOP: judge, certifier, terminal lane)")
      for s in ("external_gauntlet", "certification_lane", "fusion_terminal_research_lane",
                "tape_features")),
    ("pf_allocator", "reads the live terminal and feeds the gateway's sizing; never auto-stopped"),
)


# ------------------------------------------------------------------------------------- the facts
@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    name: str
    cmdline: str
    create_time: float
    cpu_s: float


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace('"', " ").replace("'", " ")).strip().lower()


def _image(p: Proc) -> str:
    return os.path.basename((p.name or "").lower())


def denied(p: Proc) -> str | None:
    """Why `p` may never be touched, or None. Checked before any allowlist match."""
    text = f"{_image(p)} {_fold(p.cmdline)}"
    for needle, why in DENY:
        if needle in text:
            return f"{needle!r}: {why}"
    return None


def matches(rule: Rule, p: Proc) -> bool:
    """`p` is the process `rule` names: its image and EVERY required command-line fragment."""
    if not rule.cmd_all:
        return False
    img = _image(p)
    if rule.images and img not in rule.images and img.removesuffix(".exe") not in rule.images:
        return False
    text = _fold(p.cmdline)
    return all(frag in text for frag in rule.cmd_all)


def allowlisted(p: Proc) -> Rule | None:
    """The rule `p` is on, or None. A denied process is on no rule, whatever it matches."""
    if denied(p):
        return None
    return next((r for r in RULES if matches(r, p)), None)


def descendants(pid: int, procs: Sequence[Proc]) -> list[Proc]:
    kids: dict[int, list[Proc]] = {}
    for p in procs:
        kids.setdefault(p.ppid, []).append(p)
    out: list[Proc] = []
    stack = [pid]
    seen = {pid}
    while stack:
        for k in kids.get(stack.pop(), []):
            if k.pid not in seen:
                seen.add(k.pid)
                out.append(k)
                stack.append(k.pid)
    return out


def ancestors(pid: int, procs: Sequence[Proc]) -> set[int]:
    by = {p.pid: p for p in procs}
    out: set[int] = set()
    cur = by.get(pid)
    while cur is not None and cur.ppid not in out and cur.ppid != cur.pid:
        out.add(cur.ppid)
        cur = by.get(cur.ppid)
    return out


def _ident(p: Proc) -> str:
    return f"{p.pid}:{round(p.create_time, 1)}"


def tree_cpu(p: Proc, procs: Sequence[Proc]) -> float:
    return p.cpu_s + sum(d.cpu_s for d in descendants(p.pid, procs))


def progress(p: Proc, procs: Sequence[Proc], prior: Mapping[str, Any], now: float
             ) -> tuple[str, str]:
    """("STALLED" | "PROGRESSING" | "OBSERVING", why) for `p`'s whole tree, across passes."""
    cpu = tree_cpu(p, procs)
    prev = prior.get(_ident(p)) if isinstance(prior, Mapping) else None
    if not isinstance(prev, Mapping):
        return "OBSERVING", f"first observation of pid {p.pid} (tree cpu {cpu:.1f}s)"
    try:
        dt = now - float(prev["at"])
        dcpu = cpu - float(prev["cpu_s"])
    except (KeyError, TypeError, ValueError):
        return "OBSERVING", "the prior observation is unreadable; re-baselining"
    if dt > PROGRESS_MAX_GAP_S:
        return "OBSERVING", f"the prior observation is {dt:.0f}s old; re-baselining"
    if dt < PROGRESS_WINDOW_S:
        return "OBSERVING", f"only {dt:.0f}s since the baseline (need {PROGRESS_WINDOW_S}s)"
    if dcpu < CPU_EPS_S:
        return "STALLED", f"tree cpu moved {dcpu:.2f}s in {dt:.0f}s (< {CPU_EPS_S}s)"
    return "PROGRESSING", f"tree cpu moved {dcpu:.1f}s in {dt:.0f}s"


# --------------------------------------------------------------------------------- the actuators
@dataclass
class Box:
    """Everything the pass reads or does to the machine. Tests swap every field."""

    procs: Callable[[], list[Proc] | None]
    task_running: Callable[[str], bool | None]
    end_task: Callable[[str], dict[str, Any]]
    run_task: Callable[[str], dict[str, Any]]
    #: kill(target, table, allowed_images): freeze, re-verify and end the tree (`_kill_tree`).
    kill: Callable[[Proc, Sequence[Proc], frozenset[str] | None], dict[str, Any]]
    host: str = field(default_factory=socket.gethostname)
    gate_beat: Path = GATE_BEAT
    windows: bool = sys.platform == "win32"


def _live_procs() -> list[Proc] | None:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return None
    rows: list[Proc] = []
    for pr in psutil.process_iter(["pid", "ppid", "name", "cmdline", "create_time", "cpu_times"]):
        try:
            info = pr.info
            ct = info.get("cpu_times")
            cpu = float(getattr(ct, "user", 0.0) + getattr(ct, "system", 0.0)) if ct else 0.0
            rows.append(Proc(int(info["pid"]), int(info.get("ppid") or 0),
                             str(info.get("name") or ""), " ".join(info.get("cmdline") or []),
                             float(info.get("create_time") or 0.0), cpu))
        except Exception:
            continue
    return rows


def _schtasks(verb: str, task: str) -> dict[str, Any]:
    """The ONLY subprocess this file starts: schtasks with a literal verb on an allowlisted task."""
    allowed = {"/Query": ENDABLE_TASKS | RUNNABLE_TASKS, "/End": ENDABLE_TASKS,
               "/Run": RUNNABLE_TASKS}
    if verb not in allowed or task not in allowed[verb]:
        raise ValueError(f"schtasks {verb} {task!r} is not in the closed table")
    argv = ["schtasks", verb, "/TN", task] + (["/FO", "CSV", "/NH"] if verb == "/Query" else [])
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
        return {"argv": argv, "rc": r.returncode,
                "out": ((r.stdout or "") + (r.stderr or "")).strip()[-300:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "rc": None, "out": f"{type(exc).__name__}"}


def _task_running(task: str) -> bool | None:
    r = _schtasks("/Query", task)
    if r.get("rc") != 0:
        return None
    running_states = _running_states()
    try:
        import csv
        import io
        row = next(csv.reader(io.StringIO(str(r.get("out") or ""))), [])
        state = str(row[2] if len(row) > 2 else "").strip().lower()
    except Exception:
        return None
    if not state:
        return None
    return state in running_states


def _running_states() -> frozenset[str]:
    """process_health's locale-aware Running set (schtasks prints the state in the OS language).

    Loaded by path: `desks/mt5/ops` is a regular package called `ops`, and wherever
    desks/mt5 is on sys.path it shadows this repo's `ops`."""
    name = "_box_self_heal_process_health"
    try:
        mod = sys.modules.get(name)
        if mod is None:
            spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / "process_health.py")
            if spec is None or spec.loader is None:
                raise ImportError(name)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        return frozenset(mod.STATE_RUNNING)
    except Exception:
        sys.modules.pop(name, None)
        return frozenset({"running"})


def _kill_tree(target: Proc, procs: Sequence[Proc],
               allowed_images: frozenset[str] | None = None) -> dict[str, Any]:
    """FREEZE the tree, re-verify it against the LIVE process table, then end it bottom-up.

    The same pattern job_lock_health uses: a busy owner keeps spawning, so a tree enumerated once
    and killed top-down leaves the children it started in between as orphans. Every member is
    suspended first and the tree re-enumerated until no new member appears; only then is each one
    checked (identity, deny list, gate-child image) and killed deepest-first, the target last.
    Any refusal RESUMES everything it froze and stops nothing.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return {"ok": False, "why": "psutil absent: cannot verify identity, nothing stopped"}
    frozen: list[Any] = []

    def thaw() -> None:
        for fp in reversed(frozen):
            with contextlib.suppress(Exception):
                fp.resume()

    try:
        live = psutil.Process(target.pid)
        if abs(float(live.create_time()) - target.create_time) > 1.0:
            return {"ok": False, "why": "pid was reused since it was judged; nothing stopped"}
        live.suspend()
        frozen.append(live)
        for _round in range(5):
            fresh = [k for k in live.children(recursive=True)
                     if k.pid not in {f.pid for f in frozen}]
            if not fresh:
                break
            for k in fresh:
                with contextlib.suppress(psutil.NoSuchProcess):
                    k.suspend()
                    frozen.append(k)
        else:
            thaw()
            return {"ok": False, "why": "the tree kept growing while frozen; nothing stopped"}
        for k in frozen[1:]:
            kp = Proc(k.pid, target.pid, k.name(), " ".join(k.cmdline()), k.create_time(), 0.0)
            bad = denied(kp) or (None if allowed_images is None or _image(kp) in allowed_images
                                 else f"image {_image(kp)!r} is not allowed in this tree")
            if bad:
                thaw()
                return {"ok": False, "why": f"descendant {k.pid} may not be stopped ({bad}); "
                                            f"tree resumed, nothing stopped"}
        for k in reversed(frozen):                 # deepest (latest found) first, target last
            with contextlib.suppress(psutil.NoSuchProcess):
                k.kill()
        gone, alive = psutil.wait_procs(frozen, timeout=10)
        return {"ok": not alive, "killed": sorted(p.pid for p in gone),
                "survived": sorted(p.pid for p in alive), "frozen_first": True}
    except psutil.NoSuchProcess:
        thaw()
        return {"ok": True, "why": "already gone", "killed": []}
    except psutil.AccessDenied:
        thaw()
        return {"ok": False, "why": "access denied (the task must run as SYSTEM); tree resumed"}


def real_box() -> Box:
    return Box(procs=_live_procs, task_running=_task_running,
               end_task=lambda t: _schtasks("/End", t), run_task=lambda t: _schtasks("/Run", t),
               kill=_kill_tree)


# ------------------------------------------------------------------------------------- the pass
def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _parse_iso(text: Any) -> float | None:
    try:
        d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp()
    except (TypeError, ValueError):
        return None


class Pass:
    """One pass's decisions. Every act and refusal becomes a RED row; nothing is silent."""

    def __init__(self, box: Box, prior: Mapping[str, Any], now: float, apply: bool) -> None:
        self.box, self.prior, self.now, self.apply = box, prior, now, apply
        self.rows: list[dict[str, Any]] = []
        self.observed: dict[str, dict[str, float]] = {}
        self.gate_tree: dict[str, float] = {}
        self.restarts: list[float] = [float(x) for x in (prior.get("restarts") or [])
                                      if isinstance(x, (int, float))]
        self.no_owner: dict[str, float] = {
            str(k): float(v) for k, v in (prior.get("no_owner") or {}).items()
            if isinstance(v, (int, float))}
        self.next_no_owner: dict[str, float] = {}
        self.procs: list[Proc] = []
        self.me: set[int] = set()

    def row(self, rule: str, level: str, verdict: str, why: str, **extra: Any) -> None:
        self.rows.append({"at": _iso(self.now), "rule": rule, "level": level,
                          "verdict": verdict, "why": why, **extra})

    def red(self, rule: str, verdict: str, why: str, **extra: Any) -> None:
        self.row(rule, "RED", verdict, why, **extra)

    def ok(self, rule: str, verdict: str, why: str, **extra: Any) -> None:
        self.row(rule, "OK", verdict, why, **extra)

    def observe(self, p: Proc) -> tuple[str, str]:
        self.observed[_ident(p)] = {"at": self.now, "cpu_s": tree_cpu(p, self.procs)}
        return progress(p, self.procs, self.prior.get("cpu") or {}, self.now)

    # -- the one way anything is stopped
    def stop(self, rule: Rule, p: Proc, why: str, *, children_only: frozenset[str] | None = None
             ) -> bool:
        if p.pid in self.me:
            self.red(rule.key, "REFUSED", "that is this watchdog or its ancestor", pid=p.pid)
            return False
        why_denied = denied(p)
        if why_denied:
            self.red(rule.key, "REFUSED", f"pid {p.pid} is on the deny list: {why_denied}",
                     pid=p.pid, cmdline=p.cmdline[:300])
            return False
        by_pid = {q.pid: q for q in self.procs}
        for a in sorted(ancestors(p.pid, self.procs)):
            anc = by_pid.get(a)
            if anc is not None and denied(anc):
                self.red(rule.key, "REFUSED", f"ancestor {a} is on the deny list "
                         f"({denied(anc)}); a protected tree is never cut into",
                         pid=p.pid, ancestor=a, cmdline=anc.cmdline[:300])
                return False
        for d in descendants(p.pid, self.procs):
            bad = denied(d) or (None if children_only is None or _image(d) in children_only
                                else f"image {_image(d)!r} is not a gate child")
            if bad or d.pid in self.me:
                self.red(rule.key, "REFUSED", f"descendant {d.pid} may not be stopped: "
                         f"{bad or 'this watchdog'}; the whole tree is left alone",
                         pid=p.pid, descendant=d.pid, cmdline=d.cmdline[:300])
                return False
        if not self.apply:
            self.red(rule.key, "WOULD_STOP", why, pid=p.pid, cmdline=p.cmdline[:300], dry_run=True)
            return False
        res = self.box.kill(p, self.procs, children_only)
        self.red(rule.key, "STOPPED" if res.get("ok") else "STOP_FAILED", why, pid=p.pid,
                 cmdline=p.cmdline[:300], result=res)
        return bool(res.get("ok"))

    def end(self, rule: Rule, task: str, why: str) -> bool:
        if task not in ENDABLE_TASKS:
            self.red(rule.key, "REFUSED", f"{task} is not an endable task")
            return False
        if not self.apply:
            self.red(rule.key, "WOULD_END", why, task=task, dry_run=True)
            return False
        res = self.box.end_task(task)
        self.red(rule.key, "ENDED" if res.get("rc") == 0 else "END_FAILED", why, task=task,
                 result=res)
        return res.get("rc") == 0

    def start(self, rule: Rule, task: str, why: str) -> bool:
        if task not in RUNNABLE_TASKS:
            self.red(rule.key, "REFUSED", f"{task} is not a runnable task")
            return False
        res = self.box.run_task(task)
        self.red(rule.key, "STARTED" if res.get("rc") == 0 else "START_FAILED", why, task=task,
                 result=res)
        return res.get("rc") == 0

    # -- rule kinds
    def task_rule(self, rule: Rule) -> None:
        assert rule.task is not None
        mine = [p for p in self.procs if matches(rule, p) and not denied(p)]
        running = self.box.task_running(rule.task)
        if running is None:
            self.red(rule.key, "UNMEASURED", f"the scheduler would not say whether {rule.task} "
                     f"is running; nothing done")
            return
        if not running:
            self.ok(rule.key, "NOT_RUNNING", f"{rule.task} is not running")
            return
        if not mine:
            # TWO PASSES, NOT ONE: a task that started a second ago reads Running before its
            # python exists. Only a Running task with no owner across PROGRESS_WINDOW_S is dead.
            first = self.no_owner.get(rule.task, self.now)
            self.next_no_owner[rule.task] = first
            if self.now - first < PROGRESS_WINDOW_S:
                self.ok(rule.key, "OBSERVING", f"{rule.task} reads Running with no "
                        f"{' + '.join(rule.cmd_all)} process; confirming next pass")
                return
            self.end(rule, rule.task, f"{rule.task} has read Running for {self.now - first:.0f}s "
                     f"with no {' + '.join(rule.cmd_all)} process alive (dead owner)")
            return
        oldest = min(mine, key=lambda p: p.create_time)
        budget = float(rule.fallback_budget_s)
        m = re.search(r"--budget-s\s+(\d+)", _fold(oldest.cmdline))
        if m:
            budget = max(budget, float(m.group(1)) * 2)
        age = self.now - oldest.create_time
        facts = {"pid": oldest.pid, "age_s": round(age), "budget_s": round(budget)}
        if age <= budget:
            self.ok(rule.key, "WITHIN_BUDGET", f"running {age:.0f}s of {budget:.0f}s", **facts)
            return
        verdict, why = self.observe(oldest)
        if verdict != "STALLED":
            self.ok(rule.key, verdict, f"past budget but {why}", **facts)
            return
        reason = f"{rule.task} running {age:.0f}s past a {budget:.0f}s budget and {why}"
        self.end(rule, rule.task, reason)
        if self.apply:
            again = self.box.procs() or []
            if any(p.pid == oldest.pid and abs(p.create_time - oldest.create_time) < 1
                   for p in again):
                self.procs = again
                self.stop(rule, oldest, reason + "; it survived schtasks /End")

    def gate_rule(self, rule: Rule) -> None:
        roots = [p for p in self.procs if matches(rule, p) and not denied(p)]
        live_gate: set[str] = set()
        for root in roots:
            tree = [root, *descendants(root.pid, self.procs)]
            for p in tree:
                self.gate_tree[_ident(p)] = p.create_time
                live_gate.add(_ident(p))
            age = self.now - root.create_time
            budget = float(rule.fallback_budget_s)
            facts = {"pid": root.pid, "age_s": round(age), "budget_s": round(budget),
                     "tree": [f"{_image(p)}:{p.pid}" for p in tree]}
            if age <= budget:
                self.ok(rule.key, "WITHIN_BUDGET", f"gate run {age:.0f}s of {budget:.0f}s",
                        **facts)
                continue
            verdict, why = self.observe(root)
            if verdict != "STALLED":
                self.ok(rule.key, verdict, f"past budget but {why}", **facts)
                continue
            reason = f"gate run {age:.0f}s past a {budget:.0f}s budget and {why}"
            if self.stop(rule, root, reason, children_only=GATE_CHILD_IMAGES):
                self.end(rule, "Quant-WorkflowGate", reason)
        # ORPHANS: a gh/git/python we SAW inside a gate tree last pass, now with no gate above it.
        prior_tree = self.prior.get("gate_tree") or {}
        for p in self.procs:
            ident = _ident(p)
            if ident not in prior_tree or ident in live_gate:
                continue
            if _image(p) not in GATE_CHILD_IMAGES or denied(p):
                continue
            self.gate_tree[ident] = p.create_time
            age = self.now - p.create_time
            if age <= rule.fallback_budget_s:
                self.ok(rule.key, "ORPHAN_WITHIN_BUDGET", f"orphaned gate child {p.pid} "
                        f"{age:.0f}s old", pid=p.pid)
                continue
            verdict, why = self.observe(p)
            if verdict != "STALLED":
                self.ok(rule.key, verdict, f"orphaned gate child {p.pid}: {why}", pid=p.pid)
                continue
            self.stop(rule, p, f"orphaned gate child (its gate run is gone) {age:.0f}s old and "
                      f"{why}", children_only=GATE_CHILD_IMAGES)

    def gate_restart_rule(self, rule: Rule) -> None:
        beat = self.box.gate_beat
        doc: Any = None
        try:
            doc = json.loads(beat.read_text("utf-8-sig"))
            at = _parse_iso(doc.get("at")) if isinstance(doc, dict) else None
            if at is None:
                at = beat.stat().st_mtime
        except FileNotFoundError:
            self.red(rule.key, "REFUSED", f"{beat.name} is absent: the gate was never installed "
                     f"here or writes elsewhere; a restart cannot be proven, so none is made")
            return
        except (OSError, ValueError):
            try:
                at = beat.stat().st_mtime
            except OSError:
                self.red(rule.key, "UNMEASURED", f"{beat.name} is unreadable; nothing done")
                return
        age = self.now - at
        # A FRESH BEAT IS NOT A SWEEP (workflow_gate.ps1, 2026-10-29): a run refused by a held
        # mutex stamps rc 4 and `mutex_held_runs`, so the beat stays fresh while nothing merges.
        # Its age as a SWEEP is at least the held runs times the 10-minute cadence. A live holder
        # is judged by the workflow_gate rule; this only fires when no gate run is alive at all.
        held = 0
        if isinstance(doc, dict) and doc.get("rc") == 4:
            with contextlib.suppress(TypeError, ValueError):
                held = max(0, int(doc.get("mutex_held_runs") or 0))
        age = max(age, held * GATE_CADENCE_S)
        last = max(self.restarts) if self.restarts else None
        facts = {"heartbeat_age_s": round(age), "stale_after_s": GATE_STALE_S,
                 "mutex_held_runs": held, "last_restart": _iso(last) if last else None}
        if last is not None:
            facts["restart_proved"] = at > last
        if age <= GATE_STALE_S:
            self.ok(rule.key, "FRESH", f"gate heartbeat {age:.0f}s old", **facts)
            return
        if any(matches(RULE_BY_KEY["workflow_gate"], p) for p in self.procs):
            self.ok(rule.key, "RUN_IN_PROGRESS", "heartbeat stale but a gate run is alive; the "
                    "workflow_gate rule judges it", **facts)
            return
        day = datetime.fromtimestamp(self.now, tz=UTC).date()
        today = [t for t in self.restarts if datetime.fromtimestamp(t, tz=UTC).date() == day]
        if len(today) >= MAX_RESTARTS_PER_DAY:
            self.red(rule.key, "REFUSED", f"heartbeat {age:.0f}s stale but {len(today)} restarts "
                     f"already today (max {MAX_RESTARTS_PER_DAY}); restarting again is not "
                     f"repairing it -- read logs/workflow_gate.log", **facts)
            return
        if today:
            wait = RESTART_BACKOFF_S * (2 ** (len(today) - 1))
            since = self.now - max(today)
            if since < wait:
                self.red(rule.key, "BACKOFF", f"heartbeat {age:.0f}s stale; last restart "
                         f"{since:.0f}s ago, next allowed after {wait}s", **facts)
                return
        why = f"gate heartbeat {age:.0f}s old (> {GATE_STALE_S}s) and no gate run is alive"
        if not self.apply:
            self.red(rule.key, "WOULD_RESTART", why, dry_run=True, **facts)
            return
        self.end(rule, "Quant-WorkflowGate", why)
        if self.start(rule, "Quant-WorkflowGate", why):
            self.restarts.append(self.now)

    def run(self) -> None:
        procs = self.box.procs()
        if procs is None:
            self.red("*", "UNMEASURED", "the process table is unreadable (psutil absent); "
                     "nothing is judged, nothing is stopped")
            return
        self.procs = procs
        me = os.getpid()
        self.me = {me} | ancestors(me, procs)
        for rule in RULES:
            try:
                getattr(self, f"{rule.kind}_rule")(rule)
            except Exception as exc:     # one rule's failure never silences the others
                self.red(rule.key, "ERROR", f"{type(exc).__name__}: {exc}"[:300])


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False), "utf-8")
    os.replace(tmp, path)


def _append_ledger(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size > LEDGER_ROTATE_BYTES:
            os.replace(path, path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def rules_table() -> list[dict[str, Any]]:
    return [{"key": r.key, "kind": r.kind, "identity": list(r.cmd_all) or [r.task],
             "task": r.task, "fallback_budget_s": r.fallback_budget_s,
             "budget_source": r.budget_source} for r in RULES]


def run(*, apply: bool = True, box: Box | None = None, now: float | None = None,
        report: Path = REPORT, ledger: Path = LEDGER, state: Path = STATE) -> dict[str, Any]:
    """One pass. Writes the report, appends RED rows to the ledger, keeps cross-pass state."""
    b = box or real_box()
    t = datetime.now(UTC).timestamp() if now is None else now
    prior = _read_json(state)
    prior = prior if isinstance(prior, dict) else {}
    p = Pass(b, prior, t, apply)
    if not b.windows and box is None:
        p.row("*", "UNMEASURED", "NOT_THE_BOX", "not Windows: the rules name Windows tasks and "
              "processes; nothing judged, nothing stopped")
    else:
        p.run()
    red = [r for r in p.rows if r["level"] == "RED"]
    unmeasured = [r for r in p.rows if r["level"] == "UNMEASURED"]
    status = "RED" if red else "UNMEASURED" if unmeasured else "OK"
    doc = {"schema": SCHEMA, "version": VERSION, "at": _iso(t), "host": b.host,
           "task": TASK_NAME, "applied": apply, "status": status,
           "stale_after_s": STALE_AFTER_S, "cadence_s": CADENCE_S,
           "n_red": len(red), "actions": [r for r in red if r["verdict"] in
                                          ("STOPPED", "ENDED", "STARTED", "STOP_FAILED",
                                           "END_FAILED", "START_FAILED")],
           "refusals": [r for r in red if r["verdict"] in ("REFUSED", "BACKOFF", "DEAD_OWNER")],
           "rows": p.rows, "rules": rules_table(),
           "deferred": [{"paste_line": k, "owner": v} for k, v in DEFERRED],
           "deny": [n for n, _ in DENY]}
    _write_json(report, doc)
    _append_ledger(ledger, red)
    keep = dict(p.observed)
    cutoff = t - 2 * 86400
    _write_json(state, {"at": _iso(t), "cpu": keep, "gate_tree": p.gate_tree,
                        "no_owner": p.next_no_owner,
                        "restarts": [x for x in p.restarts if x >= cutoff]})
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Closed-table self-heal for the box (no commands "
                                             "are read from anywhere; see the module docstring).")
    ap.add_argument("--dry-run", action="store_true",
                    help="decide and log every rule, act on nothing")
    args = ap.parse_args(argv)
    doc = run(apply=not args.dry_run)
    for r in doc["rows"]:
        print(f"[{r['level']:<10}] {r['rule']:<22} {r['verdict']:<16} {r['why']}")
    print(f"box_self_heal: {doc['status']} ({doc['n_red']} red) -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
