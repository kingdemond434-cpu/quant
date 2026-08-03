#!/usr/bin/env python3
"""CALIBRATE MARKET IMPACT ON THE DESK'S OWN L2 TAPE -- and report per-symbol capacity.

WHY THIS EXISTS, AND IT IS A CORRECTION. Execution modelling was rated "near ceiling, blocked on
book depth nobody has recorded". The desk has 8.2GB of self-recorded 15-second L2 depth across
three venues, and `asymmetry_ledger.py` grades it the single EXCLUSIVE asset it owns. The data was
never missing; it was unused. `libs/signal_engine/market_impact_forecaster.py` carried literature
coefficients for a generic instrument while the actual book for the actual pairs sat on disk.

WHAT IT PRODUCES:
  k, the square-root impact coefficient, FITTED on the desk's own books rather than borrowed.
  CAPACITY per symbol -- the largest order whose slippage stays inside the impact budget. This is
  the number that sizes a strategy, and `libs/portfolio/capacity_allocation.py` binds weights to
  it as a hard constraint. An alpha with a 30bp edge and 5bp of capacity at the size it needs is
  not an alpha.
  The r2 of the fit, so a bad one is visible rather than a coefficient being used because it was
  produced.

IT REFUSES TO SYNTHESISE A BOOK. A calibration run on generated depth measures the generator, and
its coefficient would enter the cost model wearing the same vocabulary as a real one -- then size
every strategy on the desk.

Read-only over data/moat. Writes one artifact. No network, no keys, no order paths.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.execution.book_walk import (  # noqa: E402
    book_from_row,
    calibrate_impact,
    capacity_at_impact,
    walk_book,
)

MOAT = ROOT / "data/moat"
REPORT = ROOT / "data/impact_calibration.json"

#: Files read per run. Budgeted work every cycle beats heroic work never -- the moat miner's rule.
FILE_BUDGET = 200


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _tape(venue: str | None = None) -> list[Path]:
    if not MOAT.exists():
        return []
    out: list[Path] = []
    for vdir in sorted(p for p in MOAT.iterdir() if p.is_dir()):
        if venue and vdir.name != venue:
            continue
        for sym in sorted(p for p in vdir.iterdir() if p.is_dir()):
            out.extend(sorted(sym.glob("*.jsonl.gz")))
    return out


def _books_by_symbol(files: list[Path]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for f in files:
        sym = f"{f.parent.parent.name}:{f.parent.name}"
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    parsed = book_from_row(row)
                    if parsed is not None:
                        out[sym].append(parsed)
        except OSError:
            continue
    return dict(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-bps", type=float, default=5.0,
                    help="impact budget defining capacity, in bp. Default 5bp.")
    ap.add_argument("--files", type=int, default=FILE_BUDGET)
    a = ap.parse_args()

    files = _tape()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not files:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO TAPE",
            "reason": (f"{_rel(MOAT)} absent or empty. data/ is gitignored, so this is expected in "
                       "a fresh checkout and a REAL blocker on the VPS -- the recorders write it."),
            "note": ("books are NOT synthesised: a coefficient fitted on generated depth measures "
                     "the generator, then sizes every strategy on the desk"),
        }, indent=1), "utf-8")
        print(f"impact-calibration: NO TAPE under {_rel(MOAT)} -- recorders are the blocker")
        return 0

    by_sym = _books_by_symbol(files[-a.files:])
    rows = []
    for sym, books in sorted(by_sym.items()):
        asks = [b[1] for b in books]
        if len(asks) < 8:
            rows.append({"symbol": sym, "snapshots": len(asks), "state": "TOO FEW SNAPSHOTS",
                         "why": "a coefficient fitted on fewer than 8 books is noise"})
            continue
        # Probe sizes spanning the visible book so the fit covers real participation rates.
        med_depth = float(np.median([float(x.size.sum()) for x in asks]))
        sizes = [med_depth * f for f in np.linspace(0.02, 0.9, len(asks))]
        fit = calibrate_impact(asks, sizes)
        caps = [capacity_at_impact(x, max_bps=a.max_bps) for x in asks]
        touch_slip = [walk_book(x, min(1e-9 + x.size[0], x.size.sum()), is_buy=True).slippage_bps
                      for x in asks]
        rows.append({
            "symbol": sym, "snapshots": len(asks),
            "impact_k": fit["k"], "fit_r2": fit["r2"],
            "median_visible_depth": med_depth,
            "capacity_at_budget": float(np.median(caps)),
            "capacity_p10": float(np.percentile(caps, 10)),
            "touch_slippage_bps": float(np.median(touch_slip)),
        })

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "files_read": len(files[-a.files:]), "files_on_disk": len(files),
        "impact_budget_bps": a.max_bps,
        "symbols": rows,
        "note": ("k is FITTED on the desk's own books, not borrowed from a paper about large-cap "
                 "equities. Capacity is the p50 and p10 across snapshots because the number that "
                 "matters is what the book carries on a BAD day, not an average one -- sizing to "
                 "the median means being wrong exactly when liquidity is gone."),
        "authority": ("NONE. Produces a cost input. Nothing here promotes, sizes or trades -- "
                      "libs/portfolio/capacity_allocation.py is what binds weights to it."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"impact-calibration: {len(rows)} symbol(s) from {len(files[-a.files:])}/{len(files)} "
          f"files | budget {a.max_bps}bp")
    for r in rows:
        if "impact_k" in r:
            print(f"  {r['symbol']:<24} k={r['impact_k']:>8.2f} r2={r['fit_r2']:>5.2f} "
                  f"cap(p50)={r['capacity_at_budget']:>10.3f} cap(p10)={r['capacity_p10']:>10.3f}")
        else:
            print(f"  {r['symbol']:<24} {r['state']} ({r['snapshots']} snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
