#!/usr/bin/env python3
"""NET-PROFIT OPTIMISER (principal 2026-08-01): every live strategy runs at its measured
net-profit maximum, not at a parameter somebody once guessed.

THE LAW BEHIND IT. L1.1 maximises E[log(W_T)] and L1.5 says nothing counts until it survives real
costs. A carry sleeve has free parameters -- how long to hold, how big to size, how patiently to
quote -- and each one has a NET optimum that is nowhere near its gross optimum, because funding
accrues in 8h steps while fees are paid per round trip. Holding one hour past a settlement earns a
full funding period for zero extra fee; closing one hour before it pays the fee and collects
nothing. Nobody had measured where that line falls on THIS desk's own fills.

WHY OWN FILLS AND NOT A MODEL (L1.11b endogenous execution intelligence): a fee schedule and a
funding curve give you a theoretical optimum for a frictionless book. The desk's 254 real closed
trades already contain its actual slippage, its actual fill quality, its actual basis drift and
its actual funding capture -- an Execution Reality Model no competitor has, because it is made of
our own order flow.

WHAT IT REPORTS, and refuses to report. Net PnL per hour held, bucketed by hold period, with the
funding/price/fee decomposition inside each bucket -- so a "better" bucket that is really just
lucky price drift on a delta-neutral book is visible rather than hidden. Buckets thinner than
MIN_TRADES are reported as UNDERPOWERED and never ranked: picking the best of a dozen noisy cells
is the garden of forking paths, and it is exactly how a desk talks itself into a worse parameter.

    python scripts/optimise_net_profit.py            # report
    python scripts/optimise_net_profit.py --json     # machine-readable for the cycle
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data/cashcarry_trades.json"
OUT = ROOT / "data/net_profit_optimum.json"

#: A bucket thinner than this is noise; it is reported but never ranked or recommended.
MIN_TRADES = 12
#: Funding settles every 8h on Binance perps -- the natural grid for a carry hold period.
FUNDING_PERIOD_H = 8.0
BUCKETS = [(0, 8), (8, 16), (16, 24), (24, 48), (48, 96), (96, 1e9)]


def _rows() -> list[dict]:
    try:
        raw = json.loads(TRADES.read_text("utf-8"))
    except Exception as e:
        raise SystemExit(f"cannot read {TRADES}: {e!r}") from e
    out = []
    for r in raw:
        h, n = r.get("held_hours"), r.get("net")
        if h is None or n is None:
            continue
        try:
            out.append({"h": float(h), "net": float(n),
                        "fund": float(r.get("est_funding") or 0.0),
                        "price": float(r.get("price_pnl") or 0.0),
                        "notional": float(r.get("notional") or 0.0),
                        "symbol": str(r.get("symbol", "?"))})
        except (TypeError, ValueError):
            continue
    return out


def main() -> None:
    rows = _rows()
    if not rows:
        raise SystemExit("no closed trades with held_hours -- nothing to optimise")

    report = []
    for lo, hi in BUCKETS:
        b = [r for r in rows if lo <= r["h"] < hi]
        if not b:
            continue
        net = [r["net"] for r in b]
        # per-hour so buckets of different length compare honestly
        per_h = [r["net"] / max(r["h"], 0.25) for r in b]
        fees = [r["net"] - r["fund"] - r["price"] for r in b]
        report.append({
            "bucket_h": f"{lo}-{'inf' if hi > 1e8 else int(hi)}",
            "n": len(b),
            "net_total": round(sum(net), 2),
            "net_mean": round(statistics.fmean(net), 4),
            "net_per_hour_mean": round(statistics.fmean(per_h), 5),
            "net_per_hour_median": round(statistics.median(per_h), 5),
            "funding_mean": round(statistics.fmean(r["fund"] for r in b), 4),
            "price_mean": round(statistics.fmean(r["price"] for r in b), 4),
            "implied_fee_mean": round(statistics.fmean(fees), 4),
            "win_rate": round(sum(1 for x in net if x > 0) / len(b), 3),
            "powered": len(b) >= MIN_TRADES,
        })

    ranked = [b for b in report if b["powered"]]
    ranked.sort(key=lambda b: b["net_per_hour_median"], reverse=True)

    print(f"NET-PROFIT OPTIMUM -- {len(rows)} closed trades, funding settles every "
          f"{FUNDING_PERIOD_H:.0f}h\n")
    print(f"  {'hold':<10} {'n':>4} {'net/h med':>11} {'net mean':>10} {'funding':>9} "
          f"{'price':>9} {'fee':>9} {'win':>6}")
    for b in report:
        flag = "" if b["powered"] else "   UNDERPOWERED (never ranked)"
        print(f"  {b['bucket_h']:<10} {b['n']:>4} {b['net_per_hour_median']:>11.5f} "
              f"{b['net_mean']:>10.3f} {b['funding_mean']:>9.3f} {b['price_mean']:>9.3f} "
              f"{b['implied_fee_mean']:>9.3f} {b['win_rate']:>6.1%}{flag}")

    verdict: dict[str, object]
    if not ranked:
        verdict = {"status": "UNDERPOWERED",
                   "detail": f"no hold bucket reaches {MIN_TRADES} trades -- the desk cannot yet "
                             "say which hold period pays best, and guessing from thin cells is "
                             "how a book talks itself into a worse parameter"}
        print(f"\n  VERDICT: UNDERPOWERED -- no bucket reaches {MIN_TRADES} trades.")
    else:
        best = ranked[0]
        worst = ranked[-1]
        verdict = {"status": "MEASURED", "best_bucket": best["bucket_h"],
                   "best_net_per_hour": best["net_per_hour_median"],
                   "worst_bucket": worst["bucket_h"],
                   "spread_per_hour": round(best["net_per_hour_median"]
                                            - worst["net_per_hour_median"], 5),
                   "n_powered_buckets": len(ranked)}
        print(f"\n  VERDICT: best NET/hour is the {best['bucket_h']}h hold "
              f"({best['net_per_hour_median']:+.5f}/h on n={best['n']}), worst is "
              f"{worst['bucket_h']}h ({worst['net_per_hour_median']:+.5f}/h).")
        print("  NOTE: on a delta-neutral book the price column should be ~0. A bucket that wins "
              "on PRICE is carrying directional exposure, not earning carry -- read the "
              "decomposition before moving any parameter.")

    OUT.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat(),
                               "n_trades": len(rows), "min_trades_to_rank": MIN_TRADES,
                               "buckets": report, "verdict": verdict}, indent=1), "utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    if "--json" in sys.argv:
        print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
