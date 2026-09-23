"""JUDGING THROUGHPUT -- size the SEALED gauntlet's parallelism off the box, every hour.

THE DEFECT THIS ORGAN EXISTS FOR (principal, 2026-09-23: "we have tons of headroom in our box to
increase judging -- give it tons of headroom possible for maximum throughput").

`desks/mt5/scripts/external_gauntlet.py` is sealed and may never be edited. Its `_worker_count()`
already derives workers from measured cores and a per-worker memory budget, and it already honours
`GAUNTLET_WORKERS` / `GAUNTLET_MEMORY_BUDGET_MB` / `GAUNTLET_PER_WORKER_MB` /
`GAUNTLET_HEADROOM_CAP_MB` from the ENVIRONMENT. So throughput is raised from OUTSIDE the sealed
file, by measuring the box and writing those variables where the gauntlet's launchers read them.

WHAT BOUND THE JUDGE, measured off `GAUNTLET_BACKPRESSURE.json` rather than argued: the sweep's
own memory budget is `max(declared_need, min(0.5 x free, HEADROOM_CAP_MB=8192))`, and at
`PER_WORKER_MB=768` that ceiling alone caps the judge at ten workers NO MATTER HOW BIG THE BOX IS.
On the trading box (18 cores, 98 GB) the cores would allow 15 in session and 18 at the weekend,
and the last published sweep ran with `workers: 1` and `memory_budget_mb: 1984` while deferring
3,490 cells on the build budget with 21,391 discovered and 1,395 judged. The ceiling was sized for
an 8 GB machine and was never re-derived when the judge moved to a 98 GB one -- the exact
"NEVER SIZE A FLOOR OFF A CLAIM" failure the desk already has a scar for.

THREE RAILS, AND NONE OF THEM IS A BRAKE:

  1. THIS ORGAN NEVER LOWERS THE JUDGE'S BUDGET. `plan()` floors every decision at
     `sealed_baseline()` -- exactly what the sealed file would choose unaided -- so the worst this
     organ can do is change nothing. "Protecting the box" by shrinking the gauntlet is forbidden
     (GROWTH_GOVERNANCE rule 1: a reduction must prove it raises robust forward E[log W], and this
     one could not).
  2. THE LIVE TERMINAL ALWAYS WINS. Cores are reserved for the terminal, the gateway pass and the
     hourly cycle while the market is open, and when the terminal is measurably starved (free
     physical memory under two workers' budget) the plan STANDS DOWN to the sealed baseline --
     not below it.
  3. EVERY NUMBER IS MEASURED ON THE MACHINE THE CODE IS RUNNING ON. Nothing here is sized from a
     box size typed into a document. An unreadable counter yields UNMEASURED and the sealed
     baseline, never an invented figure (L1.28a).

WHERE THE DECISION IS WRITTEN (the launchers, all of which the desk already had):
  * `desks/mt5/data/judging_throughput.env.json` -- the env file. `apply_env()` loads it into
    `os.environ`, and `research/hourly_cycle.py` calls that before its `external_gauntlet` leg, so
    the in-cycle sweep inherits the measured worker count.
  * `desks/mt5/scripts/RunGauntlet.cmd` -- the launcher for the `MT5-Gauntlet` scheduled task
    (declared in `desks/mt5/ops/box_tasks.manifest`), which reads the same file and exports the
    variables before invoking the sealed script. The task had NO installer and no launcher at all
    before this, which is why an env var was previously unreachable from the repository.
  * machine-scope environment (`setx /M`) -- applied only on a box measured to be the judging box,
    so the other scheduled tasks (`MT5-CacheWarm`'s `WARM_WORKERS` among them) inherit it too.
  * the task's repetition interval (`schtasks /Change /RI`) -- CADENCE, raised while the queue is
    deep and headroom exists.

Clock: leg `judging_throughput` in `research/hourly_cycle.py` (department validate,
`--once --budget-s 300`). Artifact: `desks/mt5/reports/JUDGING_THROUGHPUT.json`. Consumers: the
env file above (read by the launcher and by the hourly cycle) and `GAUNTLET_BACKPRESSURE.json`'s
next `capacity.measured.workers`, which is how the raise is verified rather than asserted.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "JUDGING_THROUGHPUT.json"
ENV_FILE = BASE / "data" / "judging_throughput.env.json"
BACKPRESSURE = BASE / "reports" / "GAUNTLET_BACKPRESSURE.json"

UNMEASURED = "UNMEASURED"

#: The SEALED file's own declarations, used only as a fallback when the artifact that publishes
#: them (`GAUNTLET_BACKPRESSURE.json` -> `capacity.declared`) is unreadable. These are the
#: gauntlet's numbers, not a box size: 768 MB is what one build worker is budgeted, 1200 MB is
#: what the sweep declares at admission, 8192 MB is the headroom ceiling this organ exists to
#: lift, and 3 is the cores it keeps for the terminal in session.
FALLBACK_PER_WORKER_MB = 768.0
FALLBACK_DECLARED_NEED_MB = 1200.0
SEALED_HEADROOM_SHARE = 0.5
SEALED_HEADROOM_CAP_MB = 8192.0
SEALED_SESSION_RESERVED_CORES = 3

#: The share of measured free memory this organ will hand the judge, and the share of free commit.
#: HALF, exactly as the sealed file's own `HEADROOM_SHARE`: `exclusive_job` makes a late neighbour
#: WAIT rather than refuse, so a sweep that takes half of what was free at its start leaves the
#: other half for whoever is admitted next. The difference from the sealed file is that NO CEILING
#: is imposed on top of the share -- the ceiling is what was sized for the wrong machine.
HEADROOM_SHARE = 0.5

#: The scheduled task the launcher drives, and the cadence band. The gauntlet's cache is
#: content-addressed and cumulative, so a shorter period is strictly more judging: a pass that
#: overlaps costs a kill (MT5-StallWatch keeps the oldest parent), never a corrupt cache.
GAUNTLET_TASK = "MT5-Gauntlet"
CADENCE_FAST_MIN = 5
CADENCE_BASE_MIN = 10

#: A box is the JUDGING box when it measures at least this much. Derived, never a hostname: the
#: build box has 8 GB and its tasks are disabled, and nothing here may be sized from it.
JUDGING_BOX_MIN_CORES = 12
JUDGING_BOX_MIN_PHYS_MB = 32_768


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def market_closed(now: datetime | None = None) -> bool:
    """True inside the weekly FX close, Friday 21:00 UTC to Sunday 21:00 UTC.

    The same rule the sealed file applies, restated rather than imported: importing
    `external_gauntlet` would execute its module body (a full pandas/numpy import and a worker
    count) inside a 300-second leg whose whole job is to be cheap.
    """
    t = _now(now)
    wd, h = t.weekday(), t.hour
    return (wd == 4 and h >= 21) or wd == 5 or (wd == 6 and h < 21)


def measure_memory() -> dict[str, Any]:
    """Free physical memory AND free commit, in MB, on the machine this is running on.

    COMMIT IS NOT PHYSICAL and on Windows it is the binding one: an allocation fails when commit
    is exhausted however much RAM is free, which is how a 12.9 GB pool of paged-out cache warmers
    once killed the sweep on a box reporting 2.7 GB free. Both are measured; the plan takes the
    smaller. Unmeasurable returns UNMEASURED, never a number.
    """
    out: dict[str, Any] = {"source": UNMEASURED, "total_phys_mb": UNMEASURED,
                           "free_phys_mb": UNMEASURED, "commit_limit_mb": UNMEASURED,
                           "commit_free_mb": UNMEASURED}
    if sys.platform == "win32":
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = _MS()
            st.dwLength = ctypes.sizeof(_MS)
            kernel32 = ctypes.windll.kernel32   # type: ignore[attr-defined,unused-ignore]
            ok = kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            if ok:
                mb = 1024 * 1024
                out.update(source="GlobalMemoryStatusEx",
                           total_phys_mb=int(st.ullTotalPhys // mb),
                           free_phys_mb=int(st.ullAvailPhys // mb),
                           commit_limit_mb=int(st.ullTotalPageFile // mb),
                           commit_free_mb=int(st.ullAvailPageFile // mb))
        except Exception as exc:
            out["why"] = f"{type(exc).__name__}: {exc}"
        return out
    try:
        fields: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            k, _, rest = line.partition(":")
            parts = rest.split()
            if parts:
                fields[k.strip()] = int(parts[0]) // 1024
        if fields:
            limit = fields.get("CommitLimit")
            used = fields.get("Committed_AS")
            out.update(source="/proc/meminfo",
                       total_phys_mb=fields.get("MemTotal", UNMEASURED),
                       free_phys_mb=fields.get("MemAvailable", fields.get("MemFree", UNMEASURED)),
                       commit_limit_mb=limit if limit is not None else UNMEASURED,
                       commit_free_mb=(max(0, limit - used)
                                       if limit is not None and used is not None else UNMEASURED))
    except Exception as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"
    return out


def measure_terminal() -> dict[str, Any]:
    """Is the live terminal (and the gateway) on this box, and can it be seen at all?

    THE LIVE TERMINAL ALWAYS WINS. This does not decide how many workers to run -- cores reserved
    in session do that -- it decides whether the plan STANDS DOWN to the sealed baseline. psutil
    is optional and its absence is UNMEASURED, which stands down rather than pretending the
    terminal is idle: a judge that cannot see the terminal must not take the terminal's cores.
    """
    out: dict[str, Any] = {"terminal_running": UNMEASURED, "gateway_running": UNMEASURED,
                           "n_python": UNMEASURED, "terminal_source": UNMEASURED}
    try:
        import psutil
    except Exception:
        out["terminal_why"] = "psutil absent: terminal presence is UNMEASURED on this box"
        return out
    try:
        term = gate = pyn = 0
        for pr in psutil.process_iter(["name", "cmdline"]):
            name = str(pr.info.get("name") or "").lower()
            cmd = " ".join(pr.info.get("cmdline") or []).lower()
            if "terminal64" in name:
                term += 1
            if "gateway.py" in cmd:
                gate += 1
            if name.startswith("python"):
                pyn += 1
        out.update(terminal_running=term > 0, gateway_running=gate > 0, n_python=pyn,
                   terminal_source="psutil")
    except Exception as exc:
        out["terminal_why"] = f"{type(exc).__name__}: {exc}"
    return out


def measure_box(now: datetime | None = None) -> dict[str, Any]:
    """Everything the plan is allowed to be sized from, all of it read off this machine."""
    box: dict[str, Any] = {"cores": int(os.cpu_count() or 1), "market_closed": market_closed(now)}
    box.update(measure_memory())
    box.update(measure_terminal())
    phys = box.get("total_phys_mb")
    box["is_judging_box"] = bool(box["cores"] >= JUDGING_BOX_MIN_CORES
                                 and isinstance(phys, int) and phys >= JUDGING_BOX_MIN_PHYS_MB)
    return box


def declared_costs() -> dict[str, float]:
    """What one worker costs and what the sweep declares, from the gauntlet's own artifact.

    `GAUNTLET_BACKPRESSURE.json` publishes `capacity.declared`, which the sealed file wrote. Read
    it rather than restating it, so the two cannot drift; the fallbacks are the sealed file's
    current literals and are used only when the artifact is absent.
    """
    doc = _read_json(BACKPRESSURE, {}) or {}
    dec = ((doc.get("capacity") or {}).get("declared") or {}) if isinstance(doc, dict) else {}

    def _f(key: str, fallback: float) -> float:
        try:
            v = float(dec.get(key))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return fallback
        return v if v > 0 else fallback

    return {"per_worker_mb": _f("per_worker_mb", FALLBACK_PER_WORKER_MB),
            "declared_need_mb": _f("declared_need_mb", FALLBACK_DECLARED_NEED_MB)}


#: The breach docket written by `research/clock_certificate.py` every hour: the cells whose
#: forward clocks are running with no certificate. Read here, never written here.
BREACH_DOCKET = BASE / "reports" / "CLOCK_CERTIFICATE_BREACH.json"


def measure_queue() -> dict[str, Any]:
    """How deep the judging queue is and how many gates an hour the judge actually achieves.

    Both come from the gauntlet's own backpressure artifact, which is the only thing on this desk
    that counts cells discovered against cells judged. An absent artifact is UNMEASURED: a queue
    depth nobody measured must never be read as an empty queue.
    """
    doc = _read_json(BACKPRESSURE, {}) or {}
    out: dict[str, Any] = {"status": UNMEASURED, "depth": UNMEASURED,
                           "gates_per_hour": UNMEASURED, "workers_last_sweep": UNMEASURED,
                           "source": str(BACKPRESSURE)}
    if not isinstance(doc, dict) or not doc:
        out["why"] = f"{BACKPRESSURE.name} absent or unreadable: queue depth is UNMEASURED"
        return out
    meas = (doc.get("capacity") or {}).get("measured") or {}
    disc, judged = meas.get("n_cells_discovered"), meas.get("n_judged")
    win = (doc.get("windows") or {}).get("24h") or {}
    per_hour = (win.get("testing") or {}).get("per_hour")
    if isinstance(disc, int) and isinstance(judged, int):
        out.update(status="MEASURED", depth=max(0, disc - judged), discovered=disc,
                   judged_last_sweep=judged)
    deferred_build = meas.get("n_cells_deferred_build_budget")
    deferred_mem = meas.get("n_cells_deferred_memory_budget")
    out.update(
        deferred_build_budget=deferred_build if deferred_build is not None else UNMEASURED,
        deferred_memory_budget=deferred_mem if deferred_mem is not None else UNMEASURED,
        workers_last_sweep=meas.get("workers", UNMEASURED),
        memory_budget_mb_last_sweep=meas.get("memory_budget_mb", UNMEASURED),
        swept_at=meas.get("swept_at", UNMEASURED),
        gates_per_hour=float(per_hour) if isinstance(per_hour, (int, float)) else UNMEASURED,
        gates_per_hour_window="24h")
    # CLOCK IMPLIES CERTIFICATE (principal 2026-09-23). A cell whose forward clock is running
    # UNCERTIFIED is the desk's only currently-breached law, and `research/clock_certificate.py`
    # queues those cells at the FRONT of the judge's queue every hour. The judge's SIZING has to
    # honour that or the priority is decorative: a breach backlog is demand on the judge exactly
    # as queue depth is, so it is counted here and read by `plan` below. UNMEASURED when the
    # docket is absent -- a breach count nobody measured is never read as zero.
    doc2 = _read_json(BREACH_DOCKET, None)
    if isinstance(doc2, dict):
        n_breach = doc2.get("breached")
        out.update(clock_breach_cells=n_breach if isinstance(n_breach, int) else UNMEASURED,
                   clock_breach_overdue=doc2.get("overdue_beyond_one_judging_cycle", UNMEASURED),
                   clock_breach_source=str(BREACH_DOCKET.name))
    else:
        out.update(clock_breach_cells=UNMEASURED,
                   clock_breach_why=f"{BREACH_DOCKET.name} absent: the breach backlog is "
                                    f"UNMEASURED, which is never zero")
    return out


def sealed_baseline(box: dict[str, Any], costs: dict[str, float]) -> dict[str, Any]:
    """What `external_gauntlet._worker_count()` would choose unaided, restated, not imported.

    This is the FLOOR of every plan. Reproducing the sealed arithmetic here is what makes
    "this organ never lowers the judge's budget" a checkable property rather than an intention.
    """
    cores = int(box.get("cores") or 1)
    free = box.get("free_phys_mb")
    per, need = costs["per_worker_mb"], costs["declared_need_mb"]
    if isinstance(free, int):
        budget = max(need, min(SEALED_HEADROOM_SHARE * float(free), SEALED_HEADROOM_CAP_MB))
    else:
        budget = need
    by_mem = int(budget // per) if per > 0 else 1
    by_cores = cores if box.get("market_closed") else cores - SEALED_SESSION_RESERVED_CORES
    return {"workers": max(1, min(by_cores, by_mem)), "memory_budget_mb": round(budget, 1),
            "by_cores": by_cores, "by_mem": by_mem,
            "why": ("max(1, min(cores - reserved, memory_budget / per_worker)) with the sealed "
                    f"ceiling HEADROOM_CAP_MB={SEALED_HEADROOM_CAP_MB:.0f} applied -- the ceiling "
                    "this organ lifts")}


def plan(box: dict[str, Any], queue: dict[str, Any], costs: dict[str, float]) -> dict[str, Any]:
    """The largest worker count this box can safely hold, floored at the sealed baseline.

    LIMITING RESOURCE BY NAME, always: cores, physical memory, commit, the live terminal, or the
    queue itself (a queue shallower than the workers is the one case where more workers buy
    nothing, and even then the floor holds -- nothing is taken away).
    """
    base = sealed_baseline(box, costs)
    per = costs["per_worker_mb"]
    cores = int(box.get("cores") or 1)
    closed = bool(box.get("market_closed"))
    reserved = 0 if closed else SEALED_SESSION_RESERVED_CORES
    by_cores = max(1, cores - reserved)

    free, commit = box.get("free_phys_mb"), box.get("commit_free_mb")
    by_mem = int((HEADROOM_SHARE * float(free)) // per) if isinstance(free, int) and per > 0 else 0
    by_commit = (int((HEADROOM_SHARE * float(commit)) // per)
                 if isinstance(commit, int) and per > 0 else 0)
    measured: list[tuple[str, int]] = [("cores", by_cores)]
    if isinstance(free, int):
        measured.append(("memory", by_mem))
    if isinstance(commit, int):
        measured.append(("commit", by_commit))
    limiting, workers = min(measured, key=lambda kv: kv[1])
    workers = max(1, workers)

    # THE LIVE TERMINAL ALWAYS WINS. Two conditions stand the plan down to the sealed baseline:
    # the terminal is measurably starved of physical memory, or the terminal cannot be seen at
    # all while the market is open. Standing down means RETURNING TO THE BASELINE, never below it.
    stood_down, why_down = False, ""
    if isinstance(free, int) and float(free) < 2.0 * per:
        stood_down, limiting, why_down = True, "live_terminal", (
            f"free physical {free}MB is under two workers' budget ({2.0 * per:.0f}MB): the live "
            "terminal needs the machine, so the plan returns to the sealed baseline")
    elif box.get("terminal_running") == UNMEASURED and not closed:
        stood_down, limiting, why_down = True, "live_terminal", (
            "terminal presence is UNMEASURED while the market is open (psutil absent), so the "
            "plan returns to the sealed baseline rather than taking cores it cannot account for")
    if stood_down:
        workers = int(base["workers"])

    # NEVER BELOW THE SEALED BASELINE. This is the rail that makes the organ unable to throttle.
    if workers < int(base["workers"]):
        workers, limiting = int(base["workers"]), "sealed_baseline_floor"

    depth = queue.get("depth")
    deep = isinstance(depth, int) and depth > workers
    # A BREACHED CLOCK IS DEMAND ON THE JUDGE. Cells whose forward clocks run uncertified sit at
    # the front of the queue by priority; if the judge is not sized to reach them, the priority
    # buys nothing and the breach simply ages. So an overdue breach makes the queue DEEP, which
    # is what raises workers and cadence below. It never lowers either: this is one-way.
    breach_overdue = queue.get("clock_breach_overdue")
    if isinstance(breach_overdue, int) and breach_overdue > 0:
        deep = True
        limiting = "clock_certificate_breach"
    elif isinstance(depth, int) and not deep and not stood_down:
        limiting = "queue"

    budget_mb = max(float(base["memory_budget_mb"]), float(workers) * per)
    warm = 1 if stood_down or by_cores <= workers else max(1, min(4, by_cores - workers))
    cadence = CADENCE_FAST_MIN if deep and not stood_down else CADENCE_BASE_MIN

    before = queue.get("gates_per_hour")
    last_workers = queue.get("workers_last_sweep")
    gates_after: Any = UNMEASURED
    if isinstance(before, (int, float)) and isinstance(last_workers, int) and last_workers > 0:
        scale = (workers / float(last_workers)) * (CADENCE_BASE_MIN / float(cadence))
        gates_after = round(float(before) * scale, 3)
    days: Any = UNMEASURED
    if isinstance(depth, int) and isinstance(gates_after, float) and gates_after > 0:
        days = round(depth / (gates_after * 24.0), 3)

    return {
        "workers": int(workers),
        "per_worker_mb": per,
        "memory_budget_mb": round(budget_mb, 1),
        "headroom_cap_mb": round(budget_mb, 1),
        "warm_workers": int(warm),
        "cadence_minutes": int(cadence),
        "shards": 1,
        "shards_why": ("the sealed file exposes no partition key -- `--only` is a filter, not a "
                       "shard -- so throughput is raised by WORKERS and CADENCE, never by "
                       "splitting a docket the judge cannot be told to split"),
        "limiting_resource": limiting,
        "stood_down": stood_down,
        "why": why_down or (
            f"cores {by_cores} (reserved {reserved}), memory {by_mem}, commit {by_commit} at "
            f"{per:.0f}MB a worker; the binding one is {limiting}"),
        "baseline": base,
        "raised_by": int(workers) - int(base["workers"]),
        "queue_deep": bool(deep),
        "clock_breach_cells": queue.get("clock_breach_cells", UNMEASURED),
        "clock_breach_overdue": queue.get("clock_breach_overdue", UNMEASURED),
        "gates_per_hour_before": before if before is not None else UNMEASURED,
        "gates_per_hour_projected": gates_after,
        "days_to_drain_queue": days,
    }


ENV_KEYS = ("GAUNTLET_WORKERS", "GAUNTLET_MEMORY_BUDGET_MB", "GAUNTLET_HEADROOM_CAP_MB",
            "GAUNTLET_PER_WORKER_MB", "WARM_WORKERS")


def env_for(decision: dict[str, Any]) -> dict[str, str]:
    """The environment the sealed gauntlet and the cache warmer read, as strings."""
    return {
        "GAUNTLET_WORKERS": str(int(decision["workers"])),
        "GAUNTLET_MEMORY_BUDGET_MB": str(int(decision["memory_budget_mb"])),
        "GAUNTLET_HEADROOM_CAP_MB": str(int(decision["headroom_cap_mb"])),
        "GAUNTLET_PER_WORKER_MB": str(int(decision["per_worker_mb"])),
        "WARM_WORKERS": str(int(decision["warm_workers"])),
    }


def write_env(decision: dict[str, Any], path: Path | None = None,
              box: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish the decision where every launcher reads it (atomic, never partial).

    ONLY A RAISE IS EVER WRITTEN, and this is the rail that keeps one box from sizing another.
    This file is repo state and travels between machines; a build box that measured four cores
    would otherwise hand the 18-core judge `GAUNTLET_WORKERS=1` the moment the release landed --
    the desk's oldest recurring defect, a floor sized off the wrong machine. So when the plan
    equals the sealed baseline there is nothing to say and the env is written EMPTY: the sealed
    file then derives its own numbers exactly as it always did, which is what the launcher's own
    contract already promises for a missing file. The box fingerprint is recorded beside it so a
    reader can refuse an env measured on a machine of a different shape.
    """
    p = Path(path or ENV_FILE)
    raising = int(decision.get("raised_by", 0)) > 0
    payload = {"at": _now().isoformat(timespec="seconds"),
               "env": env_for(decision) if raising else {},
               "raised_by": int(decision.get("raised_by", 0)),
               "measured_on": ({"cores": box.get("cores"),
                                "total_phys_mb": box.get("total_phys_mb")} if box else None),
               "cadence_minutes": int(decision["cadence_minutes"]),
               "why": ("written by research/judging_throughput.py; read by "
                       "scripts/RunGauntlet.cmd, by research/hourly_cycle.py through "
                       "judging_throughput.apply_env(), and by whatever else launches the "
                       "sealed gauntlet. external_gauntlet.py is never edited. An EMPTY env "
                       "means the measured plan equalled the sealed baseline, so there was "
                       "nothing to raise -- never that the judge should be cut.")}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return payload


def apply_env(path: Path | None = None, env: dict[str, str] | None = None) -> dict[str, str]:
    """Load the published env into `os.environ` so a CHILD process inherits it.

    THE HOURLY CYCLE'S HOOK. `hourly_cycle._producer` runs each leg as a subprocess with the
    cycle's own environment, so setting these here -- before the `external_gauntlet` leg -- is
    what makes the measured worker count reach the sealed sweep in-cycle. Existing variables are
    NOT overwritten: an operator who exported `GAUNTLET_WORKERS` by hand outranks this organ.
    """
    doc = _read_json(Path(path or ENV_FILE), {}) or {}
    vals = dict((doc.get("env") or {}) if isinstance(doc, dict) else {})
    # AN ENV MEASURED ON ANOTHER MACHINE IS REFUSED. `desks/mt5/data/` travels with the release,
    # so this file can arrive from a box of a different shape; applying its numbers here is the
    # "sized off the other box" failure with extra steps. A fingerprint that disagrees is
    # ignored, which leaves the sealed file to derive its own count -- never a cut.
    stamp = doc.get("measured_on") if isinstance(doc, dict) else None
    if isinstance(stamp, dict) and vals:
        here = measure_memory()
        if (stamp.get("cores") != (os.cpu_count() or 1)
                or stamp.get("total_phys_mb") != here.get("total_phys_mb")):
            return {}
    target = os.environ if env is None else env
    applied: dict[str, str] = {}
    for k in ENV_KEYS:
        v = vals.get(k)
        if v is None or k in target:
            continue
        target[k] = str(v)
        applied[k] = str(v)
    return applied


def apply_machine_env(decision: dict[str, Any], box: dict[str, Any]) -> dict[str, Any]:
    """Persist the decision to machine-scope environment, on the judging box only.

    `MT5-Gauntlet` and `MT5-CacheWarm` have NO installer in this repository -- they exist only in
    one machine's task registry -- so machine-scope environment is the only way a repository-side
    decision reaches them. Gated on a MEASURED judging box (>=12 cores, >=32 GB) so a build box
    can never write a trading box's figures anywhere.
    """
    if not box.get("is_judging_box"):
        return {"status": "NOT_APPLIED",
                "why": (f"this box measures {box.get('cores')} cores / "
                        f"{box.get('total_phys_mb')}MB -- under the judging-box floor "
                        f"({JUDGING_BOX_MIN_CORES} cores / {JUDGING_BOX_MIN_PHYS_MB}MB), so "
                        "nothing is written to machine scope from here")}
    if sys.platform != "win32":
        return {"status": "NOT_APPLIED", "why": "machine-scope env is a Windows mechanism"}
    done: dict[str, str] = {}
    failed: dict[str, str] = {}
    for k, v in env_for(decision).items():
        try:
            subprocess.run(["setx", "/M", k, v], check=True, capture_output=True, timeout=30)
            done[k] = v
        except Exception as exc:
            failed[k] = f"{type(exc).__name__}: {exc}"
    status = "APPLIED" if done and not failed else ("PARTIAL" if done else "FAILED")
    return {"status": status, "set": done, "failed": failed}


def apply_cadence(minutes: int, box: dict[str, Any]) -> dict[str, Any]:
    """Raise the gauntlet task's repetition interval on the judging box.

    CADENCE IS THROUGHPUT. The gauntlet's cache is content-addressed and cumulative, so halving
    the period roughly doubles the cells that reach a verdict in an hour; `MT5-StallWatch` already
    keeps the oldest parent when two passes overlap, so a shorter period costs a kill at worst.
    """
    if not box.get("is_judging_box") or sys.platform != "win32":
        return {"status": "NOT_APPLIED", "minutes": int(minutes),
                "why": "not the judging box, or not Windows: cadence is published, not applied"}
    try:
        subprocess.run(["schtasks", "/Change", "/TN", GAUNTLET_TASK, "/RI", str(int(minutes))],
                       check=True, capture_output=True, timeout=30)
    except Exception as exc:
        return {"status": "FAILED", "minutes": int(minutes), "task": GAUNTLET_TASK,
                "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "APPLIED", "minutes": int(minutes), "task": GAUNTLET_TASK}


def run(write: bool = True, now: datetime | None = None, apply: bool = True) -> dict[str, Any]:
    """Measure the box, size the judge, publish the decision and apply it where it is read."""
    box = measure_box(now)
    costs = declared_costs()
    queue = measure_queue()
    decision = plan(box, queue, costs)
    applied: dict[str, Any] = {"env_file": UNMEASURED, "machine_env": UNMEASURED,
                               "cadence": UNMEASURED, "process_env": {}}
    if write:
        write_env(decision, box=box)
        applied["env_file"] = str(ENV_FILE)
        applied["process_env"] = apply_env()
    if apply:
        applied["machine_env"] = apply_machine_env(decision, box)
        applied["cadence"] = apply_cadence(int(decision["cadence_minutes"]), box)
    payload: dict[str, Any] = {
        "at": _now(now).isoformat(timespec="seconds"),
        "status": "MEASURED" if box.get("source") != UNMEASURED else UNMEASURED,
        "box": box,
        "declared_costs": costs,
        "queue": queue,
        "decision": decision,
        "applied": applied,
        "limiting_resource": decision["limiting_resource"],
        "rule": ("throughput is raised from OUTSIDE the sealed gauntlet, never by editing it; the "
                 "plan is floored at the sealed baseline so this organ can never throttle the "
                 "judge; the live terminal always wins and standing down means returning to that "
                 "baseline, not below it"),
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        try:
            from libs.ops.events import leg_events
            leg_events("judging_throughput", "OK", workers=int(decision["workers"]),
                       limiting=decision["limiting_resource"], queue_depth=queue.get("depth"))
        except Exception as exc:
            payload["events"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    return payload


def render(payload: dict[str, Any]) -> str:
    d, q, b = payload["decision"], payload["queue"], payload["box"]
    return "\n".join([
        f"JUDGING THROUGHPUT  cores={b.get('cores')} free_phys={b.get('free_phys_mb')}MB "
        f"commit_free={b.get('commit_free_mb')}MB closed={b.get('market_closed')}",
        f"  queue depth={q.get('depth')} gates/h={q.get('gates_per_hour')} "
        f"workers_last={q.get('workers_last_sweep')}",
        f"  workers {d['baseline']['workers']} -> {d['workers']} (+{d['raised_by']}) "
        f"budget={d['memory_budget_mb']}MB warm={d['warm_workers']} "
        f"cadence={d['cadence_minutes']}m limiting={d['limiting_resource']}"
        + (" STOOD-DOWN" if d["stood_down"] else ""),
        f"  gates/h {d['gates_per_hour_before']} -> {d['gates_per_hour_projected']} "
        f"days_to_drain={d['days_to_drain_queue']}",
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Size the sealed gauntlet's parallelism to the box.")
    ap.add_argument("--once", action="store_true", help="one measured pass (the leg's mode)")
    ap.add_argument("--budget-s", type=float, default=300.0,
                    help="seconds this pass may spend; the pass is a measurement, not a search")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact and apply nothing")
    args = ap.parse_args(argv)
    payload = run(write=not args.dry_run, apply=not args.dry_run)
    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
