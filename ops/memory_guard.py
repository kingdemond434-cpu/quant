"""THE BOX'S MEMORY GUARD: a research job may never starve the live terminals, and a job it stops
is run again with a memory cap, so no research is lost.

WHY (2026-11-11). The FrontierAudit organ `libs.ops.scaling_laws` loaded the whole hypothesis
graph into memory, grew about 1.3 GB a minute to more than 30 GB of commit on the 96 GB trading
box, and pushed available memory toward the floor the MT5 terminals and the gateway need. Nothing
on the box could stop it: every desk session runs non-elevated and cannot end another user's
process, so the desk watched it grow and waited. The organ itself now streams (#1049); this is
the backstop for the next organ with the same bug, owned by a SYSTEM scheduled task that has the
right to act. Principal, 2026-11-11: "find solution to things like this always without reducing
roi".

WHAT IT DOES, every two minutes (MT5-MemoryGuard, SYSTEM):

  1. PROTECT. The live path is never a candidate: only python processes are, and never one whose
     command line names the money path or the release path (gateway, allocator, executor,
     deadman, OCO, order door, E8, FTMO, tape and tick recorders, bridge, promoter, shadow
     forward, sleeves, decision core, sizing, adopt, seal, sign train, release, self-heal, workflow
     gate, root pin), and never one whose ANCESTOR is a terminal or any such process -- a helper
     the gateway or Adopt-And-Seal spawned is protected whatever its own command line says. MT5
     terminals, the bridge and every non-python process are out of scope by construction.
  2. STOP AT MOST ONE JOB A PASS, and only when one of three rules holds:
       HARD CAP  one research process holds more than HARD_CAP_FRAC of physical memory. That is
                 a leak, not a workload: nothing on this desk legitimately needs a quarter of
                 the box, and the fix is streaming, not more RAM.
       PRESSURE  available memory is under the floor (or commit is near its limit), in which
                 case the LARGEST research process above MIN_STOP_MB is stopped.
       STALLED   a research process older than STALL_AGE_H that used under STALL_CPU_S of CPU
                 on EVERY pass for at least STALL_WINDOW_S (30 min, about 15 passes). That is a job stuck on a lock or a dead handle (the
                 merge_hypotheses pass that sat 43 h holding 15 GB of commit and an inherited
                 log handle, 2026-11-11), not a slow one: a working job burns CPU every pass.
     A stop is terminate, a grace period, then kill, for the process and its children only.
     Its parent (the cmd that runs a lane of organs) is untouched, so the lane moves on to its
     next organ instead of losing the whole pass.
  3. RE-QUEUE, AS ITS OWN TASK, NEVER AS SYSTEM. The stopped job's owner and the scheduled task
     that launched it (matched from its ancestors' command lines against the scheduler's "Task To
     Run") are written to the queue with why it was stopped. When the box has headroom again
     (available above twice the floor and commit below its line) and that task is not already
     running, the guard re-runs it with `schtasks /Run /TN <task>`, so it runs under the task's
     own principal, never this guard's. A recorded command line is NEVER started by the guard:
     a SYSTEM task that re-ran whatever a python process happened to be running would be a
     ready-made privilege escalation (audit of #1051, M1). A job whose task cannot be resolved is
     stopped and marked GAVE_UP ("owner unresolved; not re-run as SYSTEM"); it runs on its own
     schedule next time. The re-run is bounded by the same rules: a re-run that leaks again is
     stopped again within two minutes. At most MAX_ATTEMPTS re-runs per task per UTC day; after
     that the row is GAVE_UP with its reason. Nothing is dropped silently.

WHAT IT NEVER DOES. It never touches a non-python process, a money-path process, its own
process tree, or anything when memory is healthy and no process is over the hard cap. It throttles
nothing: a job that fits runs at full speed, which is the "without reducing ROI" half of the ask.

Output: desks/mt5/reports/MEMORY_GUARD.json (every pass) and desks/mt5/data/MEMORY_GUARD_QUEUE.json
(the re-queue). The hourly pass reads the report. Each STOP row records the victim's open files,
so a ledger left with a torn tail by the stop is named where the cause can be seen.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "MEMORY_GUARD.json"
QUEUE = DESK / "data" / "MEMORY_GUARD_QUEUE.json"
SEEN = DESK / "data" / "MEMORY_GUARD_SEEN.json"

MB = 1024 * 1024
HARD_CAP_FRAC = 0.25        # one research process above this share of physical RAM is a leak
FLOOR_FRAC = 0.125          # available memory below this share of physical RAM is pressure
COMMIT_LINE = 0.90          # commit above this share of the commit limit is pressure
MIN_STOP_MB = 2048          # under pressure a smaller job is never the cause, so never stopped
MAX_ATTEMPTS = 2            # re-runs per task per UTC day
GRACE_S = 10.0
STALL_AGE_H = 24.0          # a research job this old ...
STALL_CPU_S = 1.0           # ... that used less CPU than this between two passes is stuck
STALL_MIN_GAP_S = 60.0      # consecutive readings must be at least this far apart
STALL_WINDOW_S = 1800.0     # ... and idle on EVERY pass for at least this long (audit M3)

PYTHON_NAMES = frozenset({"python.exe", "pythonw.exe", "python", "python3", "py.exe"})
PROTECTED_NAMES = frozenset({"terminal64.exe", "metatester64.exe", "terminal.exe"})
#: Over-matching on purpose ("oco" and "tape" as substrings): a false protect costs one missed
#: stop, a false candidate can stop the money path.
MONEY_PATH = re.compile(
    r"(?i)gateway|allocator|executor|deadman|oco|money_closure|order_door|e8_|\be8\b|ftmo|"
    r"tape|tick_record|recorder|bridge|placement|venue|mt5desk[\\/.]run|terminal64|metatrader|"
    r"promoter|shadow_forward|sleeve|decision_core|sizing|adopt|seal|sign_train|release|"
    r"selfheal|self_heal|workflow_gate|root_pin")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _protected(name: Any, cmdline: Any) -> bool:
    cmd = " ".join(cmdline or []) if isinstance(cmdline, list) else str(cmdline or "")
    return (str(name or "").lower() in PROTECTED_NAMES or bool(MONEY_PATH.search(cmd))
            or "memory_guard" in cmd)


def is_candidate(proc: dict[str, Any], own_pids: set[int]) -> bool:
    """Only research python, never the money path, never under it, never ourselves."""
    if int(proc.get("pid") or -1) in own_pids:
        return False
    if str(proc.get("name") or "").lower() not in PYTHON_NAMES:
        return False
    if not proc.get("cmdline") or _protected(proc.get("name"), proc.get("cmdline")):
        return False
    ancestors = proc.get("ancestors")
    if ancestors is None:           # unreadable lineage is not a clean one
        return False
    return not any(_protected(a.get("name"), a.get("cmdline")) for a in ancestors)


def thresholds(snap: dict[str, Any]) -> dict[str, float | None]:
    total = snap.get("total_phys_mb")
    limit = snap.get("commit_limit_mb")
    return {
        "hard_cap_mb": total * HARD_CAP_FRAC if total else None,
        "floor_mb": total * FLOOR_FRAC if total else None,
        "commit_line_mb": limit * COMMIT_LINE if limit else None,
    }


def pressure(snap: dict[str, Any], th: dict[str, float | None]) -> list[str]:
    why = []
    free, commit = snap.get("free_phys_mb"), snap.get("commit_charge_mb")
    if free is not None and th["floor_mb"] is not None and free < th["floor_mb"]:
        why.append(f"available {free} MB under the {round(th['floor_mb'])} MB floor")
    if commit is not None and th["commit_line_mb"] is not None and commit > th["commit_line_mb"]:
        why.append(f"commit {commit} MB over {round(th['commit_line_mb'])} MB "
                   f"({int(COMMIT_LINE * 100)}% of the limit)")
    return why


def headroom(snap: dict[str, Any], th: dict[str, float | None]) -> bool:
    """Room to re-run: twice the floor available and commit under its line."""
    free, commit = snap.get("free_phys_mb"), snap.get("commit_charge_mb")
    if free is None or th["floor_mb"] is None:
        return False
    if free < 2 * th["floor_mb"]:
        return False
    return not (commit is not None and th["commit_line_mb"] is not None
                and commit > th["commit_line_mb"])


def idle_since(p: dict[str, Any], prev: dict[str, Any], now_ts: float) -> float | None:
    """When this process instance went idle and has stayed idle on every pass since; None when it
    is not idle now or cannot be compared. Idle means under STALL_CPU_S of CPU between two
    readings at least STALL_MIN_GAP_S apart. One quiet pass is not a stall (audit M3): a job
    blocked on I/O or a lock for a couple of minutes would read idle once, so the run of idle
    passes is carried forward and only a long one counts."""
    started, cpu = p.get("started"), p.get("cpu_s")
    seen = prev.get(str(p.get("pid")))
    if started is None or cpu is None or not isinstance(seen, dict) \
            or seen.get("started") != started:
        return None
    at = float(seen.get("at_ts") or now_ts)
    if now_ts - at < STALL_MIN_GAP_S:
        # Too close to the last reading to judge: carry its run unchanged.
        v = seen.get("idle_since")
        return float(v) if v is not None else None
    if float(cpu) - float(seen.get("cpu_s") or 0.0) >= STALL_CPU_S:
        return None
    v = seen.get("idle_since")
    return float(v) if v is not None else at


def stalled(p: dict[str, Any], prev: dict[str, Any], now_ts: float) -> float | None:
    """Seconds this process has been idle on every pass, when it is old enough to judge."""
    started = p.get("started")
    if started is None or now_ts - float(started) < STALL_AGE_H * 3600:
        return None
    since = idle_since(p, prev, now_ts)
    return None if since is None else now_ts - since


def plan(snap: dict[str, Any], procs: list[dict[str, Any]],
         own_pids: set[int], prev: dict[str, Any] | None = None,
         now_ts: float | None = None) -> dict[str, Any]:
    """Pure decision: which one process (if any) to stop and why."""
    th = thresholds(snap)
    cands = sorted((p for p in procs if is_candidate(p, own_pids)),
                   key=lambda p: -float(p.get("private_mb") or 0.0))
    under = pressure(snap, th)
    if th["hard_cap_mb"] is not None:
        for p in cands:
            if float(p.get("private_mb") or 0.0) > th["hard_cap_mb"]:
                return {"stop": p, "rule": "HARD_CAP", "thresholds": th, "pressure": under,
                        "why": (f"pid {p['pid']} holds {round(p['private_mb'])} MB, over the "
                                f"{round(th['hard_cap_mb'])} MB per-job cap")}
    if under:
        for p in cands:
            if float(p.get("private_mb") or 0.0) >= MIN_STOP_MB:
                return {"stop": p, "rule": "PRESSURE", "thresholds": th, "pressure": under,
                        "why": (f"{'; '.join(under)}; pid {p['pid']} is the largest research "
                                f"job at {round(p['private_mb'])} MB")}
    if prev and now_ts is not None:
        for p in cands:
            idle = stalled(p, prev, now_ts)
            if idle is not None and idle >= STALL_WINDOW_S:
                age_h = (now_ts - float(p["started"])) / 3600
                return {"stop": p, "rule": "STALLED", "thresholds": th, "pressure": under,
                        "why": (f"pid {p['pid']} has run {age_h:.1f} h and been idle (under "
                                f"{STALL_CPU_S:g} s of CPU per pass) on every pass for "
                                f"{idle / 60:.0f} min while holding "
                                f"{round(float(p.get('private_mb') or 0))} MB: it is stuck, not "
                                f"working")}
    if under:
        return {"stop": None, "rule": "PRESSURE_NO_CANDIDATE", "thresholds": th,
                "pressure": under,
                "why": ("memory is under pressure but no research job is large enough to be "
                        "the cause")}
    return {"stop": None, "rule": "CLEAR", "thresholds": th, "pressure": [], "why": "healthy"}


# ------------------------------------------------------------------------------- the re-queue

def _day(at: str) -> str:
    return str(at)[:10]


def load_queue(path: Path | None = None) -> list[dict[str, Any]]:
    path = QUEUE if path is None else path
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("jobs") if isinstance(doc, dict) else None
    return [r for r in rows or [] if isinstance(r, dict)]


def save_queue(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    path = QUEUE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"at": _now().isoformat(timespec="seconds"), "jobs": rows},
                              indent=1), "utf-8")
    os.replace(tmp, path)


def _norm(cmd: Any) -> str:
    text = " ".join(cmd) if isinstance(cmd, list) else str(cmd or "")
    return " ".join(text.replace('"', " ").replace("'", " ").lower().split())


def owning_task(proc: dict[str, Any], tasks: list[dict[str, str]]) -> str | None:
    """The scheduled task that launched `proc`: the task whose "Task To Run" is the command line
    of the process or one of its ancestors. Outermost ancestor first, so a lane's cmd wins over
    a python that happens to share a prefix. None when nothing matches."""
    chain = [*reversed(proc.get("ancestors") or []), proc]
    runs = [(t.get("TaskName") or "", _norm(t.get("Task To Run"))) for t in tasks]
    runs = [(n, r) for n, r in runs if n and len(r) >= 12]
    for node in chain:
        cmd = _norm(node.get("cmdline"))
        if len(cmd) < 12:
            continue
        for name, run in runs:
            if run == cmd or run in cmd or cmd in run:
                return name
    return None


def enqueue(rows: list[dict[str, Any]], proc: dict[str, Any], rule: str, why: str,
            at: str, task: str | None) -> list[dict[str, Any]]:
    key = task or " ".join(proc.get("cmdline") or [])
    peak = float(proc.get("private_mb") or 0)
    for r in rows:
        if r.get("key") == key and r.get("state") in ("QUEUED", "RUNNING"):
            r.update(state="QUEUED", last_stop_at=at, last_rule=rule, last_why=why,
                     peak_mb=max(float(r.get("peak_mb") or 0), peak))
            return rows
    row: dict[str, Any] = {
        "key": key, "task": task, "owner": proc.get("owner"),
        "cmdline": list(proc.get("cmdline") or []), "state": "QUEUED", "first_stop_at": at,
        "last_stop_at": at, "last_rule": rule, "last_why": why, "peak_mb": peak,
        "attempts": {}}
    if task is None:
        row.update(state="GAVE_UP", gave_up_why="owner unresolved; not re-run as SYSTEM -- no "
                   "scheduled task launched it, so it runs again only when its owner runs it")
    rows.append(row)
    return rows


def next_requeue(rows: list[dict[str, Any]], at: str,
                 running_tasks: set[str]) -> dict[str, Any] | None:
    """The oldest QUEUED task still under today's attempt cap and not already running."""
    day = _day(at)
    for r in sorted(rows, key=lambda r: str(r.get("last_stop_at") or "")):
        if r.get("state") != "QUEUED" or not r.get("task"):
            continue
        if r.get("task") in running_tasks:
            continue
        if int((r.get("attempts") or {}).get(day, 0)) >= MAX_ATTEMPTS:
            r["state"] = "GAVE_UP"
            r["gave_up_why"] = (f"{MAX_ATTEMPTS} re-runs today; it runs again on its own "
                                f"schedule. If the rule was HARD_CAP the organ needs to stream "
                                f"its input (the scaling_laws fix, #1049).")
            continue
        return r
    return None


def settle(rows: list[dict[str, Any]], running_tasks: set[str], at: str) -> list[dict[str, Any]]:
    """A RUNNING re-run whose task is no longer running finished -> DONE. DONE and GAVE_UP rows
    older than seven days leave the working queue (the pass reports that closed them are the
    record)."""
    keep = []
    for r in rows:
        if r.get("state") == "RUNNING" and r.get("task") not in running_tasks:
            r["state"] = "DONE"
            r["done_at"] = at
        if r.get("state") in ("DONE", "GAVE_UP"):
            last = str(r.get("done_at") or r.get("last_stop_at") or at)
            try:
                age = (datetime.fromisoformat(at) - datetime.fromisoformat(last)).days
            except ValueError:
                age = 0
            if age > 7:
                continue
        keep.append(r)
    return keep


# --------------------------------------------------------------------------- the box side (IO)

def _processes() -> list[dict[str, Any]]:
    import psutil  # type: ignore[import-untyped,unused-ignore]
    out = []
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            mi = p.memory_info()
            private = float(getattr(mi, "private", None) or getattr(mi, "vms", 0) or 0)
            ct = _safe(p.cpu_times)
            parents = _safe(p.parents)
            ancestors = None if parents is None else [
                {"pid": q.pid, "name": _safe(q.name), "cmdline": _safe(q.cmdline) or []}
                for q in parents]
            out.append({"pid": p.info["pid"], "name": p.info["name"],
                        "owner": _safe(p.username), "ancestors": ancestors,
                        "private_mb": private / MB, "rss_mb": mi.rss / MB,
                        "cmdline": p.cmdline(), "cwd": _safe(p.cwd),
                        "started": p.info.get("create_time"),
                        "cpu_s": (ct.user + ct.system) if ct is not None else None})
        except Exception:
            continue
    return out


def _safe(fn: Any) -> Any:
    try:
        return fn()
    except Exception:
        return None


def _own_pids() -> set[int]:
    import psutil  # type: ignore[import-untyped,unused-ignore]
    me = psutil.Process()
    pids = {me.pid}
    for p in me.parents():
        pids.add(p.pid)
    for c in me.children(recursive=True):
        pids.add(c.pid)
    return pids


def stop(pid: int) -> dict[str, Any]:
    """Terminate the process and its children, wait GRACE_S, kill what is left."""
    import psutil  # type: ignore[import-untyped,unused-ignore]
    try:
        p = psutil.Process(pid)
        tree = [*p.children(recursive=True), p]
    except psutil.NoSuchProcess:
        return {"pid": pid, "result": "GONE"}
    # WHAT IT HAD OPEN, recorded before the stop: a ledger whose tail the stop tears is then
    # named here, where its reader's error can be traced back (audit of #1051, should-fix).
    files = sorted({f.path for q in tree for f in (_safe(q.open_files) or [])})[:50]
    for q in tree:
        with contextlib.suppress(psutil.Error):
            q.terminate()
    _, alive = psutil.wait_procs(tree, timeout=GRACE_S)
    for q in alive:
        with contextlib.suppress(psutil.Error):
            q.kill()
    _, still = psutil.wait_procs(alive, timeout=GRACE_S)
    return {"pid": pid, "result": "STOPPED" if not still else "STILL_ALIVE",
            "tree": [q.pid for q in tree], "killed": [q.pid for q in alive],
            "open_files": files}


def _process_health() -> Any:
    """ops/process_health.py loaded by path: `ops` is also the name of desks/mt5/ops, a regular
    package that wins any `import ops.*` once desks/mt5 is importable."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_mg_process_health",
                                                  ROOT / "ops" / "process_health.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tasks() -> tuple[list[dict[str, str]], str]:
    """The scheduler's task table (name, "Task To Run", status), via process_health's bounded,
    parse-checked reader. An unreadable table is ([], reason): nothing is matched, nothing is
    re-run."""
    try:
        rows, status = _process_health()._tasks()
        return list(rows), str(status)
    except Exception as exc:
        return [], f"UNMEASURED: {type(exc).__name__}"


def rerun_task(task: str) -> dict[str, Any]:
    """`schtasks /Run /TN <task>`: the task starts under its OWN principal. Never as SYSTEM."""
    proc = subprocess.run(["schtasks", "/Run", "/TN", task], capture_output=True, text=True,
                          errors="replace", timeout=60)
    return {"task": task, "rc": proc.returncode,
            "out": ((proc.stdout or "") + (proc.stderr or "")).strip()[:300]}


def _load_seen() -> dict[str, Any]:
    try:
        doc = json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def seen_book(procs: list[dict[str, Any]], own: set[int], prev: dict[str, Any],
              now_ts: float) -> dict[str, Any]:
    """Each research process's CPU at this pass and how long it has been idle on every pass. A
    reading too close to the last one keeps the last one, so a burst of passes cannot shorten
    the measured gap."""
    doc: dict[str, Any] = {}
    for p in procs:
        if not is_candidate(p, own) or p.get("cpu_s") is None:
            continue
        seen = prev.get(str(p["pid"]))
        if isinstance(seen, dict) and seen.get("started") == p.get("started") \
                and now_ts - float(seen.get("at_ts") or now_ts) < STALL_MIN_GAP_S:
            doc[str(p["pid"])] = seen
            continue
        doc[str(p["pid"])] = {"started": p.get("started"), "cpu_s": p.get("cpu_s"),
                              "at_ts": now_ts, "idle_since": idle_since(p, prev, now_ts)}
    return doc


def _save_seen(procs: list[dict[str, Any]], own: set[int], prev: dict[str, Any],
               now_ts: float) -> None:
    """Persist `seen_book` for the next pass's STALLED rule."""
    doc = seen_book(procs, own, prev, now_ts)
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    tmp = SEEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc), "utf-8")
    os.replace(tmp, SEEN)


def run_pass(apply: bool = True) -> dict[str, Any]:
    memory_snapshot = _process_health().memory_snapshot

    at = _now().isoformat(timespec="seconds")
    snap = memory_snapshot()
    procs = _processes()
    own = _own_pids()
    now_ts = time.time()
    prev = _load_seen()
    decision = plan(snap, procs, own, prev=prev, now_ts=now_ts)
    rows = load_queue()
    tasks, tasks_status = _tasks()
    running = {t.get("TaskName", "") for t in tasks
               if str(t.get("Status", "")).lower() == "running"}
    tasks_read = bool(tasks)
    if tasks_read:
        rows = settle(rows, running, at)
    actions: list[dict[str, Any]] = []
    victim = decision.get("stop")
    if victim is not None and apply:
        task = owning_task(victim, tasks)
        res = stop(int(victim["pid"]))
        actions.append({"action": "STOP", "rule": decision["rule"], "why": decision["why"],
                        "cmdline": victim.get("cmdline"), "owner": victim.get("owner"),
                        "task": task, **res})
        if res["result"] != "GONE":
            rows = enqueue(rows, victim, decision["rule"], decision["why"], at, task)
    elif victim is None and apply and tasks_read and headroom(snap, decision["thresholds"]):
        nxt = next_requeue(rows, at, running)
        if nxt is not None:
            att = nxt.setdefault("attempts", {})
            att[_day(at)] = int(att.get(_day(at), 0)) + 1
            try:
                res = rerun_task(str(nxt["task"]))
                if res["rc"] == 0:
                    nxt["state"] = "RUNNING"
                actions.append({"action": "REQUEUE" if res["rc"] == 0 else "REQUEUE_FAILED",
                                **res})
            except Exception as exc:  # a failed start is an attempt, not a crash of the guard
                actions.append({"action": "REQUEUE_FAILED", "task": nxt["task"],
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    if apply:
        save_queue(rows)
        _save_seen(procs, own, prev, now_ts)
    top = sorted((p for p in procs if is_candidate(p, own)),
                 key=lambda p: -float(p.get("private_mb") or 0.0))[:5]
    doc = {
        "at": at, "applied": apply, "memory": snap,
        "verdict": decision["rule"], "why": decision["why"], "tasks_read": tasks_status,
        "thresholds_mb": {k: (round(v) if v is not None else None)
                          for k, v in decision["thresholds"].items()},
        "actions": actions,
        "queue": [{k: r.get(k) for k in ("key", "task", "owner", "state", "last_rule",
                                         "last_stop_at", "attempts", "peak_mb", "gave_up_why")}
                  for r in rows],
        "largest_research_jobs": [{"pid": p["pid"], "private_mb": round(p["private_mb"]),
                                   "cmd": " ".join(p.get("cmdline") or [])[:200]} for p in top],
        "protected": ("non-python processes, every command line matching the money-path "
                      "pattern, and every process with a terminal or such a process as an "
                      "ancestor"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    apply = "--apply" in args
    t0 = time.monotonic()
    doc = run_pass(apply=apply)
    acts = ", ".join(f"{a['action']} {a.get('pid')}" for a in doc["actions"]) or "none"
    print(f"memory guard {doc['at']}: {doc['verdict']} ({doc['why']}); actions: {acts}; "
          f"{time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
