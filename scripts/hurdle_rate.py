"""HURDLE RATE -- the benchmark the desk has never had.

THE GAP: nothing in this desk has ever asked "is this better than doing nothing?". Today's own
data answered it accidentally and badly: the 8,026-trader cohort averaged -1.14% while BTC was
-0.15%, i.e. active leveraged trading UNDERPERFORMED holding. The desk itself is -4% on total
capital over 25 days. Neither number was ever compared to an alternative, so neither could be
judged.

A strategy is not "working" because it is positive. It is working when it beats what you could
have had for free, net of everything. Three benchmarks, hardest first:

  1. RISK-FREE   -- US 3-month T-bill (^IRX). Capital has a price; ignoring it flatters everything.
  2. BUY-AND-HOLD BTC -- the zero-effort crypto alternative.
  3. 50/50 BTC+cash   -- the honest risk-matched comparison for a market-neutral book, since a
                        delta-neutral carry should NOT be compared to full BTC beta.

Also computes the CARRY-SPECIFIC hurdle: funding harvested must exceed fee drag, or the sleeve is
structurally unprofitable regardless of direction.

Free (Yahoo + Binance + the desk's own state). Read-only. Run from repo root, daily.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/hurdle_rate.json"


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode())


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def main() -> None:
    port = (load(ROOT / "web/portfolio.json") or {}).get("deployed") or {}
    cc = load(ROOT / "web/cashcarry_live.json") or {}
    days = float(port.get("days_live") or 0)
    ret = float(port.get("return_pct") or 0) / 100.0
    if days <= 0:
        print("no live history yet")
        return

    # --- benchmarks over the SAME window ---------------------------------------------------
    try:
        irx = _get("https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX"
                   "?interval=1d&range=1mo")["chart"]["result"][0]
        rf_annual = float([c for c in irx["indicators"]["quote"][0]["close"] if c][-1]) / 100.0
    except Exception:
        rf_annual = 0.045
    rf = rf_annual * (days / 365.0)

    try:
        kl = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=400")
        n = min(int(days) + 1, len(kl))
        btc = float(kl[-1][4]) / float(kl[-n][1]) - 1.0
    except Exception:
        btc = float("nan")
    half = btc / 2 + rf / 2

    ann = (1 + ret) ** (365 / days) - 1 if days > 0 else 0.0
    print("=== HURDLE RATE -- is this better than doing nothing? ===")
    print(f"    window: {days:.1f} days live\n")
    print(f"  {'DESK':<26} {ret*100:+8.2f}%   ({ann*100:+.1f}%/yr annualised)")
    print(f"  {'risk-free (T-bill)':<26} {rf*100:+8.2f}%   ({rf_annual*100:.2f}%/yr)")
    print(f"  {'buy-and-hold BTC':<26} {btc*100:+8.2f}%")
    print(f"  {'50/50 BTC + cash':<26} {half*100:+8.2f}%   <- risk-matched for a neutral book")

    beats = {"risk_free": ret > rf, "btc_hold": ret > btc, "half_btc": ret > half}
    print()
    for k, v in beats.items():
        print(f"  beats {k:<12} {'YES' if v else 'NO'}   "
              f"(excess {(ret - {'risk_free': rf, 'btc_hold': btc, 'half_btc': half}[k])*100:+.2f}%)")

    # --- carry-specific hurdle: does funding actually exceed fee drag? ----------------------
    fund = float(cc.get("funding_harvested") or 0)
    net = float(cc.get("net_pnl") or 0)
    legs = float(cc.get("spot_leg_pnl") or 0) + float(cc.get("perp_leg_pnl") or 0)
    costs = fund + legs - net          # residual = what neither funding nor legs explain
    print("\n  === CARRY DECOMPOSITION (the structural question) ===")
    print(f"    funding harvested  {fund:+10.2f}")
    print(f"    legs (spot+perp)   {legs:+10.2f}   <- ~0 confirms delta-neutrality holds")
    print(f"    net P&L            {net:+10.2f}")
    print(f"    implied costs      {costs:+10.2f}   <- residual")
    if fund > 0:
        ratio = abs(costs) / fund
        print(f"    cost / funding     {ratio:8.2f}x   "
              f"{'STRUCTURALLY UNPROFITABLE -- costs exceed the harvest' if ratio > 1 else 'harvest covers costs'}")

    verdict = ("PASSES" if all(beats.values()) else
               "FAILS -- does not beat " + ", ".join(k for k, v in beats.items() if not v))
    print(f"\n  HURDLE VERDICT: {verdict}")
    print("  A strategy is not 'working' because it is positive. It works when it beats what you")
    print("  could have had for free, net of everything. Nothing should get capital until it does.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "days": days, "desk_return": ret, "annualised": ann,
                               "risk_free": rf, "btc_hold": btc, "half_btc": half,
                               "beats": beats, "funding": fund, "legs": legs,
                               "implied_costs": costs, "verdict": verdict}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
