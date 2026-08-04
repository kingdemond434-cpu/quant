"""STRUCTURAL SPREAD SCREEN -- hunting more kimchi-class edges.

THE PATTERN THAT SURVIVES ON THIS DESK: every candidate that lived is a SPREAD, not a forecast.
Cash-and-carry (spot vs perp), kimchi (KRW venue vs global, gated by capital controls), cny
(same, gated by CN controls). Every FORECAST died -- attention, dev momentum, trader skill,
order flow, reflexivity.

So the search is for spreads where something PHYSICALLY prevents arbitrage from closing the gap.
Not "this looks mispriced" -- "this cannot be closed because of a queue, a licence, a delay."

CANDIDATES (each with its named constraint):
  1. LIQUID-STAKING DISCOUNT (stETH/ETH, mSOL/SOL)
     Constraint: the validator EXIT QUEUE. Unstaking takes days-to-weeks, so the derivative can
     trade below the underlying and no one can instantly arbitrage it. This is the closest
     structural analog to kimchi on the desk -- a hard physical delay, not a sentiment gap.
  2. STABLECOIN PEG SPREAD (USDC/USDT, FDUSD/USDT, DAI/USDT)
     Constraint: REDEMPTION FRICTION -- minimum sizes, KYC, banking hours, issuer discretion.
     Retail cannot redeem at par, so the peg gap persists.
  3. DEFI-vs-CEFI DOLLAR RATE (Aave USDC supply APY vs perp funding)
     Constraint: SYSTEM SEGMENTATION -- different collateral regimes, smart-contract risk,
     no common margin. Two prices for the same thing (cost of dollar leverage) that cannot be
     netted against each other.

THE TEST IS NOT "does it predict price". For a HARVESTABLE spread the questions are:
  (a) is the level persistently non-zero?  (is there anything to capture)
  (b) does it MEAN-REVERT?                 (half-life -- can you exit, or does it drift forever)
  (c) is it BOUNDED?                       (does it blow out, i.e. is the constraint ever violent)
A spread that is wide and mean-reverting with a named constraint is a carry candidate. A spread
that random-walks is just another price.

Free public endpoints. Stage-A, zero promotion authority. Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

OUT = Path("data/structural_spreads.json")


def _get(u, t=35):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def binance_daily(sym: str, n: int = 400) -> dict[str, float]:
    try:
        rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit={n}")
        return {
            datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows
        }
    except Exception:
        return {}


def coingecko_ratio(num: str, den: str, days: int = 365) -> dict[str, float]:
    """Daily close ratio of two assets from CoinGecko market_chart (free, no key)."""
    out = {}
    series = {}
    for cid in (num, den):
        d = _get(
            f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
            f"?vs_currency=usd&days={days}&interval=daily"
        )
        series[cid] = {
            datetime.fromtimestamp(p[0] / 1000, tz=UTC).date().isoformat(): float(p[1])
            for p in d.get("prices", [])
        }
    for k in set(series[num]) & set(series[den]):
        if series[den][k]:
            out[k] = series[num][k] / series[den][k]
    return out


def analyse(name: str, spread: dict[str, float], constraint: str, centre: float = 0.0) -> dict:
    """(a) persistence of level, (b) mean-reversion half-life, (c) boundedness."""
    dates = sorted(spread)
    if len(dates) < 90:
        print(f"{name:<26} thin ({len(dates)}d)")
        return {"name": name, "verdict": "THIN", "n": len(dates)}
    x = np.array([spread[d] for d in dates]) - centre
    mean, sd = float(x.mean()), float(x.std())
    # AR(1) on deviations -> mean-reversion half-life
    x0, x1 = x[:-1] - x.mean(), x[1:] - x.mean()
    beta = float((x0 @ x1) / (x0 @ x0)) if (x0 @ x0) > 0 else 1.0
    hl = float(-np.log(2) / np.log(abs(beta))) if 0 < abs(beta) < 1 else float("inf")
    # boundedness: how fat is the tail vs the body
    p99, p50 = float(np.percentile(np.abs(x), 99)), float(np.percentile(np.abs(x), 50))
    tail = p99 / p50 if p50 > 0 else float("inf")
    frac_nonzero = float((np.abs(x) > sd * 0.25).mean())

    harvestable = (abs(mean) > sd * 0.25 or frac_nonzero > 0.5) and hl < 30 and tail < 12
    verdict = (
        "HARVESTABLE-CANDIDATE"
        if harvestable
        else "DRIFTS (no reversion)"
        if hl >= 30
        else "VIOLENT (unbounded tail)"
        if tail >= 12
        else "TOO TIGHT (nothing to capture)"
    )
    print(
        f"{name:<26} n={len(dates):<4} mean {mean * 100:+7.3f}%  sd {sd * 100:6.3f}%  "
        f"half-life {hl:6.1f}d  tail {tail:5.1f}x  -> {verdict}"
    )
    return {
        "name": name,
        "constraint": constraint,
        "n": len(dates),
        "mean_pct": round(mean * 100, 4),
        "sd_pct": round(sd * 100, 4),
        "ar1_beta": round(beta, 4),
        "half_life_days": round(hl, 2) if hl != float("inf") else None,
        "tail_ratio": round(tail, 2),
        "verdict": verdict,
    }


def main() -> None:
    print("=== STRUCTURAL SPREAD SCREEN (spreads survive; forecasts died) ===")
    print("    test: persistent level? mean-reverting? bounded?  NOT 'does it predict price'\n")
    res = []

    # --- 2. STABLECOIN PEG SPREADS (redemption friction) --------------------------------
    for sym, label in (
        ("USDCUSDT", "peg USDC/USDT"),
        ("FDUSDUSDT", "peg FDUSD/USDT"),
        ("DAIUSDT", "peg DAI/USDT"),
    ):
        s = binance_daily(sym)
        if s:
            res.append(
                analyse(
                    label,
                    {k: v - 1.0 for k, v in s.items()},
                    "redemption friction: min sizes, KYC, banking hours",
                )
            )
        else:
            print(f"{label:<26} DATA-BLOCKED")

    # --- 1. LIQUID-STAKING DISCOUNT (validator exit queue) ------------------------------
    for num, den, label in (
        ("staked-ether", "ethereum", "LSD stETH/ETH"),
        ("msol", "solana", "LSD mSOL/SOL"),
    ):
        try:
            r = coingecko_ratio(num, den)
        except Exception as e:
            print(f"{label:<26} DATA-BLOCKED ({type(e).__name__})")
            continue
        if r:
            base = 1.0 if num == "staked-ether" else float(np.median(list(r.values())))
            res.append(
                analyse(
                    label,
                    {k: v - base for k, v in r.items()},
                    "validator exit queue: unstaking takes days-weeks",
                )
            )

    Path(OUT).write_text(
        json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "results": res}, indent=1), "utf-8"
    )
    cands = [r for r in res if r.get("verdict") == "HARVESTABLE-CANDIDATE"]
    print(f"\n  HARVESTABLE CANDIDATES: {len(cands)}/{len(res)}")
    for c in cands:
        print(f"    {c['name']}  (constraint: {c['constraint']})")
    print("\n  A candidate is NOT an edge -- it means the spread is wide, reverts, and is bounded.")
    print("  Net-of-cost capture and a forward clock still decide. Stage-A only.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
