"""COLLATERAL-BASIS SPREAD -- USDT-margined vs USDC-margined perps on the SAME venue.

WHY THIS ONE IS CLEAN. Every spread that failed today failed on MEASUREMENT, not mechanism:
  mSOL/SOL   539bps sd  -> non-synchronous CoinGecko legs
  CME basis   92bps sd  -> CME 23/5 vs Binance 24/7, 16:00CT vs 00:00UTC, rolling front-month
Both were artifacts of comparing things sampled at different moments.

This construction makes that impossible: BTCUSDT-perp and BTCUSDC-perp trade on the SAME exchange,
on the SAME underlying, with the SAME funding clock and the SAME timestamps. There is no roll, no
timezone, no venue gap. Any spread that survives is real by construction.

THE MECHANISM (a genuine structural constraint, not friction):
  The two contracts are collateralised in different stablecoins. A trader holding USDC cannot post
  it as USDT margin without converting -- paying the peg spread and taking conversion risk. So the
  cost of leverage can differ between the two books, and the difference persists because moving
  between them is not free. That is the same species of constraint as kimchi (you cannot move the
  capital freely), just smaller and inside one venue.

TESTS: (a) is the funding differential persistently non-zero, (b) does it mean-revert, (c) is it
WIDE ENOUGH to clear costs -- the gate that killed all four candidates this morning. With ETH-class
symbols now measured at 0.05-1.3bps pair-open, the cost bar here is far lower than the 8bps I used
earlier, which materially changes what counts as harvestable.

Free Binance endpoints. Stage-A, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/collateral_spread.json")
PAIRS = [("BTCUSDT", "BTCUSDC"), ("ETHUSDT", "ETHUSDC"), ("SOLUSDT", "SOLUSDC")]
COST_BPS = 2.0        # measured majors pair-open ~0.05-1.3bps; 2bps is a conservative round trip


def _get(u, t=30):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def funding(sym: str, n: int = 1000) -> dict[int, float]:
    try:
        d = _get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit={n}")
        return {int(x["fundingTime"]) // 3600000: float(x["fundingRate"]) for x in d}
    except Exception:
        return {}


def main() -> None:
    print("=== COLLATERAL-BASIS SPREAD (USDT-margined vs USDC-margined, SAME venue) ===")
    print("    same exchange, same underlying, same funding clock -> no sync artifact possible\n")
    res = []
    for a, b in PAIRS:
        fa, fb = funding(a), funding(b)
        common = sorted(set(fa) & set(fb))
        if len(common) < 100:
            print(f"  {a:<10} vs {b:<10} thin ({len(common)} common funding ticks)")
            continue
        # funding is per 8h; annualise for readability, but test the raw spread
        sa = np.array([fa[t] for t in common])
        sb = np.array([fb[t] for t in common])
        sp = (sa - sb) * 10000            # spread in bps per 8h period

        mean, sd = float(sp.mean()), float(sp.std())
        x0, x1 = sp[:-1] - sp.mean(), sp[1:] - sp.mean()
        beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
        hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
        p99, p50 = np.percentile(np.abs(sp), 99), np.percentile(np.abs(sp), 50)
        tail = float(p99 / p50) if p50 > 0 else float("inf")
        tradeable = float((np.abs(sp) > COST_BPS).mean())
        ann = mean * 3 * 365 / 100.0      # 3 funding periods/day, bps -> %

        wide = abs(mean) > COST_BPS or sd > COST_BPS * 2
        verdict = ("HARVESTABLE-CANDIDATE" if wide and tradeable > 0.3 and tail < 15
                   else "TOO TIGHT" if not wide
                   else "RARELY TRADEABLE" if tradeable <= 0.3 else "VIOLENT")
        print(f"  {a:<10} vs {b:<10} n={len(common):<5} mean {mean:+7.3f}bps/8h "
              f"({ann:+6.2f}%/yr) sd {sd:6.3f}  half-life {hl:5.1f}p  "
              f"|sp|>{COST_BPS}bps {tradeable*100:3.0f}%  -> {verdict}")
        res.append({"pair": f"{a}/{b}", "n": len(common), "mean_bps_8h": round(mean, 4),
                    "annualised_pct": round(ann, 3), "sd_bps": round(sd, 4),
                    "half_life_periods": round(hl, 2) if hl != float("inf") else None,
                    "tail": round(tail, 2), "frac_above_cost": round(tradeable, 3),
                    "verdict": verdict})

    cands = [r for r in res if r["verdict"] == "HARVESTABLE-CANDIDATE"]
    print(f"\n  HARVESTABLE: {len(cands)}/{len(res)}")
    print("  NOTE: cost bar here is 2bps, not the 8bps used this morning -- the measured cost")
    print("  model shows majors at 0.05-1.3bps pair-open, so the harvestable threshold is much")
    print("  lower on liquid names than on the micro-caps currently in the book.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "cost_bar_bps": COST_BPS, "results": res}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
