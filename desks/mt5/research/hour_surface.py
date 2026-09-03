#!/usr/bin/env python3
"""WHEN the book earns, measured by UTC hour, and what an edge at each hour would be worth.

    "Hour-of-day as a first-class state ... the allocator solves on a daily R matrix, so it
     structurally cannot express 'Asia is better than NY right now'."     -- the principal

THE HOUR IS A SLEEVE ATTRIBUTE, NOT A PER-TRADE VARIABLE, and that is what makes this tractable.
Every sleeve on this desk fires in one window -- a session bracket at its signal hour, a family
at its fill hour -- so "which hours does the book cover" is answerable exactly, from the trades
themselves, without modelling an intraday process the daily-R matrix cannot carry.

MEASURED FROM TRADE TIMESTAMPS, NEVER FROM THE SLEEVE NAME. A name says which window a sleeve was
BUILT for; the timestamps say when it actually filled, and those differ whenever a resting
trigger survives into the next hour. `portfolio_gap.py` maps coverage from names because it asks
about the CERTIFICATE library; this asks about realised behaviour and must not inherit that.

WHAT IT IS FOR. Two consumers, both of which the desk already has:

  * the allocator's opportunity gap -- an hour with no funded sleeve is not "0% growth", it is
    UNCOVERED, and the difference decides whether the answer is to size up or to go and find an
    edge there (`portfolio_gap.research_requests`);
  * the research direction -- `expected_r_per_hour` ranks where a NEW edge is worth most, which
    is a different question from where the current book already earns.

ADVISORY. It moves no capital and gates nothing; it writes reports/hour_surface.json.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "hour_surface.json"
ALLOC = BASE / "reports" / "pf_allocation.json"

#: UTC hour bands, matching portfolio_gap so the two artifacts can be read side by side.
BANDS = ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24))


def band_of(hour: int) -> str:
    for lo, hi in BANDS:
        if lo <= hour < hi:
            return f"{lo:02d}-{hi:02d}"
    return "??"


def sleeve_hours() -> dict[str, dict[int, list[float]]]:
    """sleeve -> {utc_hour: [R multiples]} from the replayed trades themselves."""
    from research.portfolio_projection import build_sleeves, h18_survivor_sleeves

    sleeves = build_sleeves()
    h18, _excluded = h18_survivor_sleeves()
    sleeves += h18
    out: dict[str, dict[int, list[float]]] = {}
    for s in sleeves:
        hours = s.get("hours")
        if hours is None:
            # `build_sleeves` keeps dates; when it has not been asked for hours the entry times
            # are gone and this sleeve is UNMEASURED for this purpose rather than hour zero.
            continue
        per: dict[int, list[float]] = defaultdict(list)
        for h, r in zip(hours, s["r"], strict=False):
            per[int(h)].append(float(r))
        out[str(s["name"])] = dict(per)
    return out


def build() -> dict[str, Any]:
    by_sleeve = sleeve_hours()
    book: dict[str, float] = {}
    marginal: dict[str, float] = {}
    try:
        art = json.loads(ALLOC.read_text("utf-8"))
        book = {str(k): float(v) for k, v in (art.get("book") or {}).items()}
        marginal = {str(k): float(v) for k, v in (art.get("marginal_delta_elog") or {}).items()}
    except (OSError, ValueError):
        pass

    per_hour: dict[int, list[float]] = defaultdict(list)
    heat_hour: dict[int, float] = defaultdict(float)
    sleeves_hour: dict[int, set[str]] = defaultdict(set)
    for name, hours in by_sleeve.items():
        total = sum(len(v) for v in hours.values()) or 1
        for h, rs in hours.items():
            per_hour[h].extend(rs)
            sleeves_hour[h].add(name)
            # A sleeve's heat is attributed to its hours in proportion to where it actually
            # traded, so a sleeve straddling two hours is not counted twice.
            heat_hour[h] += book.get(name, 0.0) * (len(rs) / total)

    hours_out = []
    for h in range(24):
        rs = per_hour.get(h, [])
        hours_out.append({
            "hour_utc": h, "band": band_of(h),
            "trades": len(rs),
            "expected_r": round(statistics.fmean(rs), 5) if rs else None,
            "total_r": round(sum(rs), 2) if rs else 0.0,
            "funded_heat": round(heat_hour.get(h, 0.0), 6),
            "sleeves": len(sleeves_hour.get(h, ())),
            # UNCOVERED IS NOT ZERO GROWTH. An hour nobody trades has no expectancy to report,
            # and reporting 0.0 there would let a dark hour average into the book's rate as
            # though it had been tried and found flat (L1.28a).
            "status": ("uncovered" if not rs else
                       ("unfunded" if heat_hour.get(h, 0.0) <= 1e-9 else "funded")),
        })

    bands_out: dict[str, dict[str, Any]] = {}
    for lo, hi in BANDS:
        key = f"{lo:02d}-{hi:02d}"
        rows = [x for x in hours_out if x["band"] == key]
        rs = [r for x in rows for r in per_hour.get(int(x["hour_utc"]), [])]
        bands_out[key] = {
            "trades": sum(x["trades"] for x in rows),
            "expected_r": round(statistics.fmean(rs), 5) if rs else None,
            "funded_heat": round(sum(x["funded_heat"] for x in rows), 6),
            "sleeves": len({s for x in rows for s in sleeves_hour.get(int(x["hour_utc"]), ())}),
        }

    covered = [x for x in hours_out if x["trades"]]
    dark = [x["hour_utc"] for x in hours_out if not x["trades"]]
    unfunded = [x["hour_utc"] for x in hours_out if x["trades"] and x["status"] == "unfunded"]
    best = sorted((x for x in covered if x["expected_r"] is not None),
                  key=lambda x: -float(x["expected_r"]))[:5]

    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "hours": hours_out,
        "bands": bands_out,
        "covered_hours": len(covered),
        "dark_hours_utc": dark,
        "traded_but_unfunded_hours_utc": unfunded,
        "best_hours": [{"hour_utc": x["hour_utc"], "expected_r": x["expected_r"],
                        "trades": x["trades"]} for x in best],
        "marginal_available": bool(marginal),
        "note": ("Hours are measured from trade timestamps, not sleeve names. An UNCOVERED hour "
                 "has no expectancy and is not 0.0: the desk has not tried it, which is a "
                 "research request, not a flat result."),
    }


def main() -> int:
    doc = build()
    if not doc["covered_hours"]:
        print("hour surface UNMEASURED: no sleeve carried entry hours. build_sleeves must keep "
              "them (see sleeve_hours) -- reporting nothing rather than a book that trades at "
              "hour zero.")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return 2
    print(f"{'hr':>3} {'band':<7}{'trades':>8}{'expR':>10}{'heat':>9}{'sleeves':>9}  status")
    for x in doc["hours"]:
        e = "     --" if x["expected_r"] is None else f"{x['expected_r']:+10.4f}"
        print(f"{x['hour_utc']:3d} {x['band']:<7}{x['trades']:8d}{e}"
              f"{x['funded_heat'] * 100:8.2f}%{x['sleeves']:9d}  {x['status']}")
    print(f"\ndark hours (never traded): {doc['dark_hours_utc'] or 'none'}")
    print(f"traded but unfunded      : {doc['traded_but_unfunded_hours_utc'] or 'none'}")
    print("best hours by expectancy :",
          ", ".join(f"{b['hour_utc']:02d}Z {b['expected_r']:+.4f}" for b in doc["best_hours"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT.relative_to(BASE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
