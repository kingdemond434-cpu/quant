#!/usr/bin/env python3
"""LONG-ONLY SPOT MOMENTUM -- screen it, size it, and publish what a spot account can hold.

WHY THIS EXISTS AND WHAT IT IS NOT. The principal's account is Irish spot-only: EEA retail cannot
access crypto derivatives under MiCA, so cash-and-carry is untradeable (two legs by definition, and
the short leg cannot be opened) and `xsec_price_mom` is untradeable for the same reason -- it is a
DOLLAR-NEUTRAL book that shorts the bottom quantile.

This is the long leg, run as its own strategy under its own name. IT INHERITS NO NUMBER from
`xsec_price_mom`: not the 0.82 Sharpe, not the dashboard row, not the label. That figure was
measured on a book with a short in it and does not describe a book without one.

**THE RAW SHARPE OF A LONG-ONLY CRYPTO BOOK IS NOT ITS EDGE.** It earns in a rising tape whether or
not its selection has skill, so the number this script leads with is the EXCESS over equal-weight
buy-and-hold of the same universe, with the raw figure printed beside it and never instead of it.
Beta is published for the same reason: the short leg was what removed market exposure, and anyone
sizing this like the neutral book it came from would be sizing a completely different risk.

**PRINCIPAL EXCEPTION, RECORDED HERE RATHER THAN ASSUMED.** The principal has authorised deploying
this without the pre-registered forward clock, as an explicit one-off. That is their call and it is
logged in the artifact so nobody later mistakes it for a candidate that cleared Stage B. Every
figure it publishes is IN-SAMPLE, and the script says so in its own output rather than letting a
reader assume otherwise.

    python scripts/run_spot_momentum.py --equity 200 --min-notional 10
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.spot_momentum import (
    DEFAULT_BAND,
    DEFAULT_Q,
    benchmark_returns,
    evaluate,
    spot_long_only_returns,
)
from libs.research.vol_target import gross_exposure

_OUT = Path("data/spot_momentum.json")
_WEB = Path("web/spot_momentum.json")
_LAKE = "data/lake"

#: Binance SPOT pairs an Irish retail account can hold. Deliberately a short explicit list rather
#: than the 213-symbol research universe: a target the account cannot buy is not a target, and
#: sizing a book against symbols it cannot hold overstates diversification by exactly the names
#: that are unavailable.
_SPOT_UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                  "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT")


def _weights(close: Any, q: float) -> dict[str, float]:
    """Today's target weights -- what the account should actually hold, inverse-vol within the top
    quantile. Recomputed here from the LAST bar only: the returns series answers 'did this work',
    this answers 'what do I buy', and conflating them is how a backtest becomes an order."""
    import pandas as pd

    sig = (close / close.shift(20) - 1.0).iloc[-1].dropna()
    if sig.empty:
        return {}
    ret = close.pct_change(fill_method=None)
    inv = 1.0 / ret.rolling(30).std().iloc[-1].replace(0.0, np.nan)
    k = max(1, int(len(sig) * q))
    longs = sig.sort_values(ascending=False).index[:k]
    w = inv.reindex(longs).fillna(0.0)
    tot = float(w.sum())
    if tot <= 0:
        return dict.fromkeys(longs, round(1.0 / len(longs), 6))
    return {str(s): round(float(w[s] / tot), 6) for s in longs
            if isinstance(pd.notna(w[s]), bool)}


def _previous_gross() -> float | None:
    """Yesterday's gross, so the rebalance band has something to compare against. Absent on the
    first run, which is correct: there is no position to leave alone."""
    try:
        return float(json.loads(_OUT.read_text("utf-8"))["gross"]["gross"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default=",".join(_SPOT_UNIVERSE))
    ap.add_argument("--equity", type=float, required=True,
                    help="deployable SPOT equity in USD -- required, never guessed")
    ap.add_argument("--min-notional", type=float, default=None)
    ap.add_argument("--q", type=float, default=DEFAULT_Q)
    ap.add_argument("--band", type=float, default=DEFAULT_BAND)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--max-gross", type=float, default=1.0,
                    help="ceiling on total exposure. 1.0 is unlevered -- a spot account cannot "
                         "hold more than it paid for. A levered caller passes what "
                         "libs.execution.leverage_policy permits, which is itself Kelly-bounded")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    try:
        from libs.autodiscovery.crypto_adapter import _read_frames
        from libs.data.timeframe import Timeframe
        frames = _read_frames(symbols, Timeframe.D1, _LAKE)
    except Exception as exc:
        print(f"spot-momentum: lake unreadable ({type(exc).__name__}: {exc}) -- UNMEASURED, "
              "nothing written. An empty result would read as 'no edge', which is a different "
              "and false claim")
        return 1

    import pandas as pd
    cols = {s: frames[s]["close"] for s in symbols
            if frames.get(s) is not None and len(frames[s]) > 0}
    absent = [s for s in symbols if s not in cols]
    if len(cols) < 6:
        print(f"spot-momentum: only {len(cols)} readable symbol(s) of {len(symbols)} -- below the "
              "6-name minimum a cross-sectional rank needs. UNMEASURED, not 'no signal'")
        for s in absent:
            print(f"  absent: {s}")
        return 1

    close = pd.DataFrame(cols).dropna(how="all")
    signal = close / close.shift(20) - 1.0
    cost = dict.fromkeys(close.columns, args.cost_bps / 10_000.0)

    strat = spot_long_only_returns(close, signal, cost, q=args.q, band=args.band)
    res = evaluate(strat, benchmark_returns(close))
    w = _weights(close, args.q)

    # GROSS EXPOSURE AT THE GROWTH OPTIMUM. The weights above are RELATIVE -- inverse-vol within
    # the top quantile -- and say nothing about how much of the account should be in the book at
    # all. Left at 1.0 the book runs whatever volatility the tape happens to hand it, which is the
    # one quantity the objective is a function of. The target is not chosen: at the Kelly optimum
    # portfolio volatility EQUALS the Sharpe, so `growth_optimal_vol` is arithmetic.
    #
    # The Sharpe used is the EXCESS one. Raw Sharpe includes the market's drift, and sizing a book
    # against a number that is mostly beta would target a volatility the selection never earned.
    # n_obs IS WHAT MAKES THIS DYNAMIC IN THE DIRECTION THAT MATTERS. The Sharpe is discounted by
    # one standard error, and that error shrinks as observations accumulate -- so the book's
    # exposure RISES on its own as evidence arrives, without anyone editing a constant. A fixed
    # Kelly fraction would stay timid forever no matter how much the desk learned.
    vt = gross_exposure(float(np.std(strat[np.isfinite(strat)])) or None,
                        sharpe=res.sharpe_excess, n_obs=res.n_days,
                        max_gross=args.max_gross, current_gross=_previous_gross())
    w = {k: round(v * vt.gross, 6) for k, v in w.items()}

    # WHAT TO ACTUALLY BUY, and whether the account can buy it. A weight below venue minimum is
    # reported rather than rounded up: rounding would breach the intended allocation silently, in
    # the direction that concentrates the book.
    orders, unplaceable = [], []
    for sym, frac in sorted(w.items(), key=lambda kv: -kv[1]):
        usd = frac * float(args.equity)
        row = {"symbol": sym, "weight": frac, "usd": round(usd, 2)}
        if args.min_notional is not None and usd < float(args.min_notional):
            row["refused"] = (f"${usd:,.2f} is below the venue minimum "
                              f"${float(args.min_notional):,.2f}. Rounding up would breach the "
                              "intended weight silently and concentrate the book")
            unplaceable.append(row)
        else:
            orders.append(row)

    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "spot_long_only_momentum",
        "inherits_from": None,
        "equity_usd": float(args.equity),
        "universe": list(close.columns),
        "absent_symbols": absent,
        "target_weights": w,
        "gross": vt.as_row(),
        "orders": orders,
        "unplaceable": unplaceable,
        "evidence_status": "IN-SAMPLE ONLY -- NO FORWARD CLOCK",
        "principal_exception": (
            "Deployed at the principal's explicit instruction WITHOUT the pre-registered forward "
            "clock the two-stage law requires, as a stated one-off. Recorded here so nobody later "
            "mistakes this for a candidate that cleared Stage B. Every figure below is in-sample."),
        **res.as_row(),
    }
    for p in (_OUT, _WEB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=1), "utf-8")

    print(f"=== SPOT LONG-ONLY MOMENTUM === {res.n_days} days, {len(close.columns)} symbols")
    print(f"  sharpe RAW      {res.sharpe_raw:>7.2f}   <- measures the MARKET as much as the book")
    print(f"  benchmark       {res.benchmark_sharpe:>7.2f}   equal-weight buy-and-hold")
    print(f"  sharpe EXCESS   {res.sharpe_excess:>7.2f}   <- the only part selection can claim")
    print(f"  beta            {res.beta_to_universe:>7.2f}   NOT neutral; full drawdown retained")
    print(f"  max drawdown    {res.max_drawdown:>7.1%}")
    print("  IN-SAMPLE ONLY -- no forward clock (principal exception)")
    print(f"  GROSS           {vt.gross:>7.2f}   {vt.state} -- target vol "
          f"{0.0 if vt.target_vol is None else vt.target_vol:.0%}/yr vs realised "
          f"{0.0 if vt.realised_vol is None else vt.realised_vol:.0%}/yr")
    print(f"    {vt.why[:150]}")
    print("  TARGET BOOK:")
    for o in orders:
        print(f"    BUY  {o['symbol']:<10} {o['weight']:>7.2%}  ${o['usd']:,.2f}")
    for u in unplaceable:
        print(f"    SKIP {u['symbol']:<10} {u['weight']:>7.2%}  ${u['usd']:,.2f} -- below minimum")
    print(f"-> {_OUT} and {_WEB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
