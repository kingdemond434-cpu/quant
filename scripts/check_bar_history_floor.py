#!/usr/bin/env python3
"""THE BARS RATCHET TOO. A symbol's H1 history may never silently collapse.

    python scripts/check_bar_history_floor.py [--repair]

WHY THIS EXISTS, MEASURED 2026-09-04. `check_universe_floor.py` was written days ago because
universe.json went from 251 symbols to a 23-symbol stump and nothing noticed until the gauntlet
had swept a tenth of the desk's universe for hours. That guard now ratchets the REGISTRY.

Nothing ratchets the BARS. Measured on this tree:

    AUDCAD   53,864 rows   2,246 days   2018-01-02 -> 2026-08-28
    AUDUSD   53,864 rows   2,246 days   2018-01-02 -> 2026-08-28
    ...
    AUDNZD      479 rows      20 days   2026-08-03 -> 2026-08-28

Twenty-three symbols carry eight years. AUDNZD carries twenty days -- one per cent of its peers --
and every organ that reads it reported success. The certificate
`AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY` claims 179 days and cannot be replayed
at all: the cell needs sixty signals at the window hour and the stump yields two. The gauntlet
that certified it saw a series this file no longer holds.

THIS IS THE REGISTRY STUMP IN A SECOND PLACE, and it fails the same way for the same reason: a
truncated artifact is indistinguishable from a healthy one to anything that only asks whether the
file exists and parses. FRESHNESS IS THE WRONG QUESTION -- the stump's mtime is NEWER than the
good copy it replaced. COUNT IS THE RIGHT QUESTION, and it ratchets.

WHAT IT DOES. Keeps a per-symbol high-water mark of row count and distinct-day span. A drop past
TOLERANCE_FRAC is reported by name with both numbers. It does not delete, rewrite or refetch
anything: the bars live on the trading box and only that host can refill them. `--repair` is
therefore NOT offered -- what it would repair is not here, and a guard that pretends otherwise is
worse than one that reports honestly.

PEER COMPARISON IS THE SECOND SIGNAL, and it catches the first stump a symbol ever suffers -- one
with no high-water history to fall from. A symbol holding under PEER_FRAC of the median day-span
of its own universe is reported even on the first run, because twenty days beside two thousand is
not a short history, it is a broken file.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BARS = ROOT / "desks" / "mt5" / "data" / "universe"
KEEP = ROOT / "data" / "bar_history_high_water.json"
RECORD = ROOT / "docs" / "research" / "BAR_HISTORY_FLOOR.json"

#: Real history shrinks only by delisting or a broker changing its archive depth. 5% matches the
#: registry guard's tolerance for the same reason: below it is churn, above it is an event.
TOLERANCE_FRAC = 0.05
#: A symbol under this fraction of its universe's MEDIAN day-span is a stump even with no history
#: to compare against. 0.25 is deliberately loose -- a genuinely young listing can be short, and
#: this must fire on 1%, not on 30%.
PEER_FRAC = 0.25


def _measure() -> dict[str, dict[str, int]]:
    """Rows and distinct days per symbol. Unreadable files are reported, never skipped."""
    try:
        import pandas as pd
    except ImportError:
        print("pandas unavailable -- cannot measure bar history", file=sys.stderr)
        return {}
    out: dict[str, dict[str, int]] = {}
    for path in sorted(BARS.glob("*_H1.parquet")):
        sym = path.name.replace("_H1.parquet", "")
        try:
            df = pd.read_parquet(path)
            idx = pd.to_datetime(df.index)
            out[sym] = {"rows": len(df), "days": int(idx.normalize().nunique())}
        except Exception as exc:
            out[sym] = {"rows": -1, "days": -1, "error": f"{type(exc).__name__}: {exc}"[:120]}
    return out


def _load(path: Path) -> dict[str, Any]:
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def evaluate(now: dict[str, dict[str, int]],
             high_water: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
    """Breaches, and the high-water mark to persist. Pure, so the tests can drive it."""
    days = [v["days"] for v in now.values() if v.get("days", -1) > 0]
    median_days = statistics.median(days) if days else 0
    breaches: list[dict] = []
    keep = dict(high_water)

    for sym, cur in sorted(now.items()):
        if cur.get("rows", -1) < 0:
            breaches.append({"symbol": sym, "kind": "UNREADABLE", "why": cur.get("error", "")})
            continue
        prev = high_water.get(sym) or {}
        prev_days, prev_rows = int(prev.get("days", 0)), int(prev.get("rows", 0))

        if prev_days and cur["days"] < prev_days * (1.0 - TOLERANCE_FRAC):
            breaches.append({"symbol": sym, "kind": "COLLAPSED", "days_now": cur["days"],
                             "days_high_water": prev_days, "rows_now": cur["rows"],
                             "rows_high_water": prev_rows})
        elif median_days and cur["days"] < median_days * PEER_FRAC:
            # First-run stump: no history to fall from, but it is still obviously broken.
            breaches.append({"symbol": sym, "kind": "STUMP_VS_PEERS", "days_now": cur["days"],
                             "peer_median_days": int(median_days), "rows_now": cur["rows"]})

        # THE MARK ONLY EVER RISES. Recording a collapsed value as the new high water would let a
        # stump become the standard on its second run -- the ratchet would hold the door open.
        keep[sym] = {"days": max(prev_days, cur["days"]), "rows": max(prev_rows, cur["rows"])}
    return breaches, keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true",
                    help="do not update the high-water file")
    args = ap.parse_args()

    now = _measure()
    if not now:
        print("bar-history floor: no H1 parquets found -- UNMEASURED, not a pass")
        return 0
    breaches, keep = evaluate(now, _load(KEEP))

    if not args.report_only:
        KEEP.parent.mkdir(parents=True, exist_ok=True)
        KEEP.write_text(json.dumps(keep, indent=1, sort_keys=True), encoding="utf-8")
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(
        {"symbols": len(now), "breaches": breaches, "measured": now}, indent=1, sort_keys=True),
        encoding="utf-8")

    for b in breaches:
        print(f"BAR-HISTORY BREACH {b['kind']}: {b['symbol']} "
              + " ".join(f"{k}={v}" for k, v in b.items() if k not in ("symbol", "kind")))
    print(f"bar-history floor: {len(now)} symbol(s), {len(breaches)} breach(es) -> {RECORD.name}")
    # A breach is REPORTED, not fatal: the bars live on the trading box and no action here can
    # refill them. Exiting non-zero would make a red that nothing on this host can ever clear,
    # which is how a real fence stops being read (L1.43).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
