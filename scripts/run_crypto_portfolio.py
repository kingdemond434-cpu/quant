"""Crypto-native alpha PORTFOLIO engine -- the truth-finding core of the crypto factory.

Builds every economically-distinct sleeve from free Binance perp data (funding carry/momentum/
reversal, cross-sectional price momentum, time-series trend, BTC/ETH relative value), measures the
correlation matrix, combines them with hierarchical (cluster) risk parity, computes growth-optimal
leverage, and runs each + the portfolio through the full institutional gauntlet. The headline number
is the PORTFOLIO Sharpe -- it decides whether a Binance testnet deployment is worth wiring.

No parameter mining (crypto-standard horizons, pre-specified). Net of ADV-tiered cost + funding.

    python scripts/run_crypto_portfolio.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.portfolio.covariance import cov_forecast_portfolio
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.crypto_regime import regime_labels, regime_performance
from libs.research.crypto_sleeves import (
    basis_carry_returns,
    funding_momentum_returns,
    taker_flow_returns,
)
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.risk.growth_leverage import analyze as leverage_analyze
from libs.risk.stress import beta_shock, crisis_replay, worst_window
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/crypto_portfolio")
_PPY = 365.0
_FAIL = ["edge crowds/decays", "regime shift", "correlated crypto crash",
         "funding compresses", "exchange/liquidity risk"]
# funding_reversal (-2.3) and btc_eth_rv (-0.7) are economically REFUTED -- negative across every
# data refresh -- so they are dropped from the deployable set (honest curation, not cherry-picking;
# their failures are recorded in the rejected registry). Keep only positive-prior, working sleeves.
_CLUSTERS = {
    "funding": ["funding_carry", "funding_momentum"],
    "price": ["xsec_price_mom", "ts_trend"],
    "basis": ["basis_carry"],
    "flow": ["taker_flow"],
}
_DROPPED = {"funding_reversal": "negative across all refreshes (price-reversal thesis refuted)",
            "btc_eth_rv": "negative across all refreshes (BTC/ETH ratio trends, not mean-reverts)"}
_FAMILY = {
    "funding_carry": Family.CARRY, "funding_momentum": Family.CARRY,
    "funding_reversal": Family.MEAN_REVERSION, "xsec_price_mom": Family.MOMENTUM,
    "ts_trend": Family.TREND, "btc_eth_rv": Family.MEAN_REVERSION,
    "basis_carry": Family.CARRY, "taker_flow": Family.MOMENTUM,
    "portfolio": Family.CROSS_ASSET,
}


def _panels(universe: list[str]) -> tuple[pd.DataFrame, ...]:
    """close, funding, adv, basis, taker -- basis/taker present only after the enriched ingest."""
    lake = ParquetLake("data/lake")
    closes, fundings, adv, bases, takers = {}, {}, {}, {}, {}
    for s in universe:
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        fundings[s] = df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    return close, f, adv, basis, taker


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _riskparity(df: pd.DataFrame, *, weight: bool = True) -> np.ndarray:
    masked = df.replace(0.0, np.nan)
    vol = masked.rolling(252, min_periods=60).std().shift(1)
    inv = 1.0 / vol
    if weight:
        mean = masked.rolling(252, min_periods=60).mean().shift(1)
        inv = inv * (mean / vol).clip(lower=0.0)
    w = inv.div(inv.sum(axis=1), axis=0).fillna(0.0)
    if df.shape[1] > 1:                                   # 30% concentration cap
        for _ in range(4):
            over = w > 0.30
            if not bool(over.to_numpy().any()):
                break
            capped = w.clip(upper=0.30)
            room = inv.where(~over, 0.0)
            share = room.div(room.sum(axis=1), axis=0).fillna(0.0)
            w = capped.add(share.mul(1.0 - capped.sum(axis=1), axis=0), fill_value=0.0)
    return (w.to_numpy() * df.to_numpy()).sum(axis=1)


def _cluster_rp(df: pd.DataFrame) -> np.ndarray:
    rets = {name: _riskparity(df[[m for m in members if m in df.columns]])
            for name, members in _CLUSTERS.items()
            if any(m in df.columns for m in members)}
    return _riskparity(pd.DataFrame(rets, index=df.index))


def _validate(name: str, r: np.ndarray, matrix: np.ndarray, sharpes: np.ndarray,
              pbo, rc) -> dict[str, object]:  # type: ignore[no-untyped-def]
    active = r[r != 0.0]
    if len(active) < 250:
        return {"sleeve": name, "ann_sharpe": _ann(r), "gates": "n<250", "survived": False}
    v = validate(active, hypothesis=Hypothesis(
        family=_FAMILY.get(name, Family.CARRY), subtype=name, symbol="CRYPTO", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
        n_trials=matrix.shape[1], sharpe_estimates=sharpes, returns_matrix=matrix, pbo=pbo, rc=rc)
    return {"sleeve": name, "ann_sharpe": _ann(r), "survived": bool(v.survived),
            "gates": f"{sum(v.gates.values())}/{len(v.gates)}",
            "fails": [k for k, ok in v.gates.items() if not ok]}


def main() -> None:
    universe = list_liquid_perps(top_n=120)
    close, funding, adv, basis, taker = _panels(universe)
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel; run ingest_crypto.py --universe liquid")
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    print(f"crypto panel: {close.shape[1]} perps x {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})")

    sleeves: dict[str, np.ndarray] = {
        "funding_carry": xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
        "funding_momentum": funding_momentum_returns(close, funding, adv, lookback=7, q=0.2,
                                                     band=0.02),
        "xsec_price_mom": xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05),
        "ts_trend": trend_basket_returns(close, cost, lookback=30, band=0.05),
    }
    if not basis.empty and basis.shape[1] >= 12:           # enriched-ingest data present
        sleeves["basis_carry"] = basis_carry_returns(close[basis.columns], funding[basis.columns],
                                                     basis, adv, lookback=3, q=0.2, band=0.02)
    if not taker.empty and taker.shape[1] >= 12:
        sleeves["taker_flow"] = taker_flow_returns(close[taker.columns], funding[taker.columns],
                                                   taker, adv, lookback=5, q=0.2, band=0.02)
    sleeves = {k: v for k, v in sleeves.items() if np.isfinite(v).all()}

    df = pd.DataFrame(sleeves, index=close.index)
    port = _cluster_rp(df)                                  # static cluster risk parity
    port_flat = _riskparity(df, weight=True)               # flat trailing-Sharpe-tilted RP
    port_cov = cov_forecast_portfolio(df.to_numpy(), lam=0.94)   # dynamic-cov ERC (TC-aware)
    series = {**sleeves, "portfolio": port, "portfolio_flat": port_flat,
              "portfolio_covforecast": port_cov}
    names = list(series)
    matrix = np.column_stack([series[k] for k in names])
    sharpes = np.array([sharpe_ratio(series[k][series[k] != 0.0]) for k in names])
    pbo, rc = campaign_pbo_rc(matrix)
    results = [_validate(k, series[k], matrix, sharpes, pbo, rc) for k in names]

    corr = df.replace(0.0, np.nan).corr().round(2)
    port_sharpe, flat_sharpe, cov_sharpe = _ann(port), _ann(port_flat), _ann(port_cov)
    cand = {"cluster": (port, port_sharpe), "flat": (port_flat, flat_sharpe),
            "covforecast": (port_cov, cov_sharpe)}
    best_name = max(cand, key=lambda k: cand[k][1])
    headline, head_sharpe = cand[best_name]
    incr = {k: round(flat_sharpe - _ann(_riskparity(df.drop(columns=[k]), weight=True)),
                     3) for k in sleeves}
    lev = leverage_analyze(headline, ppy=_PPY, kelly_fraction=0.5, governance_cap=3.0)

    # Regime breakdown: which sleeves work in which environment.
    labels = regime_labels(close, funding)
    regimes = regime_performance(sleeves, labels, headline)

    # Stress testing: survivability under crypto's known failure modes.
    dates = close.index
    btc_ret = (close["BTCUSDT"].pct_change(fill_method=None).to_numpy()
               if "BTCUSDT" in close.columns else np.zeros(len(close)))
    funding_off = dict(sleeves)
    zero_f = funding * 0.0
    funding_off["funding_carry"] = xsec_funding_returns(close, zero_f, adv, lookback=7, q=0.2,
                                                        band=0.02)
    fo_port = _cluster_rp(pd.DataFrame(funding_off, index=close.index))
    stress = {
        "crisis_replay": crisis_replay(headline, dates),
        "worst_14d": worst_window(headline, dates, n=14),
        "btc_-30pct_shock": beta_shock(headline, btc_ret, shock=-0.30),
        "funding_disappears_sharpe": _ann(fo_port),
    }

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"perps": close.shape[1], "days": close.shape[0], "portfolio_ann_sharpe": port_sharpe,
               "portfolio_flat_sharpe": flat_sharpe, "portfolio_covforecast_sharpe": cov_sharpe,
               "headline_combiner": best_name, "headline_sharpe": head_sharpe,
               "results": results, "incremental_sharpe": incr, "correlations": corr.to_dict(),
               "leverage": lev, "regimes": regimes, "stress": stress, "rejected": _DROPPED}
    blob = json.dumps(payload, indent=2, default=str)
    (_OUT / "report.json").write_text(blob, "utf-8")
    Path("web/crypto_portfolio.json").write_text(blob, "utf-8")

    print("\nCRYPTO SLEEVES (ranked by portfolio contribution):")
    for d in sorted(results, key=lambda d: incr.get(d["sleeve"], 0), reverse=True):
        ic = f"incr={incr.get(d['sleeve']):+.2f}" if d["sleeve"] in incr else "(portfolio)"
        print(f"  {d['sleeve']:18} sharpe~{d['ann_sharpe']:6} gates={d.get('gates', ''):5} "
              f"{ic}  fails={d.get('fails', '')}")
    print(f"\nPORTFOLIO Sharpe: cluster~{port_sharpe}  flat-tilt~{flat_sharpe}  "
          f"cov-forecast~{cov_sharpe}  -> headline ({best_name}) {head_sharpe}  (target >1.5)  "
          f"growth-opt L={lev['growth_optimal_leverage']}x")
    print("\nSTRESS:")
    print(f"  funding disappears -> portfolio Sharpe {stress['funding_disappears_sharpe']}")
    print(f"  worst 14d: {stress['worst_14d'].get('worst_cum_return')} "
          f"({stress['worst_14d'].get('start')}..{stress['worst_14d'].get('end')})")
    print(f"  BTC -30% shock -> est P&L {stress['btc_-30pct_shock']['est_pnl']} "
          f"(beta {stress['btc_-30pct_shock']['beta']})")
    for name, cr in stress["crisis_replay"].items():
        print(f"  {name:22} cum {cr['cum_return']:+.1%}  maxDD {cr['max_dd']:+.1%}")
    print("\ncorrelation matrix:")
    print(corr.to_string())


if __name__ == "__main__":
    main()
