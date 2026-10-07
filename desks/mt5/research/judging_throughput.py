"""JUDGING THROUGHPUT -- size the SEALED gauntlet's parallelism off the box, every hour.

THE DEFECT THIS ORGAN EXISTS FOR (principal, 2026-09-23: "we have tons of headroom in our box to
increase judging -- give it tons of headroom possible for maximum throughput").

`desks/mt5/scripts/external_gauntlet.py` is sealed and may never be edited. Its `_worker_count()`
already derives workers from measured cores and a per-worker memory budget, and it already honours
`GAUNTLET_WORKERS` / `GAUNTLET_SHARDS` / `GAUNTLET_MEMORY_BUDGET_MB` / `GAUNTLET_PER_WORKER_MB` /
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
`--once --budget-s 300`). Artifacts: `desks/mt5/reports/JUDGING_THROUGHPUT.json` and (2026-09-30)
`desks/mt5/reports/JUDGING_RATE.json` -- verdicts/hour from the judge's own ledger, the backlog,
the registry's creation rate and the ETA to drain (GROWING when creation outruns judging). Free
cores are MEASURED with psutil (`measure_cpu`) and may only ever raise the worker count.
Consumers: the
env file above (read by the launcher and by the hourly cycle) and `GAUNTLET_BACKPRESSURE.json`'s
next `capacity.measured.workers`, which is how the raise is verified rather than asserted.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "JUDGING_THROUGHPUT.json"
#: The judge's RATE against its BACKLOG, hourly: verdicts/hour, backlog, creation rate, ETA.
RATE_OUT = BASE / "reports" / "JUDGING_RATE.json"
#: One row per CHANGED verdict, not every completed test. Read, never written.
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
#: The canonical registry; `research_candidates.created_at` is the creation clock. Read-only.
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
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


#: Seconds psutil samples per-process CPU over. One second is long enough to see a busy
#: terminal and short enough to be noise in a 300 s leg budget.
CPU_SAMPLE_S = 1.0
#: Safety multiple on the cores OTHER processes were measured to use. A one-second sample can
#: miss a spike, so the judge leaves half as much again, and never less than one whole core.
CPU_RESERVE_MULTIPLE = 1.5
CPU_RESERVE_MIN_CORES = 1


def _is_judge(cmd: str) -> bool:
    return "external_gauntlet" in cmd or "rungauntlet" in cmd


def measure_cpu(sample_s: float = CPU_SAMPLE_S) -> dict[str, Any]:
    """FREE CORES, MEASURED (2026-09-30): how many cores everything EXCEPT the judge is using.

    `plan()` used to reserve a fixed SESSION_RESERVED_CORES=3 whatever the box was doing. This
    samples every process's CPU over `sample_s` with psutil, attributes the gauntlet and its
    worker children to the judge, and publishes what the rest of the machine (terminal, gateway,
    hourly cycle, miners) actually consumed. The plan may then reserve that measured load x
    CPU_RESERVE_MULTIPLE instead of the fixed three -- ONLY ever to raise workers: the fixed
    reservation stays the floor, so a busy box changes nothing and an idle one gains cores.
    psutil absent or any error is UNMEASURED and the fixed reservation stands.
    """
    out: dict[str, Any] = {"cpu_source": UNMEASURED, "busy_other_cores": UNMEASURED,
                           "busy_judge_cores": UNMEASURED}
    try:
        import time as _time

        import psutil
    except Exception:
        out["cpu_why"] = "psutil absent: free cores are UNMEASURED; the fixed reservation stands"
        return out
    try:
        procs = []
        for pr in psutil.process_iter(["pid", "ppid", "cmdline"]):
            try:
                pr.cpu_percent(None)
                procs.append(pr)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        _time.sleep(max(0.1, float(sample_s)))
        ppid: dict[int, int] = {}
        judge_roots: set[int] = set()
        usage: dict[int, float] = {}
        for pr in procs:
            try:
                usage[pr.pid] = float(pr.cpu_percent(None))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            ppid[pr.pid] = int(pr.info.get("ppid") or 0)
            if _is_judge(" ".join(pr.info.get("cmdline") or []).lower()):
                judge_roots.add(pr.pid)

        def _in_judge(pid: int) -> bool:
            seen = 0
            while pid and seen < 16:
                if pid in judge_roots:
                    return True
                pid, seen = ppid.get(pid, 0), seen + 1
            return False

        judge = sum(v for pid, v in usage.items() if _in_judge(pid)) / 100.0
        other = sum(v for pid, v in usage.items()
                    if not _in_judge(pid) and pid != os.getpid()) / 100.0
        out.update(cpu_source="psutil", busy_other_cores=round(other, 2),
                   busy_judge_cores=round(judge, 2), cpu_sample_s=float(sample_s))
    except Exception as exc:
        out["cpu_why"] = f"{type(exc).__name__}: {exc}"
    return out


def _psutil_memory() -> dict[str, Any]:
    """psutil's reading, used when the platform call above could not measure (CLAUDE.md: USE
    psutil for the machine the code runs on)."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {"source": "psutil", "total_phys_mb": int(vm.total // 1048576),
                "free_phys_mb": int(vm.available // 1048576)}
    except Exception:
        return {}


def measure_box(now: datetime | None = None, *, sample_cpu: bool = True) -> dict[str, Any]:
    """Everything the plan is allowed to be sized from, all of it read off this machine."""
    box: dict[str, Any] = {"cores": int(os.cpu_count() or 1), "market_closed": market_closed(now)}
    box.update(measure_memory())
    if box.get("free_phys_mb") == UNMEASURED:
        box.update(_psutil_memory())
    if sample_cpu:
        box.update(measure_cpu())
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
                           "source": str(BACKPRESSURE), **_breach_backlog(),
                           **_burndown(), **_judge_environment()}
    if not isinstance(doc, dict) or not doc:
        out["why"] = f"{BACKPRESSURE.name} absent or unreadable: queue depth is UNMEASURED"
        return out
    meas = (doc.get("capacity") or {}).get("measured") or {}
    disc, judged = meas.get("n_cells_discovered"), meas.get("n_judged")
    win = (doc.get("windows") or {}).get("24h") or {}
    per_hour = (win.get("testing") or {}).get("per_hour")
    if isinstance(disc, int) and isinstance(judged, int):
        out.update(status="MEASURED", depth=max(0, disc - judged), discovered=disc,
                   depth_scope="sweep", judged_last_sweep=judged)
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
    out.update(_value_at_risk())
    return out


#: Intake's own measurement of what the unjudged backlog is WORTH, published per hour by
#: `research/judge_coverage.py`. Read here, never written here: that organ owns the number and
#: this one owns the response to it.
JUDGE_COVERAGE = BASE / "reports" / "JUDGE_COVERAGE.json"


def _value_at_risk() -> dict[str, Any]:
    """The expected value sitting unjudged, and whether one hour can reach it.

    DEPTH IS NOT DEMAND -- VALUE IS. A queue of ten thousand cells nobody expects anything from
    is not a reason to take cores from the live terminal, and a queue of two hundred carrying the
    desk's best expected value per judge-second is. `judge_coverage` measures both from the
    learned priors, the net-of-cost slot values and the breadth machinery; this organ is the only
    one that can answer it, by raising workers and cadence. An absent report is UNMEASURED and
    raises nothing -- a number nobody measured must never move the box.
    """
    doc = _read_json(JUDGE_COVERAGE, {}) or {}
    tot = doc.get("totals") if isinstance(doc, dict) else None
    if not isinstance(tot, dict):
        return {"value_at_risk": UNMEASURED, "value_forgone_per_hour": UNMEASURED,
                "capacity_short": UNMEASURED, "value_source": str(JUDGE_COVERAGE)}
    return {"value_at_risk": tot.get("value_at_risk", UNMEASURED),
            "value_deferred": tot.get("value_deferred", UNMEASURED),
            "value_forgone_per_hour": tot.get("value_forgone_per_hour", UNMEASURED),
            "hours_to_drain": tot.get("hours_to_drain", UNMEASURED),
            "capacity_short": tot.get("capacity_short", UNMEASURED),
            "value_source": str(JUDGE_COVERAGE)}


#: The backlog's burn-down (`research/judging_burndown.py`, leg `judging_burndown`): first rulings
#: per day against new cells per day. Read here, never written here.
BURNDOWN = BASE / "reports" / "JUDGING_BURNDOWN.json"


def _burndown() -> dict[str, Any]:
    """Whether the backlog is DRAINING or GROWING, from its own organ. Absent is UNMEASURED."""
    doc = _read_json(BURNDOWN, None)
    bd = doc.get("burn_down") if isinstance(doc, dict) else None
    if not isinstance(bd, dict):
        return {"burndown_status": UNMEASURED,
                "burndown_why": f"{BURNDOWN.name} absent: the burn-down is UNMEASURED"}
    return {"burndown_status": bd.get("status", UNMEASURED),
            "burndown_net_per_day": bd.get("net_per_day", UNMEASURED),
            "burndown_needed_first_rulings_per_hour":
                bd.get("needed_first_rulings_per_hour", UNMEASURED),
            "burndown_source": BURNDOWN.name}


#: The judge's ENVIRONMENT (`scripts/gauntlet_guard.py`, leg `gauntlet_guard`, recovered box patch
#: 08): commit headroom, torn universe frames and how many passes reached the epilogue. Read here,
#: never written here -- and REPORTED ONLY. A pass that died on the commit ceiling is not a reason
#: to size the judge down; the sizing above is one-way and this changes no worker count.
GAUNTLET_PASSES = BASE / "reports" / "GAUNTLET_PASSES.json"


def _judge_environment() -> dict[str, Any]:
    """Whether the judge's passes reach their epilogue, from the guard. Absent is UNMEASURED."""
    doc = _read_json(GAUNTLET_PASSES, None)
    if not isinstance(doc, dict):
        return {"judge_env_status": UNMEASURED,
                "judge_env_why": (f"{GAUNTLET_PASSES.name} absent: the judge's environment is "
                                  f"UNMEASURED, which is never clean")}
    commit = doc.get("commit") if isinstance(doc.get("commit"), dict) else {}
    frames = doc.get("frame_integrity") if isinstance(doc.get("frame_integrity"), dict) else {}
    return {"judge_env_status": "MEASURED",
            "judge_env_reach_rate": doc.get("reach_rate", UNMEASURED),
            "judge_env_passes_closed": doc.get("passes_closed", UNMEASURED),
            "judge_env_commit_headroom_gb": commit.get("headroom_gb", UNMEASURED),
            "judge_env_commit_ceiling_touched": commit.get("peak_touched_ceiling", UNMEASURED),
            "judge_env_torn_frames": frames.get("n_torn", UNMEASURED),
            "judge_env_source": GAUNTLET_PASSES.name}


def _breach_backlog() -> dict[str, Any]:
    """CLOCK IF AND ONLY IF CERTIFICATE (principal 2026-09-23): cells that LOST their forward
    clocks for want of a canonical certificate, from `research/clock_certificate.py`'s docket.
    Read here, never written here.

    They keep the FRONT of the judge's queue -- losing a clock is not losing priority, and
    judging one of these cells is the only thing that can give it a clock back. The judge's
    SIZING has to honour that or the priority is decorative: this backlog is demand on the judge
    exactly as queue depth is. Read ABOVE the backpressure early-return on purpose -- a host with
    no backpressure artifact must not also lose this count.
    """
    doc = _read_json(BREACH_DOCKET, None)
    if not isinstance(doc, dict):
        return {"clock_breach_cells": UNMEASURED,
                "clock_breach_why": (f"{BREACH_DOCKET.name} absent: the breach backlog is "
                                     f"UNMEASURED, which is never zero")}
    n = doc.get("breached")
    return {"clock_breach_cells": n if isinstance(n, int) else UNMEASURED,
            "clock_breach_overdue": doc.get("overdue_beyond_one_judging_cycle", UNMEASURED),
            "clock_breach_source": str(BREACH_DOCKET.name)}


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
    # FREE CORES, MEASURED -- AND ONLY EVER UPWARD. When psutil measured what the rest of the box
    # uses, the in-session reservation becomes that load x CPU_RESERVE_MULTIPLE (at least one
    # core). It replaces the fixed three only when it leaves MORE cores to the judge, so today's
    # count is the floor and a busy terminal can never cost the judge a worker it had.
    other = box.get("busy_other_cores")
    cores_basis = "fixed_reservation"
    if not closed and isinstance(other, (int, float)):
        measured_reserve = max(CPU_RESERVE_MIN_CORES,
                               int(-(-float(other) * CPU_RESERVE_MULTIPLE // 1)))
        if cores - measured_reserve > by_cores:
            by_cores, reserved = cores - measured_reserve, measured_reserve
            cores_basis = "measured_free_cores"

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
    # VALUE AT RISK IS DEMAND ON THE JUDGE, and it is the honest trigger for capacity. When
    # `judge_coverage` measures that one hour cannot reach the backlog it has priced -- expected
    # value per judge-second, from the learned priors, the net-of-cost slot values and the
    # breadth machinery -- the desk is choosing to forgo that value every hour it waits. The
    # answer is MORE JUDGE, never a smaller docket: this raises workers and cadence exactly as a
    # deep queue does, and like every other signal here it is one-way and can lower neither.
    value_short = queue.get("capacity_short") is True
    if isinstance(breach_overdue, int) and breach_overdue > 0:
        deep = True
        limiting = "clock_certificate_breach"
    elif value_short:
        deep = True
        limiting = "judge_value_at_risk"
    elif queue.get("burndown_status") == "GROWING":
        # THE BACKLOG IS OUTGROWING THE JUDGE (`JUDGING_BURNDOWN.json`: first rulings/day below
        # new cells/day). Demand, exactly as a deep queue is -- one-way, it can lower nothing.
        deep = True
        limiting = "backlog_growing"
    elif isinstance(depth, int) and not deep and not stood_down:
        limiting = "queue"

    budget_mb = max(float(base["memory_budget_mb"]), float(workers) * per)
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
        # THE WARMER SIZES ITSELF (2026-09-30). This used to be `min(4, by_cores - workers)`,
        # published machine-wide as WARM_WORKERS -- ONE whenever the judge held its cores, which
        # pinned the cache warmer to one worker through every single-threaded gate phase.
        # `scripts/warm_gauntlet_cache.py` now measures idle cores and free memory with psutil
        # every few seconds and runs its workers at IDLE priority; nothing is published for it.
        "warm_workers": "SELF_SIZED",
        "cadence_minutes": int(cadence),
        # The sealed judge now exposes SHARD_PROTOCOL=2: one stable ownership hash per cell,
        # a union-derived lockbox cut, fail-closed collection and one program-level merge. The
        # dispatcher therefore uses the same measured core allocation as the build pool. A
        # stood-down box remains serial so the live terminal keeps the machine.
        "shards": 1 if stood_down else int(workers),
        "shards_why": ("serial because live-terminal admission stood the plan down"
                       if stood_down else
                       "the judge's fail-closed SHARD_PROTOCOL=2 partitions cell-local work "
                       "across the measured worker allocation and computes program-level gates "
                       "once on the union"),
        "limiting_resource": limiting,
        "stood_down": stood_down,
        "why": why_down or (
            f"cores {by_cores} (reserved {reserved}), memory {by_mem}, commit {by_commit} at "
            f"{per:.0f}MB a worker; the binding one is {limiting}"),
        "baseline": base,
        "cores_basis": cores_basis,
        "reserved_cores": reserved,
        "raised_by": int(workers) - int(base["workers"]),
        "queue_deep": bool(deep),
        "clock_breach_cells": queue.get("clock_breach_cells", UNMEASURED),
        "clock_breach_overdue": queue.get("clock_breach_overdue", UNMEASURED),
        "gates_per_hour_before": before if before is not None else UNMEASURED,
        "gates_per_hour_projected": gates_after,
        "days_to_drain_queue": days,
    }


#: EVERY SUBPROCESS THIS ORGAN RUNS IS BOUNDED, and so is their sum (CRO 2026-09-30: the leg ran
#: 290-400 s against a 300 s budget on every pass, because `schtasks` calls carried 60 s timeouts
#: and sat AHEAD of the artifact writes, so JUDGING_RATE.json went 4.4 h stale). One call may take
#: `SUBPROCESS_TIMEOUT_S`; all of them together `APPLY_BUDGET_S`, counted from the moment the
#: artifacts are already on disk.
SUBPROCESS_TIMEOUT_S = 20.0
APPLY_BUDGET_S = 90.0
_APPLY_DEADLINE: list[float] = []
_MACHINE_ENV_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


def _sub_timeout() -> float:
    """Seconds the next subprocess may take: its own cap, never past the apply deadline."""
    import time as _time
    if not _APPLY_DEADLINE:
        return SUBPROCESS_TIMEOUT_S
    left = _APPLY_DEADLINE[0] - _time.monotonic()
    if left <= 1.0:
        raise TimeoutError("apply budget spent; the call was skipped and is recorded as such")
    return min(SUBPROCESS_TIMEOUT_S, left)


ENV_KEYS = ("GAUNTLET_WORKERS", "GAUNTLET_SHARDS", "GAUNTLET_MEMORY_BUDGET_MB",
            "GAUNTLET_HEADROOM_CAP_MB", "GAUNTLET_PER_WORKER_MB",
            "GAUNTLET_FRESH_BUDGET_SEC")

#: Machine-scope variables this organ once published and now RETIRES. `apply_machine_env` deletes
#: them so a stale value stops reaching the scheduled tasks (`WARM_WORKERS=1` pinned the warmer).
RETIRED_MACHINE_KEYS = ("WARM_WORKERS",)

#: The sealed file's own default for the FIRST-TIME build, and the share of the judge's real wall
#: clock the build may have. `_prewarm_cache` is given the SAME deadline as the build loop
#: (`_build_t0 + FRESH_BUILD_BUDGET_SEC`), so when the docket outgrows the budget the warm eats all
#: of it and the gate phase gets what was already cached. MEASURED 2026-09-24 on a docket of
#: 250,992 cells: "PRE-WARM: 15 worker(s) warmed 13993 cell(s) in 2874s ... 67910 NOT REACHED
#: BEFORE THE BUILD BUDGET" -- 2,874 seconds spent against a 2,700-second budget, with a quarter
#: of the docket never built. The judge is not being asked to decide anything different; it is
#: being given the wall clock its own task already allows.
SEALED_FRESH_BUDGET_SEC = 2700.0
FRESH_BUDGET_SHARE_OF_LIMIT = 0.6


def task_time_limit_s(task: str = GAUNTLET_TASK) -> float | None:
    """The judge task's own ExecutionTimeLimit in seconds, read off the box. None if unreadable.

    THE CEILING IS THE SCHEDULER'S, NOT THIS MODULE'S. `MT5-Gauntlet` carries
    `<ExecutionTimeLimit>PT4H</ExecutionTimeLimit>`: a build budget above that is time the sweep
    is killed before it can use, and one far below it is the gauntlet stopping itself while the
    task would happily have let it finish. An unreadable limit writes NOTHING and the sealed
    default stands (L1.28a) -- never a number invented here.
    """
    if sys.platform != "win32":
        return None
    try:
        proc = subprocess.run(["schtasks", "/query", "/tn", task, "/xml"],
                              capture_output=True, text=True, timeout=_sub_timeout(),
                              check=False)
    except Exception:
        return None
    import re
    m = re.search(r"<ExecutionTimeLimit>PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?</ExecutionTimeLimit>",
                  proc.stdout or "")
    if not m:
        return None
    h, mi, s = (float(g or 0) for g in m.groups())
    total = h * 3600.0 + mi * 60.0 + s
    # PT0S means unlimited execution, not a failed measurement. Conflating the two
    # resurrected the previous four-hour limit after the operator removed it.
    return total


def fresh_budget_s(limit_s: float | None,
                   current_budget_s: float | None = None) -> tuple[float | None, str]:
    """The build seconds to publish, or None to leave the sealed default alone. ONE WAY: the
    figure is floored at the sealed default, so this can only ever give the judge MORE time."""
    if limit_s is None:
        return None, ("the judge task's ExecutionTimeLimit is unreadable, so the sealed "
                      f"{SEALED_FRESH_BUDGET_SEC:.0f}s build budget stands unchanged")
    if limit_s == 0:
        import math
        prior = current_budget_s
        want = (max(SEALED_FRESH_BUDGET_SEC, prior)
                if isinstance(prior, (int, float)) and math.isfinite(prior)
                else SEALED_FRESH_BUDGET_SEC)
        return (want if want > SEALED_FRESH_BUDGET_SEC else None,
                f"task execution is unlimited; retain the bounded {want:.0f}s build budget")
    want = max(SEALED_FRESH_BUDGET_SEC, limit_s * FRESH_BUDGET_SHARE_OF_LIMIT)
    if want <= SEALED_FRESH_BUDGET_SEC:
        return None, (f"{FRESH_BUDGET_SHARE_OF_LIMIT:.0%} of the task's {limit_s:.0f}s limit is "
                      f"not more than the sealed default; nothing is raised")
    return want, (f"{want:.0f}s = {FRESH_BUDGET_SHARE_OF_LIMIT:.0%} of the task's own "
                  f"{limit_s:.0f}s ExecutionTimeLimit, leaving {limit_s - want:.0f}s for the "
                  f"gate phase")


def env_for(decision: dict[str, Any]) -> dict[str, str]:
    """The environment the sealed gauntlet and the cache warmer read, as strings."""
    env = {
        "GAUNTLET_WORKERS": str(int(decision["workers"])),
        "GAUNTLET_SHARDS": str(int(decision.get("shards", 1))),
        "GAUNTLET_MEMORY_BUDGET_MB": str(int(decision["memory_budget_mb"])),
        "GAUNTLET_HEADROOM_CAP_MB": str(int(decision["headroom_cap_mb"])),
        "GAUNTLET_PER_WORKER_MB": str(int(decision["per_worker_mb"])),
    }
    fresh = decision.get("fresh_budget_s")
    if isinstance(fresh, (int, float)) and float(fresh) > SEALED_FRESH_BUDGET_SEC:
        env["GAUNTLET_FRESH_BUDGET_SEC"] = str(int(fresh))
    return env


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
    fresh = decision.get("fresh_budget_s")
    raising = (int(decision.get("raised_by", 0)) > 0
               or (isinstance(fresh, (int, float))
                   and float(fresh) > SEALED_FRESH_BUDGET_SEC))
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
    unchanged: dict[str, str] = {}
    # A VALUE ALREADY IN MACHINE SCOPE IS NOT RE-WRITTEN. Each `setx /M` is a registry write plus
    # a WM_SETTINGCHANGE broadcast that can block for its whole timeout; six of them every hour
    # were part of why this leg ran past its budget. `os.environ` of this process is what the
    # scheduler handed it from machine scope, so equality there means there is nothing to do.
    for k, v in env_for(decision).items():
        if os.environ.get(k) == v:
            unchanged[k] = v
            continue
        try:
            subprocess.run(["setx", "/M", k, v], check=True, capture_output=True,
                           timeout=_sub_timeout())
            done[k] = v
        except Exception as exc:
            failed[k] = f"{type(exc).__name__}: {exc}"
    retired: dict[str, str] = {}
    for k in RETIRED_MACHINE_KEYS:
        try:
            r = subprocess.run(["reg", "delete", _MACHINE_ENV_KEY, "/v", k, "/f"],
                               capture_output=True, text=True, timeout=_sub_timeout(),
                               check=False)
            retired[k] = "DELETED" if r.returncode == 0 else "ABSENT"
        except Exception as exc:
            retired[k] = f"FAILED: {type(exc).__name__}: {exc}"
    status = ("FAILED" if failed and not done and not unchanged
              else "PARTIAL" if failed else "APPLIED")
    return {"status": status, "set": done, "unchanged": unchanged, "failed": failed,
            "retired": retired}


def _next_run(task: str) -> str:
    """The task's next run time as the box reports it; empty when it cannot be read.

    THE ONLY PROOF A CADENCE WAS APPLIED. `schtasks /Change` returns SUCCESS against a trigger
    whose repetition window has already closed, so the return code says nothing about whether the
    judge will ever fire again. This re-reads the one field that does.
    """
    try:
        proc = subprocess.run(["schtasks", "/query", "/tn", task, "/fo", "csv", "/v"],
                              capture_output=True, text=True, timeout=_sub_timeout(),
                              check=False)
    except Exception:
        return ""
    import csv
    import io
    for row in csv.DictReader(io.StringIO(proc.stdout)):
        if (row.get("TaskName") or "").strip():
            return (row.get("Next Run Time") or "").strip()
    return ""


#: The repetition WINDOW the judge's trigger is given, in `schtasks` `HHHH:MM`. 9999:59 is the
#: maximum the tool accepts (~416 days) and this organ re-applies it every hour, so the window can
#: never close again. It bounds EXPIRY, never work.
CADENCE_DURATION = "9999:59"


def apply_cadence(minutes: int, box: dict[str, Any]) -> dict[str, Any]:
    """Raise the gauntlet task's repetition interval on the judging box, and KEEP ITS WINDOW OPEN.

    CADENCE IS THROUGHPUT. The gauntlet's cache is content-addressed and cumulative, so halving
    the period roughly doubles the cells that reach a verdict in an hour; `MT5-StallWatch` already
    keeps the oldest parent when two passes overlap, so a shorter period costs a kill at worst.

    THE INTERVAL WAS NEVER THE WHOLE STORY, and it cost the desk a day of judging (measured
    2026-09-23/24). `MT5-Gauntlet`'s trigger carried `<Interval>PT5M</Interval>` inside a
    `<Duration>P7DT1H35M</Duration>` with `StopAtDurationEnd`. THE WINDOW CLOSED. The task stayed
    Enabled with a real Last Run Time and its Next Run Time went to `N/A`, so nothing in the tree
    noticed: `stall_watch` heals tasks that are missing or disabled and this one was neither. The
    judge last fired at 06:51 and produced verdicts in TWO of the day's twenty-four hours, while
    this organ went on writing five-minute intervals onto a trigger that had already stopped --
    `/RI` sets the interval and leaves the duration exactly where it was.

    So the duration is now pushed out with the interval, and the result is VERIFIED by re-reading
    the next run time rather than trusting the exit code. Both are one-way: the interval only ever
    comes from `plan()`, which is floored at the sealed baseline, and the duration only ever grows.
    """
    if not box.get("is_judging_box") or sys.platform != "win32":
        return {"status": "NOT_APPLIED", "minutes": int(minutes),
                "why": "not the judging box, or not Windows: cadence is published, not applied"}
    before = _next_run(GAUNTLET_TASK)
    try:
        subprocess.run(["schtasks", "/Change", "/TN", GAUNTLET_TASK, "/RI", str(int(minutes)),
                        "/DU", CADENCE_DURATION],
                       check=True, capture_output=True, timeout=_sub_timeout())
    except Exception as exc:
        return {"status": "FAILED", "minutes": int(minutes), "task": GAUNTLET_TASK,
                "next_run_before": before, "why": f"{type(exc).__name__}: {exc}"}
    after = _next_run(GAUNTLET_TASK)
    alive = bool(after) and after.lower() not in ("", "n/a")
    return {"status": "APPLIED" if alive else "APPLIED_BUT_STOPPED",
            "minutes": int(minutes), "task": GAUNTLET_TASK, "duration": CADENCE_DURATION,
            "next_run_before": before, "next_run_after": after,
            "why": ("" if alive else
                    "the command succeeded and the task still has no next run time -- its trigger "
                    "is not a repetition this organ can re-arm, and the judge is idle")}


def _write_atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def run(write: bool = True, now: datetime | None = None, apply: bool = True) -> dict[str, Any]:
    """Measure the box, size the judge, PUBLISH, and only then apply where it is read.

    ORDER IS THE FIX (CRO 2026-09-30). Every artifact -- the env file, JUDGING_RATE.json and
    JUDGING_THROUGHPUT.json -- is written BEFORE any `setx`/`schtasks` call, so a slow or hung
    apply can no longer cost the hour its measurement (it cost 4.4 h of JUDGING_RATE staleness).
    The apply is best-effort inside `APPLY_BUDGET_S`, each call inside `SUBPROCESS_TIMEOUT_S`,
    and its outcome is written into JUDGING_THROUGHPUT.json by a second, equally atomic write.
    """
    import time as _time

    t0 = _time.monotonic()
    box = measure_box(now)
    costs = declared_costs()
    queue = measure_queue()
    decision = plan(box, queue, costs)
    # THE BUILD BUDGET, FROM THE TASK'S OWN LIMIT. Measured 2026-09-24: the pre-warm shares the
    # build deadline and spent 2,874 s of a 2,700 s budget on a 250,992-cell docket, leaving
    # 67,910 cells never built. This gives the judge the wall clock its own scheduled task already
    # allows and floors it at the sealed default, so it can only ever add time. A query that times
    # out reuses the last limit this organ read on this box, and says so.
    _limit = task_time_limit_s() if box.get("is_judging_box") else None
    _limit_basis = "schtasks" if _limit is not None else UNMEASURED
    if _limit is None and box.get("is_judging_box"):
        prev = ((_read_json(OUT, {}) or {}).get("decision") or {}).get("task_time_limit_s")
        if isinstance(prev, (int, float)) and prev > 0:
            _limit, _limit_basis = float(prev), "previous_pass (schtasks query unanswered)"
    _current_budget = None
    if _limit == 0:
        previous_env = _read_json(ENV_FILE, {}) or {}
        stamp = previous_env.get("measured_on") or {}
        if (stamp.get("cores") == box.get("cores")
                and stamp.get("total_phys_mb") == box.get("total_phys_mb")):
            with contextlib.suppress(TypeError, ValueError):
                _current_budget = float((previous_env.get("env") or {}).get(
                    "GAUNTLET_FRESH_BUDGET_SEC"))
    _fresh, _fresh_why = fresh_budget_s(_limit, _current_budget)
    decision["fresh_budget_s"] = _fresh
    decision["fresh_budget_why"] = _fresh_why
    decision["task_time_limit_s"] = _limit if _limit is not None else UNMEASURED
    decision["task_time_limit_basis"] = _limit_basis
    applied: dict[str, Any] = {"env_file": UNMEASURED, "machine_env": "PENDING",
                               "cadence": "PENDING", "process_env": {}}
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
    try:
        payload["rate"] = measure_rate(queue, decision, now)
    except Exception as exc:     # a broken rate read must never cost the sizing decision
        payload["rate"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    if write:
        write_env(decision, box=box)
        applied["env_file"] = str(ENV_FILE)
        applied["process_env"] = apply_env()
        _write_atomic(RATE_OUT, payload["rate"])
        payload["measure_seconds"] = round(_time.monotonic() - t0, 1)
        _write_atomic(OUT, payload)
    if apply:
        _APPLY_DEADLINE[:] = [_time.monotonic() + APPLY_BUDGET_S]
        try:
            steps: tuple[tuple[str, Any], ...] = (
                ("machine_env", lambda: apply_machine_env(decision, box)),
                ("cadence", lambda: apply_cadence(int(decision["cadence_minutes"]), box)))
            for name, fn in steps:
                try:
                    applied[name] = fn()
                except Exception as exc:   # best effort: the measurement is already published
                    applied[name] = {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
        finally:
            _APPLY_DEADLINE[:] = []
    else:
        applied["machine_env"] = applied["cadence"] = "NOT_ATTEMPTED (dry run)"
    payload["seconds"] = round(_time.monotonic() - t0, 1)
    if write:
        _write_atomic(OUT, payload)
        try:
            from libs.ops.events import leg_events
            leg_events("judging_throughput", "OK", workers=int(decision["workers"]),
                       limiting=decision["limiting_resource"], queue_depth=queue.get("depth"))
        except Exception as exc:
            payload["events"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    return payload


_AT = re.compile(r'"at"\s*:\s*"([^"]+)"')


def _verdict_counts(now: datetime, path: Path | None = None) -> dict[str, Any]:
    """Verdict rows the judge appended in the last 1h / 24h / 7d, from its own ledger.

    Streams the file and reads only each row's `at` stamp, so a multi-million-row ledger costs
    one pass and constant memory. An absent ledger is UNMEASURED -- never zero verdicts."""
    from research.judging_burndown import classify

    p = GATE_LEDGER if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: verdicts/hour is UNMEASURED"}
    cuts = {w: (now - timedelta(hours=h)).isoformat(timespec="seconds")
            for w, h in (("1h", 1), ("24h", 24), ("7d", 168))}
    counts = dict.fromkeys(cuts, 0)
    first_counts = dict.fromkeys(cuts, 0)
    first_terminal_cells: set[str] = set()
    total, unstamped, last = 0, 0, ""
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                total += 1
                m = _AT.search(line)
                if not m:
                    unstamped += 1
                    continue
                try:
                    stamp = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                    if stamp.tzinfo is None or stamp > now:
                        unstamped += 1
                        continue
                    at = stamp.astimezone(UTC).isoformat(timespec="seconds")
                except ValueError:
                    unstamped += 1
                    continue
                last = max(last, at)
                for w, cut in cuts.items():
                    if at >= cut:
                        counts[w] += 1
                # The writer appends only when a terminal verdict changes. Repeated cells
                # are retests, not backlog cleared. UNKNOWN/build/data refusals are not
                # completed evidence judgements either. Preserve the raw event count above.
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                cell = str(row.get("cell", ""))
                if not cell or classify(row) != "ruled":
                    continue
                if cell in first_terminal_cells:
                    continue
                first_terminal_cells.add(cell)
                for w, cut in cuts.items():
                    if at >= cut:
                        first_counts[w] += 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "MEASURED", "rows_total": total, "rows_unstamped": unstamped,
            "last_verdict_at": last or None, "counts": counts,
            "count_basis": "changed verdict events; unchanged retests do not append",
            "first_terminal_counts": first_counts,
            "first_terminal_cells": len(first_terminal_cells),
            "first_terminal_per_hour": {
                "1h": float(first_counts["1h"]),
                "24h": round(first_counts["24h"] / 24.0, 3),
                "7d": round(first_counts["7d"] / 168.0, 3)},
            "per_hour": {"1h": float(counts["1h"]), "24h": round(counts["24h"] / 24.0, 3),
                         "7d": round(counts["7d"] / 168.0, 3)}}


def _creation_counts(now: datetime, path: Path | None = None) -> dict[str, Any]:
    """Cells the desk CREATED in the last 24h / 7d, from the registry's own created_at."""
    import sqlite3

    p = REGISTRY if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: creation rate is UNMEASURED"}
    try:
        c = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    try:
        cut_24h = (now - timedelta(hours=24)).isoformat(timespec="seconds")
        cut_7d = (now - timedelta(hours=168)).isoformat(timespec="seconds")
        # Both windows are in the same indexed range. One bounded scan also keeps
        # the two rates on one SQLite snapshot while the intake is writing.
        n_24h, n_7d = c.execute(
            "SELECT COALESCE(SUM(created_at >= ?), 0), COUNT(*) "
            "FROM research_candidates WHERE created_at >= ?",
            (cut_24h, cut_7d),
        ).fetchone()
        out = {"24h": int(n_24h), "7d": int(n_7d)}
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    finally:
        c.close()
    return {"status": "MEASURED", "counts": out,
            "per_hour": {"24h": round(out["24h"] / 24.0, 3), "7d": round(out["7d"] / 168.0, 3)}}


def measure_rate(queue: dict[str, Any], decision: dict[str, Any],
                 now: datetime | None = None, *, ledger: Path | None = None,
                 registry: Path | None = None) -> dict[str, Any]:
    """VERDICTS/HOUR AGAINST THE BACKLOG, and how long the backlog takes to drain.

    ETA = backlog / (verdicts/hour - created/hour), both over the same 24 h window. A judge that
    judges slower than the desk creates never drains: that is reported as GROWING with the net
    growth per day, not as a large finite number. Any missing input makes the ETA UNMEASURED."""
    t = _now(now)
    ver = _verdict_counts(t, ledger)
    cre = _creation_counts(t, registry)
    # One sweep can cover only a prefix of the full docket. Its remainder is not
    # the institutional backlog and must never drive a claim of full clearance.
    backlog = (UNMEASURED if queue.get("depth_scope") == "sweep"
               else queue.get("depth"))
    backlog_source = queue.get("source", UNMEASURED)
    # THE DOCKET IS THE BACKLOG. GAUNTLET_BACKPRESSURE counts one sweep's discovered-minus-judged
    # and went unwritten from 2026-09-25, which left this ETA UNMEASURED for five days while
    # JUDGE_COVERAGE, written every hour from the docket itself, held 1,398,253 unjudged. The
    # docket count is preferred whenever it exists; backpressure is the fallback.
    _cov = _read_json(JUDGE_COVERAGE, {}) or {}
    _unj = ((_cov.get("totals") or {}).get("unjudged_total")
            if isinstance(_cov, dict) else None)
    # Require a timezone-aware content timestamp; touching the file is not freshness.
    try:
        cov_at = datetime.fromisoformat(str(_cov.get("at") or "").replace("Z", "+00:00"))
        coverage_fresh = cov_at.tzinfo is not None and 0 <= (t - cov_at).total_seconds() <= 7200
    except (ValueError, TypeError, AttributeError):
        coverage_fresh = False
    if isinstance(_unj, int) and coverage_fresh:
        backlog, backlog_source = _unj, f"{JUDGE_COVERAGE} totals.unjudged_total"
    vph = ((ver.get("per_hour") or {}).get("24h") if ver.get("status") == "MEASURED" else None)
    first_vph = ((ver.get("first_terminal_per_hour") or {}).get("24h")
                 if ver.get("status") == "MEASURED" else None)
    cph = ((cre.get("per_hour") or {}).get("24h") if cre.get("status") == "MEASURED" else None)
    eta: dict[str, Any] = {"status": UNMEASURED}
    if isinstance(backlog, int) and isinstance(first_vph, float) and isinstance(cph, float):
        net = first_vph - cph
        if backlog == 0:
            eta = {"status": "DRAINED", "hours": 0.0}
        elif net > 0:
            eta = {"status": "DRAINING", "hours": round(backlog / net, 1),
                   "days": round(backlog / net / 24.0, 2), "net_per_hour": round(net, 3)}
        else:
            eta = {"status": "GROWING", "hours": None, "net_per_day": round(net * 24.0, 1),
                   "why": ("the judge returns fewer verdicts an hour than the desk creates cells; "
                           "the backlog cannot drain at this rate")}
    elif not isinstance(backlog, int):
        eta["why"] = "backlog UNMEASURED (GAUNTLET_BACKPRESSURE.json absent)"
    else:
        eta["why"] = "verdict or creation rate UNMEASURED"
    return {
        "at": t.isoformat(timespec="seconds"),
        "verdicts": ver, "created": cre,
        "verdicts_per_hour": vph if vph is not None else UNMEASURED,
        "verdicts_per_day": round(vph * 24.0, 1) if vph is not None else UNMEASURED,
        "verdict_rate_basis": "changed verdict events, not total completed tests",
        "first_judged_per_day": (round(first_vph * 24.0, 1)
                                 if first_vph is not None else UNMEASURED),
        "eta_basis": "first terminal cell dispositions, never repeated changed verdicts",
        "coverage_backlog_fresh": coverage_fresh,
        "created_per_day": round(cph * 24.0, 1) if cph is not None else UNMEASURED,
        "backlog": backlog if backlog is not None else UNMEASURED,
        "backlog_source": backlog_source,
        "eta_to_drain": eta,
        "workers_planned": decision.get("workers"),
        "workers_last_sweep": queue.get("workers_last_sweep", UNMEASURED),
        "cores_basis": decision.get("cores_basis", UNMEASURED),
    }


def render(payload: dict[str, Any]) -> str:
    d, q, b = payload["decision"], payload["queue"], payload["box"]
    r = payload.get("rate") or {}
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
        f"  verdicts/h={r.get('verdicts_per_hour')} created/day={r.get('created_per_day')} "
        f"backlog={r.get('backlog')} eta={(r.get('eta_to_drain') or {}).get('status')}",
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
