"""THE BOX SELF-HEAL LIBRARY: the closed rule table, the process reading it is judged by, and the
watchdog's own state and ledger files.

Split out of ops/box_self_heal.py (2026-11-04) only so each file fits the independent reviewer
whole: a new file is one hunk, and a hunk is never read in part. Nothing here stops, ends or starts
anything: it holds the rules, the deny list, the Proc record, the functions that decide whether a
process matches a rule, is denied, is allowlisted and is making progress, and the readers and
writers of the watchdog's own state, ledger and attempt history.

THE RULES (`RULES` below is the table; tests pin it through box_self_heal):

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

box_self_heal.py loads this file ONLY from beside itself (repo ops/, or the admin-only
C:\\ProgramData\\QuantBox\\bin the installer pins it into), never from sys.path, and re-exports
every name, so `box_self_heal.<name>` is unchanged for its callers and tests.
"""
from __future__ import annotations

import json
import ntpath
import os
import re
import shlex
import stat
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The memecoin spot launcher's scheduled task (MemecoinResourceLimits wrapper).
MEMECOIN_SPOT_TASK = "MemecoinShadowCodex"
#: A status older than this, or any state but BOUNDED, is a launcher that is not running spot.
MEMECOIN_SPOT_STALE_S = 300

#: CPU progress is judged across PASSES, never inside one: a 20-second sample of a job that is
#: waiting on disk reads as wedged. Two observations at least this far apart, and less than
#: CPU_EPS_S of CPU (the whole tree) between them, is "no progress".
PROGRESS_WINDOW_S = 4 * 60
CPU_EPS_S = 2.0
#: An observation older than this is not a baseline (the watchdog itself was down).
PROGRESS_MAX_GAP_S = 30 * 60

#: The gate's own cadence; a heartbeat older than three of them is a gate that is not running.
GATE_CADENCE_S = 10 * 60
GATE_STALE_S = 3 * GATE_CADENCE_S

LEDGER_ROTATE_BYTES = 5 * 1024 * 1024


# ------------------------------------------------------------------------------ the closed table
@dataclass(frozen=True)
class Rule:
    """One allowlisted thing this watchdog may act on. Literal in code; never loaded."""

    key: str
    kind: str                      # "task" | "gate" | "gate_restart" | "spot_restart"
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
    # MEMECOIN SPOT (2026-11-03): its launcher exited on a status-write IOException at 04:36Z,
    # KILL_ON_JOB_CLOSE took spot with it, and the task sat Ready all day because a non-elevated
    # session cannot start a LOCAL SERVICE task. RUN ONLY: never ended, nothing in its tree is
    # ever stopped. /Run starts the task's own wrapped action, so its identity and CPU cap stay.
    Rule("memecoin_spot_restart", "spot_restart", (), (), task=MEMECOIN_SPOT_TASK,
         fallback_budget_s=MEMECOIN_SPOT_STALE_S,
         budget_source="spot.json observed_at older than 300 s, or state != BOUNDED, held "
                       "across two passes",
         why="the spot launcher is down while its task reads Ready; nothing restarts it"),
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
RUNNABLE_TASKS: frozenset[str] = frozenset({"Quant-WorkflowGate", MEMECOIN_SPOT_TASK})

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
    ("memecoinautonomousdevelopment", "the memecoin development lane: its owner runs it"),
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
    #: The account it runs as ("NT AUTHORITY\\SYSTEM", "HOST\\Administrator"); None if unreadable.
    user: str | None = None


def _on_windows() -> bool:
    return sys.platform == "win32"


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
        # Unbalanced quotes: not parseable, so the whole line is ONE token. Nothing that needs
        # an exact argument then matches it, and the deny list sees all of it.
        return [(p.cmdline or "").strip()]
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


#: Python's own options that take a value (the next token is not the script).
_PY_OPT_ARG = frozenset({"-W", "-X", "-Q"})

#: Images whose arguments are PURE DATA, never code they run: a git/gh ref, an API path, a
#: console title. `git fetch origin claude/miner-x` is git, not a miner, so only their image
#: identifies them. Nothing that runs code (no shell, no interpreter) belongs here.
_DATA_ARG_IMAGES = frozenset({"gh", "git", "git-credential-manager", "conhost"})
_DATA_ARG_PREFIXES = ("git-remote-",)
#: The only switches the installers pass BEFORE -File. A valued one (its value is the next token).
_PS_PRE_FILE_FLAGS = frozenset({"-noprofile", "-noninteractive", "-nologo", "-sta", "-mta"})
_PS_PRE_FILE_VALUED = frozenset({"-windowstyle", "-executionpolicy", "-ex", "-ep"})


def _ps_file(argv: Sequence[str]) -> str | None:
    """The script a PowerShell `-File` runs, ONLY when every switch before it is one the
    installers pass (audit should-fix of 5b3504f50). A `-Command`/`-EncodedCommand`, or any other
    switch, before -File means the file is not what runs, so this returns None."""
    i = 1
    while i < len(argv):
        a = argv[i].lower()
        if a in ("-file", "/file"):
            return argv[i + 1] if i + 1 < len(argv) else None
        if a in _PS_PRE_FILE_FLAGS:
            i += 1
            continue
        if a in _PS_PRE_FILE_VALUED:
            i += 2
            continue
        return None
    return None


def _is_data_image(base: str) -> bool:
    return base in _DATA_ARG_IMAGES or base.startswith(_DATA_ARG_PREFIXES)


def _deny_haystack(p: Proc) -> str:
    """What the deny list searches: the WHOLE folded command line, for every image except the
    pure-data ones (git, gh, git-remote-*, git-credential-manager, conhost), whose arguments are
    refs and paths, never code; those contribute their image and argv[0] only. No interpreter or
    shell is parsed for "the code it runs": `run.py --role gateway`, `-Command Invoke-Desk -Name
    gateway` and `sh -c "python gateway.py"` all carry the money organ in an ARGUMENT, so any
    token anywhere on the line denies (over-match, never under-match)."""
    img = _image(p)
    whole = _fold(p.cmdline or " ".join(p.argv))
    if _is_data_image(img.removesuffix(".exe")):
        argv = _argv(p)
        return _fold(" ".join(t for t in (img, *(argv[:1])) if t))
    return _fold(f"{img} {whole}")


def denied(p: Proc) -> str | None:
    """Why `p` may never be touched, or None. Checked before any allowlist match."""
    u = unreadable(p)
    if u:
        return f"unidentifiable: {u}"
    text = _deny_haystack(p)
    for needle, why in DENY:
        if needle in text:
            return f"{needle!r}: {why}"
    return None


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
        # _ps_file refuses when any switch before -File is not an installer's own (so a
        # `-Command ... -File <gate>` wrapper, which runs the command and not the file, is not it).
        f = _ps_file(argv)
        return f is not None and _norm_path(f) == GATE_FILE
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


# ------------------------------------------------------------------------- time and attempts
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


# ------------------------------------------------------------------------------- the durable side
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _read_state(path: Path) -> tuple[str, dict[str, Any]]:
    """("ok" | "absent" | "unreadable" | "marked", doc). A state that exists and cannot be read is
    NOT a fresh start: it is a lost attempt count. "marked" is a state a previous pass wrote while
    the history was unknown: it is readable, and a readable ledger now clears it (v4 should-fix
    4), so one bad pass is not a refusal forever."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return "absent", {}
    except (OSError, ValueError):
        return "unreadable", {}
    if not isinstance(doc, dict):
        return "unreadable", {}
    if doc.get("history") == "UNREADABLE":
        return "marked", doc
    return "ok", doc


def _write_json(path: Path, doc: Any) -> None:
    """Atomic write. The temp file has a fresh random name and is created EXCLUSIVELY (mkstemp:
    O_CREAT|O_EXCL), so a symlink or hard link planted at a predictable `<path>.tmp` is never
    written through; os.replace then swaps the directory entry, never writing through `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1, sort_keys=False))
    os.replace(tmp, path)


_REPARSE_POINT = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT


def redirected(path: Path) -> str | None:
    """Why a SYSTEM write to `path` -- a file under the user-writable repo -- could land somewhere
    else, or None (v4 should-fix 2): any component of the path (the file, its folder, or any folder
    above) that is a junction or symlink, or an existing file with a second hard link. Absent
    components are fine (they are created as plain folders). Checked before EVERY such write."""
    full = Path(os.path.abspath(path))
    for comp in (full, *full.parents):
        try:
            st = os.lstat(comp)
        except FileNotFoundError:
            continue
        except OSError as exc:
            return f"{comp} cannot be inspected ({type(exc).__name__})"
        if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & _REPARSE_POINT:
            return f"{comp} is a junction or symlink"
        if comp == full and stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
            return f"{comp} has {st.st_nlink} hard links"
    return None


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


def attempts_from_ledger(ledger: Path, since: float, bad: list[int] | None = None
                         ) -> dict[str, list[float]] | None:
    """Rebuild the attempt count from the ledger (and its rotated `.1`), or None when the file
    itself cannot be read. Absent is an empty history (an attempt always writes a row). A torn or
    unparseable LINE is skipped and counted into `bad` (audit should-fix of 5b3504f50): one bad
    line must not throw away every good attempt row around it -- that would read as no history
    and stop every rule, or (worse, before v2) as a reset cap."""
    out: dict[str, list[float]] = {}
    for path in (ledger.with_suffix(ledger.suffix + ".1"), ledger):
        try:
            lines = path.read_text("utf-8").splitlines()
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return None
        for line in lines:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                r = None
            if not isinstance(r, dict):
                if bad is not None:
                    bad.append(1)
                continue
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
