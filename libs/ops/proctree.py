"""Process-tree discipline for every launcher on the desk.

MEASURED 2026-09-22 on the trading box: 72 `multiprocessing` worker processes whose parents no
longer existed held 147 GB of the 251 GB commit limit (six pools of twelve, ~2.1 GB each), with
67 GB of physical memory FREE. Every new leg then died with STATUS_COMMITMENT_LIMIT (rc
3221225773) or MemoryError, and the departments built that week never left an artifact.

The leak is `subprocess.run(..., timeout=...)`: on timeout it kills the child it started and
nothing else, so a gauntlet that had opened a worker pool leaves the pool behind, still charged
against the commit limit, forever. Two rails close it:

* `run()` -- a drop-in for `subprocess.run` that kills the WHOLE TREE on timeout before
  re-raising `TimeoutExpired` (the call sites keep their semantics).
* `reap_orphaned_workers()` -- an actuator under the control plane: a worker whose parent is
  gone can never deliver a result, so it is killed and the commit it held is recorded.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

#: Substrings that identify a pool worker on every platform Python supports.
WORKER_MARKERS: tuple[str, ...] = (
    "multiprocessing.spawn", "spawn_main", "multiprocessing.forkserver",
    "multiprocessing.resource_tracker", "joblib.externals.loky",
)

try:  # psutil is optional: the desk falls back to the OS tools without it
    import psutil
except ImportError:  # pragma: no cover - exercised only where psutil is absent
    psutil = None  # type: ignore[assignment]


def kill_tree(pid: int, *, include_parent: bool = True) -> dict[str, Any]:
    """Kill `pid` and every descendant. Never raises; reports what it did."""
    out: dict[str, Any] = {"pid": pid, "killed": 0, "method": None}
    if psutil is not None:
        try:
            root = psutil.Process(pid)
            kids = root.children(recursive=True)
            for k in kids:
                try:
                    k.kill()
                    out["killed"] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if include_parent:
                try:
                    root.kill()
                    out["killed"] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            psutil.wait_procs(kids, timeout=5)
            out["method"] = "psutil"
            return out
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            out["note"] = f"{type(exc).__name__}"
    if sys.platform == "win32":
        try:
            r = subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                               text=True, timeout=30, check=False)
            out["method"] = "taskkill"
            out["rc"] = r.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            out["note"] = f"taskkill: {type(exc).__name__}"
        return out
    try:  # POSIX without psutil: the process group, then the pid
        os.killpg(os.getpgid(pid), 9)
        out["method"] = "killpg"
    except (OSError, AttributeError):
        try:
            os.kill(pid, 9)
            out["method"] = "kill"
        except OSError as exc:
            out["note"] = f"kill: {type(exc).__name__}"
    return out


def run(argv: Sequence[str], *, timeout: float | None, capture_output: bool = False,
        text: bool = False, cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None, check: bool = False,
        **popen_kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """`subprocess.run` whose timeout kills the child WHOLE TREE, then raises TimeoutExpired.

    Same return type, same exceptions, same `capture_output`/`text`/`cwd`/`env`/`check` and any
    Popen keyword (`creationflags`, ...). A leg swapped onto this runner changes nothing about
    how it reads its result; it only stops leaking its worker pools when the budget stops it.
    """
    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE
    with subprocess.Popen(list(argv), cwd=cwd, env=env, text=text, **popen_kwargs) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            try:
                out, err = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - tree already killed
                out, err = None, None
            raise subprocess.TimeoutExpired(list(argv), timeout or 0.0, output=out,
                                            stderr=err) from None
        rc = proc.returncode
    done = subprocess.CompletedProcess(list(argv), rc, out, err)
    if check:
        done.check_returncode()
    return done


@dataclass
class ProcInfo:
    """The few facts the reaper needs about one process (injectable for tests)."""
    pid: int
    ppid: int
    cmdline: str
    commit_mb: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _live_table() -> list[ProcInfo]:
    if psutil is None:
        return []
    rows: list[ProcInfo] = []
    for pr in psutil.process_iter(["pid", "ppid", "cmdline", "memory_info"]):
        try:
            mi = pr.info.get("memory_info")
            commit = int(getattr(mi, "pagefile", 0) or getattr(mi, "vms", 0) or 0) // (1024 * 1024)
            rows.append(ProcInfo(int(pr.info["pid"]), int(pr.info["ppid"] or 0),
                                 " ".join(pr.info.get("cmdline") or []), commit))
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return rows


def is_worker(cmdline: str) -> bool:
    return any(m in cmdline for m in WORKER_MARKERS)


def find_orphaned_workers(table: Iterable[ProcInfo]) -> list[ProcInfo]:
    """Pool workers whose parent pid is not in the table: nothing can ever collect their work."""
    rows = list(table)
    alive = {r.pid for r in rows}
    return [r for r in rows if is_worker(r.cmdline) and r.ppid not in alive]


def reap_orphaned_workers(*, apply: bool = True, table: Iterable[ProcInfo] | None = None,
                          killer: Any = None) -> dict[str, Any]:
    """Kill every orphaned pool worker; report count, commit freed and whether it was applied."""
    rows = list(table) if table is not None else _live_table()
    orphans = find_orphaned_workers(rows)
    kill = killer if killer is not None else (lambda pid: kill_tree(pid))
    killed: list[int] = []
    if apply:
        for o in orphans:
            res = kill(o.pid)
            if not isinstance(res, dict) or res.get("killed", 1):
                killed.append(o.pid)
    unmeasured = table is None and psutil is None
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "measured": not unmeasured,
        "workers_total": sum(1 for r in rows if is_worker(r.cmdline)),
        "orphans": len(orphans),
        "orphan_commit_mb": int(sum(o.commit_mb for o in orphans)),
        "orphans_by_dead_parent": _by_parent(orphans),
        "killed": len(killed),
        "applied": bool(apply),
        "note": ("psutil absent: the process table is UNMEASURED" if unmeasured
                 else "an orphaned worker has no parent to read its result; it only holds commit"),
    }


def _by_parent(rows: Sequence[ProcInfo]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        d = out.setdefault(str(r.ppid), {"n": 0, "commit_mb": 0})
        d["n"] += 1
        d["commit_mb"] += int(r.commit_mb)
    return out
