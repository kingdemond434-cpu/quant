"""CME-vs-OFFSHORE BASIS -- the best remaining structural-spread candidate.

WHY THIS ONE. Today's refined criterion for a survivable spread: width >~50bps AND a HARD physical
constraint AND a free daily series. Pegs (1-15bps) and liquid-staking discounts (10-30bps) failed
on WIDTH because their constraints are SOFT -- redemption is annoying, exit queues are days.

CME is different: US regulated institutions LEGALLY CANNOT trade offshore perps. That is not
friction, it is a licence boundary -- the same class of constraint as Korean capital controls,
which is the only class that has ever survived on this desk (kimchi, ~142bps std).

CONSTRUCTION:
    cme_basis      = CME front-month future / Binance spot - 1     (regulated venue)
    offshore_basis = Binance perp mark      / Binance spot - 1     (offshore venue)
    SPREAD         = cme_basis - offshore_basis                    (the segmentation premium)
Both legs are BTC at the same timestamp, so a directional move cancels. What remains is purely the
price of being allowed to trade where you are allowed to trade.

TEST (spread test, not a forecast test): persistent non-zero level? mean-reverting (half-life)?
bounded? AND -- the gate that killed all four candidates this morning -- WIDE ENOUGH TO PAY COSTS.

Free: Yahoo BTC=F (CME front-month) + Binance klines. Stage-A, zero promotion authority.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/cme_basis_screen.json")
ROUND_TRIP_BPS = 8.0        # ~2 legs x ~4bps: the bar a spread must clear to be harvestable


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode())


def yahoo(sym: str, rng: str = "2y") -> dict[str, float]:
    d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
             f"?interval=1d&range={rng}")
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]["close"]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(r["timestamp"], q, strict=False) if c}


def binance(sym: str, base: str, n: int = 730) -> dict[str, float]:
    rows = _get(f"{base}?symbol={sym}&interval=1d&limit={n}")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    print("=== CME vs OFFSHORE BASIS -- regulatory segmentation spread ===")
    print("    constraint: US institutions legally CANNOT trade offshore perps (licence, not friction)\n")
    cme = yahoo("BTC=F")
    spot = binance("BTCUSDT", "https://api.binance.com/api/v3/klines")
    perp = binance("BTCUSDT", "https://fapi.binance.com/fapi/v1/klines")
    dates = sorted(set(cme) & set(spot) & set(perp))
    print(f"  aligned days: {len(dates)}  ({dates[0]} .. {dates[-1]})" if dates else "  no overlap")
    if len(dates) < 120:
        print("  insufficient overlap")
        return

    cb = np.array([cme[d] / spot[d] - 1.0 for d in dates])          # regulated basis
    ob = np.array([perp[d] / spot[d] - 1.0 for d in dates])         # offshore basis
    sp = cb - ob                                                    # segmentation premium

    for nm, x in (("CME basis", cb), ("offshore basis", ob), ("SPREAD (cme-offshore)", sp)):
        print(f"  {nm:<24} mean {x.mean()*10000:+8.1f}bps   sd {x.std()*10000:7.1f}bps   "
              f"range {x.min()*10000:+.0f}..{x.max()*10000:+.0f}")

    # mean-reversion half-life on the spread
    x0, x1 = sp[:-1] - sp.mean(), sp[1:] - sp.mean()
    beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
    hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
    p99, p50 = np.percentile(np.abs(sp), 99), np.percentile(np.abs(sp), 50)
    tail = float(p99 / p50) if p50 > 0 else float("inf")
    sd_bps = float(sp.std() * 10000)
    # how often is the spread actually wide enough to pay for a round trip?
    tradeable = float((np.abs(sp) * 10000 > ROUND_TRIP_BPS).mean())

    print(f"\n  half-life {hl:.1f}d | tail {tail:.1f}x | sd {sd_bps:.1f}bps")
    print(f"  fraction of days |spread| > {ROUND_TRIP_BPS:.0f}bps round-trip cost: "
          f"{tradeable*100:.0f}%")

    wide = sd_bps > 50
    reverts = hl < 30
    bounded = tail < 12
    verdict = ("HARVESTABLE-CANDIDATE" if (wide and reverts and bounded and tradeable > 0.5)
               else "TOO TIGHT (fails the >50bps width bar)" if not wide
               else "DRIFTS (no reversion)" if not reverts
               else "VIOLENT (unbounded)" if not bounded
               else "RARELY TRADEABLE (spread < costs most days)")
    print(f"\n  VERDICT: {verdict}")
    print(f"    width>50bps {wide} | reverts<30d {reverts} | bounded {bounded} | "
          f"tradeable>50% {tradeable > 0.5}")
    if wide:
        print(f"\n  NOTE: at {sd_bps:.0f}bps sd this is {sd_bps/5.4:.0f}x the USDC peg spread and "
              f"{'comparable to' if sd_bps > 100 else 'below'} kimchi (~142bps).")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(dates),
                               "cme_basis_bps": round(float(cb.mean() * 10000), 2),
                               "offshore_basis_bps": round(float(ob.mean() * 10000), 2),
                               "spread_mean_bps": round(float(sp.mean() * 10000), 2),
                               "spread_sd_bps": round(sd_bps, 2),
                               "half_life_d": round(hl, 2) if hl != float("inf") else None,
                               "tail_ratio": round(tail, 2),
                               "frac_days_above_cost": round(tradeable, 3),
                               "verdict": verdict}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  Stage-A only. A candidate still needs net-of-cost capture and a forward clock.")


if __name__ == "__main__":
    main()
