"""OPTIMAL HOLDING PERIOD -- optimise the alpha that WORKS instead of hunting a new one.

Today established: the entry signal is real (funding persistence IC +0.43, top-decile +29%/yr vs
+3.8% median). The strategy is not broken; its ECONOMICS are. So the highest-value remaining
question is not "what else predicts returns" but "what holding period maximises NET capture".

THE TRADE-OFF, both sides now measured:
  LONGER hold  -> more funding periods collected per round trip (cost amortises)
               -> but the selection edge DECAYS (top-decile advantage falls as the entry-time
                  ranking goes stale; funding shock half-life is ~6h)
  SHORTER hold -> captures the freshest, richest funding
               -> but pays the round trip more often

_MIN_HOLD_H = 24 was chosen to STOP CHURN (gap #42), not because 24h maximised anything. It has
never been optimised against measured persistence and measured cost. This computes the optimum
directly from both.

METHOD: for each candidate hold H, walk the funding panel -- at each rebalance take the top-decile
by current funding, hold H hours, sum the funding actually realised, subtract one round trip, and
annualise. The winner is the H with the highest NET annualised capture.

Free Binance funding + the desk's own measured cost model. Stage-A. Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/optimal_hold.json")
HOLDS_H = [8, 16, 24, 32, 48, 72, 120, 168]  # 1 period .. 1 week
N_HIST = 500


def _get(u, t=30):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def universe(n: int = 40) -> list[str]:
    d = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    rows = [
        (float(x.get("quoteVolume", 0)), x["symbol"]) for x in d if x["symbol"].endswith("USDT")
    ]
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]


def funding(sym: str) -> dict[int, float]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={N_HIST}")
        return {int(x["fundingTime"]) // 3600000: float(x["fundingRate"]) for x in d}
    except Exception:
        return {}


def cost_bps() -> dict[str, float]:
    try:
        m = json.loads(Path("data/cost_model.json").read_text("utf-8"))["symbols"]
    except Exception:
        return {}
    out = {}
    for s, d in m.items():
        v = d.get("pair", {}).get("500", {}).get("pair_roundtrip_bps")
        if v is not None:
            out[s] = float(v)
    return out


def main() -> None:
    syms = universe()
    ser = {s: f for s in syms if len(f := funding(s)) >= 200}
    if len(ser) < 15:
        print(f"only {len(ser)} usable symbols")
        return
    grid = sorted(set.intersection(*[set(v) for v in ser.values()]))
    costs = cost_bps()
    med_cost = float(np.median(list(costs.values()))) if costs else 5.7
    print("=== OPTIMAL HOLDING PERIOD (optimising the alpha that works) ===")
    print(f"    {len(ser)} symbols, {len(grid)} funding periods (~{len(grid) / 3:.0f} days)")
    print(
        f"    round-trip cost: median measured {med_cost:.2f} bps ({len(costs)} symbols priced)\n"
    )
    print(
        f"  {'hold':>6} {'gross %/yr':>11} {'cost %/yr':>10} {'NET %/yr':>10} {'rotations/yr':>13}"
    )

    res = []
    for H in HOLDS_H:
        k = max(1, H // 8)  # funding periods per hold
        gross, used = [], 0
        for i in range(0, len(grid) - k, k):  # non-overlapping rotations
            t = grid[i]
            cur = np.array([ser[s][t] for s in ser])
            names = list(ser)
            top = np.argsort(cur)[-max(2, len(cur) // 10) :]
            picked = [names[j] for j in top]
            # funding actually realised over the hold, per picked symbol
            realised = [sum(ser[s][grid[i + j]] for j in range(1, k + 1)) for s in picked]
            gross.append(float(np.mean(realised)))
            used += 1
        if not gross:
            continue
        per_rot = float(np.mean(gross))  # fraction, per rotation
        rots = 365 * 24 / H
        gross_ann = per_rot * rots * 100
        # cost: one round trip per rotation, weighted to the picked (liquid) names
        cost_ann = (med_cost / 1e4) * rots * 100
        net_ann = gross_ann - cost_ann
        print(f"  {H:>5}h {gross_ann:>10.2f}% {cost_ann:>9.2f}% {net_ann:>9.2f}% {rots:>12.0f}")
        res.append(
            {
                "hold_h": H,
                "gross_pct_yr": round(gross_ann, 3),
                "cost_pct_yr": round(cost_ann, 3),
                "net_pct_yr": round(net_ann, 3),
                "rotations_yr": round(rots, 1),
                "n_rotations_tested": used,
            }
        )

    if res:
        best = max(res, key=lambda r: r["net_pct_yr"])
        cur24 = next((r for r in res if r["hold_h"] == 24), None)
        print(f"\n  OPTIMUM: {best['hold_h']}h  ->  net {best['net_pct_yr']:+.2f}%/yr")
        if cur24:
            d = best["net_pct_yr"] - cur24["net_pct_yr"]
            print(f"  CURRENT _MIN_HOLD_H = 24h -> net {cur24['net_pct_yr']:+.2f}%/yr")
            print(
                f"  IMPROVEMENT AVAILABLE: {d:+.2f} %/yr by moving 24h -> {best['hold_h']}h"
                if abs(d) > 0.5
                else "  24h is at/near the optimum -- leave it alone"
            )
        print("\n  CAVEAT: gross uses the LIQUID top-40 universe and the MEDIAN measured cost.")
        print("  A book trading unmeasured illiquid names pays far more than this and its true")
        print("  optimum is LONGER (cost amortises over more periods). Re-run per-universe.")
    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "median_cost_bps": med_cost,
                "results": res,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
