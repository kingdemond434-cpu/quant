"""MT5 alpha-PORTFOLIO campaign -- search for low-correlation sleeves, not one strategy.

Builds every MT5-executable sleeve we have real data for (cross-asset trend, cross-sectional
momentum, metals/FX momentum, index trend, gold/silver & gold/platinum & WTI/Brent relative value,
and CFTC COT positioning), runs each through the FULL institutional gauntlet, measures the
correlation matrix, then combines the positive-economic-prior sleeves with rolling inverse-vol
(risk-parity, lagged -> no look-ahead) into a diversified portfolio and gauntlets THAT. Diversifying
across uncorrelated real edges is the only honest lever to raise survivor probability -- no gate is
weakened, no parameter is tuned to pass. Ranks by gates passed, then Sharpe, then diversification.

    python scripts/run_mt5_portfolio.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.cleaning import DEFAULT_CAPS, guard_close
from libs.data.cot_source import COT_MAP, cot_zscore_daily
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.sleeves import (
    calendar_event_returns,
    cot_positioning_returns,
    cot_timeseries_returns,
    crisis_hedge_returns,
    ratio_meanrev_returns,
    swap_carry_returns,
)
from libs.risk.growth_leverage import analyze as leverage_analyze
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_COVERAGE = Path("reports/multiasset_coverage.json")
_OUT = Path("reports/mt5_portfolio")
_PPY = 252.0
_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4,
         "index": 1.0e-4, "crypto": 6.0e-4, "equity": 2.0e-4}
# Realistic per-side DAILY overnight financing (CFD swap) charged on a HELD position. Dominated by
# crypto CFDs (~5bps/day) -- ignoring it overstates any continuously-held crypto book. Honest cost.
_HOLD = {"fx": 0.3e-4, "metal": 1.0e-4, "energy": 1.0e-4,
         "index": 0.5e-4, "crypto": 5.0e-4, "equity": 0.5e-4}
_FAIL = ["premium compresses/crowds", "regime shift", "correlated drawdown",
         "cost exceeds edge", "edge decay"]


def _load() -> tuple[pd.DataFrame, dict[str, float], dict[str, list[str]]]:
    cov = json.loads(_COVERAGE.read_text("utf-8"))
    lake = ParquetLake("data/lake")
    closes, cost, by_class = {}, {}, {}
    for c in cov:
        if not c.get("bars"):
            continue
        sym, ac = str(c["symbol"]), str(c["asset_class"])
        register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass(ac), description=sym))
        df = lake.read_bars(Layer.BRONZE, sym, Timeframe.D1).set_index("timestamp")
        if len(df) < 250:
            continue
        closes[sym] = df["close"]
        cost[sym] = _COST.get(ac, 2.0e-4)
        by_class.setdefault(ac, []).append(sym)
    close = pd.DataFrame(closes).sort_index()
    caps = {s: DEFAULT_CAPS.get(ac, 0.5) for ac, syms in by_class.items() for s in syms}
    close = guard_close(close, caps)                     # gap-guard: kill bad-print spikes
    return close, cost, by_class


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _sub(close: pd.DataFrame, syms: list[str]) -> pd.DataFrame:
    keep = [s for s in syms if s in close.columns]
    return close[keep]


def _build_sleeves(close: pd.DataFrame, cost: dict[str, float],
                   by: dict[str, list[str]]) -> dict[str, np.ndarray]:
    n = len(close)
    hold = {sym: _HOLD.get(ac, 0.5e-4) for ac, syms in by.items() for sym in syms}
    sl: dict[str, np.ndarray] = {}
    # Cross-asset book = the original FX/metal/energy/index/crypto universe (ETFs feed their own
    # dedicated sleeves below, so the broad trend/momentum sleeves stay clean & comparable).
    xa_syms = [s for ac, syms in by.items() if ac != "equity" for s in syms if s in close.columns]
    xa = close[xa_syms]
    sl["trend_all"] = trend_basket_returns(xa, cost, lookback=100, band=0.05, hold_cost=hold)
    sl["xsec_mom_all"] = xsec_momentum_returns(xa, cost, lookback=120, q=0.3, band=0.05,
                                               hold_cost=hold)
    metals = _sub(close, by.get("metal", []))
    if metals.shape[1] >= 3:
        sl["metals_mom"] = xsec_momentum_returns(metals, cost, lookback=120, q=0.5, band=0.05,
                                                 min_names=3, hold_cost=hold)
    fx = _sub(close, by.get("fx", []))
    if fx.shape[1] >= 5:
        sl["fx_mom"] = xsec_momentum_returns(fx, cost, lookback=120, q=0.3, band=0.05,
                                             hold_cost=hold)
    idx = _sub(close, by.get("index", []))
    if idx.shape[1] >= 3:
        sl["index_trend"] = trend_basket_returns(idx, cost, lookback=100, band=0.05, min_names=3,
                                                 hold_cost=hold)

    def rv(a: str, b: str, name: str) -> None:
        if a in close.columns and b in close.columns:
            c = 0.5 * (cost.get(a, 2e-4) + cost.get(b, 2e-4))
            sl[name] = ratio_meanrev_returns(close[a], close[b], lookback=60, cost=c, band=0.05)

    rv("XAUUSD", "XAGUSD", "gold_silver_rv")
    rv("XAUUSD", "XPTUSD", "gold_plat_rv")
    rv("XTIUSD", "XBRUSD", "wti_brent_rv")

    # --- ETF sleeves (new free orthogonal families: rates/duration, credit, sector rotation) ---
    rates = [s for s in ("TLT", "IEF", "SHY", "LQD", "EMB") if s in close.columns]
    if len(rates) >= 3:
        sl["rates_trend"] = trend_basket_returns(close[rates], cost, lookback=100, band=0.05,
                                                 min_names=3, hold_cost=hold)
    sectors = [s for s in ("XLE", "XLF", "XLI", "XLP", "XLU", "XLK", "XLV", "XLY")
               if s in close.columns]
    if len(sectors) >= 5:
        sl["sector_rotation"] = xsec_momentum_returns(close[sectors], cost, lookback=120, q=0.3,
                                                      band=0.05, hold_cost=hold)
    rv("TLT", "IEF", "curve_rv")           # Treasury curve (long-end vs intermediate)
    rv("EMB", "TLT", "credit_rv")          # EM credit vs duration

    cot_syms = [s for s in COT_MAP if s in close.columns]
    if len(cot_syms) >= 5:
        cache = Path("data/cot_zcache.parquet")
        if cache.exists():
            cz = pd.read_parquet(cache).reindex(close.index)
        else:
            cz = cot_zscore_daily(cot_syms, close.index, z_weeks=156)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cz.to_parquet(cache)
        cz = cz.dropna(axis=1, how="all")
        if cz.shape[1] >= 5:
            cclose = close[list(cz.columns)]
            sl["cot_positioning"] = cot_positioning_returns(
                cclose, cz, cost, band=0.05, min_names=3, long_high=False)
            sl["cot_timeseries"] = cot_timeseries_returns(cclose, cz, cost, band=0.05, z_entry=1.0)
    if "XAUUSD" in close.columns and "US500" in close.columns:
        sl["gold_crisis_hedge"] = crisis_hedge_returns(
            close["XAUUSD"], close["US500"], ma_window=200, cost=cost.get("XAUUSD", 2e-4))
    if idx.shape[1] >= 2:
        sl["macro_calendar"] = calendar_event_returns(idx, cost=_COST["index"], tom_first=3)
    crypto = _sub(close, by.get("crypto", []))
    if crypto.shape[1] >= 2:                              # crypto = trendiest market -> own sleeve
        sl["crypto_trend"] = trend_basket_returns(crypto, cost, lookback=100, band=0.05,
                                                  min_names=2, hold_cost=hold)
    carry = _swap_carry(close, cost)
    if carry is not None:
        sl["swap_carry"] = carry
    return {k: v for k, v in sl.items() if len(v) == n and np.isfinite(v).all()}


def _swap_carry(close: pd.DataFrame, cost: dict[str, float]) -> np.ndarray | None:
    """Build the broker-swap carry sleeve IF a swap-rate history has accumulated (else None).

    Carry has no backtest (MT5 exposes only current swaps); this activates once log_swaps.py has
    seeded enough distinct days. Until then the sleeve is forward-only and excluded honestly.
    """
    log = Path("data/swap_log.parquet")
    if not log.exists():
        return None
    df = pd.read_parquet(log)
    if df["ts"].dt.date.nunique() < 250:                 # need real history to backtest
        return None
    cl = df.pivot_table(index=df["ts"].dt.tz_convert("UTC").dt.normalize(),
                        columns="symbol", values="carry_long")
    cs = df.pivot_table(index=df["ts"].dt.tz_convert("UTC").dt.normalize(),
                        columns="symbol", values="carry_short")
    syms = [s for s in cl.columns if s in close.columns]
    if len(syms) < 5:
        return None
    cl = cl[syms].reindex(close.index).ffill()
    cs = cs[syms].reindex(close.index).ffill()
    return swap_carry_returns(close[syms], cl, cs, cost, q=0.3, band=0.05)


def _families() -> dict[str, Family]:
    return {"trend_all": Family.TREND, "xsec_mom_all": Family.MOMENTUM,
            "metals_mom": Family.MOMENTUM, "fx_mom": Family.MOMENTUM,
            "index_trend": Family.TREND, "gold_silver_rv": Family.MEAN_REVERSION,
            "gold_plat_rv": Family.MEAN_REVERSION, "wti_brent_rv": Family.MEAN_REVERSION,
            "cot_positioning": Family.CARRY, "cot_timeseries": Family.CARRY,
            "gold_crisis_hedge": Family.REGIME_TRANSITION, "macro_calendar": Family.SESSION,
            "swap_carry": Family.CARRY, "crypto_trend": Family.TREND,
            "rates_trend": Family.TREND, "sector_rotation": Family.MOMENTUM,
            "curve_rv": Family.MEAN_REVERSION, "credit_rv": Family.MEAN_REVERSION,
            "portfolio": Family.CROSS_ASSET}


def _riskparity(df: pd.DataFrame, *, mode: str = "plain", max_weight: float | None = None) -> (
        np.ndarray):
    """Daily sleeve combination, all weights computed from LAGGED data (no look-ahead).

    * ``plain``  : risk-parity (rolling inverse-vol).
    * ``gate``   : risk-parity, but fund a sleeve only while its trailing 252d return is positive.
    * ``weight`` : tilt risk-parity weights by each sleeve's trailing 252d Sharpe (>=0) -- the most
      robust "max" combination: more capital to what is genuinely working, zero to losers, without
      the overfit of full mean-variance optimization.

    ``max_weight`` caps any single column's weight (concentration limit) and redistributes the
    excess to the others -- the survivability fix that stops one cluster (crypto) from dominating.
    """
    masked = df.replace(0.0, np.nan)
    vol = masked.rolling(252, min_periods=60).std().shift(1)
    inv = 1.0 / vol
    if mode in {"gate", "weight"}:
        mean = masked.rolling(252, min_periods=60).mean().shift(1)
        inv = (inv.where(mean > 0.0, 0.0) if mode == "gate"
               else inv * (mean / vol).clip(lower=0.0))
    w = inv.div(inv.sum(axis=1), axis=0).fillna(0.0)
    if max_weight is not None and df.shape[1] > 1:
        for _ in range(4):                               # iterate: cap, push excess to the rest
            over = w > max_weight
            if not bool(over.to_numpy().any()):
                break
            capped = w.clip(upper=max_weight)
            deficit = 1.0 - capped.sum(axis=1)
            room = inv.where(~over, 0.0)
            share = room.div(room.sum(axis=1), axis=0).fillna(0.0)
            w = capped.add(share.mul(deficit, axis=0), fill_value=0.0)
    return (w.to_numpy() * df.to_numpy()).sum(axis=1)


# Economic clusters: correlated sleeves count as ONE bet so the book does not over-allocate to the
# momentum family. Two-level: trailing-Sharpe-weighted risk-parity within a cluster, then across.
_CLUSTERS = {
    "momentum": ["trend_all", "xsec_mom_all", "fx_mom", "index_trend"],
    "metals": ["metals_mom"],
    "relval": ["wti_brent_rv", "gold_silver_rv", "gold_plat_rv"],
    "positioning": ["cot_positioning", "cot_timeseries"],
    "hedge": ["gold_crisis_hedge"],
    "calendar": ["macro_calendar"],
    "crypto": ["crypto_trend"],
    "carry": ["swap_carry"],
    "rates": ["rates_trend", "curve_rv"],
    "credit": ["credit_rv"],
    "sector": ["sector_rotation"],
}


_MAX_CLUSTER_WEIGHT = 0.30   # survivability: no single cluster (e.g. crypto) above 30% of the book


def _cluster_riskparity(df: pd.DataFrame) -> np.ndarray:
    """Hierarchical risk parity: combine each cluster, then capped risk-parity across clusters."""
    cluster_rets: dict[str, np.ndarray] = {}
    for name, members in _CLUSTERS.items():
        cols = [m for m in members if m in df.columns]
        if cols:
            cluster_rets[name] = _riskparity(df[cols], mode="weight")
    cdf = pd.DataFrame(cluster_rets, index=df.index)
    return _riskparity(cdf, mode="weight", max_weight=_MAX_CLUSTER_WEIGHT)


def _validate(name: str, r: np.ndarray, matrix: np.ndarray, sharpes: np.ndarray,
              fam: Family, pbo, rc) -> dict[str, object]:  # type: ignore[no-untyped-def]
    active = r[r != 0.0]
    if len(active) < 250:
        return {"sleeve": name, "ann_sharpe": _ann(r), "gates": "n<250", "survived": False,
                "reason": "insufficient active data"}
    v = validate(active, hypothesis=Hypothesis(
        family=fam, subtype=name, symbol="MT5_PORT", params={},
        mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
        n_trials=matrix.shape[1], sharpe_estimates=sharpes, returns_matrix=matrix, pbo=pbo, rc=rc)
    return {"sleeve": name, "ann_sharpe": _ann(r), "survived": bool(v.survived),
            "gates": f"{sum(v.gates.values())}/{len(v.gates)}",
            "fails": [k for k, ok in v.gates.items() if not ok], "reason": v.rejection_reason}


def main() -> None:
    close, cost, by = _load()
    sleeves = _build_sleeves(close, cost, by)
    fam = _families()
    print(f"panel: {close.shape[1]} instruments x {close.shape[0]} days; "
          f"{len(sleeves)} sleeves: {list(sleeves)}\n")

    df = pd.DataFrame(sleeves, index=close.index)
    port = _riskparity(df)                               # plain risk-parity
    port_gated = _riskparity(df, mode="gate")            # trailing-Sharpe-gated
    port_max = _riskparity(df, mode="weight")            # trailing-Sharpe-weighted
    port_cluster = _cluster_riskparity(df)               # hierarchical (cluster-aware) -- headline
    all_series = {**sleeves, "portfolio_rp": port, "portfolio_gated": port_gated,
                  "portfolio_max": port_max, "portfolio_cluster": port_cluster}

    names = list(all_series)
    matrix = np.column_stack([all_series[k] for k in names])
    sharpes = np.array([sharpe_ratio(all_series[k][all_series[k] != 0.0]) for k in names])
    pbo, rc = campaign_pbo_rc(matrix)
    results = [_validate(k, all_series[k], matrix, sharpes, fam.get(k, Family.CROSS_ASSET), pbo, rc)
               for k in names]

    # correlation matrix (active days only) + incremental portfolio Sharpe (leave-one-out on max)
    corr = df.replace(0.0, np.nan).corr().round(2)
    port_sharpe = _ann(port_cluster)
    incr = {}
    for k in sleeves:
        loo = _cluster_riskparity(df.drop(columns=[k]))
        incr[k] = round(port_sharpe - _ann(loo), 3)

    # Growth-optimal leverage (geometric CAGR), headline portfolio + positive-expectancy sleeves.
    # Unvalidated edges => half-Kelly de-rating + a conservative absolute governance cap.
    lev_targets = {"portfolio_cluster": port_cluster}
    lev_targets.update({k: v for k, v in sleeves.items() if _ann(v) > 0.0})
    leverage = {k: leverage_analyze(v, kelly_fraction=0.5, governance_cap=3.0)
                for k, v in lev_targets.items()}
    _WEB = Path("web/leverage.json")
    _WEB.write_text(json.dumps(
        {"updated_days": close.shape[0], "kelly_fraction": 0.5, "governance_cap": 3.0,
         "note": "Growth-optimal (Kelly) leverage maximizes geometric CAGR. Edges are UNVALIDATED "
                 "(fail DSR) -> recommended = half-Kelly capped; deploy only fractional + after "
                 "forward validation. CAGR assumes the in-sample edge persists.",
         "leverage": leverage}, indent=2, default=str), "utf-8")

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"instruments": close.shape[1], "days": close.shape[0],
               "portfolio_ann_sharpe": port_sharpe, "results": results,
               "incremental_sharpe": incr, "correlations": corr.to_dict(),
               "leverage": leverage}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")

    order = sorted(results, key=lambda d: (d.get("survived", False), d.get("ann_sharpe", 0)),
                   reverse=True)
    print("SLEEVE / PORTFOLIO RESULTS (ranked):")
    for d in order:
        inc = f" incr={incr[d['sleeve']]:+.2f}" if d["sleeve"] in incr else ""
        print(f"  {d['sleeve']:16} sharpe~{d['ann_sharpe']:5} gates={d.get('gates', '')!s:5} "
              f"survived={d.get('survived')}{inc}  fails={d.get('fails', '')}")
    print(f"\nPORTFOLIO_CLUSTER (hierarchical risk parity) ann_sharpe~{port_sharpe}")

    pc = leverage["portfolio_cluster"]
    print("\nGROWTH-OPTIMAL LEVERAGE (portfolio, geometric CAGR; assumes edge persists):")
    print(f"  growth-optimal (full Kelly) L={pc['growth_optimal_leverage']}  -> "
          f"CAGR {pc['points']['growth_optimal']['cagr']:.1%}  "
          f"maxDD {pc['points']['growth_optimal']['max_dd']:.0%}  "
          f"ruin {pc['points']['growth_optimal']['risk_of_ruin']:.0%}")
    print(f"  recommended (half-Kelly, cap) L={pc['recommended_leverage']}  -> "
          f"CAGR {pc['points']['recommended']['cagr']:.1%}  "
          f"maxDD {pc['points']['recommended']['max_dd']:.0%}  "
          f"ruin {pc['points']['recommended']['risk_of_ruin']:.0%}")
    print(f"  aggressive (2x Kelly)         L={pc['points']['aggressive']['leverage']}  -> "
          f"CAGR {pc['points']['aggressive']['cagr']:.1%}  "
          f"maxDD {pc['points']['aggressive']['max_dd']:.0%}  "
          f"ruin {pc['points']['aggressive']['risk_of_ruin']:.0%}")
    print("\nsleeve correlation matrix (active days):")
    print(corr.to_string())


if __name__ == "__main__":
    main()
