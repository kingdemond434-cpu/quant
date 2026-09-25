"""Citadel-style adapter (REBUILT, numpy only) -- the published capability is treating MARKET
IMPACT as a research object rather than a nuisance. The adapter measures the impact surface this
desk actually has: the bundle's spread points by hour turned into a cost in basis points of
price, per symbol and per hour, with the realised range beside it. The cost surface is a
representation; no size is implied or produced."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_citadel"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    rows: list[dict[str, Any]] = []
    trials = 0
    for f in bundle.frames("H1"):
        row = bundle.costs.get(f.symbol)
        if row is None:
            continue
        c = np.asarray(f.close, dtype=float)
        px = float(np.nanmedian(c)) if c.size else float("nan")
        tick = float(row.tick_size) or 0.0
        hours = np.array([int(t[11:13]) if len(t) >= 13 else -1 for t in f.time])
        r = np.abs(f.log_returns())
        by_hour: list[dict[str, Any]] = []
        for hh in sorted({int(h) for h in hours if h >= 0}):
            trials += 1
            m = hours[:-1] == hh
            spread = float(row.spread_pts_p50_by_hour.get(str(hh),
                                                          row.pooled_median_spread_pts))
            cost_bps = (spread * tick / px * 1e4) if (px and tick and np.isfinite(px)) else None
            by_hour.append({"hour_utc": hh, "spread_pts": spread, "cost_bps": cost_bps,
                            "median_abs_return_bps": float(np.nanmedian(r[m]) * 1e4)
                            if m.any() else None, "n_bars": int(m.sum())})
        rows.append({"symbol": f.symbol, "median_price": None if not np.isfinite(px) else px,
                     "tick_size": tick, "pooled_spread_pts": row.pooled_median_spread_pts,
                     "by_hour": by_hour})
    if not rows:
        return A.unmeasured(SYSTEM, bundle, "the bundle carried no cost rows to measure")
    return A.packet(
        SYSTEM, bundle, trials=trials,
        representations=[{
            "kind": "impact_surface", "system": SYSTEM, "symbols": rows,
            "representation": ("the cost of crossing, in basis points of price, hour by hour, "
                               "beside the move that hour actually delivers -- impact as a "
                               "research object, never a size")}],
        note=f"{trials} (symbol, hour) impact cells")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
