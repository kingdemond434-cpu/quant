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

WHERE IT RUNS FROM (audit HOLD of 7a01c1b09). The SYSTEM task runs the ADMIN-ONLY copy the
installer puts in C:\\ProgramData\\QuantBox\\bin (this file, ops/process_health.py and
libs/ops/alert_channels.py, the only code it loads), never the repo tree a non-admin can write. The
installed copy loads its two helpers from beside itself and nowhere else; the repo is only where it
writes its report, ledger and state (the task's working directory).

THE RULES (`RULES` below is the table; tests pin it):

    independence_intake   identity: task MT5-IndependenceIntake Running + a python whose SCRIPT
                          argument is desks\\mt5\\research\\independence_intake.py with --once,
                          under the task's cmd.exe
                          budget:   its installer's PT20M limit + 5 min (2x its --budget-s if more)
                          action:   schtasks /End; then its tree if it survived the /End
    workflow_gate         identity: powershell -File exactly
                          C:\\ProgramData\\QuantBox\\bin\\workflow_gate.ps1
                          budget:   install_unattended.ps1's 30 min limit + 5 min
                          action:   end the tree (gh/git/python children only), schtasks /End
    workflow_gate_restart identity: logs/workflow_gate.json older than 30 min, no gate run alive
                          action:   schtasks /End + /Run

    STUCK = held/running past its budget AND (its owner pid is dead, OR it made no CPU progress
    across two passes at least PROGRESS_WINDOW_S apart). A long job that is still computing is not
    an abandoned one (job_lock's own lesson: liveness vetoes age), so CPU progress always vetoes.

    EVERY ATTEMPT IS COUNTED, whatever it returned (a failed /Run, /End or stop is an attempt):
    each acting rule waits 30/60/120 min between attempts and makes at most 4 a UTC day. The attempt
    is written to the state AND the ledger BEFORE the action; a pass that cannot read its attempt
    history from either takes no action at all and pages once.

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
Remote Control session, the miners/recorders/moat, the research organs other owners run (promoter,
shadow_forward, scalp_shadow, certifier_launcher, hourly_cycle, #526's jobs), and this watchdog
itself and its ancestors. A process whose command line or image CANNOT BE READ is treated as
denied: what cannot be identified is never touched. A process that is on neither list is never
stopped: there is no default action.

RED-LOGGED. Every action and every refusal is a RED row in desks/mt5/reports/BOX_SELF_HEAL.json
(this pass) and appended to desks/mt5/logs/box_self_heal.jsonl (the ledger). The report carries its
own `at`, and `check_desk_health.py` and the organ contract both read it, so a watchdog that
stopped running shows RED rather than silence. When a pass STOPS, ENDS or STARTS anything it pages
zuck through libs/ops/alert_channels.send_all (ntfy on the box); a FAILED action, the daily cap and
an unreadable attempt history page at most once a UTC day each. A dry run never pages. Every stop
of the intake (a research organ) publishes a two-sided missed-growth line on the report.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import ntpath
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
#: In the repo this file is ops/box_self_heal.py. The installed copy (C:\ProgramData\QuantBox\bin)
#: is not, and then the repo is the task's working directory (set by the admin installer).
_IN_REPO = _HERE.name == "ops" and (_HERE.parent / "desks" / "mt5").is_dir()
ROOT = _HERE.parent if _IN_REPO else Path.cwd()
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "BOX_SELF_HEAL.json"
LEDGER = DESK / "logs" / "box_self_heal.jsonl"
#: Cross-pass memory (CPU baselines, gate tree, attempts). Under logs/, which the box sync ignores.
STATE = DESK / "logs" / "box_self_heal_state.json"
#: The gate's own folder (ops/box/workflow_gate.ps1, $Root). A literal, never an argument.
QUANTBOX_LOGS = Path(r"C:\ProgramData\QuantBox\logs")
GATE_BEAT = QUANTBOX_LOGS / "workflow_gate.json"

SCHEMA = "box_self_heal/1"
VERSION = "boxheal-2026-10-29-b"
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

#: Attempts: the first may happen at once; each later one by the same rule waits twice as long as
#: the one before (30/60/120 min); never more than MAX_ATTEMPTS_PER_DAY per rule per UTC day.
GATE_CADENCE_S = 10 * 60
GATE_STALE_S = 3 * GATE_CADENCE_S
RESTART_BACKOFF_S = 30 * 60
MAX_RESTARTS_PER_DAY = 4
MAX_ATTEMPTS_PER_DAY = MAX_RESTARTS_PER_DAY

#: THE FREEZE WINDOW (audit HOLD of 7a01c1b09). From the first suspend to the last kill. A tree
#: left suspended is a wedge this file made, so the window is short and the task's limit
#: (install_box_self_heal_task.ps1, 15 min) is far above a pass's worst case (five 60 s schtasks
#: calls, two 10 s waits, one page: about 6.5 min).
FREEZE_MAX_S = 5.0
SCHTASKS_TIMEOUT_S = 60

LEDGER_ROTATE_BYTES = 5 * 1024 * 1024
MISSED_GROWTH_HISTORY = 50


# ------------------------------------------------------------------------------ the closed table
@dataclass(frozen=True)
class Rule:
    """One allowlisted thing this watchdog may act on. Literal in code; never loaded."""

    key: str
    kind: str                      # "task" | "gate" | "gate_restart"
    #: The identity, for the report (`matches` checks it exactly, per rule).
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

#: The intake's exact SCRIPT argument (path-normalised, lower-case), and the flag its task passes.
INTAKE_SCRIPT = r"desks\mt5\research\independence_intake.py"
INTAKE_ONCE = "--once"
#: The gate's exact -File argument (install_unattended.ps1's admin-only copy).
GATE_FILE = r"c:\programdata\quantbox\bin\workflow_gate.ps1"

RULES: tuple[Rule, ...] = (
    Rule("independence_intake", "task", (INTAKE_SCRIPT, INTAKE_ONCE), _PY,
         task="MT5-IndependenceIntake", fallback_budget_s=20 * 60 + 5 * 60,
         budget_source="install_independence_intake_task.ps1 ExecutionTimeLimit PT20M + 5 min; "
                       "its own --budget-s if larger",
         why="registered with a 20 minute limit and found hung far past it"),
    Rule("workflow_gate", "gate", ("-File", GATE_FILE), _PS, task="Quant-WorkflowGate",
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
#: The orphan stop is its own attempt budget (a gate wedge and its orphans are two incidents).
ORPHAN_KEY = "workflow_gate_orphan"

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
    "git-credential-manager.exe", "git-credential-manager", "sh.exe", "sh",
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
    # The research organs other owners run and keep alive (audit HOLD of 7a01c1b09): the
    # promoter and certifier launcher mint and move capital state, the forward clocks are
    # time-series that a kill corrupts, and the hourly cycle is the clock of everything else.
    ("promoter", "the promoter: it moves sleeves between tiers"),
    ("shadow_forward", "a forward clock: a kill tears its series"),
    ("scalp_shadow", "a forward clock: a kill tears its series"),
    ("certifier_launcher", "the certifier's launcher (#526 NEVER_STOP's lane)"),
    ("hourly_cycle", "the hourly cycle: the clock every other organ runs on"),
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

#: The kernel's own pseudo-processes have no command line by definition. They are never a target
#: (no rule matches them) and are the root of every tree, so their empty command line is not
#: "unreadable". Nothing else is exempt.
_KERNEL_PSEUDO: frozenset[tuple[int, str]] = frozenset({(0, "system idle process"),
                                                        (4, "system")})


# ------------------------------------------------------------------------------------- the facts
@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    name: str
    cmdline: str
    create_time: float
    cpu_s: float
    #: The argv as the OS reports it (psutil). Empty: split from `cmdline`, Windows-style.
    argv: tuple[str, ...] = ()


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace('"', " ").replace("'", " ")).strip().lower()


def _image(p: Proc) -> str:
    return ntpath.basename((p.name or "").lower())


def _argv(p: Proc) -> list[str]:
    if p.argv:
        return [str(a) for a in p.argv]
    try:
        toks = shlex.split(p.cmdline or "", posix=False)
    except ValueError:
        toks = (p.cmdline or "").split()
    return [t.strip('"') for t in toks]


def _norm_path(tok: str) -> str:
    t = (tok or "").strip().strip('"').replace("/", "\\")
    return ntpath.normpath(t).lower() if t else ""


def unreadable(p: Proc) -> str | None:
    """Why `p` cannot be identified, or None. An empty image or command line is not "nothing to
    match": it is a process this file cannot see, and what it cannot see it never touches."""
    if (p.pid, _image(p)) in _KERNEL_PSEUDO:
        return None
    if not (p.name or "").strip():
        return "its image name is unreadable"
    if not (p.cmdline or "").strip() and not any(str(a).strip() for a in p.argv):
        return "its command line is unreadable or empty"
    return None


def denied(p: Proc) -> str | None:
    """Why `p` may never be touched, or None. Checked before any allowlist match."""
    u = unreadable(p)
    if u:
        return f"unidentifiable: {u}"
    text = f"{_image(p)} {_fold(p.cmdline or ' '.join(p.argv))}"
    for needle, why in DENY:
        if needle in text:
            return f"{needle!r}: {why}"
    return None


#: Python's own options that take a value (the next token is not the script).
_PY_OPT_ARG = frozenset({"-W", "-X", "-Q"})


def _py_script(argv: Sequence[str]) -> tuple[str, list[str]] | None:
    """(normalised script path, its arguments) for `python [options] script args`, or None when
    python runs `-m`/`-c`/stdin or nothing at all."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in _PY_OPT_ARG:
            i += 2
            continue
        if a in ("-m", "-c", "-"):
            return None
        if a.startswith("-"):                   # a flag, or -Wignore / -Xutf8 (value attached)
            i += 1
            continue
        return _norm_path(a), list(argv[i + 1:])
    return None


def _is_intake_script(path: str) -> bool:
    return path == INTAKE_SCRIPT or path.endswith("\\" + INTAKE_SCRIPT)


def _image_ok(rule: Rule, p: Proc) -> bool:
    img = _image(p)
    return not rule.images or img in rule.images or img.removesuffix(".exe") in rule.images


def matches(rule: Rule, p: Proc) -> bool:
    """`p` is the process `rule` names, EXACTLY: its image and its identifying argument (never a
    substring of the command line -- a pytest run naming the file must never match)."""
    if not rule.cmd_all or not _image_ok(rule, p):
        return False
    argv = _argv(p)
    if rule.key == "independence_intake":
        got = _py_script(argv)
        return got is not None and _is_intake_script(got[0]) and INTAKE_ONCE in got[1]
    if rule.key == "workflow_gate":
        for i, a in enumerate(argv[1:], start=1):
            if a.lower() in ("-file", "/file"):
                return i + 1 < len(argv) and _norm_path(argv[i + 1]) == GATE_FILE
        return False
    return False


def allowlisted(p: Proc) -> Rule | None:
    """The rule `p` is on, or None. A denied process is on no rule, whatever it matches."""
    if denied(p):
        return None
    return next((r for r in RULES if matches(r, p)), None)


def _parent(p: Proc, procs: Sequence[Proc]) -> Proc | None:
    """`p`'s parent, only if it is older than `p` (a recycled ppid names a newer process)."""
    if p.ppid == p.pid:
        return None
    par = next((q for q in procs if q.pid == p.ppid), None)
    return par if par is not None and par.create_time <= p.create_time else None


def intake_under_its_task(p: Proc, procs: Sequence[Proc]) -> bool:
    """The task runs `cmd.exe /d /s /c ""python" ... independence_intake.py --once ..."`
    (install_independence_intake_task.ps1): the intake python is a child of THAT cmd.exe."""
    par = _parent(p, procs)
    if par is None or _image(par) not in ("cmd.exe", "cmd"):
        return False
    text = _fold(par.cmdline).replace("/", "\\")
    return INTAKE_SCRIPT in text and INTAKE_ONCE in text.split()


def descendants(pid: int, procs: Sequence[Proc]) -> list[Proc]:
    """Every process below `pid`, by ppid AND create time: a child is never older than its parent,
    so a process whose ppid names a newer process (a recycled pid) is not in the tree."""
    kids: dict[int, list[Proc]] = {}
    for p in procs:
        kids.setdefault(p.ppid, []).append(p)
    root = next((p for p in procs if p.pid == pid), None)
    out: list[Proc] = []
    stack: list[tuple[int, float]] = [(pid, root.create_time if root else float("-inf"))]
    seen = {pid}
    while stack:
        cur, born = stack.pop()
        for k in kids.get(cur, []):
            if k.pid not in seen and k.create_time >= born:
                seen.add(k.pid)
                out.append(k)
                stack.append((k.pid, k.create_time))
    return out


def ancestors(pid: int, procs: Sequence[Proc]) -> set[int]:
    """Every live ancestor of `pid`, walking up only to a parent OLDER than its child."""
    by = {p.pid: p for p in procs}
    out: set[int] = set()
    cur = by.get(pid)
    while cur is not None and cur.ppid not in out and cur.ppid != cur.pid:
        par = by.get(cur.ppid)
        if par is None or par.create_time > cur.create_time:
            break
        out.add(par.pid)
        cur = par
    return out


def _ident(p: Proc) -> str:
    return f"{p.pid}:{round(p.create_time, 1)}"


def tree_members(p: Proc, procs: Sequence[Proc]) -> dict[str, float]:
    return {_ident(m): m.cpu_s for m in (p, *descendants(p.pid, procs))}


def tree_cpu(p: Proc, procs: Sequence[Proc]) -> float:
    return sum(tree_members(p, procs).values())


def progress(p: Proc, procs: Sequence[Proc], prior: Mapping[str, Any], now: float
             ) -> tuple[str, str]:
    """("STALLED" | "PROGRESSING" | "OBSERVING", why) for `p`'s whole tree, across passes.

    MONOTONE, PER MEMBER (audit HOLD of 7a01c1b09): the tree's CPU is the sum of each member's own
    advance, so a child that exits takes its CPU out of the sum but never makes the delta negative
    -- and a member that exited since the baseline is itself the tree doing work."""
    members = tree_members(p, procs)
    cpu = sum(members.values())
    prev = prior.get(_ident(p)) if isinstance(prior, Mapping) else None
    if not isinstance(prev, Mapping):
        return "OBSERVING", f"first observation of pid {p.pid} (tree cpu {cpu:.1f}s)"
    try:
        dt = now - float(prev["at"])
        pm = prev.get("members")
        if isinstance(pm, Mapping):
            base = {str(k): float(v) for k, v in pm.items()}
            gone = sorted(k for k in base if k not in members)
            dcpu = sum(max(0.0, c - base[k]) if k in base else c for k, c in members.items())
        else:
            gone = []
            dcpu = cpu - float(prev["cpu_s"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return "OBSERVING", "the prior observation is unreadable; re-baselining"
    if dt > PROGRESS_MAX_GAP_S:
        return "OBSERVING", f"the prior observation is {dt:.0f}s old; re-baselining"
    if dt < PROGRESS_WINDOW_S:
        return "OBSERVING", f"only {dt:.0f}s since the baseline (need {PROGRESS_WINDOW_S}s)"
    if gone:
        return "PROGRESSING", f"{len(gone)} tree member(s) exited in {dt:.0f}s: the tree is working"
    if dcpu < 0:
        return "PROGRESSING", f"tree cpu fell {dcpu:.1f}s in {dt:.0f}s: a member exited"
    if dcpu < CPU_EPS_S:
        return "STALLED", f"tree cpu moved {dcpu:.2f}s in {dt:.0f}s (< {CPU_EPS_S}s)"
    return "PROGRESSING", f"tree cpu moved {dcpu:.1f}s in {dt:.0f}s"


# --------------------------------------------------------------------------------- the actuators
Verify = Callable[[Proc], str | None]


@dataclass
class Box:
    """Everything the pass reads or does to the machine. Tests swap every field."""

    procs: Callable[[], list[Proc] | None]
    task_running: Callable[[str], bool | None]
    end_task: Callable[[str], dict[str, Any]]
    run_task: Callable[[str], dict[str, Any]]
    #: kill(target, table, allowed_images, verify): freeze, re-verify and end the tree
    #: (`_kill_tree`). `verify` re-checks the LIVE target's identity; None means it still matches.
    kill: Callable[[Proc, Sequence[Proc], frozenset[str] | None, Verify | None], dict[str, Any]]
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
            argv = tuple(str(a) for a in (info.get("cmdline") or []))
            # An AccessDenied cmdline arrives as None -> "" here, and `unreadable` denies it.
            rows.append(Proc(int(info["pid"]), int(info.get("ppid") or 0),
                             str(info.get("name") or ""), " ".join(argv),
                             float(info.get("create_time") or 0.0), cpu, argv))
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
        r = subprocess.run(argv, capture_output=True, text=True, timeout=SCHTASKS_TIMEOUT_S,
                           check=False)
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


def _dep(name: str, repo_rel: str) -> Path | None:
    """Where a helper this file loads lives. The installed copy loads ONLY its admin-only sibling
    (install_box_self_heal_task.ps1 copies it there): never the repo tree, which a non-admin can
    write and a SYSTEM task must not execute from."""
    beside = _HERE / name
    if not _IN_REPO:
        return beside if beside.is_file() else None
    repo = ROOT / repo_rel
    return repo if repo.is_file() else None


def _load(modname: str, path: Path | None) -> Any:
    mod = sys.modules.get(modname)
    if mod is not None:
        return mod
    if path is None:
        raise ImportError(modname)
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise ImportError(modname)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(modname, None)
        raise
    return mod


def _running_states() -> frozenset[str]:
    """process_health's locale-aware Running set (schtasks prints the state in the OS language).

    Loaded by path: `desks/mt5/ops` is a regular package called `ops`, and wherever
    desks/mt5 is on sys.path it shadows this repo's `ops`."""
    name = "_box_self_heal_process_health"
    try:
        return frozenset(_load(name, _dep("process_health.py", "ops/process_health.py"))
                         .STATE_RUNNING)
    except Exception:
        sys.modules.pop(name, None)
        return frozenset({"running"})


def _live_proc(pr: Any, ppid: int | None = None) -> Proc:
    """A psutil process re-read NOW. Raises on anything it cannot read."""
    argv = tuple(str(a) for a in (pr.cmdline() or []))
    name = str(pr.name() or "")
    par = int(pr.ppid()) if ppid is None else ppid
    return Proc(int(pr.pid), par, name, " ".join(argv), float(pr.create_time()), 0.0, argv)


def _kill_tree(target: Proc, procs: Sequence[Proc],
               allowed_images: frozenset[str] | None = None,
               verify: Verify | None = None, *,
               clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """RE-READ the target live, FREEZE the tree, then end it bottom-up -- or resume all of it.

    The same pattern job_lock_health uses: a busy owner keeps spawning, so a tree enumerated once
    and killed top-down leaves the children it started in between as orphans. The target is
    re-read from the LIVE table first (pid, create time, image, command line, deny list and the
    rule's own identity). Each round's new children are identified and deny-checked BEFORE they
    are suspended; the tree is re-enumerated until no new member appears; then every member is
    killed deepest-first, the target last.

    THAW IS UNCONDITIONAL (audit HOLD of 7a01c1b09). Whatever ends this function -- a refusal, a
    vanished child, AccessDenied, an OSError (WinError 299 from a half-read process), a
    RuntimeError from cmdline() or name(), anything -- every process it suspended and did not
    kill is resumed in `finally`. The freeze window is bounded by FREEZE_MAX_S.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return {"ok": False, "target_gone": False,
                "why": "psutil absent: cannot verify identity, nothing stopped"}
    frozen: list[Any] = []
    killed: set[int] = set()
    t0 = clock()

    def refuse(why: str) -> dict[str, Any]:
        return {"ok": False, "target_gone": False, "why": f"{why}; tree resumed, nothing stopped"}

    def target_alive() -> bool:
        try:
            return abs(float(psutil.Process(target.pid).create_time())
                       - target.create_time) <= 1.0
        except psutil.NoSuchProcess:
            return False
        except Exception:
            return True                     # cannot tell: never claim it is gone

    def bad_member(k: Any) -> str | None:
        kp = _live_proc(k, ppid=target.pid)
        if kp.create_time < target.create_time:
            return None                     # not a child (a recycled ppid); never frozen
        return denied(kp) or (None if allowed_images is None or _image(kp) in allowed_images
                              else f"image {_image(kp)!r} is not allowed in this tree")

    try:
        live = psutil.Process(target.pid)
        tp = _live_proc(live)
        if abs(tp.create_time - target.create_time) > 1.0:
            return refuse("pid was reused since it was judged")
        why = denied(tp) or (verify(tp) if verify is not None else None)
        if why:
            return refuse(f"the live target {target.pid} no longer qualifies ({why})")
        frozen_pids: set[int] = set()
        for k in live.children(recursive=True):        # deny-checked BEFORE the first freeze
            bad = bad_member(k)
            if bad:
                return refuse(f"descendant {k.pid} may not be stopped ({bad})")
        live.suspend()
        frozen.append(live)
        frozen_pids.add(live.pid)
        for _round in range(5):
            if clock() - t0 > FREEZE_MAX_S:
                return refuse(f"the freeze took over {FREEZE_MAX_S:.0f}s")
            fresh = []
            for k in live.children(recursive=True):
                if k.pid in frozen_pids:
                    continue
                if float(k.create_time()) < target.create_time:
                    continue
                fresh.append(k)
            if not fresh:
                break
            for k in fresh:                             # identified BEFORE it is suspended
                bad = bad_member(k)
                if bad:
                    return refuse(f"descendant {k.pid} may not be stopped ({bad})")
                with contextlib.suppress(psutil.NoSuchProcess):
                    k.suspend()
                    frozen.append(k)
                    frozen_pids.add(k.pid)
        else:
            return refuse("the tree kept growing while frozen")
        if clock() - t0 > FREEZE_MAX_S:
            return refuse(f"the freeze took over {FREEZE_MAX_S:.0f}s")
        for k in reversed(frozen):                 # deepest (latest found) first, target last
            with contextlib.suppress(psutil.NoSuchProcess):
                k.kill()
            killed.add(k.pid)
        gone, alive = psutil.wait_procs(frozen, timeout=10)
        still = target_alive()
        return {"ok": not alive and not still, "target_gone": not still,
                "killed": sorted(p.pid for p in gone),
                "survived": sorted(p.pid for p in alive), "frozen_first": True}
    except psutil.NoSuchProcess:
        still = target_alive()
        if still:
            return refuse(f"a member of {target.pid}'s tree vanished mid-stop while the target "
                          f"is still alive")
        return {"ok": True, "target_gone": True, "why": "already gone", "killed": []}
    except psutil.AccessDenied:
        return refuse("access denied (the task must run as SYSTEM)")
    except Exception as exc:                       # WinError 299, RuntimeError, anything
        return refuse(f"{type(exc).__name__}: {exc}"[:200])
    finally:
        for fp in reversed(frozen):
            if fp.pid in killed:
                continue
            with contextlib.suppress(Exception):
                fp.resume()


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


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()


#: The verdicts of an action that was TAKEN. A failed one is still an attempt.
ACTION_VERDICTS = frozenset({"STOPPED", "ENDED", "STARTED", "STOP_FAILED", "END_FAILED",
                             "START_FAILED"})
FAILED_VERDICTS = frozenset({"STOP_FAILED", "END_FAILED", "START_FAILED"})


def _attempts_from(raw: Any) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    if isinstance(raw, Mapping):
        for k, v in raw.items():
            if isinstance(v, list):
                out[str(k)] = [float(x) for x in v
                               if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return out


class Pass:
    """One pass's decisions. Every act and refusal becomes a RED row; nothing is silent."""

    def __init__(self, box: Box, prior: Mapping[str, Any], now: float, apply: bool, *,
                 attempts: Mapping[str, list[float]] | None = None,
                 history_known: bool = True,
                 persist: Callable[[Pass, dict[str, Any]], bool] | None = None) -> None:
        self.box, self.prior, self.now, self.apply = box, prior, now, apply
        self.rows: list[dict[str, Any]] = []
        self.observed: dict[str, dict[str, Any]] = {}
        self.gate_tree: dict[str, float] = {}
        self.attempts: dict[str, list[float]] = {k: list(v) for k, v in (attempts or {}).items()}
        self.history_known = history_known
        self.persist = persist
        self.no_owner: dict[str, float] = {
            str(k): float(v) for k, v in (prior.get("no_owner") or {}).items()
            if isinstance(v, (int, float))}
        self.next_no_owner: dict[str, float] = {}
        self.procs: list[Proc] = []
        self.me: set[int] = set()
        self.missed_growth: list[dict[str, Any]] = []
        #: rows already written to the ledger by `persist` (the ATTEMPT rows)
        self.ledgered: set[int] = set()

    @property
    def restarts(self) -> list[float]:
        return self.attempts.get("workflow_gate_restart", [])

    def row(self, rule: str, level: str, verdict: str, why: str, **extra: Any) -> None:
        self.rows.append({"at": _iso(self.now), "rule": rule, "level": level,
                          "verdict": verdict, "why": why, **extra})

    def red(self, rule: str, verdict: str, why: str, **extra: Any) -> None:
        self.row(rule, "RED", verdict, why, **extra)

    def ok(self, rule: str, verdict: str, why: str, **extra: Any) -> None:
        self.row(rule, "OK", verdict, why, **extra)

    def observe(self, p: Proc) -> tuple[str, str]:
        members = tree_members(p, self.procs)
        self.observed[_ident(p)] = {"at": self.now, "cpu_s": sum(members.values()),
                                    "members": members}
        return progress(p, self.procs, self.prior.get("cpu") or {}, self.now)

    # -- the attempt budget: checked before, and recorded BEFORE, any action
    def may_attempt(self, key: str, **facts: Any) -> bool:
        if not self.history_known:
            self.red(key, "REFUSED", "the attempt history is unreadable (state AND ledger): "
                     "how many attempts were made today is unknown, so none is made",
                     history="UNREADABLE", **facts)
            return False
        day = _day(self.now)
        today = [t for t in self.attempts.get(key, []) if _day(t) == day]
        if len(today) >= MAX_ATTEMPTS_PER_DAY:
            self.red(key, "REFUSED", f"{len(today)} attempts already today (max "
                     f"{MAX_ATTEMPTS_PER_DAY}); restarting again is not repairing it -- read "
                     f"its log", capped=True, **facts)
            return False
        if today:
            wait = RESTART_BACKOFF_S * (2 ** (len(today) - 1))
            since = self.now - max(today)
            if since < wait:
                self.red(key, "BACKOFF", f"last attempt {since:.0f}s ago, next allowed after "
                         f"{wait}s ({len(today)} today)", **facts)
                return False
        return True

    def record_attempt(self, key: str, action: str, **facts: Any) -> bool:
        """Count the attempt and make it DURABLE before acting. If neither the state nor the
        ledger takes it, the action is not taken: an uncounted attempt is an uncapped one."""
        self.attempts.setdefault(key, []).append(self.now)
        row = {"at": _iso(self.now), "ts": self.now, "rule": key, "level": "RED",
               "verdict": "ATTEMPT", "why": f"about to {action}", "action": action, **facts}
        self.rows.append(row)
        durable = True if self.persist is None else self.persist(self, row)
        if durable:
            self.ledgered.add(id(row))
            return True
        self.attempts[key].remove(self.now)
        self.red(key, "REFUSED", f"the attempt to {action} could not be recorded (state and "
                 f"ledger both unwritable); nothing done", **facts)
        return False

    def attempt(self, key: str, action: str, **facts: Any) -> bool:
        return self.may_attempt(key, **facts) and self.record_attempt(key, action, **facts)

    # -- the one way anything is stopped
    def stop(self, rule: Rule, p: Proc, why: str, *, children_only: frozenset[str] | None = None,
             verify: Verify | None = None, key: str | None = None, counted: bool = False
             ) -> bool:
        key = key or rule.key
        if p.pid in self.me:
            self.red(key, "REFUSED", "that is this watchdog or its ancestor", pid=p.pid)
            return False
        why_denied = denied(p)
        if why_denied:
            self.red(key, "REFUSED", f"pid {p.pid} is on the deny list: {why_denied}",
                     pid=p.pid, cmdline=p.cmdline[:300])
            return False
        by_pid = {q.pid: q for q in self.procs}
        for a in sorted(ancestors(p.pid, self.procs)):
            anc = by_pid.get(a)
            if anc is not None and denied(anc):
                self.red(key, "REFUSED", f"ancestor {a} is on the deny list "
                         f"({denied(anc)}); a protected tree is never cut into",
                         pid=p.pid, ancestor=a, cmdline=anc.cmdline[:300])
                return False
        for d in descendants(p.pid, self.procs):
            bad = denied(d) or (None if children_only is None or _image(d) in children_only
                                else f"image {_image(d)!r} is not a gate child")
            if bad or d.pid in self.me:
                self.red(key, "REFUSED", f"descendant {d.pid} may not be stopped: "
                         f"{bad or 'this watchdog'}; the whole tree is left alone",
                         pid=p.pid, descendant=d.pid, cmdline=d.cmdline[:300])
                return False
        if not self.apply:
            self.red(key, "WOULD_STOP", why, pid=p.pid, cmdline=p.cmdline[:300], dry_run=True)
            return False
        if not counted and not self.attempt(key, f"stop pid {p.pid}", pid=p.pid):
            return False
        res = self.box.kill(p, self.procs, children_only, verify)
        gone = bool(res.get("ok")) and res.get("target_gone") is True
        if gone:
            # VERIFIED GONE, NOT REPORTED GONE: the target must be absent from a fresh table.
            again = self.box.procs()
            if again is None or any(q.pid == p.pid and abs(q.create_time - p.create_time) < 1
                                    for q in again):
                gone = False
                res = {**res, "verify": "the target is still in the live table (or the table "
                                        "is unreadable)"}
        self.red(key, "STOPPED" if gone else "STOP_FAILED", why, pid=p.pid,
                 cmdline=p.cmdline[:300], result=res)
        return gone

    def end(self, rule: Rule, task: str, why: str, *, key: str | None = None) -> bool:
        key = key or rule.key
        if task not in ENDABLE_TASKS:
            self.red(key, "REFUSED", f"{task} is not an endable task")
            return False
        if not self.apply:
            self.red(key, "WOULD_END", why, task=task, dry_run=True)
            return False
        res = self.box.end_task(task)
        self.red(key, "ENDED" if res.get("rc") == 0 else "END_FAILED", why, task=task,
                 result=res)
        return res.get("rc") == 0

    def start(self, rule: Rule, task: str, why: str) -> bool:
        if task not in RUNNABLE_TASKS:
            self.red(rule.key, "REFUSED", f"{task} is not a runnable task")
            return False
        res = self.box.run_task(task)
        self.red(rule.key, "STARTED" if res.get("rc") == 0 else "START_FAILED", why, task=task,
                 result=res, attempt=True)
        return res.get("rc") == 0

    def intake_missed_growth(self, p: Proc | None, age_s: float | None, budget_s: float | None,
                             how: str, ok: bool) -> None:
        """THE INTAKE STOP'S TWO-SIDED LINE. independence_intake is a research organ: stopping it
        throws away the wall its run spent (the cost: no verdict from this run), and frees the
        task slot the hung run held past its budget (the benefit: MT5-IndependenceIntake is
        IgnoreNew, so every scheduled run in that time was skipped). Both in their own units;
        neither priced in E[log W], so UNMEASURED -- never a clean zero. Published on the report,
        where research/missed_growth.py's organ reader can carry it."""
        lost = round(age_s, 1) if age_s is not None else None
        freed = round(max(0.0, age_s - budget_s), 1) if age_s is not None and budget_s else None
        self.missed_growth.append({
            "day": _day(self.now), "at": _iso(self.now), "rail": "box_self_heal_intake_stop",
            "kind": "opportunity_cost", "value": None, "verdict": "UNMEASURED",
            "units": "intake wall-seconds discarded (cost) / task-slot seconds held past budget "
                     "and freed (benefit)",
            "reason": how, "applied_ok": ok, "pid": p.pid if p else None, "lost_s": lost,
            "cost": {"intake_wall_s_discarded": lost,
                     "basis": "the stopped run's age: it published no intake verdict"},
            "benefit": {"slot_s_freed_past_budget": freed, "budget_s": budget_s,
                        "basis": "the run held the IgnoreNew task slot this long past its budget; "
                                 "the next scheduled run can start"},
            "why": (f"MT5-IndependenceIntake {how}: {lost if lost is not None else '?'}s of intake "
                    f"wall discarded against {freed if freed is not None else 'UNMEASURED'}s of "
                    f"held slot freed; the E[log W] price of either side is not measured")})

    # -- rule kinds
    def task_rule(self, rule: Rule) -> None:
        assert rule.task is not None
        mine = [p for p in self.procs if matches(rule, p) and not denied(p)
                and intake_under_its_task(p, self.procs)]
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
                        f"{' '.join(rule.cmd_all)} process; confirming next pass")
                return
            why = (f"{rule.task} has read Running for {self.now - first:.0f}s with no "
                   f"{' '.join(rule.cmd_all)} process alive (dead owner)")
            if not self.apply:
                self.end(rule, rule.task, why)
                return
            if self.attempt(rule.key, f"end {rule.task}", task=rule.task):
                ok = self.end(rule, rule.task, why)
                self.intake_missed_growth(None, None, None, "ended with no owner alive", ok)
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
        if not self.apply:
            self.end(rule, rule.task, reason)
            return
        if not self.attempt(rule.key, f"end {rule.task} (and its tree if it survives)", **facts):
            return
        ok = self.end(rule, rule.task, reason)
        again = self.box.procs() or []
        if any(p.pid == oldest.pid and abs(p.create_time - oldest.create_time) < 1
               for p in again):
            self.procs = again
            # The cmd.exe /End killed is gone, so the survivor is judged by its own identity:
            # the same pid, create time and exact script argument judged above.
            ok = self.stop(rule, oldest, reason + "; it survived schtasks /End", counted=True,
                           verify=lambda q: None if matches(rule, q) else "no longer the intake")
        self.intake_missed_growth(oldest, age, budget, "stopped past its budget", ok)

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
            if self.stop(rule, root, reason, children_only=GATE_CHILD_IMAGES,
                         verify=lambda q: None if matches(rule, q) else "no longer the gate"):
                self.end(rule, "Quant-WorkflowGate", reason)
        # ORPHANS: a gh/git/python we SAW inside a gate tree last pass, now with no gate above it.
        # The tree was walked by ppid AND create time, so a recycled ppid never put a stranger in.
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
                self.ok(ORPHAN_KEY, "ORPHAN_WITHIN_BUDGET", f"orphaned gate child {p.pid} "
                        f"{age:.0f}s old", pid=p.pid)
                continue
            verdict, why = self.observe(p)
            if verdict != "STALLED":
                self.ok(ORPHAN_KEY, verdict, f"orphaned gate child {p.pid}: {why}", pid=p.pid)
                continue
            self.stop(rule, p, f"orphaned gate child (its gate run is gone) {age:.0f}s old and "
                      f"{why}", children_only=GATE_CHILD_IMAGES, key=ORPHAN_KEY,
                      verify=lambda q: None if _image(q) in GATE_CHILD_IMAGES
                      else "no longer a gate child image")

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
        why = f"gate heartbeat {age:.0f}s old (> {GATE_STALE_S}s) and no gate run is alive"
        if not self.apply:
            if self.may_attempt(rule.key, **facts):
                self.red(rule.key, "WOULD_RESTART", why, dry_run=True, **facts)
            return
        # COUNTED AND RECORDED BEFORE /End and /Run, whatever they return (audit HOLD).
        if not self.attempt(rule.key, "end and run Quant-WorkflowGate", **facts):
            return
        self.end(rule, "Quant-WorkflowGate", why)
        self.start(rule, "Quant-WorkflowGate", why)

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


# ------------------------------------------------------------------------------- the durable side
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _read_state(path: Path) -> tuple[str, dict[str, Any]]:
    """("ok" | "absent" | "unreadable", doc). A state that exists and cannot be read is NOT a
    fresh start: it is a lost attempt count."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return "absent", {}
    except (OSError, ValueError):
        return "unreadable", {}
    if not isinstance(doc, dict):
        return "unreadable", {}
    if doc.get("history") == "UNREADABLE":
        return "unreadable", doc
    return "ok", doc


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


def attempts_from_ledger(ledger: Path, since: float) -> dict[str, list[float]] | None:
    """Rebuild the attempt count from the ledger (and its rotated `.1`), or None when it cannot
    be read. Absent is an empty history (an attempt always writes a row); a torn LAST line is a
    crash mid-append and is skipped; any other unparseable line is an unreadable ledger."""
    out: dict[str, list[float]] = {}
    for path in (ledger.with_suffix(ledger.suffix + ".1"), ledger):
        try:
            lines = path.read_text("utf-8").splitlines()
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return None
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                if i == len(lines) - 1:
                    continue
                return None
            if not isinstance(r, dict):
                return None
            ts = r.get("ts")
            if not isinstance(ts, (int, float)) or isinstance(ts, bool):
                ts = _parse_iso(r.get("at"))
            if ts is None or ts < since:
                continue
            rule = str(r.get("rule") or "")
            # An ATTEMPT row is the record; a STARTED/START_FAILED row from before ATTEMPT rows
            # existed (no `attempt` key) was one restart attempt.
            if r.get("verdict") == "ATTEMPT" or (
                    rule == "workflow_gate_restart" and not r.get("attempt")
                    and r.get("verdict") in ("STARTED", "START_FAILED")):
                out.setdefault(rule, []).append(float(ts))
    return out


def rules_table() -> list[dict[str, Any]]:
    return [{"key": r.key, "kind": r.kind, "identity": list(r.cmd_all) or [r.task],
             "task": r.task, "fallback_budget_s": r.fallback_budget_s,
             "budget_source": r.budget_source} for r in RULES]


#: Verdicts that page zuck every time: something was stopped, ended or started. A FAILED action
#: pages once a UTC day per rule and verdict; so does the daily cap and an unreadable history.
PAGE_VERDICTS = frozenset({"STOPPED", "ENDED", "STARTED", *FAILED_VERDICTS})


def _send_alert(title: str, body: str) -> dict[str, Any]:
    """libs/ops/alert_channels.send_all (ntfy on the box). Loaded by path from the admin-only copy
    beside the installed watchdog, or from the repo when run from the repo."""
    mod = _load("_box_self_heal_alert_channels",
                _dep("alert_channels.py", "libs/ops/alert_channels.py"))
    res: dict[str, Any] = mod.send_all(title, body,
                                       config=ROOT / "data" / "secrets" / "alert_channels.json",
                                       ledger=ROOT / "data" / "alert_delivery.jsonl")
    return res


def _once_key(r: Mapping[str, Any]) -> str | None:
    """The once-a-day key of a row that pages at most daily, or None for one that always pages."""
    v = r.get("verdict")
    if v in FAILED_VERDICTS:
        return f"{r.get('rule')}:{v}"
    if v == "REFUSED" and r.get("capped"):
        return f"{r.get('rule')}:CAPPED"
    if v == "REFUSED" and r.get("history") == "UNREADABLE":
        return "*:HISTORY_UNREADABLE"
    return None


def _pages(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in rows if r.get("verdict") in PAGE_VERDICTS or _once_key(r)]


def run(*, apply: bool = True, box: Box | None = None, now: float | None = None,
        report: Path = REPORT, ledger: Path = LEDGER, state: Path = STATE,
        alert: Callable[[str, str], Any] | None = None) -> dict[str, Any]:
    """One pass. Writes the report, appends RED rows to the ledger, keeps cross-pass state, and
    pages zuck when it acted (failures, the cap and a lost history at most once a UTC day)."""
    b = box or real_box()
    t = datetime.now(UTC).timestamp() if now is None else now
    cutoff = t - 2 * 86400
    status, prior = _read_state(state)
    history_known = True
    history_source = "state"
    if status == "ok":
        attempts = _attempts_from(prior.get("attempts"))
        legacy = [float(x) for x in (prior.get("restarts") or [])
                  if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if legacy:
            attempts.setdefault("workflow_gate_restart", [])
            attempts["workflow_gate_restart"] = sorted(
                set(attempts["workflow_gate_restart"]) | set(legacy))
    else:
        rebuilt = attempts_from_ledger(ledger, cutoff)
        history_source = "ledger" if rebuilt is not None else "UNREADABLE"
        if status == "absent" and rebuilt is not None and not rebuilt:
            history_source = "fresh"
        history_known = rebuilt is not None
        attempts = rebuilt or {}
    prior_report = _read_json(report)
    prior_report = prior_report if isinstance(prior_report, dict) else {}
    paged_once: dict[str, str] = {}
    for src in (prior_report.get("paged_once"), prior.get("paged_once")):
        if isinstance(src, dict):
            paged_once.update({str(k): str(v) for k, v in src.items()})
    if isinstance(prior.get("gave_up_paged"), str):          # the pre-v2 key
        paged_once.setdefault("workflow_gate_restart:CAPPED", prior["gave_up_paged"])

    def snapshot(p: Pass, *, final: bool) -> dict[str, Any]:
        mg = [*(x for x in (prior.get("missed_growth") or []) if isinstance(x, dict)),
              *p.missed_growth][-MISSED_GROWTH_HISTORY:]
        return {"at": _iso(t), "version": VERSION,
                "cpu": dict(p.observed) if final else prior.get("cpu") or {},
                "gate_tree": p.gate_tree if final else prior.get("gate_tree") or {},
                "no_owner": p.next_no_owner if final else prior.get("no_owner") or {},
                "attempts": {k: [x for x in v if x >= cutoff] for k, v in p.attempts.items()},
                "history": "known" if p.history_known else "UNREADABLE",
                "paged_once": paged_once, "missed_growth": mg}

    def persist(p: Pass, row: dict[str, Any]) -> bool:
        """BEFORE the action: the state AND the ledger. Either one is enough to count it."""
        wrote = False
        try:
            _write_json(state, snapshot(p, final=False))
            wrote = True
        except OSError:
            pass
        try:
            _append_ledger(ledger, [row])
            wrote = True
        except OSError:
            pass
        return wrote

    p = Pass(b, prior, t, apply, attempts=attempts, history_known=history_known,
             persist=persist)
    if not history_known:
        p.red("*", "REFUSED", f"the state ({status}) and the ledger are both unreadable: no "
              f"action is taken until the attempt history can be read", history="UNREADABLE")
    if not b.windows and box is None:
        p.row("*", "UNMEASURED", "NOT_THE_BOX", "not Windows: the rules name Windows tasks and "
              "processes; nothing judged, nothing stopped")
    else:
        p.run()
    red = [r for r in p.rows if r["level"] == "RED"]
    unmeasured = [r for r in p.rows if r["level"] == "UNMEASURED"]
    rstatus = "RED" if red else "UNMEASURED" if unmeasured else "OK"
    mg_hist = snapshot(p, final=True)["missed_growth"]
    doc = {"schema": SCHEMA, "version": VERSION, "at": _iso(t), "host": b.host,
           "task": TASK_NAME, "applied": apply, "status": rstatus,
           "stale_after_s": STALE_AFTER_S, "cadence_s": CADENCE_S,
           "n_red": len(red), "actions": [r for r in red if r["verdict"] in ACTION_VERDICTS],
           "refusals": [r for r in red if r["verdict"] in ("REFUSED", "BACKOFF", "DEAD_OWNER")],
           "attempt_history": history_source,
           "attempts_today": {k: sum(1 for x in v if _day(x) == _day(t))
                              for k, v in p.attempts.items()},
           "rows": p.rows, "rules": rules_table(),
           "deferred": [{"paste_line": k, "owner": v} for k, v in DEFERRED],
           "deny": [n for n, _ in DENY],
           "missed_growth": mg_hist[-20:]}
    pages = list(_pages(p.rows)) if apply else []
    day = _day(t)
    keep: list[Mapping[str, Any]] = []
    for r in pages:
        k = _once_key(r)
        if k is None:
            keep.append(r)
        elif paged_once.get(k) != day:
            paged_once[k] = day
            keep.append(r)
    pages = keep
    doc["paged"] = None
    doc["paged_once"] = paged_once
    if pages:
        body = "\n".join(f"{r['rule']}: {r['verdict']} -- {r['why']}" for r in pages)[:1500]
        try:
            res = (alert or _send_alert)(f"Box self-heal on {b.host}: {len(pages)} action(s)",
                                         body)
            doc["paged"] = {"rows": len(pages), "result": res if isinstance(res, dict) else
                            str(res)}
        except Exception as exc:          # a pager failure is RED, never a lost pass
            doc["paged"] = {"rows": len(pages), "error": f"{type(exc).__name__}: {exc}"[:200]}
    try:
        _write_json(state, snapshot(p, final=True))
    except OSError as exc:
        doc["state_write_error"] = f"{type(exc).__name__}: {exc}"[:200]
        doc["status"] = "RED"
    _write_json(report, doc)
    with contextlib.suppress(OSError):
        _append_ledger(ledger, [r for r in red if id(r) not in p.ledgered])
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Closed-table self-heal for the box (no commands "
                                             "are read from anywhere; see the module docstring).")
    ap.add_argument("--dry-run", action="store_true",
                    help="decide and log every rule, act on nothing")
    args = ap.parse_args(argv)
    if not DESK.is_dir():
        print(f"box_self_heal: {DESK} is not a desk: run from the repo (the installed task's "
              f"working directory is the repo root)")
        return 2
    doc = run(apply=not args.dry_run)
    for r in doc["rows"]:
        print(f"[{r['level']:<10}] {r['rule']:<22} {r['verdict']:<16} {r['why']}")
    print(f"box_self_heal: {doc['status']} ({doc['n_red']} red) -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
