"""Reap orphaned cache-warmer processes: a `warm_gauntlet_cache.py` python that outlived its run.

MEASURED 2026-11-10 (box read cachewarm_cause_2026-11-10T1928Z): the MT5-CacheWarm run of
2026-11-02 11:00Z logged `CacheWarm END status=HARD_STOP rc=3` at 11:59Z and its python, pid 36780,
never exited. Its parent cmd was gone; it sat at one thread and 2 MB and still held the task's
`>> logs\\MT5-CacheWarm.log` handle. Every hourly run after it died in cmd, before python started,
with Last Result 1 -- eight days in which the warmer warmed nothing and every judge sweep spent
three quarters of its time (8,251 s of prewarm) doing the warmer's job.

THE RULE, and nothing wider. A process is reaped only when ALL of these hold:
  * its command line names `warm_gauntlet_cache.py` (no other script is ever touched);
  * it is not this process, nor any ancestor of this process;
  * it is older than the warmer's own hard stop (budget + grace) plus REAP_MARGIN_S, so a run
    that is still inside its hour is never touched, whatever it is doing;
  * its parent is gone, or its parent is not a process that could still be waiting on it (the
    scheduler's cmd/python is dead).
Every reaped and every spared candidate is logged with pid, create time and command line, and the
result is written to REAP_LOG (append-only JSON lines) so the act is never silent.

Callers: the judge sweep's start (`run_sharded_gauntlet`, so it runs hourly even while the warmer
cannot start) and the warmer's own start. Each call costs one process listing.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
#: Append-only record of every reap decision.
REAP_LOG = DESK / "reports" / "warm_cache_state" / "reaped.jsonl"
#: The script name a candidate's command line must carry.
SCRIPT = "warm_gauntlet_cache.py"
#: Above the warmer's hard stop: a run never lives past budget + grace, so anything older by this
#: margin is not a run any more.
REAP_MARGIN_S = 900.0


def _hard_stop_s() -> float:
    budget = float(os.environ.get("WARM_BUDGET_SEC", "3300"))
    grace = float(os.environ.get("WARM_GRACE_SEC", "240"))
    return budget + grace


def _cmdline(p: Any) -> list[str]:
    try:
        return [str(x) for x in (p.cmdline() or [])]
    except Exception:
        return []


def _is_warmer(cmd: list[str]) -> bool:
    return any(Path(part.replace("\\", "/")).name == SCRIPT for part in cmd)


def _ancestors() -> set[int]:
    out = {os.getpid()}
    try:
        import psutil
        out |= {p.pid for p in psutil.Process().parents()}
    except Exception:
        pass
    return out


def candidates(now: float | None = None, *, procs: Any = None) -> list[dict[str, Any]]:
    """Every warmer process, with the decision for it. `procs` is for tests (psutil-shaped)."""
    now = time.time() if now is None else now
    if procs is None:
        import psutil
        procs = psutil.process_iter()
    limit = _hard_stop_s() + REAP_MARGIN_S
    mine = _ancestors()
    out: list[dict[str, Any]] = []
    for p in procs:
        cmd = _cmdline(p)
        if not _is_warmer(cmd):
            continue
        try:
            created = float(p.create_time())
        except Exception:
            continue
        try:
            parent = p.parent()
            parent_alive = parent is not None and parent.is_running()
        except Exception:
            parent_alive = False
        age = now - created
        row = {"pid": int(p.pid), "created": created, "age_s": round(age, 1),
               "cmdline": " ".join(cmd)[:400], "parent_alive": parent_alive}
        if int(p.pid) in mine:
            row["decision"] = "SPARED_SELF"
        elif age <= limit:
            row["decision"] = "SPARED_YOUNG"
        elif parent_alive:
            row["decision"] = "SPARED_PARENT_ALIVE"
        else:
            row["decision"] = "REAP"
        row["_proc"] = p
        out.append(row)
    return out


def reap(now: float | None = None, *, procs: Any = None, log: Path | None = None,
         by: str = "") -> dict[str, Any]:
    """End every orphaned warmer (see the module rule). Never raises."""
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))
    res: dict[str, Any] = {"at": at, "by": by, "reaped": 0, "failed": 0, "spared": 0, "rows": []}
    try:
        rows = candidates(now, procs=procs)
    except Exception as exc:
        res["status"] = f"UNMEASURED: {type(exc).__name__}: {str(exc)[:160]}"
        return res
    for row in rows:
        p = row.pop("_proc")
        if row["decision"] == "REAP":
            try:
                p.kill()
                with contextlib.suppress(Exception):
                    p.wait(timeout=10)
                row["outcome"] = "KILLED"
                res["reaped"] += 1
            except Exception as exc:
                row["outcome"] = f"FAILED: {type(exc).__name__}: {str(exc)[:160]}"
                res["failed"] += 1
        else:
            res["spared"] += 1
        res["rows"].append(row)
    res["status"] = "OK"
    if res["rows"]:
        target = log or REAP_LOG
        with contextlib.suppress(OSError):
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, default=str) + "\n")
    return res
