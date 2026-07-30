"""Backtest exchange-flow / on-chain hypotheses on PAID HISTORY (CryptoQuant/Glassnode CSV).

Pay-once-then-cancel model: drop a downloaded CSV in data/paid/ and this runs the full gauntlet on
YEARS of history instead of the ~13-day free forward clock. The paid data VALIDATES the edge; the
free keyless reader (libs/data/onchain_flows.py) keeps trading it forward -- no subscription.

CSV format (vendor-agnostic): a date column + one or more metric columns. Auto-detects common
column names (date/time/t; value/netflow/exchange_netflow/reserve/supply). Point --price at a BTC
daily close CSV (or it pulls free Binance) to compute forward returns.

Hypothesis tested (pre-registered, economic): exchange NETFLOW predicts forward return -- stables
flowing ONTO exchanges = dry powder / buy pressure (sign is empirical, resolved by gauntlet, not
assumed). Runs the SAME validate + campaign_gate_stats gauntlet every alpha uses. Nothing fabricated.

    python scripts/run_onchain_history_backtest.py --csv data/paid/exchange_netflow.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import daily_with_funding
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_FAIL = ["flow signal crowds/decays", "regime shift", "thin sample", "cost exceeds edge"]

_OUT = Path("web/onchain_history_backtest.json")
_DATE_COLS = ("date", "time", "timestamp", "t", "datetime", "day")
_VAL_COLS = ("value", "netflow", "exchange_netflow", "reserve", "exchange_reserve",
             "supply", "v", "flow", "net_flow")


def _pick(cols: list[str], candidates: tuple[str, ...]) -> str | None:
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in low:
            return low[cand]
    for c in cols:                                     # fuzzy: any col containing a candidate word
        if any(k in c.lower() for k in candidates):
            return c
    return None


def _load_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    dc = _pick(list(df.columns), _DATE_COLS)
    vc = _pick([c for c in df.columns if c != dc], _VAL_COLS)
    if not dc or not vc:
        raise SystemExit(f"could not detect date/value columns in {list(df.columns)}; "
                         "rename to date,value")
    s = pd.Series(pd.to_numeric(df[vc], errors="coerce").to_numpy(),
                  index=pd.to_datetime(df[dc], utc=True, errors="coerce")).dropna()
    return s[~s.index.duplicated()].sort_index()


def _btc_returns(price_csv: str | None) -> pd.Series:
    if price_csv:
        px = _load_csv(Path(price_csv))
    else:
        bars = daily_with_funding("BTCUSDT", start="2019-01-01").set_index("timestamp")["close"]
        px = bars
    px.index = pd.to_datetime(px.index, utc=True)
    return px.resample("1D").last().pct_change(fill_method=None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="paid on-chain metric CSV (date + value)")
    ap.add_argument("--price", default=None, help="optional BTC daily close CSV (else Binance)")
    ap.add_argument("--lookback", type=int, default=7, help="signal smoothing window (days)")
    args = ap.parse_args()

    metric = _load_csv(Path(args.csv)).resample("1D").last().ffill()
    ret = _btc_returns(args.price)
    df = pd.concat({"m": metric, "r": ret}, axis=1).dropna()
    if len(df) < 250:
        raise SystemExit(f"only {len(df)} aligned days; need >=250 for the gauntlet")

    # signal = z-scored netflow change (lagged -> no look-ahead); position = -sign (contrarian) and
    # +sign (momentum) BOTH tested, gauntlet keeps the honest one. Net of a flat 5bps/turn cost.
    z = ((df["m"] - df["m"].rolling(args.lookback).mean())
         / df["m"].rolling(args.lookback).std()).shift(1)
    fwd = df["r"]
    strat = {}
    for name, sgn in (("flow_momentum", 1.0), ("flow_contrarian", -1.0)):
        pos = np.tanh(sgn * z).fillna(0.0)
        turn = pos.diff().abs().fillna(0.0)
        r = (pos * fwd - turn * 5e-4).dropna().to_numpy()
        strat[name] = r

    matrix = np.column_stack([strat["flow_momentum"], strat["flow_contrarian"]])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    results = {}
    # enumerate order == column_stack order over `strat`, so `col` is the strategy's matrix column
    for col, (name, r) in enumerate(strat.items()):
        sh = round(float(sharpe_ratio(r) * np.sqrt(365)), 2)
        hyp = Hypothesis(family=Family.LIQUIDITY, subtype=name, symbol="CRYPTO", params={},
                         mechanism=MechanismType.BEHAVIORAL, edge_source="exchange_flow",
                         failure_modes=_FAIL)
        v = validate(r, hypothesis=hyp, n_trials=2, sharpe_estimates=[sh, -sh],
                     returns_matrix=matrix, campaign=campaign, column=col)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results[name] = {"ann_sharpe": sh, "gates": gates,
                         "pbo": round(float(v.metrics.pbo), 3) if v else None,
                         "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                         "survived": bool(getattr(v, "survived", False))}

    out = {"source": str(args.csv), "aligned_days": len(df),
           "date_range": [str(df.index.min())[:10], str(df.index.max())[:10]],
           # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the
           # gate values are per-strategy now -- see results[*].pbo / results[*].rc_p.
           "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                   if campaign is not None and campaign.legacy_pbo is not None else None),
           "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                               if campaign is not None and campaign.legacy_rc is not None
                               else None),
           "results": results,
           "note": "paid history validates; free keyless onchain_flows.py trades it forward. "
                   "Sign chosen by gauntlet, not assumed. One-off pull -> no subscription needed."}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for name, res in results.items():
        print(f"{name}: annSharpe {res['ann_sharpe']} pbo={res['pbo']} rc_p={res['rc_p']} "
              f"survived={res['survived']}")
    print(f"aligned {len(df)}d {out['date_range']} | campaign diagnostics pbo {out['pbo']} "
          f"rc {out['reality_check_p']} (gates are per-strategy)")


if __name__ == "__main__":
    main()
