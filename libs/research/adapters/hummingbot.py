"""Hummingbot adapter (REBUILT, numpy only) -- the market-making question asked of the data this
desk actually has: at which HOUR does the bar's realised range pay for the spread it must cross?
The adapter joins the bundle's own cost surface (spread points by hour) to the hourly realised
range and reports the range-to-cost ratio by hour. No inventory model, no quoting, no execution:
a spread_state hypothesis with the hours named."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "hummingbot"
CAPABILITY_FAMILY = "microstructure"
LICENCE_EXPECTED = "Apache-2.0"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 120]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 120 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        row = bundle.costs.get(f.symbol)
        if row is None or not np.isfinite(row.pooled_median_spread_pts):
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": "no cost row for this symbol in the bundle"})
            continue
        tick = float(row.tick_size) or 0.0
        h = np.asarray(f.high, dtype=float)
        lo = np.asarray(f.low, dtype=float)
        hours = np.array([int(t[11:13]) if len(t) >= 13 else -1 for t in f.time])
        rng_pts = (h - lo) / tick if tick > 0 else (h - lo)
        profile: list[dict[str, Any]] = []
        for hh in range(24):
            m = hours == hh
            if not m.any():
                continue
            trials += 1
            spread = float(row.spread_pts_p50_by_hour.get(str(hh),
                                                          row.pooled_median_spread_pts))
            med = float(np.nanmedian(rng_pts[m]))
            profile.append({"hour_utc": hh, "n_bars": int(m.sum()), "median_range_pts": med,
                            "spread_pts": spread,
                            "range_to_cost": (med / spread) if spread > 0 else None})
        measured = [p for p in profile if p["range_to_cost"] is not None]
        if not measured:
            continue
        reps.append({"kind": "hourly_range_to_cost", "symbol": f.symbol, "profile": profile,
                     "tick_size": tick,
                     "representation": ("the bar range each hour offers against the spread that "
                                        "hour charges -- the market maker's own ratio")})
        best = max(measured, key=lambda p: float(p["range_to_cost"]))
        worst = min(measured, key=lambda p: float(p["range_to_cost"]))
        cands.append(A.candidate(
            "spread_state", [f.symbol],
            f"{f.symbol}: hour {best['hour_utc']:02d} UTC offers {best['range_to_cost']:.2f}x "
            f"its spread in median bar range against {worst['range_to_cost']:.2f}x at hour "
            f"{worst['hour_utc']:02d} -- a cost-state hypothesis about when this instrument is "
            f"worth touching",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"best_hour": best["hour_utc"], "best_ratio": best["range_to_cost"],
                      "worst_hour": worst["hour_utc"], "worst_ratio": worst["range_to_cost"],
                      "method": "hourly median range over the bundle's own spread surface"}))
    if not cands and not reps:
        return A.unmeasured(SYSTEM, bundle, "the bundle carried no cost surface to join")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} (symbol, hour) cost-to-range cells")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
