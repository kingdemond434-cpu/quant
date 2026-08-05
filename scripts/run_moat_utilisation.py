#!/usr/bin/env python3
"""MOAT UTILISATION -- measure how much of the un-replicable tape has ever been READ.

WHY THIS EXISTS. The desk records ~10 GB of L2 order-book depth across ~28,361 hourly partitions
on the VPS, and that tape is the ONE asset here that cannot be bought, re-fetched or replicated --
it accrues only in calendar time, so an unrecorded hour is unbuyable at any price. Every organ
touching it measures something else: `moat_audit.py` scores book QUALITY, `mine_moat.py` and
`screen_moat.py` track their own coverage GRIDS, `data_registry.py` scores span and moat. Nothing
measured what fraction of the recorded bytes, symbols, venues, hours or depth LEVELS has ever
reached a screen. An asset you record and do not read is a cost centre wearing an asset's name.

WHAT IT PRINTS AND WRITES (data/moat_utilisation.json):
  1. COVERAGE OF RECORDING, both directions -- wanted-but-never-recorded (a hole that widens every
     hour and never backfills) and recorded-but-never-read (spend with no return).
  2. CONTINUITY -- recorded hours vs elapsed hours per (venue, symbol), with the largest hole and
     hours-since-last. Gaps, not endpoints: today's registry pass caught a feed claiming 2,356
     elapsed days while holding 38, because one 2,318-day hole sat between the extremes.
  3. UTILISATION -- read fractions of symbol-hours, symbol-days, symbols and bytes, bracketed
     between what is PROVEN read and what could plausibly have been read, plus unread symbols,
     unread date ranges and unread depth levels.
  4. HUNTING YIELD -- distinct hypotheses ever screened on the tape, in how many census mechanism
     classes, and the best OOS. Reported as a MEASURED NEGATIVE: the two moat "survivors" landed
     at OOS 0.103/0.098, the same noise ceiling the public-data campaign reached.
  5. A RANKED NEXT-ACTION LIST -- the largest unread slice and the mechanism class it could test.

RUNS ANYWHERE, LIES NOWHERE. On the recording box it measures. In a checkout the tape is absent and
every utilisation figure is NOT-READABLE-HERE with the exact missing paths named -- never 0%, never
simulated. "0% utilised" is a measurement and it is damning; "cannot measure utilisation here" is
the absence of one, and conflating them is the precise defect this desk keeps finding in its own
instruments. Exits 0 either way, because a cadenced organ that hard-fails on an absent input gets
switched off, and a switched-off organ measures nothing forever.

Read-only. No network, no keys, no tape parsing of its own -- partition inventory is filesystem
metadata and every content question is answered by the existing audited readers. Zero authority:
promotes nothing, blocks nothing, changes no gate.

    python scripts/run_moat_utilisation.py [--root .] [--out data/moat_utilisation.json] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.moat_utilisation import (  # noqa: E402
    MEASURED,
    NOT_READABLE_HERE,
    build_report,
)

OUT = ROOT / "data/moat_utilisation.json"


def _fmt_pct(v: Any) -> str:
    """A percentage, or the reason there is not one. NEVER a zero standing in for an absence."""
    return f"{float(v):.4f}%" if isinstance(v, int | float) else str(v or NOT_READABLE_HERE)


def _fmt_bytes(v: Any) -> str:
    if not isinstance(v, int | float):
        return NOT_READABLE_HERE
    n = float(v)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            return f"{n:,.1f}{unit}"
        n /= 1024.0
    return f"{n:,.1f}TB"


def render(rep: dict[str, Any]) -> None:
    tape = rep["tape"]
    util = rep["utilisation"]
    cov = rep["coverage_of_recording"]
    cont = rep["continuity"]
    yield_ = rep["hunting_yield"]

    print("=== MOAT UTILISATION -- what fraction of the un-replicable tape has been READ ===")
    print(f"    status {rep['status']}   tape {tape['status']}")
    if tape["missing_paths"]:
        for p in tape["missing_paths"]:
            print(f"    MISSING {p}")
        print("    the recorders are the blocker; no tape is synthesised and no figure is "
              "invented")
    else:
        print(f"    {tape['partitions']:,} partitions | {_fmt_bytes(tape['bytes_partitions'])} "
              f"| {tape['symbols']} symbol-streams across {', '.join(tape['venues'] or [])}")

    print("\n--- 1. COVERAGE OF RECORDING (both directions)")
    for d in cov["recorders"]:
        print(f"  {d['script']:<34} venue={d['venue']:<6} declares {d['n_declared']:>3} symbols "
              f"| depth limit {d['depth_levels_requested']}")
    for src in cov["universe_sources"]:
        print(f"  {src['name']:<20} {src['kind']:<18} {src['status']:<20} "
              f"{src['n_symbols']:>4} symbols  ({src['path']})")
    for key, names in cov["holes"].items():
        if names:
            print(f"  HOLE {key:<26} {len(names):>4}: {', '.join(map(str, names[:14]))}"
                  + (" ..." if len(names) > 14 else ""))

    print("\n--- 2. CONTINUITY (gaps, not endpoints)")
    if cont["status"] != MEASURED:
        print(f"  {cont['status']} -- no partitions to measure continuity over")
    else:
        big = cont["largest_gap"]
        print(f"  {'venue/symbol':<24}{'rec_h':>8}{'elap_h':>8}{'cov%':>8}{'gaps':>6}"
              f"{'max_gap_h':>11}{'stale_h':>9}")
        for s in cont["streams"][:15]:
            print(f"  {s['venue'] + '/' + s['symbol']:<24}{s['recorded_hours']:>8}"
                  f"{s['elapsed_hours']:>8}{s['coverage_pct'] or 0:>8.2f}{s['n_gaps'] or 0:>6}"
                  f"{s['largest_gap_hours'] or 0:>11}{s['hours_since_last'] or 0:>9}")
        if big is not None:
            print(f"  LARGEST HOLE: {big['venue']}/{big['symbol']} "
                  f"{big['largest_gap_hours']}h from {big['largest_gap_from']} to "
                  f"{big['largest_gap_to']}")

    print("\n--- 3. UTILISATION")
    print(f"  status {util['status']}")
    print(f"  symbol-hours read   {_fmt_pct(util['symbol_hours_read_pct'])}"
          f"   (upper bound {_fmt_pct(util['symbol_hours_read_pct_upper_bound'])})")
    print(f"  bytes read          {_fmt_pct(util['bytes_read_pct'])}"
          f"   (upper bound {_fmt_pct(util['bytes_read_pct_upper_bound'])})")
    print(f"  symbols read        {_fmt_pct(util['symbols_read_pct'])}")
    if util["status"] != MEASURED:
        print(f"  ^ {util['status']} IS NOT 0%. Utilisation was not measured on this box.")
    for d in util["depth_levels"]:
        if d["unread_levels"]:
            print(f"  UNREAD DEPTH: {d['venue']} records {d['recorded_levels']} levels, deepest "
                  f"consumer reads {d['consumed_levels']} -> {d['unread_levels']} level(s) never "
                  "read")
    blind = util["tape_openers_without_consumption_record"]
    if blind:
        print(f"  TAPE OPENERS THAT RECORD NOTHING THEY READ ({len(blind)}): {', '.join(blind)}")
    doc = util["documented_reference"]
    if doc.get("status") == "DOCUMENTED-NOT-MEASURED":
        print(f"  DOCUMENTED (not measured here) -- {doc['arithmetic']}")
        print(f"    -> {doc['scored_fraction_of_tape_pct_upper_bound']}% of the tape scored, "
              f"upper bound. {doc['source']}")

    print("\n--- 4. HUNTING YIELD")
    print(f"  status {yield_['status']} | tape-testable census classes "
          f"{yield_['n_tape_testable_classes']}: "
          f"{', '.join(c['class_id'] for c in yield_['tape_testable_classes'])}")
    print(f"  hypotheses screened on tape {yield_['n_hypotheses']} in "
          f"{yield_['n_mechanism_classes_occupied']} class(es) | best OOS "
          f"{yield_['best_oos_sharpe']}")
    print(f"  READING: {yield_['reading'][:220]}")

    print("\n--- 5. RANKED NEXT ACTIONS (largest unread slice first)")
    for a in rep["next_actions"]:
        hrs = a["unread_symbol_hours"]
        print(f"  {a['rank']:>2}. [{a['mechanism_class']}] {a['action']}")
        print(f"      {a['slice']}"
              + (f"  ({hrs:,} unread symbol-hours, {_fmt_bytes(a['unread_bytes'])})"
                 if hrs is not None else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="repo root to measure (default: this checkout)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--json", action="store_true", help="print the artifact instead of the table")
    a = ap.parse_args(argv)

    rep = build_report(Path(a.root))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        render(rep)
    print(f"\nwrote {out}")
    # ALWAYS 0. A missing tape is the EXPECTED state in a checkout and a real blocker on the box;
    # both are reported in the artifact's status. Exiting non-zero here would make a cron line red
    # every night on every non-recording box, and a chronically red line gets disabled -- which is
    # how an instrument stops measuring the thing it was built to measure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
