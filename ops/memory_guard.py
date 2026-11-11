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
     command line names the money path (gateway, allocator, executor, deadman, OCO, order door,
     E8, FTMO, tape and tick recorders, bridge). MT5 terminals, the bridge and every non-python
     process are out of scope by construction.
  2. STOP AT MOST ONE JOB A PASS, and only when one of three rules holds:
       HARD CAP  one research process holds more than HARD_CAP_FRAC of physical memory. That is
                 a leak, not a workload: nothing on this desk legitimately needs a quarter of
                 the box, and the fix is streaming, not more RAM.
       PRESSURE  available memory is under the floor (or commit is near its limit), in which
                 case the LARGEST research process above MIN_STOP_MB is stopped.
       STALLED   a research process older than STALL_AGE_H that used under STALL_CPU_S of CPU
                 between two passes. That is a job stuck on a lock or a dead handle (the
                 merge_hypotheses pass that sat 43 h holding 15 GB of commit and an inherited
                 log handle, 2026-11-11), not a slow one: a working job burns CPU every pass.
     A stop is terminate, a grace period, then kill, for the process and its children only.
     Its parent (the cmd that runs a lane of organs) is untouched, so the lane moves on to its
     next organ instead of losing the whole pass.
  3. RE-QUEUE. The stopped command line, its directory and why it was stopped are written to the
     queue. When the box has headroom again (available above twice the floor and commit below
     its line) the guard runs it again, at below-normal priority, inside a Windows job object
     whose per-process memory limit is the hard cap. A capped run that leaks fails with a
     MemoryError at the cap instead of taking the box down. At most MAX_ATTEMPTS re-runs per
     command per UTC day; after that the row is GAVE_UP with its reason, and the organ still runs
     on its own schedule tomorrow. Nothing is dropped silently.

WHAT IT NEVER DOES. It never touches a non-python process, a money-path process, its own
process tree, or anything when memory is healthy and no process is over the hard cap. It throttles
nothing: a job that fits runs at full speed, which is the "without reducing ROI" half of the ask.

Output: desks/mt5/reports/MEMORY_GUARD.json (every pass) and desks/mt5/data/MEMORY_GUARD_QUEUE.json
(the re-queue). The hourly pass reads the report.
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
REQUEUE_LOG = DESK / "logs" / "MT5-MemoryGuard-requeue.log"
SEEN = DESK / "data" / "MEMORY_GUARD_SEEN.json"

MB = 1024 * 1024
HARD_CAP_FRAC = 0.25        # one research process above this share of physical RAM is a leak
FLOOR_FRAC = 0.125          # available memory below this share of physical RAM is pressure
COMMIT_LINE = 0.90          # commit above this share of the commit limit is pressure
MIN_STOP_MB = 2048          # under pressure a smaller job is never the cause, so never stopped
MAX_ATTEMPTS = 2            # re-runs per command line per UTC day
GRACE_S = 10.0
STALL_AGE_H = 24.0          # a research job this old ...
STALL_CPU_S = 1.0           # ... that used less CPU than this between two passes is stuck
STALL_MIN_GAP_S = 60.0      # the two readings must be at least this far apart

PYTHON_NAMES = frozenset({"python.exe", "pythonw.exe", "python", "python3", "py.exe"})
MONEY_PATH = re.compile(
    r"(?i)gateway|allocator|executor|deadman|oco|money_closure|order_door|e8_|\be8\b|ftmo|"
    r"tape|tick_record|recorder|bridge|placement|venue|mt5desk[\\/.]run|terminal64|metatrader")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def is_candidate(proc: dict[str, Any], own_pids: set[int]) -> bool:
    """Only research python, never the money path, never ourselves."""
    if int(proc.get("pid") or -1) in own_pids:
        return False
    if str(proc.get("name") or "").lower() not in PYTHON_NAMES:
        return False
    cmd = " ".join(proc.get("cmdline") or [])
    if not cmd or MONEY_PATH.search(cmd):
        return False
    return "memory_guard" not in cmd


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


def stalled(p: dict[str, Any], prev: dict[str, Any], now_ts: float) -> float | None:
    """CPU seconds this process used since the last pass when it is old enough to judge and that
    reading is comparable (same process instance, far enough apart); None otherwise."""
    started, cpu = p.get("started"), p.get("cpu_s")
    if started is None or cpu is None or now_ts - float(started) < STALL_AGE_H * 3600:
        return None
    seen = prev.get(str(p.get("pid")))
    if not isinstance(seen, dict) or seen.get("started") != started:
        return None
    if now_ts - float(seen.get("at_ts") or now_ts) < STALL_MIN_GAP_S:
        return None
    return float(cpu) - float(seen.get("cpu_s") or 0.0)


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
            used = stalled(p, prev, now_ts)
            if used is not None and used < STALL_CPU_S:
                age_h = (now_ts - float(p["started"])) / 3600
                return {"stop": p, "rule": "STALLED", "thresholds": th, "pressure": under,
                        "why": (f"pid {p['pid']} has run {age_h:.1f} h and used {used:.2f} s of "
                                f"CPU since the last pass while holding "
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


def enqueue(rows: list[dict[str, Any]], proc: dict[str, Any], rule: str, why: str,
            at: str) -> list[dict[str, Any]]:
    key = " ".join(proc.get("cmdline") or [])
    for r in rows:
        if r.get("key") == key and r.get("state") in ("QUEUED", "RUNNING"):
            r.update(state="QUEUED", last_stop_at=at, last_rule=rule, last_why=why,
                     peak_mb=max(float(r.get("peak_mb") or 0), float(proc.get("private_mb") or 0)))
            return rows
    rows.append({"key": key, "cmdline": list(proc.get("cmdline") or []),
                 "cwd": proc.get("cwd"), "state": "QUEUED", "first_stop_at": at,
                 "last_stop_at": at, "last_rule": rule, "last_why": why,
                 "peak_mb": float(proc.get("private_mb") or 0), "attempts": {}})
    return rows


def next_requeue(rows: list[dict[str, Any]], at: str,
                 running_keys: set[str]) -> dict[str, Any] | None:
    """The oldest QUEUED job still under today's attempt cap and not already running."""
    day = _day(at)
    for r in sorted(rows, key=lambda r: str(r.get("last_stop_at") or "")):
        if r.get("state") != "QUEUED":
            continue
        if r.get("key") in running_keys:
            continue
        if int((r.get("attempts") or {}).get(day, 0)) >= MAX_ATTEMPTS:
            r["state"] = "GAVE_UP"
            r["gave_up_why"] = (f"{MAX_ATTEMPTS} capped re-runs today; it runs again on its own "
                                f"schedule. If the rule was HARD_CAP the organ needs to stream "
                                f"its input (the scaling_laws fix, #1049).")
            continue
        return r
    return None


def settle(rows: list[dict[str, Any]], running_keys: set[str], at: str) -> list[dict[str, Any]]:
    """A RUNNING re-run that is no longer running finished (or failed at its cap) -> DONE.
    GAVE_UP and DONE rows older than seven days are dropped from the working queue (the
    report of the pass that closed them is the record)."""
    keep = []
    for r in rows:
        if r.get("state") == "RUNNING" and r.get("key") not in running_keys:
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
            out.append({"pid": p.info["pid"], "name": p.info["name"],
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
    for q in tree:
        with contextlib.suppress(psutil.Error):
            q.terminate()
    _, alive = psutil.wait_procs(tree, timeout=GRACE_S)
    for q in alive:
        with contextlib.suppress(psutil.Error):
            q.kill()
    _, still = psutil.wait_procs(alive, timeout=GRACE_S)
    return {"pid": pid, "result": "STOPPED" if not still else "STILL_ALIVE",
            "tree": [q.pid for q in tree], "killed": [q.pid for q in alive]}


def _job_with_memory_cap(cap_bytes: int) -> Any:
    """A Windows job object whose per-process committed memory is capped (None elsewhere)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = EXTENDED()
    job_object_limit_process_memory = 0x00000100
    info.BasicLimitInformation.LimitFlags = job_object_limit_process_memory
    info.ProcessMemoryLimit = cap_bytes
    job_object_extended_limit_information = 9
    if not k32.SetInformationJobObject(wintypes.HANDLE(job), job_object_extended_limit_information,
                                       ctypes.byref(info), ctypes.sizeof(info)):
        k32.CloseHandle(wintypes.HANDLE(job))
        return None
    return (k32, job)


def requeue_run(row: dict[str, Any], cap_mb: float) -> dict[str, Any]:
    """Start the stopped command again, below-normal priority, inside the memory-capped job."""
    REQUEUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    cwd = row.get("cwd") if row.get("cwd") and Path(row["cwd"]).is_dir() else str(ROOT)
    with REQUEUE_LOG.open("ab") as log:
        log.write((f"\n--- {_now().isoformat(timespec='seconds')} re-run with a "
                   f"{round(cap_mb)} MB cap: {row['key']}\n").encode("utf-8", "replace"))
        log.flush()
        proc = subprocess.Popen(row["cmdline"], cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    capped = False
    job = _job_with_memory_cap(int(cap_mb * MB))
    if job is not None:
        from ctypes import wintypes
        k32, handle = job
        capped = bool(k32.AssignProcessToJobObject(wintypes.HANDLE(handle),
                                                   wintypes.HANDLE(int(proc._handle))))  # type: ignore[attr-defined]
        # The handle is deliberately leaked to the OS for the guard's lifetime: closing it
        # would not lift the limit, and the guard exits within the pass.
    return {"pid": proc.pid, "capped": capped, "cap_mb": round(cap_mb)}


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


def _load_seen() -> dict[str, Any]:
    try:
        doc = json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _save_seen(procs: list[dict[str, Any]], own: set[int], now_ts: float) -> None:
    """The CPU each research process had used at this pass, for the next pass's STALLED rule."""
    doc = {str(p["pid"]): {"started": p.get("started"), "cpu_s": p.get("cpu_s"), "at_ts": now_ts}
           for p in procs if is_candidate(p, own) and p.get("cpu_s") is not None}
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
    running = {" ".join(p.get("cmdline") or []) for p in procs}
    rows = settle(rows, running, at)
    actions: list[dict[str, Any]] = []
    victim = decision.get("stop")
    if victim is not None and apply:
        res = stop(int(victim["pid"]))
        actions.append({"action": "STOP", "rule": decision["rule"], "why": decision["why"],
                        "cmdline": victim.get("cmdline"), **res})
        if res["result"] != "GONE":
            rows = enqueue(rows, victim, decision["rule"], decision["why"], at)
    elif victim is None and apply and headroom(snap, decision["thresholds"]):
        nxt = next_requeue(rows, at, running)
        cap = decision["thresholds"]["hard_cap_mb"]
        if nxt is not None and cap:
            try:
                res = requeue_run(nxt, cap)
                nxt["state"] = "RUNNING"
                att = nxt.setdefault("attempts", {})
                att[_day(at)] = int(att.get(_day(at), 0)) + 1
                actions.append({"action": "REQUEUE", "cmdline": nxt["cmdline"], **res})
            except Exception as exc:  # a failed start is an attempt, not a crash of the guard
                att = nxt.setdefault("attempts", {})
                att[_day(at)] = int(att.get(_day(at), 0)) + 1
                actions.append({"action": "REQUEUE_FAILED", "cmdline": nxt["cmdline"],
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    if apply:
        save_queue(rows)
        _save_seen(procs, own, now_ts)
    top = sorted((p for p in procs if is_candidate(p, own)),
                 key=lambda p: -float(p.get("private_mb") or 0.0))[:5]
    doc = {
        "at": at, "applied": apply, "memory": snap,
        "verdict": decision["rule"], "why": decision["why"],
        "thresholds_mb": {k: (round(v) if v is not None else None)
                          for k, v in decision["thresholds"].items()},
        "actions": actions,
        "queue": [{k: r.get(k) for k in ("key", "state", "last_rule", "last_stop_at",
                                         "attempts", "peak_mb", "gave_up_why")} for r in rows],
        "largest_research_jobs": [{"pid": p["pid"], "private_mb": round(p["private_mb"]),
                                   "cmd": " ".join(p.get("cmdline") or [])[:200]} for p in top],
        "protected": "non-python processes and every command line matching the money-path pattern",
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
