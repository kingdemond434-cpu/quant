"""THE PLUMBING WATCHDOG -- the desk's plumbing may never stop PERMANENTLY and SILENTLY again.

    python desks/mt5/research/plumbing_watchdog.py --once --budget-s 180
    python desks/mt5/research/plumbing_watchdog.py --once --apply     # MT5-PlumbingWatchdog, 15 min

WHY THIS ORGAN EXISTS. Five failures were measured on this box inside one day, and every one of
them was a stop that LOOKED like running:

  1. THE BOX ADOPTED NO SHIPPED CODE FOR FOUR DAYS. `Adopt-And-Seal.ps1` could not OPEN the named
     mutex `Local\\MT5-GitWriter` -- a kernel object created under another principal's default
     descriptor -- and it logged that refusal correctly, once an hour, to a file nobody reads.
     Correct, polite, permanently wrong. The lock now lives at `MT5-GitWriter-v2`
     (`desks/mt5/scripts/GitWriterMutex.ps1`), and this organ TAKES it every pass, because a lock
     that cannot be taken is the only proof that matters.
  2. THE ADOPTION TASK SILENTLY EXPIRED. A `-Once` trigger whose repetition the scheduler folded
     to nine days; `Next Run Time: N/A`; later the task was gone from the scheduler entirely. A
     task that does not exist writes no artifact, raises no error and fails no check -- it is
     indistinguishable from a task that ran and found nothing to do.
  3. 72 ORPHANED POOL WORKERS HELD 147 GB OF A 251 GB COMMIT LIMIT while 67 GB of RAM was free.
     Every new leg then died of STATUS_COMMITMENT_LIMIT and left no artifact, so the departments
     built that week reported nothing, which reads on a board exactly like nothing to report.
  4. THE RECOMMENDATION LEDGER WENT 11.7 DAYS WITHOUT A WRITE while the CEO docket that feeds it
     ran hourly and exited 0. Green producer, dead artifact.
  5. A BANDIT WROTE `data/research_budget.json` WHILE SIX READERS READ
     `reports/RESEARCH_BANDIT.json`, which nothing wrote. A producer and its consumers
     disagreeing about a path, silently, for weeks: both halves green, the wire absent.

THE ONE RULE THEY SHARE: each was OBSERVABLE and nothing was shaped to observe it. So every check
here PROVES BY OBSERVATION, never by a label. Not "the task is registered" but "the scheduler
returns it, Enabled, with a next run time inside the hour and a last result that is not an error".
Not "the lock is fine" but "this process took it just now and gave it back". Not "the pipeline is
wired" but "the path the consumer reads is the path the producer writes".

NEVER SILENT. A defect that survives one pass escalates into three places a human meets without
asking: the desk state the dashboard renders (`web/desk_state.json -> plumbing`), the event log
(`PLUMBING_DEFECT`), and `docs/research/PLUMBING_ALERTS.md`. And the law gate's
`scripts/check_plumbing_watchdog.py` FAILS while any defect is older than its own escalation
window -- including the defect of this report being absent, because an absent watchdog is the
silence it exists to end.

NEVER A NEW FIXER. Repairs are raised through the control plane that already owns them:
`fingerprints.record` for the negative-knowledge ledger, and under `--apply` the reconciler's own
actuators (`reap_orphans` first, which is why `libs/ops/proctree.py` exists at all). This organ
observes and escalates; it never grows a healer of its own.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops import events, proctree  # noqa: E402
from libs.ops.control_plane import edges as edg  # noqa: E402
from libs.ops.control_plane import fingerprints as fp  # noqa: E402
from libs.ops.control_plane import lease  # noqa: E402
from libs.ops.control_plane import watermarks as wm  # noqa: E402

REPORT = DESK / "reports" / "PLUMBING_WATCHDOG.json"
DEFECT_STATE = DESK / "data" / "plumbing_defects.json"
ALERTS = ROOT / "docs" / "research" / "PLUMBING_ALERTS.md"
COMPONENT = "leg:plumbing_watchdog"

#: The adoption clock and this organ's own clock, by the names the scheduler must return.
ADOPT_TASK = "MT5-AdoptRelease"
WATCHDOG_TASK = "MT5-PlumbingWatchdog"

#: The mutex the four git writers share. `GitWriterMutex.ps1` is the only place the names live;
#: they are repeated here as the FALLBACK for a box where that helper has not landed, and the
#: helper is read first so the two can never drift apart silently.
MUTEX_NAMES: tuple[str, ...] = ("Global\\MT5-GitWriter-v2", "Local\\MT5-GitWriter-v2")

#: HOW LONG A DEFECT MAY LIVE BEFORE THE LAW GATE REFUSES TO PASS. Per check class, because the
#: cost of each is different: a dead adoption clock is four days of unshipped fixes, a path-pair
#: disagreement is a code change somebody has to write. None of these is a grace period for the
#: DEFECT -- it is published on pass one either way -- it is the window before the gate wedges.
ESCALATION_S: dict[str, int] = {
    "watchdog_artifact": 2 * 3600,
    "adoption_task": 3 * 3600,
    "adoption_lag": 6 * 3600,
    "git_writer_lock": 2 * 3600,
    "orphan_workers": 2 * 3600,
    "commit_headroom": 2 * 3600,
    "scheduled_task": 3 * 3600,
    "path_pair": 24 * 3600,
    "orphan_artifact_path": 24 * 3600,
    "fence_ran": 24 * 3600,
}
DEFAULT_ESCALATION_S = 24 * 3600

#: A defect escalates to the dashboard, the events log and the alerts page the moment it has been
#: seen on more than one pass. Once is an incident; twice is a stop.
ESCALATE_AFTER_PASSES = 1

UNMEASURED = "UNMEASURED"


# --------------------------------------------------------------------------- small utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return False
    return True


def _run(argv: Sequence[str], timeout: float = 60.0, cwd: Path | None = None) -> tuple[int, str]:
    """Run a command through the tree-killing runner. Never raises; returns (rc, stdout+stderr).

    `libs.ops.proctree.run` and not `subprocess.run`, for the reason proctree exists: a timeout
    that kills only the direct child leaves its pool behind, charged against the commit limit,
    forever. An organ whose job is to notice that leak may not be a source of it.
    """
    try:
        done = proctree.run(list(argv), timeout=timeout, capture_output=True, text=True,
                            cwd=str(cwd) if cwd else None)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return int(done.returncode or 0), f"{done.stdout or ''}{done.stderr or ''}"


def _powershell(script: str, timeout: float = 60.0) -> tuple[int, str]:
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


def _on_windows() -> bool:
    return os.name == "nt"


def _load_by_path(name: str, path: Path) -> Any:
    """Import a repo script by FILE PATH. None when it cannot be loaded, never a raise."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location(f"_pw_{name}", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def defect(check: str, organ: str, evidence: str, repair: str, *,
           severity: str = "MAJOR", key: str | None = None) -> dict[str, Any]:
    """One DEFECT ROW: the organ, the evidence that it is broken, and the repair. All three,
    always -- a row without a repair is a complaint, and complaints are what get muted."""
    return {"check": check, "organ": organ, "evidence": evidence, "repair": repair,
            "severity": severity, "key": key or f"{check}:{organ}",
            "escalate_after_s": ESCALATION_S.get(check, DEFAULT_ESCALATION_S)}


# ------------------------------------------------------------------- 1. the adoption clock
def _task_facts(name: str) -> dict[str, Any]:
    """What the SCHEDULER says about one task, or why it could not be asked.

    `Get-ScheduledTask` for existence and Enabled, `Get-ScheduledTaskInfo` for NextRunTime and
    LastTaskResult -- the four facts that would each, alone, have caught the four-day outage.
    """
    if not _on_windows():
        return {"measured": False, "why": "not a Windows host: the task scheduler is UNMEASURED"}
    rc, out = _powershell(
        "$ErrorActionPreference='SilentlyContinue';"
        f"$t = Get-ScheduledTask -TaskName '{name}';"
        "if (-not $t) { 'ABSENT'; exit }"
        f"$i = Get-ScheduledTaskInfo -TaskName '{name}';"
        "'STATE=' + $t.State;"
        "'PRINCIPAL=' + $t.Principal.UserId;"
        "'NEXT=' + $(if ($i.NextRunTime) { $i.NextRunTime.ToUniversalTime()"
        ".ToString('yyyy-MM-ddTHH:mm:ssZ') } else { 'NONE' });"
        "'LAST=' + $(if ($i.LastRunTime) { $i.LastRunTime.ToUniversalTime()"
        ".ToString('yyyy-MM-ddTHH:mm:ssZ') } else { 'NONE' });"
        "'RESULT=' + $i.LastTaskResult;", timeout=75)
    if rc not in (0,) and not out.strip():
        return {"measured": False, "why": f"Get-ScheduledTask failed (rc={rc})"}
    text = out.strip()
    if not text:
        return {"measured": False, "why": "the scheduler returned nothing at all"}
    if "ABSENT" in text.splitlines()[0]:
        return {"measured": True, "present": False}
    facts: dict[str, Any] = {"measured": True, "present": True}
    for ln in text.splitlines():
        k, _, v = ln.strip().partition("=")
        if k in ("STATE", "PRINCIPAL", "NEXT", "LAST", "RESULT"):
            facts[k.lower()] = v.strip()
    return facts


def _parse_iso(text: str | None) -> datetime | None:
    if not text or text in ("NONE", UNMEASURED):
        return None
    try:
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def check_task(name: str, *, max_next_run_s: int, check: str,
               now: datetime | None = None, facts: Mapping[str, Any] | None = None,
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """PROVE a clock by observation: present, Enabled, next run inside its window, last result
    not an error. Four separate facts because the outage arrived through each of them in turn."""
    t = now or _now()
    f = dict(facts) if facts is not None else _task_facts(name)
    rows: list[dict[str, Any]] = []
    if not f.get("measured"):
        rows.append(defect(check, name,
                           f"the scheduler could not be queried: {f.get('why')}",
                           "run this organ on the box; UNMEASURED is a verdict, never a pass "
                           "(L1.28a)", severity="MAJOR"))
        return rows, f
    if not f.get("present"):
        rows.append(defect(check, name,
                           f"{name} is ABSENT from the task scheduler. A task that does not "
                           f"exist writes no artifact, raises no error and fails no other "
                           f"check -- it reads exactly like a task with nothing to do.",
                           f"desks/mt5/scripts/install_adopt_release_task.ps1 (or the installer "
                           f"named for {name}) registers it daily-repeating-hourly under SYSTEM",
                           severity="CRITICAL"))
        return rows, f
    state = str(f.get("state") or UNMEASURED)
    if state.lower() not in ("ready", "running", "3", "4"):
        rows.append(defect(check, name,
                           f"{name} is in scheduler state {state!r}, not Ready/Running",
                           f"Enable-ScheduledTask -TaskName {name}", severity="CRITICAL"))
    nxt = _parse_iso(str(f.get("next") or ""))
    if nxt is None:
        rows.append(defect(check, name,
                           f"{name} has NO next run time. This is exactly how the adoption task "
                           f"expired: a -Once trigger whose repetition the scheduler folded to "
                           f"nine days, leaving 'Next Run Time: N/A' and four days of shipped "
                           f"code that never reached the box.",
                           "re-register with a DAILY trigger repeating hourly for one day, never "
                           "a -Once trigger with a long RepetitionDuration",
                           severity="CRITICAL", key=f"{check}:{name}:next_run"))
    else:
        ahead = (nxt - t).total_seconds()
        if ahead > max_next_run_s or ahead < -max_next_run_s:
            rows.append(defect(check, name,
                               f"{name} next runs {nxt.isoformat()} -- {ahead / 3600:.1f}h from "
                               f"now, outside its {max_next_run_s / 3600:.1f}h window",
                               "re-register the trigger; a clock whose next tick is a day away "
                               "is stopped, not slow",
                               severity="CRITICAL", key=f"{check}:{name}:next_run"))
    result = str(f.get("result") or UNMEASURED)
    # 267009 is "task is currently running"; 267011 is "has not yet run". Neither is an error.
    if result not in ("0", "267009", "267011", UNMEASURED):
        rows.append(defect(check, name,
                           f"{name} last exited {result} at {f.get('last')}",
                           f"read the task's own log, then repair the organ it runs; "
                           f"Get-ScheduledTaskInfo -TaskName {name}",
                           severity="MAJOR", key=f"{check}:{name}:last_result"))
    return rows, f


# ------------------------------------------------------- 2. does HEAD descend from the tip?
def adopt_branch(root: Path | None = None) -> str:
    """The branch the box is supposed to be running, read from the adopt script itself rather
    than from a second list that can drift away from it."""
    p = (root or ROOT) / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"
    try:
        src = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return UNMEASURED
    m = re.search(r'\$Branch\s*=\s*"([^"]+)"', src)
    return m.group(1) if m else UNMEASURED


def check_adoption_lag(root: Path | None = None,
                       runner: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """IS THE RUNNING TREE THE SHIPPED TREE? Measured as commits, not as a green log line.

    The four-day outage published a perfectly healthy adopt log every hour. The only observation
    that would have caught it is this one: how many commits on the branch tip are NOT ancestors
    of what this box has checked out.
    """
    base = root or ROOT
    run = runner or (lambda argv: _run(argv, timeout=45, cwd=base))
    branch = adopt_branch(base)
    facts: dict[str, Any] = {"branch": branch}
    rows: list[dict[str, Any]] = []
    if branch == UNMEASURED:
        rows.append(defect("adoption_lag", "Adopt-And-Seal.ps1",
                           "the adopt script declares no $Branch, so what this box SHOULD be "
                           "running is unknown",
                           "restore the `[string] $Branch = \"...\"` default in "
                           "desks/mt5/scripts/Adopt-And-Seal.ps1"))
        return rows, facts
    rc, head = run(["git", "rev-parse", "HEAD"])
    facts["head"] = head.strip().splitlines()[0][:12] if rc == 0 and head.strip() else UNMEASURED
    tip_rc, tip = run(["git", "rev-parse", f"origin/{branch}"])
    if tip_rc != 0 or not tip.strip():
        facts["tip"] = UNMEASURED
        facts["why"] = f"origin/{branch} is not a ref this checkout knows"
        rows.append(defect("adoption_lag", f"origin/{branch}",
                           f"the box cannot resolve origin/{branch}: {tip.strip()[:160]}",
                           "git fetch origin, then re-run the adopt task", severity="MAJOR"))
        return rows, facts
    facts["tip"] = tip.strip().splitlines()[0][:12]
    cnt_rc, cnt = run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"])
    behind: int | None = None
    if cnt_rc == 0 and cnt.strip():
        try:
            behind = int(cnt.strip().splitlines()[0])
        except ValueError:
            behind = None
    facts["commits_behind"] = behind if behind is not None else UNMEASURED
    anc_rc, _ = run(["git", "merge-base", "--is-ancestor", "HEAD", f"origin/{branch}"])
    facts["head_descends_from_tip"] = behind == 0
    facts["head_is_ancestor_of_tip"] = anc_rc == 0
    if behind is None:
        rows.append(defect("adoption_lag", ADOPT_TASK,
                           f"could not count commits between HEAD and origin/{branch}",
                           "git fetch origin && git rev-list --count HEAD..origin/" + branch,
                           severity="MAJOR"))
    elif behind > 0:
        rows.append(defect("adoption_lag", ADOPT_TASK,
                           f"this box's HEAD is {behind} commit(s) behind origin/{branch}. The "
                           f"gateway is running code that is not the shipped code; the last "
                           f"time this went unnoticed it lasted four days.",
                           "powershell desks/mt5/scripts/Adopt-And-Seal.ps1 -- and if it refuses, "
                           "the refusal is the defect: read desks/mt5/scripts/GitWriterMutex.ps1",
                           severity="CRITICAL"))
    return rows, facts


# ------------------------------------------------------------- 3. can the lock be taken NOW?
def _mutex_names(root: Path | None = None) -> tuple[str, ...]:
    p = (root or ROOT) / "desks" / "mt5" / "scripts" / "GitWriterMutex.ps1"
    try:
        src = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return MUTEX_NAMES
    m = re.search(r'\$Names\s*=\s*@\(([^)]*)\)', src)
    if not m:
        return MUTEX_NAMES
    found = tuple(re.findall(r'"([^"]+)"', m.group(1)))
    return found or MUTEX_NAMES


def check_git_writer_lock(root: Path | None = None,
                          prober: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """TAKE THE LOCK. Not "is the helper present" -- take it, hold it for a moment, give it back.

    The four-day outage was a lock that could not be OPENED (a kernel object created under
    another principal's default security descriptor: "Access to the path 'Local\\MT5-GitWriter'
    is denied"). No inspection of the code would have found it. One acquisition would have.
    """
    names = _mutex_names(root)
    facts: dict[str, Any] = {"names": list(names)}
    if prober is None and not _on_windows():
        facts["measured"] = False
        facts["why"] = "named mutexes are a Windows object; UNMEASURED off the box"
        return [], facts
    probe = prober or _probe_mutex
    res = probe(names)
    facts.update(res)
    if res.get("taken"):
        return [], facts
    return [defect("git_writer_lock", "Local\\MT5-GitWriter-v2",
                   f"the git-writer lock could not be taken right now: {res.get('why')}. Every "
                   f"adopt, seal, intel-ship and shadow-sync serialises on this object; when it "
                   f"cannot be opened they refuse, hourly, correctly, and ship nothing.",
                   "desks/mt5/scripts/GitWriterMutex.ps1 creates it with a permissive descriptor "
                   "-- confirm all four writers dot-source it, then kill any git/ssh process "
                   "holding it (scripts/check_scheduled_tasks.py stuck_writers)",
                   severity="CRITICAL")], facts


def _probe_mutex(names: Sequence[str]) -> dict[str, Any]:
    """Open each candidate name, take it with a zero wait, release it. Report the first success."""
    script = "\n".join((
        "$ok=$false; $why=''",
        "foreach ($n in @(" + ",".join(f"'{n}'" for n in names) + ")) {",
        "  try {",
        "    $created = $false",
        "    $m = New-Object System.Threading.Mutex($false, $n, [ref]$created)",
        "    if ($m.WaitOne(0)) {",
        "      $m.ReleaseMutex(); $m.Dispose(); 'TAKEN=' + $n; $ok=$true; break }",
        "    $m.Dispose(); $why += $n + ': held by another writer; '",
        "  } catch { $why += $n + ': ' + $_.Exception.Message + '; ' }",
        "}",
        "if (-not $ok) { 'FAILED=' + $why }"))
    rc, out = _powershell(script, timeout=45)
    text = (out or "").strip()
    for ln in text.splitlines():
        if ln.startswith("TAKEN="):
            return {"measured": True, "taken": True, "name": ln.split("=", 1)[1].strip()}
    why = next((ln.split("=", 1)[1] for ln in text.splitlines() if ln.startswith("FAILED=")),
               f"powershell rc={rc}: {text[:200]}")
    return {"measured": True, "taken": False, "why": why.strip()}


# ---------------------------------------------------- 4. orphaned workers and commit headroom
def _commit() -> dict[str, Any]:
    """The commit limit and what is free of it, MEASURED on this host.

    Physical memory is the wrong number and measuring it is how the 147 GB leak hid: 67 GB of RAM
    was free while the commit limit was exhausted, so every leg died of STATUS_COMMITMENT_LIMIT
    with plenty of RAM on the board.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return {"measured": False, "why": "psutil absent: commit headroom is UNMEASURED"}
    try:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
    except (OSError, RuntimeError) as exc:  # pragma: no cover - platform dependent
        return {"measured": False, "why": f"{type(exc).__name__}: {exc}"}
    mb = 1024 * 1024
    limit = int((vm.total + sw.total) // mb)
    free = int((vm.available + sw.free) // mb)
    return {"measured": True, "commit_limit_mb": limit, "commit_free_mb": free,
            "phys_free_mb": int(vm.available // mb), "phys_total_mb": int(vm.total // mb)}


def commit_floor_mb(limit_mb: int) -> int:
    """The headroom floor, DERIVED from the measured limit, never from a machine size in a note.

    8% of this host's own commit limit, floored at 2,048 MB so a tiny reading cannot make the
    check vacuous. CLAUDE.md carries the cautionary case: a floor sized for a 96 GB box was
    applied to the 8 GB box that actually trades, and stood the gauntlet down twice.
    """
    return max(2048, int(limit_mb * 0.08))


def check_processes(reaper: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report = (reaper or (lambda: proctree.reap_orphaned_workers(apply=False)))()
    mem = _commit()
    facts = {"orphans": report, "memory": mem}
    rows: list[dict[str, Any]] = []
    if report.get("measured") and int(report.get("orphans") or 0) > 0:
        rows.append(defect("orphan_workers", "pool workers",
                           f"{report['orphans']} orphaned pool worker(s) holding "
                           f"{report.get('orphan_commit_mb')} MB of commit. Their parents are "
                           f"gone, so nothing can ever collect their results; they only hold "
                           f"commit. 72 of these held 147 GB on 2026-09-22 and every new leg "
                           f"died of STATUS_COMMITMENT_LIMIT.",
                           "the control plane's reap_orphans actuator "
                           "(desks/mt5/scripts/reap_orphaned_workers.py) runs first in every "
                           "--apply pass; if they survive it, a launcher is not using "
                           "libs/ops/proctree.run",
                           severity="CRITICAL"))
    if not report.get("measured"):
        rows.append(defect("orphan_workers", "pool workers",
                           "the process table is UNMEASURED (psutil absent), so an orphan leak "
                           "of any size would be invisible",
                           "install psutil on the box; UNMEASURED is a verdict, not a pass",
                           severity="MAJOR"))
    if mem.get("measured"):
        floor = commit_floor_mb(int(mem["commit_limit_mb"]))
        facts["commit_floor_mb"] = floor
        if int(mem["commit_free_mb"]) < floor:
            rows.append(defect("commit_headroom", "host commit limit",
                               f"commit free {mem['commit_free_mb']} MB is below the derived "
                               f"floor {floor} MB of a {mem['commit_limit_mb']} MB limit "
                               f"(physical free {mem['phys_free_mb']} MB -- physical is the "
                               f"number that lies here)",
                               "reap orphans, then find the launcher that is not bounding its "
                               "pool; every spawn path must go through libs/ops/proctree.run",
                               severity="CRITICAL"))
    else:
        rows.append(defect("commit_headroom", "host commit limit",
                           f"commit headroom is UNMEASURED: {mem.get('why')}",
                           "install psutil on the box", severity="MAJOR"))
    return rows, facts


# ------------------------------------------------------- 5. every declared clock still exists
def check_declared_tasks(present: Mapping[str, str] | None = None,
                         declared: Sequence[str] | None = None) -> tuple[list[dict[str, Any]],
                                                                        dict[str, Any]]:
    """Every task the installer declares must be in the scheduler and Enabled.

    The declared list is READ FROM THE INSTALLER (`scripts/check_scheduled_tasks.declared`), never
    typed again here: a second list is a second opinion, and the desk has paid for those.
    """
    if declared is None or present is None:
        # LOADED BY PATH, never `from scripts import ...`. `tests/scripts/__init__.py` makes a
        # REGULAR package called `scripts`, and a regular package beats the repo root's namespace
        # package wherever it sits on sys.path -- so the package import silently resolved to the
        # TEST directory, this function took its ImportError branch, and the watchdog reported
        # "not importable" instead of the box's disabled clocks. A watchdog defeated by an
        # import-shadowing rule is exactly the silent stop it exists to end.
        cst = _load_by_path("check_scheduled_tasks", ROOT / "scripts" / "check_scheduled_tasks.py")
        if cst is None:
            return [], {"measured": False,
                        "why": "scripts/check_scheduled_tasks.py could not be loaded"}
        want = list(declared) if declared is not None else cst.declared()
        have = dict(present) if present is not None else cst.present()
    else:
        want, have = list(declared), dict(present)
    facts: dict[str, Any] = {"declared": len(want), "present": len(have)}
    if not have:
        facts["measured"] = False
        facts["why"] = ("the scheduler returned no tasks at all -- either this is not the box, "
                        "or every clock is gone (measured 2026-09-15: eighteen of twenty were)")
        return [], facts
    facts["measured"] = True
    rows: list[dict[str, Any]] = []
    absent = [n for n in want if have.get(n) is None]
    disabled = [n for n in want
                if str(have.get(n) or "").strip().lower() in ("disabled", "1")]
    live = [n for n in want if have.get(n) is not None]
    facts.update({"absent": absent, "disabled": disabled, "present_declared": len(live)})
    for name in absent:
        rows.append(defect("scheduled_task", name,
                           f"{name} is declared by the installer and ABSENT from the scheduler",
                           "re-run the installer that declares it "
                           "(desks/mt5/scripts/Install-QuantWindows.ps1 or the task's own "
                           "install_*.ps1); then confirm with Get-ScheduledTask",
                           severity="CRITICAL"))
    # ONE DEFECT, NOT FORTY, WHEN THE DESK IS ADMINISTRATIVELY STOPPED. Every clock disabled is
    # ONE fact -- somebody turned the box off -- and no session can repair it by editing code.
    # Publishing it as forty rows is how a watchdog gets muted, and a muted watchdog is the
    # silence this organ exists to end. The same suspension `check_no_staleness` already makes,
    # for the same reason, and it is LOUDER not quieter: one CRITICAL row naming every clock.
    if live and len(disabled) >= max(3, int(0.8 * len(live))):
        rows.append(defect("scheduled_task", "the whole box",
                           f"{len(disabled)} of {len(live)} declared tasks are Disabled -- the "
                           f"desk is administratively STOPPED, not slow. Nothing on this box is "
                           f"adopting, judging, enrolling or trading: "
                           f"{', '.join(sorted(disabled)[:12])}"
                           + (" ..." if len(disabled) > 12 else ""),
                           "Get-ScheduledTask MT5-* | Enable-ScheduledTask -- and if the stop "
                           "was deliberate, it still belongs in the principal's hands, not in a "
                           "silence",
                           severity="CRITICAL", key="scheduled_task:box_administratively_stopped"))
    else:
        for name in disabled:
            rows.append(defect("scheduled_task", name,
                               f"{name} exists but is Disabled",
                               f"Enable-ScheduledTask -TaskName {name}", severity="CRITICAL"))
    facts["missing"] = absent
    return rows, facts


# ------------------------------------------------- 6. producer and consumer agree on the path
_WRITE_VERBS = re.compile(
    r"write_text|write_report|json\.dump|os\.replace|to_json|to_parquet|to_csv|"
    r"open\([^)]*['\"][wax]|savez|\.save\(|write_bytes|stamp_sidecar")

_LEG_SCRIPT = re.compile(r'_producer\(\s*"([A-Za-z0-9_]+)"\s*,\s*"([^"]+)"')


def leg_scripts(root: Path | None = None) -> dict[str, str]:
    """leg name -> the script `hourly_cycle` actually runs for it, parsed from the cycle itself.

    DERIVED, NOT LISTED. The mapping exists in exactly one place already -- the `_producer` calls
    in `hourly_cycle.py` -- and a hand copy of it here would be the same class of defect this
    check hunts: two statements of one fact, drifting apart in silence.
    """
    base = root or ROOT
    src = base / "desks" / "mt5" / "research" / "hourly_cycle.py"
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return dict(_LEG_SCRIPT.findall(text))


def _component_source(component: str, legs: Mapping[str, str],
                      root: Path) -> tuple[Path | None, str]:
    """The file behind a `leg:x` / `task:X` component id, and its text. ('', '') when unknown."""
    if component.startswith("leg:"):
        script = legs.get(component.split(":", 1)[1])
        if script:
            for cand in (root / "desks" / "mt5" / script, root / script):
                if cand.exists():
                    try:
                        return cand, cand.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        return cand, ""
    return None, ""


def check_edge_paths(root: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """THE ARTIFACT A CONSUMER READS MUST BE THE ONE ITS PRODUCER WRITES.

    Derived from `libs/ops/control_plane/edges.py` REQUIRED_EDGES -- the desk's declared pipeline
    -- and never from a list kept here. Three ways an edge's PATH can be a lie, each measured:

        NEVER_WRITTEN   the declared artifact does not exist on disk at all. Nothing has ever
                        produced it, whatever both ends report about themselves.
        PRODUCER_MUTE   the producer's source never names the path, so it cannot be its writer.
        CONSUMER_MUTE   the consumer's source never names the path, so it cannot be its reader.

    The measured case: a bandit wrote `data/research_budget.json` while six readers read
    `reports/RESEARCH_BANDIT.json`, which nothing wrote. Both ends green, the wire absent.
    """
    base = root or ROOT
    legs = leg_scripts(base)
    rows: list[dict[str, Any]] = []
    checked = 0
    for e in edg.REQUIRED_EDGES:
        if e.criticality != "required":
            continue
        checked += 1
        art = base / e.artifact
        name = Path(e.artifact).name
        if not art.exists():
            rows.append(defect("path_pair", e.edge_id,
                               f"the declared artifact {e.artifact} does not exist. {e.producer} "
                               f"is supposed to write it and {e.consumer} to read it; nothing "
                               f"has ever produced it. ({e.why})",
                               f"run {e.producer} and confirm it writes {e.artifact}; if it "
                               f"writes somewhere else, the edge or the organ is wrong and one "
                               f"of them must move",
                               severity="CRITICAL", key=f"path_pair:{e.edge_id}:absent"))
            continue
        _pp, ptext = _component_source(e.producer, legs, base)
        _cp, ctext = _component_source(e.consumer, legs, base)
        if ptext and name not in ptext:
            rows.append(defect("path_pair", e.edge_id,
                               f"{e.producer}'s source never names {name}, so it cannot be the "
                               f"writer of {e.artifact} the pipeline declares it to be",
                               f"either {e.producer} writes {e.artifact}, or edges.py names the "
                               f"path it really writes -- a producer and a declaration "
                               f"disagreeing about a path is how RESEARCH_BANDIT.json went weeks "
                               f"with six readers and no writer",
                               key=f"path_pair:{e.edge_id}:producer"))
        if ctext and name not in ctext:
            rows.append(defect("path_pair", e.edge_id,
                               f"{e.consumer}'s source never names {name}, so it cannot be "
                               f"reading {e.artifact}",
                               f"point {e.consumer} at {e.artifact}, or correct the edge",
                               key=f"path_pair:{e.edge_id}:consumer"))
    return rows, {"edges_checked": checked}


_JSON_LITERAL = re.compile(r'"((?:reports|data)/[A-Za-z0-9_./-]+\.(?:json|jsonl))"')

#: WHERE THE LIVE DESK LIVES. The scan is bounded to the MT5 desk and the libraries its organs
#: import, and deliberately NOT to the repo's root `scripts/`: that directory still holds the
#: retired crypto-exchange operations lane, whose artifacts live on the VPS and are gitignored
#: here. Reporting 73 of those as orphaned wires would bury the one MT5 row that matters under
#: a ground the standing mandate says is never hunted again.
SCAN_ROOTS: tuple[str, ...] = (
    "desks/mt5/research", "desks/mt5/scripts", "desks/mt5/moat", "desks/mt5/prop",
    "libs/research", "libs/ops", "libs/moat", "libs/portfolio",
)


def check_orphan_artifact_paths(root: Path | None = None,
                                limit_files: int = 4000) -> tuple[list[dict[str, Any]],
                                                                  dict[str, Any]]:
    """PATHS THAT ARE READ BY SEVERAL ORGANS AND WRITTEN BY NONE.

    The generalisation of failure 5. A path literal that appears in two or more modules, in none
    of them beside a write verb, is a file every one of those readers expects and nobody creates.
    Two readers is the threshold on purpose: one module naming a path it does not write is an
    ordinary consumer of somebody else's artifact; two, with no writer anywhere, is a wire that
    was never connected.

    THE WRITE IS USUALLY NOT BESIDE THE LITERAL, and pretending otherwise is how this check first
    reported 128 false positives on its own repo: the desk's house style is
    `OUT = DESK / "reports" / "X.json"` at the top of the module and `OUT.write_text(...)` four
    hundred lines down. So when a literal is bound to a constant, the WHOLE module is searched for
    a write through that constant. A check whose first output is mostly noise is a check the next
    session switches off, and then the one true row it would have found is lost with it.
    """
    base = root or ROOT
    files: list[Path] = []
    for rel_root in SCAN_ROOTS:
        sub = base / rel_root
        if sub.exists():
            files.extend(sorted(sub.rglob("*.py"))[:limit_files])
    readers: dict[str, set[str]] = {}
    writers: dict[str, set[str]] = {}
    for f in files[:limit_files]:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _JSON_LITERAL.finditer(text):
            rel = m.group(1)
            line_start = text.rfind("\n", 0, m.start()) + 1
            const = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=",
                             text[line_start:m.start()])
            window = text[max(0, m.start() - 220): m.end() + 220]
            wrote = bool(_WRITE_VERBS.search(window))
            if not wrote and const:
                nm = re.escape(const.group(1))
                wrote = bool(re.search(
                    rf"\b{nm}\s*\.\s*(?:write_text|write_bytes|open\(\s*['\"][wax]|parent\.mkdir)"
                    rf"|(?:write_report|stamp_sidecar|_atomic_write|os\.replace|json\.dump)"
                    rf"\([^)]*\b{nm}\b"
                    rf"|\bto_(?:json|csv|parquet)\(\s*{nm}\b", text))
            (writers if wrote else readers).setdefault(rel, set()).add(f.name)
    rows: list[dict[str, Any]] = []
    orphans: list[str] = []
    for rel, who in sorted(readers.items()):
        if writers.get(rel) or len(who) < 2:
            continue
        if (base / rel).exists() or (base / "desks" / "mt5" / rel).exists():
            continue
        orphans.append(rel)
        rows.append(defect("orphan_artifact_path", rel,
                           f"{len(who)} module(s) read {rel} -- {', '.join(sorted(who)[:6])} -- "
                           f"no module in this tree writes it and no such file exists. This is "
                           f"the shape that cost the desk weeks: a bandit wrote "
                           f"data/research_budget.json while six readers read "
                           f"reports/RESEARCH_BANDIT.json.",
                           f"make one producer write {rel}, or repoint the readers at the path "
                           f"the producer really writes"))
    return rows, {"paths_scanned": len(readers) + len(writers), "orphan_paths": orphans[:40],
                  "files_scanned": len(files)}


# ------------------------------------------------------------- 7. every fence has actually run
def check_fences_ran(root: Path | None = None,
                     now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A GATE THAT NEVER RAN IS A CLAIM THE DESK CANNOT CASH (L1.49).

    `data/law_gate.json` is the only record that the battery ran. Every fence registered in
    `run_law_gate` must appear in it, and the record itself must be inside a day.
    """
    base = root or ROOT
    t = now or _now()
    doc = _read_json(base / "data" / "law_gate.json")
    facts: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    # BY PATH, for the reason `check_declared_tasks` explains: `scripts` is a namespace package
    # that a regular `scripts` package elsewhere on sys.path shadows without a word.
    gate = _load_by_path("run_law_gate", base / "scripts" / "run_law_gate.py")
    if gate is None or not hasattr(gate, "_LAW_FENCES"):
        return [], {"measured": False, "why": "scripts/run_law_gate.py could not be loaded"}
    want = {n for n, _a in (*gate._LAW_FENCES, *gate._STATE_FENCES)}
    facts["declared_fences"] = len(want)
    if not isinstance(doc, dict):
        rows.append(defect("fence_ran", "run_law_gate",
                           "data/law_gate.json is absent or unreadable: there is no record that "
                           "the law battery has ever run on this box",
                           "./ops/gates.sh --full", severity="MAJOR",
                           key="fence_ran:law_gate:absent"))
        return rows, facts
    gen = _parse_iso(str(doc.get("generated") or ""))
    facts["generated"] = doc.get("generated")
    age_h = (t - gen).total_seconds() / 3600 if gen else None
    facts["age_h"] = round(age_h, 1) if age_h is not None else UNMEASURED
    results = doc.get("results")
    seen: set[str] = set()
    if isinstance(results, dict):
        seen = {str(k) for k in results}
    elif isinstance(results, list):
        for r in results:
            if isinstance(r, Mapping):
                seen.add(str(r.get("fence") or r.get("name") or r.get("script") or ""))
            else:
                seen.add(str(r))
    missing = sorted(n for n in want if not any(n in s for s in seen))
    facts["fences_recorded"] = len(seen)
    facts["never_ran"] = missing[:40]
    if age_h is not None and age_h > 36:
        rows.append(defect("fence_ran", "run_law_gate",
                           f"the last full law gate ran {age_h:.1f}h ago",
                           "./ops/gates.sh --full", severity="MAJOR",
                           key="fence_ran:law_gate:stale"))
    for name in missing:
        rows.append(defect("fence_ran", name,
                           f"{name} is registered in run_law_gate and does not appear in the "
                           f"last battery's results: a gate that never ran is a claim the desk "
                           f"cannot cash (L1.49)",
                           f"python scripts/{name}", key=f"fence_ran:{name}"))
    return rows, facts


# ---------------------------------------------------------------- the pass, and escalation
def _load_first_seen(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read_json(path or DEFECT_STATE)
    rows = (doc or {}).get("defects") if isinstance(doc, dict) else None
    return {str(k): dict(v) for k, v in (rows or {}).items()} if isinstance(rows, dict) else {}


def age_defects(rows: Sequence[Mapping[str, Any]], prior: Mapping[str, Mapping[str, Any]],
                now: datetime) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Carry each defect's FIRST SEEN forward, count the passes it has survived, and decide
    escalation. A defect that heals drops out of the ledger, so a recurrence is a new first
    sighting and its age is honest rather than cumulative."""
    out: list[dict[str, Any]] = []
    ledger: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = str(r.get("key"))
        was = prior.get(key) or {}
        first = _parse_iso(str(was.get("first_seen") or "")) or now
        passes = int(was.get("passes") or 0) + 1
        age_s = max(0.0, (now - first).total_seconds())
        window = int(r.get("escalate_after_s") or DEFAULT_ESCALATION_S)
        row = {**r, "first_seen": first.isoformat(timespec="seconds"), "passes": passes,
               "age_s": int(age_s),
               "escalated": passes > ESCALATE_AFTER_PASSES,
               "past_escalation_window": age_s > window}
        out.append(row)
        ledger[key] = {"first_seen": row["first_seen"], "passes": passes,
                       "check": r.get("check"), "organ": r.get("organ")}
    return out, ledger


def render_alerts(doc: Mapping[str, Any], path: Path | None = None) -> str:
    """docs/research/PLUMBING_ALERTS.md -- the page a human meets without asking for it."""
    p = path or ALERTS
    rows = [r for r in (doc.get("defects") or []) if r.get("escalated")]
    lines = [
        "# PLUMBING ALERTS",
        "",
        "<!-- DERIVED. Written by desks/mt5/research/plumbing_watchdog.py every pass; never",
        "     edit by hand. Editing this file hides a defect instead of repairing it. -->",
        "",
        f"Generated {doc.get('at')} from `desks/mt5/reports/PLUMBING_WATCHDOG.json`.",
        "",
        f"**{len(doc.get('defects') or [])} defect(s) this pass; {len(rows)} escalated "
        f"(seen on more than one pass).**",
        "",
    ]
    if not rows:
        lines += ["No escalated plumbing defect. The adoption clock, the git-writer lock, the "
                  "process table, the declared task set, the pipeline's path pairs and the law "
                  "battery were all observed, not assumed.", ""]
    else:
        lines += ["| organ | check | age | passes | evidence | repair |",
                  "|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: (-int(x.get("age_s") or 0), str(x.get("organ")))):
            ev = str(r.get("evidence") or "").replace("|", "\\|").replace("\n", " ")
            rp = str(r.get("repair") or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{r.get('organ')}` | {r.get('check')} | "
                         f"{int(r.get('age_s') or 0) // 3600}h | {r.get('passes')} | "
                         f"{ev[:300]} | {rp[:220]} |")
        lines.append("")
    lines += [
        "## Why this page exists",
        "",
        "Every failure it watches for was already being logged correctly when it happened, once "
        "an hour, to a file nobody reads. The adoption task refused the git-writer mutex for four "
        "days and said so every time. Silence is not the absence of a message; it is the absence "
        "of a reader. `scripts/check_plumbing_watchdog.py` fails the law gate while any defect "
        "above is older than its own escalation window -- including the defect of this page's own "
        "report being missing.",
        "",
    ]
    text = "\n".join(lines)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    except OSError:
        pass
    return text


def _raise_through_control_plane(rows: Sequence[Mapping[str, Any]], *, apply: bool,
                                 runner: Any = None) -> dict[str, Any]:
    """Raise every defect through the plane that already owns repair. Never a fixer of our own.

    OBSERVE: each defect is recorded as a failure FINGERPRINT against its component, so a shape
    seen twice appears in the control plane's published debt with the test that must forbid it.

    APPLY: the reaper runs FIRST, always, for the reason libs/ops/proctree.py exists -- an
    exhausted commit limit makes every other repair fail in a way that looks like a different
    problem. It is the reconciler's own `reap_orphans` actuator, run through `run_actuator`, so
    its postcondition is proved rather than inferred from a return code.
    """
    out: dict[str, Any] = {"fingerprints": 0, "actuators": []}
    for r in rows:
        ok = fp.record(f"{r.get('check')}: {r.get('evidence')}",
                       f"plumbing:{r.get('organ')}",
                       invariant_test="desks/mt5/tests/test_plumbing_watchdog.py")
        if ok:
            out["fingerprints"] += 1
    if not apply:
        return out
    try:
        from libs.ops.control_plane import actuators as act
        a = act.desk_actuators().get("reap_orphans")
        if a is None:
            out["actuators"].append({"name": "reap_orphans", "result": "ABSENT",
                                     "why": "the control plane declares no reap_orphans actuator"})
            return out
        rec = act.run_actuator(a, {"component_id": COMPONENT}, apply=True, runner=runner)
        out["actuators"].append({"name": "reap_orphans", **{k: rec.get(k) for k in
                                                            ("result", "repaired", "why")}})
    except Exception as exc:  # a repair that cannot run may never take the watchdog with it
        out["actuators"].append({"name": "reap_orphans", "result": "FAILED",
                                 "why": f"{type(exc).__name__}: {exc}"})
    return out


def run(*, budget_s: float = 180.0, apply: bool = False, root: Path | None = None,
        now: datetime | None = None, write: bool = True,
        state_path: Path | None = None) -> dict[str, Any]:
    """One pass. Every check is time-boxed by the caller's budget and none may raise."""
    base = root or ROOT
    t = now or _now()
    t0 = time.monotonic()
    defects: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}
    skipped: list[str] = []

    checks: tuple[tuple[str, Any], ...] = (
        ("adoption_task", lambda: check_task(ADOPT_TASK, max_next_run_s=3600,
                                             check="adoption_task", now=t)),
        ("watchdog_task", lambda: check_task(WATCHDOG_TASK, max_next_run_s=1800,
                                             check="scheduled_task", now=t)),
        ("adoption_lag", lambda: check_adoption_lag(base)),
        ("git_writer_lock", lambda: check_git_writer_lock(base)),
        ("processes", check_processes),
        ("declared_tasks", check_declared_tasks),
        ("edge_paths", lambda: check_edge_paths(base)),
        ("orphan_artifact_paths", lambda: check_orphan_artifact_paths(base)),
        ("fences_ran", lambda: check_fences_ran(base, t)),
    )
    for name, fn in checks:
        if time.monotonic() - t0 >= budget_s:
            skipped.append(name)
            continue
        try:
            rows, detail = fn()
        except Exception as exc:  # a watchdog may never be the thing that dies
            rows = [defect("watchdog_artifact", name,
                           f"the {name} check raised {type(exc).__name__}: {exc}",
                           "repair the check; a watchdog that crashes is the silence it exists "
                           "to end", severity="MAJOR", key=f"watchdog_check:{name}")]
            detail = {"error": f"{type(exc).__name__}: {exc}"}
        defects.extend(rows)
        facts[name] = detail

    prior = _load_first_seen(state_path)
    aged, ledger = age_defects(defects, prior, t)
    escalated = [r for r in aged if r.get("escalated")]
    overdue = [r for r in aged if r.get("past_escalation_window")]
    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "PLUMBING_MOVING": not defects,
        "defects": aged,
        "n_defects": len(aged),
        "n_escalated": len(escalated),
        "n_past_escalation_window": len(overdue),
        "escalated_keys": [r["key"] for r in escalated],
        "past_window_keys": [r["key"] for r in overdue],
        "checks_run": [n for n, _ in checks if n not in skipped],
        "checks_skipped_for_budget": skipped,
        "facts": facts,
        "escalation_windows_s": dict(ESCALATION_S),
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("every check proves by OBSERVATION: the scheduler returns the task, the mutex "
                 "is taken and released, HEAD is counted against the branch tip, the process "
                 "table is read, and the path a consumer reads is compared to the path its "
                 "producer writes. A label is never evidence."),
    }
    doc["control_plane"] = _raise_through_control_plane(aged, apply=apply)
    if write:
        _write_json(state_path or DEFECT_STATE,
                    {"at": doc["at"], "defects": ledger})
        try:
            env = lease.write_report(REPORT, doc, COMPONENT, inputs=(), ttl="fifteen_minute",
                                     root=base)
            doc = {**doc, "envelope": {"artifact_id": env.get("artifact_id"),
                                       "producer_run_id": env.get("producer_run_id")}}
            wm.progress(COMPONENT, "watchdog_passes",
                        int((wm.read(COMPONENT) or {}).get("value") or 0) + 1,
                        run_id=str(env.get("producer_run_id")))
        except (OSError, ValueError, RuntimeError):
            _write_json(REPORT, doc)
        render_alerts(doc, ALERTS if base == ROOT else base / "docs" / "research" /
                      "PLUMBING_ALERTS.md")
        for r in escalated:
            events.emit("PLUMBING_DEFECT", organ=str(r.get("organ")), check=str(r.get("check")),
                        age_s=int(r.get("age_s") or 0), passes=int(r.get("passes") or 0),
                        severity=str(r.get("severity")), evidence=str(r.get("evidence"))[:400])
        if not defects:
            events.emit("PLUMBING_CLEAR", checks=len(doc["checks_run"]))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=180.0)
    ap.add_argument("--apply", action="store_true",
                    help="raise repairs through the control plane's actuators (reaper first)")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 while any defect is past its escalation window")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, apply=bool(a.apply), write=not a.no_write)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"plumbing watchdog {doc['at']}: PLUMBING_MOVING={doc['PLUMBING_MOVING']} "
              f"defects={doc['n_defects']} escalated={doc['n_escalated']} "
              f"past_window={doc['n_past_escalation_window']} in {doc['elapsed_s']}s")
        for r in doc["defects"][:20]:
            mark = "!!" if r.get("past_escalation_window") else ("! " if r.get("escalated")
                                                                 else "  ")
            print(f" {mark} [{r['severity']}] {r['organ']} ({r['check']}, "
                  f"{int(r.get('age_s') or 0) // 3600}h, pass {r.get('passes')})")
            print(f"      {str(r['evidence'])[:200]}")
            print(f"      repair: {str(r['repair'])[:180]}")
        if doc["checks_skipped_for_budget"]:
            print(f"  skipped for budget: {doc['checks_skipped_for_budget']}")
    if a.strict and doc["n_past_escalation_window"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
