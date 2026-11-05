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
to schtasks is a literal in THIS file or its table (box_self_heal_lib.py), reviewed with it (a
"box runner" was refused before, and this is deliberately not one). Adding a rule is a code
change that goes through review like any other.

WHERE IT RUNS FROM (audit HOLD of 7a01c1b09). The SYSTEM task runs the ADMIN-ONLY copy the
installer puts in C:\\ProgramData\\QuantBox\\bin (this file, ops/box_self_heal_lib.py,
ops/process_health.py and libs/ops/alert_channels.py, the only code it loads), never the repo tree a
non-admin can write. The installed copy loads its three helpers from beside itself and nowhere
else; the repo (the path the installer writes to bin\\box_self_heal.root, never the working
directory) is only where it writes its report. Its state, ledger and alert record live in the
admin-only C:\\ProgramData\\QuantBox\\state, which is also the task's working directory.

THE RULES, THE DENY LIST AND DEFERRED live with the table in ops/box_self_heal_lib.py (its
docstring says what each rule may do, what is never touched, and why the job-lock lines are not
here).

RED-LOGGED. Every action and every refusal is a RED row in desks/mt5/reports/BOX_SELF_HEAL.json
(this pass, the only thing written into the repo) and appended to the attempt ledger under the
admin-only C:\\ProgramData\\QuantBox\\state (box_self_heal.jsonl). The report carries its
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
#: is not; then the repo is the path the admin installer wrote beside it, in the admin-only bin
#: (`box_self_heal.root`), else the box's fixed checkout. NEVER the working directory (v5 MF-A):
#: the task runs in the admin-only state folder, and nothing here depends on where it was started.
_IN_REPO = _HERE.name == "ops" and (_HERE.parent / "desks" / "mt5").is_dir()
#: The box's checkout, when the installer's root file is absent or unreadable.
DEFAULT_BOX_ROOT = Path(r"C:\opt\quant")
ROOT_FILE_NAME = "box_self_heal.root"


def _resolve_root(here: Path, in_repo: bool) -> Path:
    """The repo root: the repo this file sits in, else the absolute path in `here`'s admin-only
    root file, else DEFAULT_BOX_ROOT. A relative or empty value is ignored (it would be cwd)."""
    if in_repo:
        return here.parent
    try:
        text = (here / ROOT_FILE_NAME).read_text("utf-8-sig").strip()
    except (OSError, ValueError):
        text = ""
    if text and ntpath.isabs(text) and "\n" not in text:
        return Path(text)
    return DEFAULT_BOX_ROOT


ROOT = _resolve_root(_HERE, _IN_REPO)
DESK = ROOT / "desks" / "mt5"
#: The ONLY thing this file writes into the repo: its report, which it never reads back to decide.
REPORT = DESK / "reports" / "BOX_SELF_HEAL.json"
#: WHAT IT DECIDES FROM LIVES WHERE ONLY ADMINS CAN WRITE (audit HOLD of 5b3504f50). The bridge
#: and every agent session can write the repo, so a state there could plant an "orphan" for SYSTEM
#: to stop, a CPU baseline that reads STALLED, a dead-owner clock, or an empty attempt count. The
#: state and the attempt ledger live in C:\ProgramData\QuantBox\state, created by the installer
#: with install_unattended.ps1's locked ACL, and a pass whose directory (or any file in it) is not
#: provably admin-only acts on nothing.
STATE_DIR = Path(r"C:\ProgramData\QuantBox\state")
LEDGER = STATE_DIR / "box_self_heal.jsonl"
#: Cross-pass memory (CPU baselines, gate tree, attempts, no-owner clocks).
STATE = STATE_DIR / "box_self_heal_state.json"
#: The gate's own folder (ops/box/workflow_gate.ps1, $Root). A literal, never an argument.
QUANTBOX_LOGS = Path(r"C:\ProgramData\QuantBox\logs")
GATE_BEAT = QUANTBOX_LOGS / "workflow_gate.json"
#: The memecoin spot launcher's own status file (MemecoinResourceLimits wrapper). Read only.
MEMECOIN_SPOT_STATUS = Path(r"C:\ProgramData\MemecoinResourceLimits\status\spot.json")

SCHEMA = "box_self_heal/1"
VERSION = "boxheal-2026-11-03-a"
TASK_NAME = "Quant-BoxSelfHeal"
#: How often the task fires, and the age past which its own report is stale (desk health, contract).
CADENCE_S = 5 * 60
STALE_AFTER_S = 20 * 60

#: Attempts: the first may happen at once; each later one by the same rule waits twice as long as
#: the one before (30/60/120 min); never more than MAX_ATTEMPTS_PER_DAY per rule per UTC day.
RESTART_BACKOFF_S = 30 * 60
MAX_RESTARTS_PER_DAY = 4
MAX_ATTEMPTS_PER_DAY = MAX_RESTARTS_PER_DAY

#: THE FREEZE WINDOW (audit HOLD of 7a01c1b09). From the first suspend to the last kill. A tree
#: left suspended is a wedge this file made, so the window is short and the task's limit
#: (install_box_self_heal_task.ps1, 15 min) is far above a pass's worst case (five 60 s schtasks
#: calls, two 10 s waits, one page: about 6.5 min).
FREEZE_MAX_S = 5.0
SCHTASKS_TIMEOUT_S = 60

MISSED_GROWTH_HISTORY = 50


# ------------------------------------------------------------------------------ the closed table
def _sibling(modname: str, filename: str) -> Any:
    """A module that lives beside this file, loaded from exactly that path: repo ops/ in the repo,
    the admin-only bin in the installed copy. Never sys.path, never the working directory: a SYSTEM
    task must not execute a file a non-admin can write (see `_dep`). A module of the same name
    already loaded from anywhere else is refused, not reused (audit SF on 451e1b8ed)."""
    want = (_HERE / filename).resolve()
    mod = sys.modules.get(modname)
    if mod is not None:
        got = getattr(mod, "__file__", None)
        if got is None or Path(got).resolve() != want:
            raise ImportError(f"{modname} is already loaded from {got!r}, not {want}")
        return mod
    spec = importlib.util.spec_from_file_location(modname, want)
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


#: The closed table, the process reading and the state/ledger files (box_self_heal_lib.py),
#: re-exported by name so `box_self_heal.<name>` is unchanged.
_table = _sibling("box_self_heal_lib", "box_self_heal_lib.py")
MEMECOIN_SPOT_TASK = _table.MEMECOIN_SPOT_TASK
MEMECOIN_SPOT_STALE_S = _table.MEMECOIN_SPOT_STALE_S
PROGRESS_WINDOW_S = _table.PROGRESS_WINDOW_S
CPU_EPS_S = _table.CPU_EPS_S
PROGRESS_MAX_GAP_S = _table.PROGRESS_MAX_GAP_S
GATE_CADENCE_S = _table.GATE_CADENCE_S
GATE_STALE_S = _table.GATE_STALE_S
Rule = _table.Rule
_PY = _table._PY
_PS = _table._PS
INTAKE_SCRIPT = _table.INTAKE_SCRIPT
INTAKE_ONCE = _table.INTAKE_ONCE
GATE_FILE = _table.GATE_FILE
RULES = _table.RULES
RULE_BY_KEY = _table.RULE_BY_KEY
ORPHAN_KEY = _table.ORPHAN_KEY
DEFERRED = _table.DEFERRED
ENDABLE_TASKS = _table.ENDABLE_TASKS
RUNNABLE_TASKS = _table.RUNNABLE_TASKS
GATE_CHILD_IMAGES = _table.GATE_CHILD_IMAGES
DENY = _table.DENY
_KERNEL_PSEUDO = _table._KERNEL_PSEUDO
Proc = _table.Proc
_on_windows = _table._on_windows
_fold = _table._fold
_image = _table._image
_argv = _table._argv
_norm_path = _table._norm_path
unreadable = _table.unreadable
_PY_OPT_ARG = _table._PY_OPT_ARG
_DATA_ARG_IMAGES = _table._DATA_ARG_IMAGES
_DATA_ARG_PREFIXES = _table._DATA_ARG_PREFIXES
_PS_PRE_FILE_FLAGS = _table._PS_PRE_FILE_FLAGS
_PS_PRE_FILE_VALUED = _table._PS_PRE_FILE_VALUED
_ps_file = _table._ps_file
_is_data_image = _table._is_data_image
_deny_haystack = _table._deny_haystack
denied = _table.denied
_py_script = _table._py_script
_is_intake_script = _table._is_intake_script
_image_ok = _table._image_ok
matches = _table.matches
allowlisted = _table.allowlisted
_parent = _table._parent
intake_under_its_task = _table.intake_under_its_task
descendants = _table.descendants
ancestors = _table.ancestors
_ident = _table._ident
tree_members = _table.tree_members
tree_cpu = _table.tree_cpu
progress = _table.progress
LEDGER_ROTATE_BYTES = _table.LEDGER_ROTATE_BYTES
_iso = _table._iso
_parse_iso = _table._parse_iso
_day = _table._day
ACTION_VERDICTS = _table.ACTION_VERDICTS
FAILED_VERDICTS = _table.FAILED_VERDICTS
_attempts_from = _table._attempts_from
_read_json = _table._read_json
_read_state = _table._read_state
_write_json = _table._write_json
_REPARSE_POINT = _table._REPARSE_POINT
redirected = _table.redirected
_append_ledger = _table._append_ledger
attempts_from_ledger = _table.attempts_from_ledger
rules_table = _table.rules_table


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
    spot_status: Path = MEMECOIN_SPOT_STATUS
    windows: bool = sys.platform == "win32"
    #: secure(path): why the state directory (or a file in it) is NOT admin-only, or None.
    secure: Callable[[Path], str | None] = field(default=lambda p: admin_only(p))
    #: task_principal(task): the account the task is registered to run as (name or SID), or None.
    task_principal: Callable[[str | None], str | None] = field(
        default=lambda t: _task_principal(t) if t else None)
    #: sid_of(account): the SID of an account name or SID string, or None (`_account_sid`).
    sid_of: Callable[[str | None], str | None] = field(default=lambda a: _account_sid(a))


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
            try:
                user: str | None = str(pr.username())
            except Exception:
                user = None
            # An AccessDenied cmdline arrives as None -> "" here, and `unreadable` denies it.
            rows.append(Proc(int(info["pid"]), int(info.get("ppid") or 0),
                             str(info.get("name") or ""), " ".join(argv),
                             float(info.get("create_time") or 0.0), cpu, argv, user))
        except Exception:
            continue
    return rows


def _system32() -> str:
    """The absolute System32 folder: GetSystemDirectoryW, else the fixed default (v5 MF-A). Never a
    bare image name: CreateProcess searches the CURRENT directory before PATH, so a bare
    `schtasks` would run a planted schtasks.exe in whatever folder the task started in."""
    if _on_windows():
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260)  # type: ignore[attr-defined,unused-ignore]
            if 0 < n < 260 and ntpath.isabs(buf.value):
                return str(buf.value)
        except Exception:
            pass
    return r"C:\Windows\System32"


#: The ONE image this file launches, by absolute path.
SCHTASKS_EXE = ntpath.join(_system32(), "schtasks.exe")


def _schtasks(verb: str, task: str, *, xml: bool = False) -> dict[str, Any]:
    """The ONLY subprocess this file starts: schtasks with a literal verb on an allowlisted task."""
    allowed = {"/Query": ENDABLE_TASKS | RUNNABLE_TASKS, "/End": ENDABLE_TASKS,
               "/Run": RUNNABLE_TASKS}
    if verb not in allowed or task not in allowed[verb]:
        raise ValueError(f"schtasks {verb} {task!r} is not in the closed table")
    tail = (["/XML"] if xml else ["/FO", "CSV", "/NH"]) if verb == "/Query" else []
    argv = [SCHTASKS_EXE, verb, "/TN", task, *tail]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=SCHTASKS_TIMEOUT_S,
                           check=False)
        return {"argv": argv, "rc": r.returncode,
                "out": ((r.stdout or "") + (r.stderr or "")).strip()[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "rc": None, "out": f"{type(exc).__name__}"}


#: The images Task Scheduler launches a task through. A task's process is a child of one of these;
#: a gate or intake command line run by hand (an operator shell, an agent) is not.
_SCHEDULER_IMAGES = frozenset({"svchost.exe", "taskeng.exe", "taskhostw.exe", "services.exe"})
#: The SYSTEM account's SID. Owners and principals are compared as SIDs, never as names: the
#: names are localized ("NT-AUTORITÄT\\SYSTEM") and schtasks may export a SID or a name.
_SYSTEM_SID = "S-1-5-18"
#: The English names of SYSTEM, for when the account lookup itself is unavailable (off Windows).
_WELL_KNOWN_SIDS = {"nt authority\\system": _SYSTEM_SID, "system": _SYSTEM_SID,
                    "localsystem": _SYSTEM_SID}


def _lookup_sid(name: str) -> str:
    """LookupAccountNameW + ConvertSidToStringSidW through ctypes (Windows only). Raises."""
    import ctypes
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    vp = ctypes.c_void_p
    dw = ctypes.POINTER(wintypes.DWORD)
    advapi.LookupAccountNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, vp, dw,
                                          wintypes.LPWSTR, dw, ctypes.POINTER(ctypes.c_int)]
    advapi.LookupAccountNameW.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [vp, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [vp]
    kernel.LocalFree.restype = vp
    cb, cch, use = wintypes.DWORD(0), wintypes.DWORD(0), ctypes.c_int(0)
    advapi.LookupAccountNameW(None, name, None, ctypes.byref(cb), None, ctypes.byref(cch),
                              ctypes.byref(use))
    if not cb.value:
        raise OSError(ctypes.get_last_error(), "LookupAccountNameW")  # type: ignore[attr-defined,unused-ignore]
    sid = ctypes.create_string_buffer(cb.value)
    dom = ctypes.create_unicode_buffer(max(cch.value, 1))
    if not advapi.LookupAccountNameW(None, name, ctypes.cast(sid, vp), ctypes.byref(cb), dom,
                                     ctypes.byref(cch), ctypes.byref(use)):
        raise OSError(ctypes.get_last_error(), "LookupAccountNameW")  # type: ignore[attr-defined,unused-ignore]
    out = wintypes.LPWSTR()
    if not advapi.ConvertSidToStringSidW(ctypes.cast(sid, vp), ctypes.byref(out)):
        raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW")  # type: ignore[attr-defined,unused-ignore]
    try:
        return str(out.value).upper()
    finally:
        kernel.LocalFree(ctypes.cast(out, vp))


def _account_sid(account: str | None) -> str | None:
    """The SID of `account` -- a name in any locale ("DOMAIN\\user") or a SID string -- upper-
    cased; None when it does not resolve (the caller fails closed)."""
    a = (account or "").strip()
    if not a:
        return None
    if re.fullmatch(r"(?i)s-1(-\d+)+", a):
        return a.upper()
    if _on_windows():
        try:
            return _lookup_sid(a)
        except Exception:
            pass
    return _WELL_KNOWN_SIDS.get(a.lower())


def _task_principal(task: str) -> str | None:
    """The account `task` runs as, from its registration XML (a name or a SID, as exported);
    None if unreadable. scheduler_owned resolves it to a SID before comparing."""
    r = _schtasks("/Query", task, xml=True)
    if r.get("rc") != 0:
        return None
    m = re.search(r"<UserId>\s*([^<]+?)\s*</UserId>", str(r.get("out") or ""),
                  re.IGNORECASE)
    return m.group(1).strip() if m else None


def scheduler_owned(p: Proc, procs: Sequence[Proc], box: Box, task: str | None) -> str | None:
    """Why `p` is NOT a process Task Scheduler launched for `task`, or None (audit should-fix of
    5b3504f50): a `-Command ... -File <gate>` or a hand-run intake matches the string but is not
    the task. Require SYSTEM (or the task's own principal) to own it, and the parent chain to pass
    through svchost/taskeng. Owner and principal are compared as SIDs (v4 should-fix 9): a
    localized name or a principal schtasks exports as a SID must not decide it. Fail CLOSED: an
    owner that does not resolve to a SID is a reason; an unresolvable principal allows SYSTEM
    only."""
    owner = (p.user or "").strip()
    owner_sid = box.sid_of(owner) if owner else None
    if not owner_sid:
        return (f"pid {p.pid}'s owner {owner!r} is unreadable or has no SID: not provably SYSTEM "
                f"or {task}'s principal")
    allowed = {_SYSTEM_SID}
    principal = box.task_principal(task) if task else None
    principal_sid = box.sid_of(principal) if principal else None
    if principal_sid:
        allowed.add(principal_sid)
    if owner_sid not in allowed:
        return f"pid {p.pid} runs as {owner!r} ({owner_sid}), not SYSTEM or {task}'s principal"
    by = {q.pid: q for q in procs}
    for a in ancestors(p.pid, procs):
        anc = by.get(a)
        if anc is not None and _image(anc) in _SCHEDULER_IMAGES:
            return None
    return f"pid {p.pid} has no Task Scheduler ancestor (svchost/taskeng); not a task run"


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


#: Admins and SYSTEM may hold any right; Users may read. Any other SID, or a Users ACE with a write
#: bit, makes the directory writable by someone a SYSTEM pass must not take orders from.
_ADMIN_SIDS = frozenset({"S-1-5-32-544", "S-1-5-18"})
_READ_SIDS = frozenset({"S-1-5-32-545"})
#: FILE_WRITE_DATA|APPEND|WRITE_EA|DELETE_CHILD|WRITE_ATTRIBUTES|DELETE|WRITE_DAC|WRITE_OWNER and
#: GENERIC_ALL|GENERIC_WRITE.
_WRITE_BITS = (0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000
               | 0x10000000 | 0x40000000)
_ALLOW_ACE, _OTHER_ALLOW_ACES = 0, frozenset({5, 9, 11})


def _acl_entries(path: Path) -> tuple[str, list[tuple[int, int, str]] | None]:
    """(owner SID, [(ace type, access mask, SID)]) of `path`; None for a NULL DACL. Windows only:
    advapi32 through ctypes, so proving the ACL starts no process."""
    import ctypes
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    vp = ctypes.c_void_p
    advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
                                             ctypes.POINTER(vp), ctypes.POINTER(vp),
                                             ctypes.POINTER(vp), ctypes.POINTER(vp),
                                             ctypes.POINTER(vp)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.ConvertSidToStringSidW.argtypes = [vp, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [vp, wintypes.DWORD, ctypes.POINTER(vp)]
    advapi.GetAce.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [vp]
    kernel.LocalFree.restype = vp

    class _ACL(ctypes.Structure):
        _fields_ = [("AclRevision", ctypes.c_ubyte), ("Sbz1", ctypes.c_ubyte),
                    ("AclSize", wintypes.WORD), ("AceCount", wintypes.WORD),
                    ("Sbz2", wintypes.WORD)]

    owner, dacl, sd = vp(), vp(), vp()
    # SE_FILE_OBJECT = 1; OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
    rc = advapi.GetNamedSecurityInfoW(str(path), 1, 0x1 | 0x4, ctypes.byref(owner), None,
                                      ctypes.byref(dacl), None, ctypes.byref(sd))
    if rc != 0:
        raise OSError(rc, "GetNamedSecurityInfoW")

    def sid_text(psid: int | None) -> str:
        out = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(psid, ctypes.byref(out)):
            raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW")  # type: ignore[attr-defined,unused-ignore]
        try:
            return str(out.value)
        finally:
            kernel.LocalFree(ctypes.cast(out, vp))

    try:
        own = sid_text(owner.value)
        if not dacl.value:
            return own, None
        acl = _ACL.from_address(dacl.value)
        aces: list[tuple[int, int, str]] = []
        for i in range(acl.AceCount):
            ace = vp()
            if not advapi.GetAce(dacl, i, ctypes.byref(ace)) or not ace.value:
                raise OSError(ctypes.get_last_error(), "GetAce")  # type: ignore[attr-defined,unused-ignore]
            kind = ctypes.c_ubyte.from_address(ace.value).value
            mask = wintypes.DWORD.from_address(ace.value + 4).value
            aces.append((kind, mask, sid_text(ace.value + 8) if kind in (0, 1) else ""))
        return own, aces
    finally:
        kernel.LocalFree(sd)


def admin_only(path: Path) -> str | None:
    """Why `path` is NOT provably writable by Administrators and SYSTEM alone, or None.

    Fail closed: absent, a junction, an unreadable ACL, a NULL DACL, an owner outside
    Administrators/SYSTEM, an allow ACE of a kind this does not parse, or any write right for any
    other SID is a reason. Off Windows nothing can be proven, which is also a reason."""
    if not _on_windows():
        return "not Windows: an admin-only ACL cannot be proven here"
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return f"{path} is absent (the installer creates it)"
    except OSError as exc:
        return f"{path} cannot be inspected ({type(exc).__name__})"
    if getattr(st, "st_file_attributes", 0) & 0x400:          # FILE_ATTRIBUTE_REPARSE_POINT
        return f"{path} is a junction or symlink"
    try:
        owner, aces = _acl_entries(path)
    except Exception as exc:
        return f"{path}'s ACL is unreadable ({type(exc).__name__}: {exc})"[:200]
    if owner not in _ADMIN_SIDS:
        return f"{path} is owned by {owner}, not Administrators/SYSTEM"
    if aces is None:
        return f"{path} has a NULL DACL: everyone may write it"
    for kind, mask, sid in aces:
        if kind in _OTHER_ALLOW_ACES:
            return f"{path} carries an allow ACE of type {kind} this cannot prove harmless"
        if kind != _ALLOW_ACE or sid in _ADMIN_SIDS:
            continue
        if sid in _READ_SIDS and not mask & _WRITE_BITS:
            continue
        return f"{path} grants {sid} more than read (mask 0x{mask:x})"
    return None


def _live_proc(pr: Any, ppid: int | None = None) -> Proc:
    """A psutil process re-read NOW. Raises on anything it cannot read."""
    argv = tuple(str(a) for a in (pr.cmdline() or []))
    name = str(pr.name() or "")
    par = int(pr.ppid()) if ppid is None else ppid
    try:
        user: str | None = str(pr.username())
    except Exception:
        user = None
    return Proc(int(pr.pid), par, name, " ".join(argv), float(pr.create_time()), 0.0, argv, user)


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
        # A REFUSAL AFTER THE FIRST KILL NAMES WHAT DIED (audit should-fix of 5b3504f50): an
        # AccessDenied on the third member is not "nothing stopped" when two are already gone.
        if killed:
            return {"ok": False, "target_gone": not target_alive(), "killed": sorted(killed),
                    "why": f"{why}; PARTIALLY stopped: killed {sorted(killed)}, every other "
                           f"member resumed"}
        return {"ok": False, "target_gone": False, "killed": [],
                "why": f"{why}; tree resumed, nothing stopped"}

    def tree_below(root: Any, root_ct: float) -> list[Any]:
        """The live tree, LEVEL BY LEVEL (audit HOLD of 5b3504f50): each child is checked against
        ITS OWN parent's create time. children(recursive=True) only compares every descendant with
        the root, so a process that adopted a recycled pid deeper down came along."""
        out: list[Any] = []
        seen = {root.pid}
        level = [(root, root_ct)]
        while level:
            nxt: list[tuple[Any, float]] = []
            for par, pct in level:
                try:
                    kids = par.children(recursive=False)
                except psutil.NoSuchProcess:
                    continue
                for k in kids:
                    if k.pid in seen:
                        continue
                    try:
                        kct = float(k.create_time())
                    except psutil.NoSuchProcess:
                        continue
                    if kct < pct:
                        continue                # older than this parent: a recycled ppid
                    seen.add(k.pid)
                    out.append(k)
                    nxt.append((k, kct))
            level = nxt
        return out

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
        for k in tree_below(live, tp.create_time):     # deny-checked BEFORE the first freeze
            bad = bad_member(k)
            if bad:
                return refuse(f"descendant {k.pid} may not be stopped ({bad})")
        live.suspend()
        frozen.append(live)
        frozen_pids.add(live.pid)
        for _round in range(5):
            if clock() - t0 > FREEZE_MAX_S:
                return refuse(f"the freeze took over {FREEZE_MAX_S:.0f}s")
            fresh = [k for k in tree_below(live, tp.create_time) if k.pid not in frozen_pids]
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
                and intake_under_its_task(p, self.procs)
                and scheduler_owned(p, self.procs, self.box, rule.task) is None]
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
        roots = [p for p in self.procs if matches(rule, p) and not denied(p)
                 and scheduler_owned(p, self.procs, self.box, rule.task) is None]
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

    def spot_restart_rule(self, rule: Rule) -> None:
        """/Run the memecoin spot task when it reads NOT running and its launcher's status says
        spot is not BOUNDED (or has gone quiet), on two passes in a row. Never /End, never kill."""
        assert rule.task is not None
        task = rule.task
        running = self.box.task_running(task)
        if running is None:
            self.red(rule.key, "UNMEASURED", f"the scheduler would not say whether {task} is "
                     f"running; nothing done")
            return
        if running:
            self.ok(rule.key, "RUNNING", f"{task} reads Running")
            return
        try:
            doc = json.loads(self.box.spot_status.read_text("utf-8-sig"))
        except FileNotFoundError:
            self.red(rule.key, "UNMEASURED", f"{self.box.spot_status.name} is absent: whether "
                     f"spot is down cannot be proven, so {task} is not started")
            return
        except (OSError, ValueError) as exc:
            self.red(rule.key, "UNMEASURED", f"{self.box.spot_status.name} is unreadable "
                     f"({type(exc).__name__}); nothing done")
            return
        state = str(doc.get("state") or "") if isinstance(doc, dict) else ""
        raw_at = doc.get("observed_at") if isinstance(doc, dict) else None
        # The launcher stamps EPOCH SECONDS (box read 2026-11-03: 1793738850); ISO is accepted too.
        if isinstance(raw_at, (int, float)) and not isinstance(raw_at, bool):
            at: float | None = float(raw_at) / (1000.0 if raw_at > 1e12 else 1.0)
        else:
            at = _parse_iso(raw_at)
        age = None if at is None else self.now - at
        facts = {"spot_state": state or None,
                 "status_age_s": None if age is None else round(age)}
        if state == "BOUNDED" and age is not None and age <= MEMECOIN_SPOT_STALE_S:
            self.ok(rule.key, "BOUNDED", f"{task} is between runs and spot is BOUNDED "
                    f"({age:.0f}s old)", **facts)
            return
        why = (f"{task} reads not running and spot is "
               + (f"{state or 'state-less'}" if state != "BOUNDED"
                  else f"BOUNDED but {('un-stamped' if age is None else f'{age:.0f}s old')}"))
        # TWO PASSES, NOT ONE: the launcher rewrites its status every few seconds, and a task
        # between its own restart and its first write reads exactly like a dead one.
        first = self.no_owner.get(task, self.now)
        self.next_no_owner[task] = first
        if self.now - first < PROGRESS_WINDOW_S:
            self.ok(rule.key, "OBSERVING", why + "; confirming next pass", **facts)
            return
        if not self.apply:
            if self.may_attempt(rule.key, **facts):
                self.red(rule.key, "WOULD_RUN", why, dry_run=True, task=task, **facts)
            return
        if not self.attempt(rule.key, f"run {task}", **facts):
            return
        self.start(rule, task, why)

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


#: Verdicts that page zuck every time: something was stopped, ended or started. A FAILED action
#: pages once a UTC day per rule and verdict; so does the daily cap and an unreadable history.
PAGE_VERDICTS = frozenset({"STOPPED", "ENDED", "STARTED", *FAILED_VERDICTS})


def _https_channel(cfg: Mapping[str, Any], heartbeat: Path,
                   trusted: Callable[[Path], str | None] | None = None) -> dict[str, Any] | None:
    """`cfg` with every URL it would open proven https, or None (v4 should-fix 3): SYSTEM never
    opens a file:// or http:// URL. ntfy and telegram build their own https URL; email opens no
    URL. An hc channel without a url reads `heartbeat` only when `trusted` (admin_only) passes."""
    trusted = trusted or admin_only
    out = dict(cfg)
    kind = out.get("kind")
    if kind == "webhook" or kind == "hc":
        url = str(out.get("url") or "").strip()
        if not url and kind == "hc":
            if trusted(heartbeat) is not None:
                return None
            try:
                url = str(json.loads(heartbeat.read_text("utf-8")).get("url", "")).strip()
            except (OSError, ValueError, AttributeError):
                return None
        if not url.lower().startswith("https://"):
            return None
        out["url"] = url
    return out


#: The alert config SYSTEM reads (v5 should-fix 3): the admin's install-time copy of
#: data\secrets\alert_channels.json (and heartbeat_url.json), in the admin-only state folder with
#: an Administrators/SYSTEM-only ACL. The repo copy is writable by the bridge and every session,
#: so SYSTEM never reads it; re-run the installer after changing the channels.
ALERT_CONFIG = STATE_DIR / "alert_channels.json"
ALERT_HEARTBEAT = STATE_DIR / "heartbeat_url.json"
#: Where SYSTEM records each delivery attempt (v5 should-fix 1): the admin-only state folder,
#: never a fixed name in the repo.
ALERT_LEDGER = STATE_DIR / "alert_delivery.jsonl"


def _send_alert(title: str, body: str) -> dict[str, Any]:
    """libs/ops/alert_channels' senders (ntfy on the box), loaded by path from the admin-only copy
    beside the installed watchdog, or from the repo when run from the repo. The channels are read
    only from the admin-only install-time copy, and only https ones are fired; every attempt is
    logged in the admin-only state folder."""
    mod = _load("_box_self_heal_alert_channels",
                _dep("alert_channels.py", "libs/ops/alert_channels.py"))
    ledger = ALERT_LEDGER
    raw = mod.load_channels(ALERT_CONFIG) if admin_only(ALERT_CONFIG) is None else []
    heartbeat = ALERT_HEARTBEAT
    channels = [c for c in (_https_channel(x, heartbeat) for x in raw) if c is not None]
    if not channels:
        mod._log("none", False, f"NOT-ARMED: no https channel of {len(raw)} configured",
                 title, ledger)
        return {"armed": 0, "delivered": 0, "results": [], "configured": len(raw)}
    results = []
    for cfg in channels:
        kind = str(cfg.get("kind"))
        try:
            detail = str(mod._SENDERS[kind](cfg, title, body))
            ok = True
        except Exception as exc:          # one channel's failure never stops another's
            ok, detail = False, f"{type(exc).__name__}: {exc}"[:200]
        mod._log(kind, ok, detail, title, ledger)
        results.append({"channel": kind, "ok": ok, "detail": detail})
    return {"armed": len(channels), "delivered": sum(1 for r in results if r["ok"]),
            "results": results, "configured": len(raw)}


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

    def clamp(xs: Iterable[float]) -> list[float]:
        # THE CLOCK MAY HAVE MOVED BACK (audit should-fix of 5b3504f50): a future-dated attempt
        # is still an attempt and counts toward the cap, but at `now`, so a backward clock cannot
        # park four restarts in tomorrow and leave today empty.
        return sorted(min(float(x), t) for x in xs)

    # THE STATE DIRECTORY MUST BE ADMIN-ONLY (audit HOLD of 5b3504f50). On the box, a state the
    # bridge or an agent could write would plant orphan targets, STALLED baselines, dead-owner
    # clocks and a reset cap. If it is not provably writable by Administrators/SYSTEM alone, the
    # pass reads no state, keeps no state, and -- because an unprovable store is an uncapped one
    # -- acts on nothing.
    #
    # A FRESH INSTALL (v4 must-fix 1): the installer creates the folder only. Once the FOLDER is
    # proven admin-only, nobody else can create a file in it, so a file that is absent is accepted
    # and is created by this SYSTEM pass with the folder's inherited ACL. A file that EXISTS must
    # itself be proven admin-only (the state, the ledger and the rotated ledger.1).
    insecure = b.secure(state.parent)
    if insecure is None:
        for probe in (state, ledger, ledger.with_suffix(ledger.suffix + ".1")):
            if not os.path.lexists(probe):
                continue
            why = b.secure(probe)
            if why is not None:
                insecure = why
                break
    status, prior = _read_state(state)
    history_known = True
    history_source = "state"
    attempts: dict[str, list[float]] = {}
    if insecure is not None:
        history_known = False
        history_source = "INSECURE"
        prior = {}
    else:
        # MAX(STATE, LEDGER), never the state alone (audit HOLD of 5b3504f50): a state that erased
        # attempts cannot lower the count below what the admin-only ledger proves. A line the
        # ledger cannot parse is skipped, not fatal.
        state_attempts = (_attempts_from(prior.get("attempts"))
                          if status in ("ok", "marked") else {})
        legacy = [float(x) for x in (prior.get("restarts") or [])
                  if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if legacy:
            state_attempts.setdefault("workflow_gate_restart", [])
            state_attempts["workflow_gate_restart"] += legacy
        torn: list[int] = []
        ledgered_attempts = attempts_from_ledger(ledger, cutoff, torn)
        if ledgered_attempts is None:
            history_known, history_source = False, "UNREADABLE"
        else:
            for src in (state_attempts, ledgered_attempts):
                for k, v in src.items():
                    attempts.setdefault(k, [])
                    attempts[k] = clamp(set(attempts[k]) | set(v))
            if status == "ok":
                history_source = "state+ledger"
            elif status == "marked":
                # The previous pass could not read the history; the ledger -- admin-only, and
                # written BEFORE every action -- is readable now, so it is the history again.
                history_source = "ledger(cleared_unreadable)"
            elif ledgered_attempts:
                history_source = "ledger"
            elif status == "absent":
                history_source = "fresh"
            else:
                history_known, history_source = False, "UNREADABLE"
            if torn and history_known:
                history_source = f"{history_source}+{len(torn)}_torn_lines_skipped"
    # Once-a-day page keys come from the admin-only state ONLY (v4 should-fix 1): the report
    # lives in the repo, and a planted `paged_once` there would silence a page.
    paged_once: dict[str, str] = {}
    po_src = prior.get("paged_once")
    if isinstance(po_src, dict):
        paged_once.update({str(pk): str(pv) for pk, pv in po_src.items()})
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
        """BEFORE the action: the admin-only state AND ledger. Either one is enough to count it.
        An insecure store is never written (and the pass never reaches here: it does not act)."""
        if insecure is not None:
            return False
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
    if insecure is not None:
        p.red("*", "REFUSED", f"the state store is not provably admin-only ({insecure}): a "
              f"writable store could plant targets or reset the cap, so nothing is read, kept "
              f"or stopped", history="INSECURE")
    elif not history_known:
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
        once = _once_key(r)
        if once is None:
            keep.append(r)
        elif paged_once.get(once) != day:
            paged_once[once] = day
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
    doc["state_dir_secure"] = insecure is None
    if insecure is None:
        try:
            _write_json(state, snapshot(p, final=True))
        except OSError as exc:
            doc["state_write_error"] = f"{type(exc).__name__}: {exc}"[:200]
            doc["status"] = "RED"
        with contextlib.suppress(OSError):
            _append_ledger(ledger, [r for r in red if id(r) not in p.ledgered])
    # The report lands in the repo (read by nothing here), unless a component of its path is a
    # junction or symlink: SYSTEM must not write through one (v4 should-fix 2).
    doc["report_refused"] = redirected(report)
    if doc["report_refused"] is None:
        try:
            _write_json(report, doc)
        except OSError as exc:
            doc["report_refused"] = f"{type(exc).__name__}: {exc}"[:200]
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Closed-table self-heal for the box (no commands "
                                             "are read from anywhere; see the module docstring).")
    ap.add_argument("--dry-run", action="store_true",
                    help="decide and log every rule, act on nothing")
    args = ap.parse_args(argv)
    if not DESK.is_dir():
        print(f"box_self_heal: {DESK} is not a desk: the installed copy reads the repo root from "
              f"{_HERE / ROOT_FILE_NAME} (written by the installer), else {DEFAULT_BOX_ROOT}")
        return 2
    doc = run(apply=not args.dry_run)
    for r in doc["rows"]:
        print(f"[{r['level']:<10}] {r['rule']:<22} {r['verdict']:<16} {r['why']}")
    print(f"box_self_heal: {doc['status']} ({doc['n_red']} red) -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
