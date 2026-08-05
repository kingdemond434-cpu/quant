"""Economically-grounded, backtestable generators for all 12 hypothesis families.

Each generator is a deterministic, causal (lag-1) rule with a DECLARED economic mechanism, edge
source, and expected failure modes — no random features, no brute-force mining. The 6 price-pattern
families reuse the Stage-13.5 strategy primitives; the rest are implemented here. Families that
need data the OHLC feed may lack (cross-asset reference, true carry/swap rates) degrade honestly to
flat and declare the limitation in their failure modes, rather than fabricating a signal.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.signal_builder import (
    Bars,
    breakout_positions,
    mean_reversion_positions,
    momentum_positions,
    strategy_returns,
    trend_positions,
    vol_compression_positions,
    vol_expansion_positions,
)
from libs.autodiscovery.models import Family, Hypothesis, MarketSeries
from libs.research.intermarket import intermarket_difference, threshold_revert
from libs.validation.economic_prior import MechanismType

PositionFn = Callable[[MarketSeries, dict[str, float]], np.ndarray]


def _bars(s: MarketSeries) -> Bars:
    return Bars(close=s.close, high=s.high, low=s.low)


def net_returns(series: MarketSeries, positions: np.ndarray, *, cost: float = 0.0003) -> np.ndarray:
    """Net, lag-1, cost-adjusted returns of a position series (reuses the shared backtest core)."""
    return strategy_returns(_bars(series), positions, cost_per_turnover=cost)


# --- price-pattern families (reuse the validated Stage-13.5 primitives) -------------
def _trend(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return trend_positions(_bars(s), fast=int(p["fast"]), slow=int(p["slow"]))


def _momentum(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return momentum_positions(_bars(s), lookback=int(p["lookback"]))


def _breakout(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return breakout_positions(_bars(s), window=int(p["window"]))


def _vol_compression(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return vol_compression_positions(
        _bars(s), window=int(p["window"]), vol_window=int(p["vol_window"])
    )


def _vol_expansion(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return vol_expansion_positions(
        _bars(s), vol_window=int(p["vol_window"]), lookback=int(p["lookback"])
    )


def _mean_reversion(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return mean_reversion_positions(_bars(s), window=int(p["window"]), z_entry=p["z_entry"])


# --- additional families ------------------------------------------------------------
def _session(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    if s.hour is None:
        return np.zeros(len(s), dtype="float64")  # honest: no intraday clock available
    lb = int(p["lookback"])
    mom = momentum_positions(_bars(s), lookback=lb)
    lo, span = int(p["open_hour"]), int(p["span"])
    gate = (s.hour >= lo) & (s.hour < lo + span)
    return (mom * gate).astype("float64")


def _cross_asset(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    if s.ref_close is None:
        return np.zeros(len(s), dtype="float64")  # honest: needs a second instrument
    ref_ret = np.zeros(len(s), dtype="float64")
    ref_ret[1:] = s.ref_close[1:] / s.ref_close[:-1] - 1.0
    return (-np.sign(ref_ret)).astype("float64")  # inverse to the reference's prior move


def _intermarket_difference(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Trade the RESIDUAL against the reference, not the market factor both legs share.

    Requires the reference's RANGE as well as its close: each leg is normalised by its own ATR
    before the subtraction, which is what makes a fixed threshold mean the same thing on a
    BTC/ETH pair and on a BTC/altcoin pair whose volatilities differ several-fold. A close-only
    reference degrades to flat rather than silently dropping the normalisation -- an unnormalised
    difference is a report of which symbol is more volatile, not a relative-value signal.
    """
    if s.ref_close is None or s.ref_high is None or s.ref_low is None:
        return np.zeros(len(s), dtype="float64")   # honest: needs the reference's range
    d = intermarket_difference(
        s.high, s.low, s.close, s.ref_high, s.ref_low, s.ref_close,
        lookback=int(p["lookback"]),
    )
    return threshold_revert(d, threshold=float(p["threshold"]))


def _carry(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    # Proxy: persistent long-horizon drift (true carry needs swap/rate data the feed lacks).
    return momentum_positions(_bars(s), lookback=int(p["lookback"]))


def _regime_transition(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    rets = np.zeros(len(s), dtype="float64")
    rets[1:] = s.close[1:] / s.close[:-1] - 1.0
    vw = int(p["vol_window"])
    vol = np.array([rets[max(0, i - vw + 1): i + 1].std() if i >= vw else np.nan
                    for i in range(len(rets))], dtype="float64")
    rising = np.zeros(len(vol), dtype=bool)
    rising[1:] = np.nan_to_num(vol[1:], nan=0.0) > np.nan_to_num(vol[:-1], nan=0.0)
    trend = trend_positions(_bars(s), fast=int(p["trend"]), slow=int(p["trend"]) * 3)
    return (trend * rising).astype("float64")


def _liquidity(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    # Fade extreme moves (liquidity provision after a shock).
    return mean_reversion_positions(_bars(s), window=int(p["window"]), z_entry=p["z_entry"])


def _risk_premia(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    return np.ones(len(s), dtype="float64")  # persistent long exposure (premium harvest)


def _funding_stress_reversal(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Fade leverage stress: extreme/persistent perp funding marks over-crowded positioning that
    mean-reverts after the stress. Positive funding (longs paying) -> short; negative -> long.

    Level-3 crypto signal; degrades to flat without funding data (honest, like cross_asset).
    """
    if s.funding is None:
        return np.zeros(len(s), dtype="float64")
    f = np.nan_to_num(s.funding, nan=0.0)
    w = int(p["window"])
    z = np.zeros(len(f), dtype="float64")
    for i in range(w, len(f)):
        seg = f[i - w + 1: i + 1]
        sd = seg.std()
        z[i] = (f[i] - seg.mean()) / sd if sd > 0 else 0.0
    thr = p["z_entry"]
    return np.where(z > thr, -1.0, np.where(z < -thr, 1.0, 0.0)).astype("float64")


@dataclass(frozen=True)
class GeneratorSpec:
    family: Family
    subtype: str
    fn: PositionFn
    mechanism: MechanismType
    edge_source: str
    failure_modes: list[str]
    param_variants: list[dict[str, float]] = field(default_factory=lambda: [{}])


_B, _S, _R, _L = (
    MechanismType.BEHAVIORAL, MechanismType.STRUCTURAL, MechanismType.RISK_PREMIUM,
    MechanismType.LIQUIDITY,
)

GENERATORS: tuple[GeneratorSpec, ...] = (
    GeneratorSpec(Family.TREND, "ma_cross", _trend, _B, "trend persistence / underreaction",
                  ["trendless chop", "whipsaw in range"],
                  [{"fast": 20, "slow": 50}, {"fast": 10, "slow": 30}, {"fast": 50, "slow": 200}]),
    GeneratorSpec(Family.MOMENTUM, "time_series_mom", _momentum, _B, "momentum continuation",
                  ["sharp reversals", "crowding"],
                  [{"lookback": 10}, {"lookback": 20}, {"lookback": 40}]),
    GeneratorSpec(Family.BREAKOUT, "donchian", _breakout, _S, "range breakout / stop cascades",
                  ["false breakouts"], [{"window": 20}, {"window": 55}]),
    GeneratorSpec(Family.VOLATILITY_COMPRESSION, "squeeze_breakout", _vol_compression, _S,
                  "volatility compression precedes expansion", ["failed expansion"],
                  [{"window": 20, "vol_window": 20}]),
    GeneratorSpec(Family.VOLATILITY_EXPANSION, "vol_trend", _vol_expansion, _S,
                  "trend strengthens as volatility expands", ["vol spike reversal"],
                  [{"vol_window": 20, "lookback": 20}]),
    GeneratorSpec(Family.MEAN_REVERSION, "zscore_fade", _mean_reversion, _L,
                  "mean reversion / liquidity provision", ["trending breakout"],
                  [{"window": 20, "z_entry": 2.0}, {"window": 50, "z_entry": 2.5}]),
    GeneratorSpec(Family.SESSION, "session_open_mom", _session, _S,
                  "order-flow concentration at session open",
                  ["needs intraday clock", "session drift varies"],
                  [{"open_hour": 8, "span": 4, "lookback": 1},
                   {"open_hour": 14, "span": 4, "lookback": 1}]),
    GeneratorSpec(Family.CROSS_ASSET, "inverse_reference", _cross_asset, _S,
                  "cross-market transmission (e.g. USD -> FX)",
                  ["needs a reference instrument", "correlation breakdown"], [{"lookback": 1}]),
    GeneratorSpec(Family.CROSS_ASSET, "intermarket_difference", _intermarket_difference, _S,
                  "relative-value dispersion: what outperforms its reference tends to continue "
                  "outperforming, and the shared market factor is differenced away",
                  ["needs the reference's range, not just its close",
                   "the residual is smaller than either leg, so costs bite harder",
                   "a correlation break makes the difference a second directional bet"],
                  [{"lookback": 24, "threshold": 0.25},
                   {"lookback": 12, "threshold": 0.30},
                   {"lookback": 48, "threshold": 0.25}]),
    GeneratorSpec(Family.CARRY, "drift_proxy", _carry, _R,
                  "risk-premium / funding drift (PROXY: no swap/rate data)",
                  ["proxy only, not true carry", "rate-regime change"], [{"lookback": 200}]),
    GeneratorSpec(Family.REGIME_TRANSITION, "vol_onset_trend", _regime_transition, _S,
                  "regime persistence after a volatility break", ["false transition calls"],
                  [{"vol_window": 20, "trend": 20}]),
    GeneratorSpec(Family.LIQUIDITY, "shock_fade", _liquidity, _L,
                  "liquidity provision after a shock", ["trending continuation"],
                  [{"window": 20, "z_entry": 2.0}]),
    GeneratorSpec(Family.LIQUIDITY, "funding_stress_reversal", _funding_stress_reversal, _L,
                  "fade crowded perp leverage (funding stress) -> mean reversion (PROXY: crypto)",
                  ["needs funding data", "persistent one-way funding in strong trends"],
                  [{"window": 30, "z_entry": 1.5}, {"window": 14, "z_entry": 2.0}]),
    GeneratorSpec(Family.RISK_PREMIA, "persistent_long", _risk_premia, _R,
                  "harvest the long-run risk premium", ["secular bear", "crash"], [{}]),
)


# --- 2026-08-04 CONTENT EXPANSION (docs/research/NEW_FAMILY_GENERATORS_PREREGISTRATION.md) ----
#
# Seven families pre-registered BEFORE running. The ICT three reuse libs/ict's lag-honest
# detectors verbatim (confirmed swings, settled-on-the-firing-bar semantics) rather than
# re-deriving them -- one definition, one place. Every function here is causal by construction:
# nothing reads past its own bar, and the truncation-invariance test in
# tests/autodiscovery/test_new_family_generators.py pins that mechanically.

def _hold_positions(signal: np.ndarray, hold: int) -> np.ndarray:
    """Event signal (+1/-1 on the firing bar) -> position held `hold` bars; refire refreshes."""
    pos = np.zeros(len(signal))
    cur, left = 0.0, 0
    for i, sig in enumerate(signal):
        if sig != 0 and not np.isnan(sig):
            cur, left = float(np.sign(sig)), hold
        if left > 0:
            pos[i] = cur
            left -= 1
        else:
            cur = 0.0
    return pos


def _prior_extrema(high: np.ndarray, low: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """N-bar high/low EXCLUDING the current bar (same discipline as the intraday engine)."""
    from numpy.lib.stride_tricks import sliding_window_view
    hi = np.full(len(high), np.nan)
    lo = np.full(len(low), np.nan)
    if len(high) > w:
        hi[w:] = sliding_window_view(high, w)[:-1].max(axis=1)
        lo[w:] = sliding_window_view(low, w)[:-1].min(axis=1)
    return hi, lo


def _wyckoff(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Spring: pierce the N-range low, close back inside -> long. Upthrust mirrored short.
    Distinct from ict_sweep_reversal on purpose: the level here is the RANGE extreme, not a
    confirmed swing point -- two different definitions of where the resting liquidity sat."""
    w, hold = int(p["window"]), int(p["hold"])
    hi_n, lo_n = _prior_extrema(s.high, s.low, w)
    with np.errstate(invalid="ignore"):
        spring = (s.low < lo_n) & (s.close > lo_n)
        upthrust = (s.high > hi_n) & (s.close < hi_n)
    return _hold_positions(np.where(spring, 1.0, np.where(upthrust, -1.0, 0.0)), hold)


def _rolling_vwap(s: MarketSeries, w: int) -> np.ndarray:
    tp = (s.high + s.low + s.close) / 3.0
    v = s.volume if s.volume is not None else np.ones(len(tp))
    pv, vv = np.cumsum(tp * v), np.cumsum(v)
    out = np.full(len(tp), np.nan)
    out[w:] = (pv[w:] - pv[:-w]) / np.maximum(vv[w:] - vv[:-w], 1e-12)
    return out


def _vwap_reversion(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Fade a z-stretched deviation from rolling VWAP; flat inside the band. State, not event:
    the position persists while the stretch does, which is what the mechanism claims."""
    import pandas as pd
    w, z = int(p["window"]), float(p["z"])
    dev = s.close - _rolling_vwap(s, w)
    sd = pd.Series(dev).rolling(w).std().to_numpy()
    with np.errstate(invalid="ignore"):
        sig = np.where(dev > z * sd, -1.0, np.where(dev < -z * sd, 1.0, 0.0))
    return np.nan_to_num(sig)


def _vwap_trend(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    w = int(p["window"])
    with np.errstate(invalid="ignore"):
        return np.asarray(np.nan_to_num(np.sign(s.close - _rolling_vwap(s, w))))


def _supply_demand(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Impulsive departure (range > k*ATR20, directional body) marks the prior bar as the base;
    the FIRST retest of that base zone within 60 bars re-enters in the departure direction."""
    import pandas as pd
    k, hold = float(p["k"]), int(p["hold"])
    n = len(s.close)
    prev = np.concatenate([[s.close[0]], s.close[:-1]])
    tr = np.maximum(s.high - s.low, np.maximum(np.abs(s.high - prev), np.abs(s.low - prev)))
    a = pd.Series(tr).rolling(20).mean().to_numpy()
    rng = s.high - s.low
    body = s.close - prev
    with np.errstate(invalid="ignore"):
        imp_up = (rng > k * a) & (body > 0)
        imp_dn = (rng > k * a) & (body < 0)
    sig = np.zeros(n)
    for i in np.flatnonzero(imp_up | imp_dn):
        if i < 1 or i + 2 >= n:
            continue
        zlo, zhi = float(s.low[i - 1]), float(s.high[i - 1])
        d = 1.0 if imp_up[i] else -1.0
        for j in range(int(i) + 2, min(int(i) + 62, n)):
            touched = (s.low[j] <= zhi) if d > 0 else (s.high[j] >= zlo)
            if touched:
                sig[j] = d
                break
    return _hold_positions(sig, hold)


def _ict_frame(s: MarketSeries) -> Any:
    """OHLC frame for the libs/ict detectors. `Any` rather than pd.DataFrame: pandas is imported
    lazily here (the autodiscovery import path stays numpy-only for callers that never touch
    ICT), so the annotation must not force a module-scope pandas import."""
    import pandas as pd
    return pd.DataFrame({"high": s.high, "low": s.low, "close": s.close})


def _ict_fvg(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    from libs.ict.patterns import fair_value_gap
    return _hold_positions(fair_value_gap(_ict_frame(s)).to_numpy(), int(p["hold"]))


def _ict_sweep(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    from libs.ict.patterns import liquidity_sweep
    return _hold_positions(
        liquidity_sweep(_ict_frame(s), confirm=int(p["confirm"])).to_numpy(), int(p["hold"]))


def _ict_mss(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    from libs.ict.patterns import market_structure_shift
    return _hold_positions(
        market_structure_shift(_ict_frame(s), confirm=int(p["confirm"])).to_numpy(),
        int(p["hold"]))


NEW_FAMILY_GENERATORS: tuple[GeneratorSpec, ...] = (
    GeneratorSpec(Family.LIQUIDITY, "wyckoff_spring", _wyckoff, _S,
                  "absorption at a failed range break (spring/upthrust)",
                  ["genuine breakout regimes", "thin ranges"],
                  [{"window": w, "hold": h} for w in (20, 40) for h in (5, 10)]),
    GeneratorSpec(Family.MEAN_REVERSION, "vwap_reversion", _vwap_reversion, _L,
                  "inventory pressure reverts stretched VWAP deviation",
                  ["trending markets", "volume droughts"],
                  [{"window": w, "z": z} for w in (20, 50) for z in (1.5, 2.5)]),
    GeneratorSpec(Family.TREND, "vwap_trend", _vwap_trend, _S,
                  "side of VWAP = side of institutional inventory",
                  ["chop around VWAP", "regime flips"],
                  [{"window": w} for w in (20, 50)]),
    GeneratorSpec(Family.LIQUIDITY, "supply_demand_retest", _supply_demand, _S,
                  "unfilled orders at the base of an impulsive departure",
                  ["zone invalidation", "stale zones"],
                  [{"k": k, "hold": h} for k in (1.5, 2.0) for h in (5, 10)]),
    GeneratorSpec(Family.MOMENTUM, "ict_fvg_follow", _ict_fvg, _S,
                  "three-bar imbalance marks displacement; follow it",
                  ["gap fills against", "low-vol microstructure"],
                  [{"hold": h} for h in (3, 8)]),
    GeneratorSpec(Family.LIQUIDITY, "ict_sweep_reversal", _ict_sweep, _L,
                  "raid through equal highs/lows that closes back is engineered liquidity",
                  ["real breakouts", "cascading stops"],
                  [{"confirm": c, "hold": h} for c in (2, 3) for h in (5, 10)]),
    GeneratorSpec(Family.TREND, "ict_mss_follow", _ict_mss, _S,
                  "market-structure shift starts the new leg",
                  ["false shifts in chop", "late entries"],
                  [{"confirm": c, "hold": h} for c in (2, 3) for h in (10, 20)]),
)

GENERATORS = (*GENERATORS, *NEW_FAMILY_GENERATORS)


def planned_hypotheses(
    symbols: Sequence[str], *, families: Sequence[Family] | None = None
) -> list[tuple[Hypothesis, GeneratorSpec]]:
    """Expand the fixed generator set x param variants x symbols into declared hypotheses.

    ``families`` restricts the universe to a focused set (committee T0): cutting crowded
    price-pattern families lowers the cumulative trial count and the deflation drag on the
    economically-grounded families that matter. ``None`` keeps all twelve.
    """
    allowed = set(families) if families is not None else None
    out: list[tuple[Hypothesis, GeneratorSpec]] = []
    for spec in GENERATORS:
        if allowed is not None and spec.family not in allowed:
            continue
        for variant in spec.param_variants:
            for symbol in symbols:
                hyp = Hypothesis(
                    family=spec.family, subtype=spec.subtype, symbol=symbol, params=dict(variant),
                    mechanism=spec.mechanism, edge_source=spec.edge_source,
                    failure_modes=list(spec.failure_modes),
                )
                out.append((hyp, spec))
    return out
