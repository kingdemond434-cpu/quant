"""THE JUDGE BORROWS IDLE CORES, AND LIVE TAKES THEM BACK (owner, 2026-11-25).

THE DECISION. "Keep the 6 reserved judge cores as a floor. Let the judge borrow idle cores
elastically, up to the 75% research cap. Live trading always has priority, so the judge yields
instantly when the gateway or live tasks need CPU or memory."

WHAT IT CHANGES, AND ONLY THIS. The CPU AFFINITY of the processes `judge_priority.classify` calls
`judge` (the resident launcher, the sweep child, its shards and its pool workers). Nothing else:

    * no process is killed, suspended, re-prioritised or restarted (the class rule stays
      `judge_priority.judge_target`'s: NORMAL on its cores, strictly below every live process);
    * no gate, threshold, trial charge, cell or verdict is read or written -- affinity decides
      WHERE the judge's arithmetic runs, never what it computes;
    * no miner, audit or live process is touched.

THE RULE, every pass (one a minute, inside the `MT5-LivePriority` task, after live is raised):

    floor    = the reserved cores in force (`judge_priority.reserved_cores`, 6 on the 18-core box)
    ceiling  = floor(RESEARCH_CAP_SHARE * cores)  = 13 of 18   (the 75% research cap)
    spare    = cores - live_reserve - ceil(busy cores of everything that is not the judge)
               live_reserve = max(LIVE_RESERVE_MIN_CORES, ceil(LIVE_RESERVE_MULTIPLE * live busy))
    want     = clamp(spare, floor, ceiling), grown by at most BORROW_STEP a pass
    SHED to the floor at once when: live busy >= LIVE_SHED_CORES, free physical memory under
    max(MEM_RESERVE_MIN_MB, MEM_RESERVE_SHARE * total), any python/live row unreadable, or any
    input unmeasured. Shedding never waits for hysteresis.

"INSTANTLY", HONESTLY. The scheduler already gives live the CPU the moment it wants it: live runs
at ABOVE_NORMAL (`live_priority.py`) and the judge at NORMAL, so on every core -- borrowed or
reserved -- a runnable live thread pre-empts the judge with no help from this module. What this
module adds is that the judge's FOOTPRINT shrinks back to its floor within one pass (<= 60 s)
of live demand or memory pressure appearing, and grows only while the cores are measured idle.

WHY THE 75% CAP IS DECLARED HERE. A search of the tree on 2026-11-25 (`grep` for 0.75 / 75% /
research cap across scripts, research, libs, ops and data) found no existing constant; the cap
is the owner's figure from the decision above. `data/JUDGE_ELASTIC_CORES.json` may set
`{"research_cap_share": x}` (0 < x <= 0.75 only: the switch can lower the ceiling, never raise it
past the owner's cap) or `{"enabled": false}` (back to the fixed six, no push needed: the next
pass confines every judge pid to the reserved cores, so borrowed cores are given back, never
kept; a malformed switch reads OFF and does the same).

UNMEASURED IS A REAL ANSWER (L1.28a): no CPU sample or no memory reading means no borrowing --
the judge is confined back to the floor (a failed reading re-enumerates the judge pids by a cheap
census to do it; if even that fails the report says status UNMEASURED, shed_not_applied). No
reservation in force means no floor exists: affinity is left exactly as the sweep child set it.

    python desks/mt5/scripts/judge_elastic_cores.py            # measure + apply + report
    python desks/mt5/scripts/judge_elastic_cores.py --dry-run  # measure + report only
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from scripts import judge_priority as jp  # noqa: E402

SWITCH = DESK / "data" / "JUDGE_ELASTIC_CORES.json"
REPORT = DESK / "reports" / "JUDGE_ELASTIC_CORES.json"
UNMEASURED = jp.UNMEASURED

#: The owner's research cap (2026-11-25): research may hold at most this share of the box's cores.
RESEARCH_CAP_SHARE = 0.75
#: Cores always left for live beyond what live is measured to use, and the multiple on its use.
#: 1.5 is `judging_throughput.CPU_RESERVE_MULTIPLE`, the desk's existing live-reserve multiple.
LIVE_RESERVE_MIN_CORES = 2
LIVE_RESERVE_MULTIPLE = 1.5
#: Live busy at or above this many cores is a gateway pass / terminal burst: shed to the floor.
LIVE_SHED_CORES = 1.0
#: Free physical memory below max(this, share x total) sheds to the floor: live wins memory too.
MEM_RESERVE_MIN_MB = 8192.0
MEM_RESERVE_SHARE = 0.15
#: Borrowing grows by at most this many cores a pass; shedding is immediate.
BORROW_STEP = 2
CPU_SAMPLE_S = 1.0


def switch(path: Path | None = None) -> dict[str, Any]:
    """`{"enabled", "cap_share", "why"}`. Absent = on at the owner's cap; malformed = OFF."""
    p = Path(path or SWITCH)
    if not p.exists():
        return {"enabled": True, "cap_share": RESEARCH_CAP_SHARE,
                "why": f"{p.name} absent: on at the owner's {RESEARCH_CAP_SHARE:.0%} cap"}
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {"enabled": False, "cap_share": None, "why": f"{p.name} unreadable: fixed floor"}
    if not isinstance(doc, dict):
        return {"enabled": False, "cap_share": None, "why": f"{p.name} not an object: fixed floor"}
    if doc.get("enabled", True) is not True:
        return {"enabled": False, "cap_share": None, "why": f"{p.name} says enabled=false"}
    cap = doc.get("research_cap_share", RESEARCH_CAP_SHARE)
    if (not isinstance(cap, (int, float)) or isinstance(cap, bool)
            or not 0 < float(cap) <= RESEARCH_CAP_SHARE):
        return {"enabled": False, "cap_share": None,
                "why": f"{p.name} research_cap_share malformed or above the owner's cap"}
    return {"enabled": True, "cap_share": float(cap), "why": f"{p.name} present"}


def plan(*, n_cpus: int, floor_cpus: list[int], percpu_busy: list[float] | None,
         judge_cores: float | None, live_cores: float | None, other_cores: float | None,
         free_mb: float | None, total_mb: float | None, unreadable: int = 0,
         previous: int | None = None, cap_share: float = RESEARCH_CAP_SHARE) -> dict[str, Any]:
    """THE RULE (module docstring), pure. Returns workers_now, floor, ceiling, cpus and reason."""
    floor_n = len(floor_cpus)
    ceiling = max(floor_n, math.floor(cap_share * max(n_cpus, 0)))
    base = {"floor": floor_n, "ceiling": ceiling, "n_cpus": n_cpus}

    def _at_floor(reason: str, shed: bool) -> dict[str, Any]:
        return {**base, "workers_now": floor_n, "cpus": sorted(floor_cpus), "borrowed": 0,
                "shed": shed, "reason": reason}

    if not floor_n or n_cpus <= 0:
        return {**base, "workers_now": floor_n, "cpus": sorted(floor_cpus), "borrowed": 0,
                "shed": False, "reason": "no reservation in force: nothing to grow from"}
    missing = [k for k, v in (("cpu sample", percpu_busy), ("live busy", live_cores),
                              ("other busy", other_cores), ("free memory", free_mb),
                              ("total memory", total_mb)) if v is None]
    if missing:
        return _at_floor(f"UNMEASURED ({', '.join(missing)}): no borrowing", shed=True)
    assert percpu_busy is not None and live_cores is not None and other_cores is not None
    assert free_mb is not None and total_mb is not None
    if unreadable:
        return _at_floor(f"{unreadable} python/live row(s) unreadable: fail closed to the floor",
                         shed=True)
    if live_cores >= LIVE_SHED_CORES:
        return _at_floor(f"live busy {live_cores:.2f} cores >= {LIVE_SHED_CORES}: live wins, "
                         "shed to the floor", shed=True)
    mem_reserve = max(MEM_RESERVE_MIN_MB, MEM_RESERVE_SHARE * total_mb)
    if free_mb < mem_reserve:
        return _at_floor(f"free memory {free_mb:.0f}MB < reserve {mem_reserve:.0f}MB: live wins, "
                         "shed to the floor", shed=True)
    live_reserve = max(LIVE_RESERVE_MIN_CORES, math.ceil(LIVE_RESERVE_MULTIPLE * live_cores))
    spare = n_cpus - live_reserve - math.ceil(max(other_cores, 0.0) - 1e-9)
    want = max(floor_n, min(ceiling, spare))
    grown = False
    if previous is not None and want > previous:
        want, grown = min(want, max(previous, floor_n) + BORROW_STEP), True
    floor_set = set(floor_cpus)
    idle_first = sorted((c for c in range(n_cpus) if c not in floor_set),
                        key=lambda c: (percpu_busy[c] if c < len(percpu_busy) else 1.0, c))
    borrowed = idle_first[: max(0, want - floor_n)]
    cpus = sorted([*floor_cpus, *borrowed])
    return {**base, "workers_now": len(cpus), "cpus": cpus, "borrowed": len(borrowed),
            "shed": False, "live_reserve": live_reserve, "spare": spare,
            "mem_reserve_mb": round(mem_reserve, 1),
            "reason": (f"{len(borrowed)} idle core(s) borrowed: {n_cpus} cores - live reserve "
                       f"{live_reserve} - others {other_cores:.2f} busy = {spare} spare, "
                       "clamped to "
                       f"[{floor_n}, {ceiling}]" + (f", grown at most {BORROW_STEP}/pass"
                                                     if grown else ""))}


def _previous(path: Path | None = None) -> int | None:
    try:
        doc = json.loads(Path(path or REPORT).read_text("utf-8"))
        v = doc.get("workers_now")
        return int(v) if isinstance(v, int) and not isinstance(v, bool) else None
    except (OSError, ValueError, AttributeError):
        return None


def measure(sample_s: float = CPU_SAMPLE_S) -> dict[str, Any]:
    """One reading: per-core busy, busy cores per class, memory. psutil only; never raises."""
    out: dict[str, Any] = {"percpu_busy": None, "judge_cores": None, "live_cores": None,
                           "other_cores": None, "free_mb": None, "total_mb": None,
                           "unreadable": 0, "n_cpus": 0, "rows": []}
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        out["n_cpus"] = int(psutil.cpu_count() or 0)
        vm = psutil.virtual_memory()
        out["free_mb"] = round(float(vm.available) / 2**20, 1)
        out["total_mb"] = round(float(vm.total) / 2**20, 1)
        psutil.cpu_percent(None, percpu=True)
        rows = jp.classify(jp.snapshot(sample_s))
        out["percpu_busy"] = [round(float(x) / 100.0, 3)
                              for x in psutil.cpu_percent(None, percpu=True)]
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    sums = {"judge": 0.0, "live": 0.0, "other": 0.0}
    for r in rows:
        c = r.get("cpu_cores")
        if not isinstance(c, (int, float)):
            continue
        k = r.get("cls")
        sums["judge" if k == "judge" else "live" if k == "live" else "other"] += float(c)
    out.update({"judge_cores": round(sums["judge"], 2), "live_cores": round(sums["live"], 2),
                "other_cores": round(sums["other"], 2),
                "unreadable": sum(1 for r in rows if r.get("unreadable")
                                  and r.get("cls") in ("live", "judge", "miner")),
                "rows": rows})
    return out


def _confine_checked(row: dict[str, Any], cpus: list[int]) -> dict[str, Any]:
    """Set one judge pid's affinity, only if it is STILL the process the census saw."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        p = psutil.Process(int(row["pid"]))
        if row.get("create_time") is not None and abs(p.create_time() - row["create_time"]) > 1:
            return {"pid": row["pid"], "applied": False, "why": "pid reused"}
        if sorted(p.cpu_affinity()) == sorted(cpus):
            return {"pid": row["pid"], "applied": True, "unchanged": True}
        return {"pid": row["pid"], **jp.confine(int(row["pid"]), cpus, process=p)}
    except Exception as exc:
        return {"pid": row.get("pid"), "applied": False, "error": f"{type(exc).__name__}: {exc}"}


def _judge_rows(m: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """The judge pids to confine: the reading's own rows, or -- when the reading FAILED (audit
    HOLD 2026-11-25, defect 2) -- a fresh cheap census (`classify(snapshot(0))`, no CPU sample).
    Returns `(judge rows, census error or None)`. Never raises."""
    rows: Any = m.get("rows") or []
    if m.get("error"):
        try:
            rows = jp.classify(jp.snapshot(0.0))
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"
    return [r for r in rows if r.get("cls") == "judge" and r.get("pid") is not None], None


def run_pass(*, apply: bool = True, write: bool = True, reading: dict[str, Any] | None = None,
             now: datetime | None = None) -> dict[str, Any]:
    """Measure, plan, apply the affinity to every judge pid, publish. Never raises.

    AUDIT HOLD 2026-11-25, both defects fail CLOSED now:
      1. the switch OFF (enabled=false or malformed) while the reservation is in force CONFINES
         every judge pid back to the reserved cores -- a judge that borrowed up to the ceiling
         gives them back on the next pass, as the docstring promises;
      2. a failed measurement sheds to the floor and still finds the judge pids by a cheap
         census; if even that fails the report says UNMEASURED with `shed_not_applied`.
    """
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    sw = switch()
    m = reading if reading is not None else measure()
    n = int(m.get("n_cpus") or 0)
    res = jp.reserved_cores(n or None)
    workers_planned = os.environ.get("GAUNTLET_WORKERS") or UNMEASURED
    measure_error = m.get("error")
    floor_cpus = sorted(res.get("cpus") or [])
    target: list[int] | None = None   # the cpus every judge pid is set to, None = untouched

    def _floor(reason: str) -> dict[str, Any]:
        return {"floor": len(floor_cpus), "ceiling": len(floor_cpus),
                "workers_now": len(floor_cpus), "cpus": list(floor_cpus), "borrowed": 0,
                "shed": True, "reason": reason}

    if not res.get("enabled"):
        why = f"{sw['why']}; " if not sw["enabled"] else ""
        p = {**_floor(f"OFF -- {why}reservation not in force ({res.get('why')}): no floor to "
                      "confine to, affinity left untouched"), "shed": False}
        mode = "off"
    elif not sw["enabled"]:
        p = _floor(f"OFF -- {sw['why']}; every judge pid confined back to the reserved floor "
                   f"({len(floor_cpus)} cores)")
        mode, target = "off", list(floor_cpus)
    elif measure_error:
        p = _floor(f"UNMEASURED (measure failed: {measure_error}): shed to the floor")
        mode, target = ("apply" if apply else "dry-run"), list(floor_cpus)
    else:
        p = plan(n_cpus=n, floor_cpus=list(res["cpus"]), percpu_busy=m.get("percpu_busy"),
                 judge_cores=m.get("judge_cores"), live_cores=m.get("live_cores"),
                 other_cores=m.get("other_cores"), free_mb=m.get("free_mb"),
                 total_mb=m.get("total_mb"), unreadable=int(m.get("unreadable") or 0),
                 previous=_previous(), cap_share=float(sw["cap_share"]))
        mode, target = ("apply" if apply else "dry-run"), list(p["cpus"])
    applied: list[dict[str, Any]] = []
    census_error: str | None = None
    if apply and target is not None:
        judge_rows, census_error = _judge_rows(m)
        for r in judge_rows:
            applied.append(_confine_checked(r, target))
    status = UNMEASURED if (measure_error or census_error) else "MEASURED"
    # The floor was wanted but could not be reached: no reservation known while the reading
    # failed, or no judge pid could be enumerated. Said loudly, never silently "fine".
    shed_not_applied = bool(apply and ((target is not None and census_error)
                                       or (target is None and measure_error)))
    doc = {
        "at": at, "mode": mode, "switch": sw, "status": status,
        "shed_not_applied": shed_not_applied,
        "measure_error": measure_error, "census_error": census_error,
        "workers_now": p["workers_now"], "floor": p["floor"], "ceiling": p["ceiling"],
        "research_cap_share": sw.get("cap_share"), "cpus": p["cpus"],
        "borrowed": p.get("borrowed", 0), "shed": p.get("shed", False), "reason": p["reason"],
        "workers_planned": workers_planned,
        "measured": {k: m.get(k) for k in ("n_cpus", "judge_cores", "live_cores", "other_cores",
                                           "free_mb", "total_mb", "unreadable")},
        "applied": {"judge_pids": len(applied), "ok": sum(1 for a in applied if a.get("applied")),
                    "failed": [a for a in applied if not a.get("applied")][:20]},
        "rule": ("judge affinity = reserved floor + idle cores, up to floor(research_cap_share x "
                 "cores); shed to the floor at once on live load, memory pressure, an unreadable "
                 "row or any unmeasured input; affinity only -- nothing killed, no class raised, "
                 "no verdict touched"),
    }
    if write:
        try:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, REPORT)
        except OSError as exc:
            doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and report; change nothing")
    ap.add_argument("--no-write", action="store_true", help="print only")
    a = ap.parse_args(argv)
    doc = run_pass(apply=not a.dry_run, write=not a.no_write)
    print(json.dumps({k: v for k, v in doc.items() if k != "measured"}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
