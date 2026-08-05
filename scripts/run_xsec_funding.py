"""Cross-sectional crypto funding -- the highest-EV free experiment (Tier 1).

Mechanism: perp funding is a leverage-demand premium that varies ACROSS coins. Go long the lowest-
funding perps and short the highest-funding perps, dollar-neutral. This harvests the funding
DISPERSION while diversifying away the idiosyncratic crash risk that sank single-name funding
(the fragility gate). Why institutions can't fully arb it: capacity-floor on small alts, borrow
constraints, and operational/venue risk they avoid. Net-of-cost, through the existing gauntlet.

    python scripts/run_xsec_funding.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/xsec_funding")
_COST = 5e-4               # per-side perp taker + slippage
_MIN_NAMES = 12            # need a real cross-section each day
# D1 crypto bars, and perps trade 24/7 -- so 365 bars a year, not the 6240 hourly constant this
# script's verdicts were annualised with until R0086 (a 4.135x inflation of ann_sharpe_metric).
_PPY = 365.0
_FAIL = ["funding dispersion compresses", "alt de-listings / illiquidity",
         "short borrow constraints", "correlated crypto crash overwhelms neutrality"]


def _panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    syms = sorted(d.name for d in _CRYPTO.iterdir() if (d / Timeframe.D1.value).exists()) \
        if _CRYPTO.exists() else []
    for s in syms:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
    lake = ParquetLake("data/lake")
    closes, fundings = {}, {}
    for s in syms:
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
    close = pd.DataFrame(closes).sort_index()
    funding = pd.DataFrame(fundings).reindex(close.index)
    return close, funding


def _xsec_returns(
    close: pd.DataFrame, funding: pd.DataFrame, *, lookback: int, q: float
) -> np.ndarray:
    ret = close.pct_change(fill_method=None)   # no ffill -> no spurious returns across gaps
    signal = funding.rolling(lookback).mean().shift(1)   # decide on prior info (no look-ahead)
    out = np.zeros(len(close), dtype="float64")
    prev_w = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        sig = signal.iloc[t].dropna()
        valid = close.iloc[t].reindex(sig.index).notna() & ret.iloc[t].reindex(sig.index).notna()
        sig = sig.reindex(sig.index[valid]).dropna()
        if len(sig) < _MIN_NAMES:
            continue
        k = max(1, int(len(sig) * q))
        ranked = sig.sort_values()
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        w = pd.Series(0.0, index=close.columns)
        w[longs] = 1.0 / (2 * k)            # long lowest funding
        w[shorts] = -1.0 / (2 * k)          # short highest funding
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        funding_collected = float(-(w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turnover = float((w - prev_w).abs().sum())
        out[t] = price_ret + funding_collected - turnover * _COST
        prev_w = w
    return out


def main() -> None:
    close, funding = _panels()
    if close.shape[1] < _MIN_NAMES:
        raise SystemExit(f"need >={_MIN_NAMES} perps; run: ingest_crypto.py --universe all")
    print(f"panel: {close.shape[1]} perps x {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})")

    variants = [("lb1_q20", 1, 0.2), ("lb3_q20", 3, 0.2), ("lb7_q20", 7, 0.2), ("lb3_q10", 3, 0.1)]
    series = [(n, _xsec_returns(close, funding, lookback=lb, q=q)) for n, lb, q in variants]
    min_len = min(len(r) for _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, r in series])
    sharpes = np.array([sharpe_ratio(r[r != 0.0]) for _, r in series], dtype="float64")
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors = 0
    results = []
    # enumerate order == column_stack order over `series`, so `col` is the variant's matrix column
    for col, ((name, rets), spr) in enumerate(zip(series, sharpes, strict=True)):
        active = rets[rets != 0.0]
        if len(active) >= 250:
            v = validate(active, hypothesis=Hypothesis(
                family=Family.CARRY, subtype=f"xsec_funding_{name}", symbol="CRYPTO_XSEC",
                params={}, mechanism=MechanismType.RISK_PREMIUM,
                edge_source="cross-sectional funding dispersion", failure_modes=_FAIL),
                periods_per_year=_PPY,
                n_trials=len(series), sharpe_estimates=sharpes,
                returns_matrix=matrix, campaign=campaign, column=col)
            survived, reason, metrics = v.survived, v.rejection_reason, v.metrics
        else:
            survived, reason, metrics = False, f"n={len(active)}<250", None
        survivors += int(survived)
        ann = float(metrics.annual_sharpe) if metrics else 0.0
        results.append({"variant": name, "days": len(active),
                        "mean_daily": round(float(np.mean(active)), 5) if len(active) else 0.0,
                        "sharpe_daily": round(float(spr), 4),
                        "survived": survived, "reason": reason, "ann_sharpe_metric": round(ann, 2)})

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"perps": close.shape[1], "survivors": survivors, "variants": results}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\n[xsec-funding] tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']}: days={r['days']} mean_daily={r['mean_daily']} "
              f"sharpe_daily={r['sharpe_daily']} survived={r['survived']} {r['reason']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost (honest).")


if __name__ == "__main__":
    main()
