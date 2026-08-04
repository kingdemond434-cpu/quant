#!/usr/bin/env python3
"""ALLOCATE ACROSS FAMILIES, BOUND BY WHAT THE BOOK CAN CARRY -- capacity_allocation's caller.

WHY IT EXISTS. `libs/portfolio/capacity_allocation.py` was built and left with no production
caller, found by a mechanical sweep for library modules nothing imports. That is the desk's own
"built but never runs" class, and an allocator nobody calls allocates nothing.

WHAT IT JOINS UP. Two numbers that were being produced and never met:

  CAPACITY, from `scripts/calibrate_impact.py` walking the desk's own recorded L2 depth. It is the
  largest position the book absorbs inside the impact budget, per symbol.
  RETURN STREAMS, per strategy. Effective breadth is MEASURED across them rather than assumed from
  the fact that they carry different names -- two families that turn out to be the same trade in
  different vocabulary are one bet, and a sleeve allocator handed their separate Sharpes doubles
  the position and reports diversification.

Allocation then runs in Sharpe space and capacity binds HARD on top. A strategy the desk cannot
execute cannot be held, and unallocated capital is reported rather than quietly absorbed.

Read-only. Writes one artifact. No keys, no order paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.portfolio.capacity_allocation import allocate_with_capacity  # noqa: E402

STREAMS = ROOT / "data/strategy_streams.csv"
IMPACT = ROOT / "data/impact_calibration.json"
REPORT = ROOT / "data/allocation.json"

#: Book size in base units, used to turn an absolute capacity into a fraction of the book.
DEFAULT_BOOK = 10.0


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_capacity(path: Path, book: float) -> dict[str, float]:
    """symbol -> capacity as a FRACTION of the book, from the impact calibration.

    Uses the p10 rather than the median: sizing to the typical book means being wrong exactly when
    liquidity is gone, which is exactly when the position needs to come off.
    """
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for row in d.get("symbols") or []:
        cap = row.get("capacity_p10")
        if isinstance(cap, int | float) and book > 0:
            out[str(row.get("symbol"))] = float(min(cap / book, 1.0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--streams", default=None, help="CSV, one column of returns per strategy")
    ap.add_argument("--book", type=float, default=DEFAULT_BOOK)
    ap.add_argument("--gross", type=float, default=1.0)
    a = ap.parse_args()

    src = Path(a.streams) if a.streams else STREAMS
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO STREAMS",
            "reason": (f"{_rel(src)} absent. Per-strategy return streams come from the backtest "
                       "organs; data/ is gitignored so this is expected in a fresh checkout."),
            "note": ("streams are NOT synthesised: an allocation computed on a generator would "
                     "size real capital against imaginary correlations"),
        }, indent=1), "utf-8")
        print(f"allocation: NO STREAMS at {_rel(src)}")
        return 0

    streams = pd.read_csv(src)
    streams = streams.select_dtypes("number").dropna(how="all", axis=1)
    if streams.shape[1] < 2:
        print(f"allocation: need >=2 strategies, got {streams.shape[1]}")
        return 0

    sharpes = {c: float(streams[c].mean() / streams[c].std(ddof=1))
               if streams[c].std(ddof=1) > 0 else 0.0 for c in streams.columns}
    cap = load_capacity(IMPACT, a.book)
    # A strategy with no measured capacity is NOT assumed unlimited -- that is how an unexecutable
    # book gets built. Absent a measurement it is given zero and reported, so the gap is visible.
    missing = [c for c in streams.columns if c not in cap]
    capacity = {c: cap.get(c, 0.0) for c in streams.columns}

    res = allocate_with_capacity(streams, sharpes, capacity, gross_target=a.gross)
    out = {
        "ts": datetime.now(tz=UTC).isoformat(), "source": _rel(src),
        "book": a.book, "weights": res.as_dict(),
        "capacity_frac": dict(zip(res.names, (float(x) for x in res.capacity_frac), strict=True)),
        "capped": list(res.capped),
        "unmeasured_capacity": missing,
        "n_eff": res.n_eff, "mean_corr": res.mean_corr, "ir_multiple": res.ir_multiple,
        "gross": res.gross, "unallocated": res.unallocated,
        "note": res.note + (
            " Strategies with no measured capacity are given ZERO, never unlimited: run "
            "scripts/calibrate_impact.py so the book can carry them."),
        "authority": "NONE. Produces target weights; sends no orders.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"allocation: {len(res.names)} strategies | measured N_eff {res.n_eff:.2f} "
          f"(IR x{res.ir_multiple:.2f}) | gross {res.gross:.2f} | "
          f"unallocated {res.unallocated:.2f}")
    for n, w in sorted(res.as_dict().items(), key=lambda kv: -kv[1]):
        flag = "  CAPPED" if n in res.capped else ""
        print(f"  {n:<24} w={w:.4f}  cap={capacity[n]:.4f}{flag}")
    if missing:
        print(f"  NO MEASURED CAPACITY (weighted 0): {', '.join(missing)} -- run "
              "scripts/calibrate_impact.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
