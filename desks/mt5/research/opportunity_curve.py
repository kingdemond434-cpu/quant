"""When capital actually makes money: the book's expected growth by hour and session, measured.

    M_t = max_h E[log W | S_t]

approximated, per session phase and per hour, from the evidence the desk already holds: every
shadow and live trade's R, bucketed by the phase it was ENTERED in, shrunk by k_state toward the
sleeve's unconditional mean exactly as the posterior would, and summed as a heat-weighted book.

WHAT IT IS FOR. Research should attack the hours where the book earns nothing, not the hours
where it already earns. The coverage map says which STATE buckets have no edge; this says which
CLOCK buckets have no edge, which is the coarser and more actionable form -- "the desk makes its
money 07:00-15:00 broker time and nothing from 17:00 to the roll" is an instruction the
prospector and the plumbing miner can act on directly. Dead phases are written to the deepening
queue as `dead_phase` tasks, keyed on this source, so a rerun replaces rather than accumulates.

DEAD IS NOT THE SAME AS UNMEASURED. The first version bucketed by HOUR and demanded MIN_N trades
per sleeve per hour; with 487 trades over 50 sleeves and 24 hours almost no cell reached it, and
seven of nine phases were reported dead when what was true was that nothing had been measured.
A phase is DEAD only when at least one sleeve reached the sample floor there and none is positive;
a phase where no sleeve reached the floor is UNMEASURED, which is a different instruction (trade
more there, or wait) and never a research target. Per-sleeve pooling is by PHASE, so the floor
is reachable; the per-hour map is kept for the picture, not for the verdict.

WHAT IT IS NOT. Not an allocator input. The allocator conditions on the session it is IN through
`state_r`; this is the retrospective map of all sessions at once, for research targeting.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = BASE / "reports" / "OPPORTUNITY_CURVE.json"
K_STATE = 40.0
MIN_N = 8
DEAD, ALIVE, UNMEASURED = "DEAD", "ALIVE", "UNMEASURED"


def _shrunk(rs: list[float], prior: float) -> float:
    n = len(rs)
    lam = n / (n + K_STATE)
    return lam * float(np.mean(rs)) + (1.0 - lam) * prior


def curve(trades, off: int | None) -> tuple[dict, dict]:
    """(by_hour, by_phase) from Trade rows with `.sleeve`, `.r`, `.when` (ISO)."""
    from research.session_phase import PHASES, phase_for_hour

    by_sleeve: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        by_sleeve[t.sleeve].append(t.r)
    mean = {k: float(np.mean(v)) for k, v in by_sleeve.items()}

    by_hour: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_phase_s: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in trades:
        try:
            h = datetime.fromisoformat(str(t.when)).hour
        except (TypeError, ValueError):
            continue
        stamp_h = (h + (off or 0)) % 24
        by_hour[stamp_h][t.sleeve].append(t.r)
        by_phase_s[phase_for_hour(stamp_h)][t.sleeve].append(t.r)

    hours = {}
    for h in range(24):
        rows = [(s, len(rs), _shrunk(rs, mean[s])) for s, rs in by_hour.get(h, {}).items()
                if len(rs) >= MIN_N]
        pos = [c for _, _, c in rows if c > 0]
        hours[h] = {"phase": phase_for_hour(h),
                    "n_trades": int(sum(len(v) for v in by_hour.get(h, {}).values())),
                    "n_sleeves_measured": len(rows), "n_sleeves_positive": len(pos),
                    "book_expectancy_r": round(float(sum(pos)), 4),
                    "best": (max(rows, key=lambda x: x[2])[0] if rows else None)}
    phases = {}
    for name, start, end in PHASES:
        per = by_phase_s.get(name, {})
        rows = [(s, len(rs), _shrunk(rs, mean[s])) for s, rs in per.items() if len(rs) >= MIN_N]
        rows.sort(key=lambda x: -x[2])
        pos = [c for _, _, c in rows if c > 0]
        n_tr = int(sum(len(v) for v in per.values()))
        verdict = (UNMEASURED if not rows else (ALIVE if pos else DEAD))
        phases[name] = {"hours": f"{start:02d}-{end:02d}", "n_trades": n_tr,
                        "n_sleeves_measured": len(rows), "n_sleeves_positive": len(pos),
                        "book_expectancy_r": round(float(sum(pos)), 4),
                        "best": ({"sleeve": rows[0][0], "n": rows[0][1],
                                  "shrunk_r": round(rows[0][2], 4)} if rows else None),
                        "measured": [{"sleeve": s, "n": n, "shrunk_r": round(c, 4)}
                                     for s, n, c in rows[:8]],
                        "verdict": verdict}
    return hours, phases


def instructions(phases: dict, clock: str) -> list[dict]:
    tasks = []
    for name, v in phases.items():
        if v["verdict"] != DEAD:
            continue
        tried = ", ".join(f"{m['sleeve']} {m['shrunk_r']:+.2f}R (n={m['n']})"
                          for m in v["measured"][:5])
        tasks.append({
            "source": "opportunity_curve", "kind": "dead_phase",
            "title": f"Book earns nothing in {name} ({v['hours']} {clock})",
            "description": (f"Session phase {name}, hours {v['hours']} on the {clock} clock: "
                            f"{v['n_trades']} realised trades, {v['n_sleeves_measured']} sleeves "
                            f"measured, none with positive shrunk expectancy. Measured: {tried}. "
                            "Propose a mechanism whose economic cause is specific to this phase "
                            "(who is forced to trade then, what is being rebalanced, which venue "
                            "opens or closes) -- not a re-parameterisation of what already loses "
                            "here."),
            "phase": name, "hours": v["hours"], "status": None,
            "consumer": "plumbing_miner / microstructure_miner / research brains",
        })
    return tasks


def run(write_queue: bool = True) -> dict:
    from research.session_phase import broker_utc_offset_h
    from research.state_admission_run import load_trades

    off, src = broker_utc_offset_h()
    trades = load_trades("shadow")
    gaps = {}
    if off is None:
        gaps["broker_clock"] = f"offset unknown ({src}); hours reported in UTC, not broker stamp"
    hours, phases = curve(trades, off)
    clock = "broker" if off is not None else "UTC"
    tasks = instructions(phases, clock)
    dead = [p for p, v in phases.items() if v["verdict"] == DEAD]
    unmeasured = [p for p, v in phases.items() if v["verdict"] == UNMEASURED]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "clock": src,
           "broker_utc_offset_h": off, "gaps": gaps, "n_trades": len(trades),
           "by_hour": {str(h): v for h, v in hours.items()}, "by_phase": phases,
           "dead_phases": dead, "unmeasured_phases": unmeasured,
           "rule": (f"DEAD = at least one sleeve with >= {MIN_N} trades in the phase and none "
                    "positive after shrinkage; UNMEASURED = no sleeve reached the floor and is "
                    "never a research target"),
           "instruction": [t["title"] for t in tasks]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    if write_queue and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="opportunity_curve")
        except Exception as exc:
            doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    doc["tasks"] = tasks
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    d = run(write_queue=not a.no_queue)
    print(f"OPPORTUNITY CURVE  clock={d['clock']}  {d['n_trades']} trades")
    for p, v in d["by_phase"].items():
        print(f"  {p:18s} {v['hours']}  n={v['n_trades']:4d}  measured={v['n_sleeves_measured']:2d}  "
              f"book_exp={v['book_expectancy_r']:+.3f}R  positive={v['n_sleeves_positive']}  "
              f"{v['verdict']}")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"  dead={d['dead_phases']}  unmeasured={d['unmeasured_phases']}  "
          f"tasks={len(d['tasks'])}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
