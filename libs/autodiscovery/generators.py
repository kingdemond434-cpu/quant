"""Economically-grounded, backtestable generators for all 12 pre-registered hypothesis FAMILIES.

Each generator is a deterministic, causal (lag-1) rule with a declared mechanism TYPE, edge
source, and expected failure modes — no random features, no brute-force mining. The 6 price-pattern
families reuse the Stage-13.5 strategy primitives; the rest are implemented here. Families that
need data the OHLC feed may lack (cross-asset reference, true carry/swap rates) degrade honestly to
flat and declare the limitation in their failure modes, rather than fabricating a signal.

=================================================================================================
A FAMILY IS NOT AN ECONOMIC MECHANISM. READ THIS BEFORE COUNTING ANYTHING IN THIS FILE.
=================================================================================================
``Family`` is the desk's pre-registered SEARCH-BUDGET PARTITION and a load-bearing runtime key. It
is NOT a claim about who is on the other side of the trade:

  * ``orchestrator._family_trials`` deflates each candidate's DSR against ITS OWN family's
    pre-registered trial budget and ITS OWN family's Sharpe dispersion, so which family a spec
    sits in sets the statistical bar applied to every OTHER spec in that family;
  * ``memory.content_hash`` is family+subtype+symbol+params, so the family string is part of every
    persisted candidate's dedup identity and of ``store.family_counts()`` — the prior tally the
    budget wall reads;
  * ``prioritization.prioritize`` orders the campaign by ``FAMILY_PRIORITY``;
  * ``planned_hypotheses(families=...)`` selects the generation universe (committee T0;
    ``scripts/smoke_orchestration.py`` asks for carry/cross_asset/momentum BY NAME).

MOVING A SPEC BETWEEN FAMILIES IS THEREFORE A GATE CHANGE, NOT A RENAME. The labels below are
frozen for exactly that reason. The honest reading of a family name is: the FEATURE CONSTRUCTION
and the error budget it is charged to. It never names the payer.

THE ECONOMIC MECHANISM — who pays, and why they cannot stop — is owned by ONE place,
``libs/research/mechanism_census.CONSTRUCTION_CLASS``, and this module DEFERS to it. Use
:func:`census_class` and :func:`mechanism_class_counts` for any diversity, coverage or
"how many mechanisms have we tested" count. ``spec.family`` must never be counted as a mechanism;
:data:`FAMILY_MECHANISM_DIVERGENCE` records, in code, every place where the two disagree, and
``tests/autodiscovery/test_generator_taxonomy_fence.py`` fails if that record ever drifts.

MEASURED 2026-08-05, which is why this warning sits at the top of the file:

  * ``scripts/measure_cross_mechanism_corr.py``: ``liquidity/shock_fade`` vs
    ``mean_reversion/zscore_fade`` correlate at **+0.953**; ``momentum/time_series_mom`` vs
    ``trend/vwap_trend`` at **+0.955**. Different families, one trade.
  * ``scripts/run_mechanism_census.py``: the 44-candidate maximum-power campaign's twelve declared
    families resolve to FOUR economic classes — price_continuation 20,
    liquidity_provision_immediacy 19, relative_value_convergence 4, market_risk_premium 1 —
    effective classes 2.787, diversity 0.139. The full 21-spec library resolves to FIVE:
    price_continuation 11, liquidity_provision_immediacy 6, relative_value_convergence 2,
    positioning_crowding_unwind 1, market_risk_premium 1.
  * 2026-08-14 adds ``derivative_carry_basis`` (true carry: reads funding/basis) and
    ``taker_flow`` (informed order flow: reads taker_buy_frac) — the first two generators whose
    inputs come from Level-3 perp data, taking the library's distinct mechanism classes from five
    to seven.
  * Cross-mechanism N_eff is 4.08 against the ~100 a weak-edge portfolio needs, and the binding
    constraint is DISTINCT MECHANISM SUPPLY. Reading 12 families as 12 mechanisms overstates that
    supply by better than 2x and makes repetition look like exploration.

THE MAXIMUM-POWER CAMPAIGN RAN NO TRUE CARRY TEST UNTIL 2026-08-14, and this file is why —
then ``derivative_carry_basis`` closed the gap.
``Family.CARRY`` holds two generators. ``drift_proxy`` is ``momentum_positions(lookback=200)`` on
OHLC bars — long-horizon price continuation; no funding rate, no swap rate and no basis appears
anywhere in its inputs, so the census files it under ``price_continuation``. A true carry test
(``derivative_carry_basis``: the leveraged long who pays funding every interval to hold exposure
he will not fund with cash) needs swap/funding/basis data, which the OHLC feed did not carry —
and which the crypto lake now does. The ``derivative_carry_basis`` spec added 2026-08-14 reads the
funding rate (and basis, when present) into its position rule: it IS carry evidence. Nothing in
``drift_proxy`` may be reported as carry coverage.

Scoped precisely, because the opposite overstatement is just as bad: the desk DOES hold real
`derivative_carry_basis` evidence elsewhere — funding/basis screen artifacts and a live
cash-and-carry book, which the census reads and marks TESTED-DEEP. The zero above is about THIS
generator campaign, which is the run whose "44 mechanisms" figure was being quoted.
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
from libs.research.mechanism_census import CONSTRUCTION_CLASS
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


def _drift_proxy(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Long-horizon price continuation. THIS IS MOMENTUM, NOT CARRY — the name says so now.

    It was called ``_carry`` until 2026-08-05 while being byte-for-byte the ``_momentum`` rule at a
    longer lookback, which is how a function that never reads a funding rate came to be counted as
    the desk's carry coverage. Its economic class is ``price_continuation`` (census ground truth),
    it shares an implementation with ``time_series_mom``, and true carry — a leveraged long paying
    funding or basis every interval — needs swap/funding/basis data the OHLC feed does not carry.
    The ``Family.CARRY`` label on its spec is the frozen budget partition, not a mechanism claim.
    """
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


def _derivative_carry_basis(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """TRUE CARRY: hold the perp leg that is PAID funding/basis, not the side price momentum favors.

    This is the ``derivative_carry_basis`` test the census has recorded as never run: the leveraged
    long who pays funding every interval to hold exposure he will not fund with cash is on the
    WRONG side; the desk should be on the side the funding stream pays. Positive funding (longs
    pay) -> short the perp; negative funding (shorts pay) -> long. The same sign logic applies to
    basis (perp mark vs spot): positive basis -> perp rich vs spot -> short; negative -> long.

    Level-3 signal; degrades to flat without funding OR basis data (honest, like cross_asset).
    """
    if s.funding is None:
        return np.zeros(len(s), dtype="float64")
    f = np.nan_to_num(s.funding, nan=0.0)
    w = int(p["window"])
    carry = np.full(len(f), 0.0, dtype="float64")
    for i in range(w, len(f)):
        seg = f[i - w + 1: i + 1]
        carry[i] = seg.mean() if len(seg) else 0.0
    # long when funding is paid TO longs (negative rate), short when longs pay (positive rate).
    pos = np.where(carry < -float(p["entry"]), 1.0,
                   np.where(carry > float(p["entry"]), -1.0, 0.0)).astype("float64")
    if s.basis is not None:
        b = np.nan_to_num(s.basis, nan=0.0)
        bw = int(p.get("basis_window", w))
        bmean = np.full(len(b), 0.0, dtype="float64")
        for i in range(bw, len(b)):
            bseg = b[i - bw + 1: i + 1]
            bmean[i] = bseg.mean() if len(bseg) else 0.0
        # basis confirmation: only trade when basis agrees with the funding-side read.
        agree = (bmean < -float(p.get("basis_entry", 0.0))) | (bmean > float(p.get("basis_entry", 0.0)))
        pos = np.where(agree, pos, 0.0)
    return pos


def _taker_flow(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Order-flow persistence: follow the aggressive (taker) side when it is one-sided.

    ``taker_buy_frac`` is the share of bar volume executed by aggressive BUYERS. A sustained
    reading above 0.5 is net aggressive demand; below 0.5 is net aggressive supply. Momentum
    variant follows it; the ``fade`` variant fades extremes (counterparty liquidity provision).

    Level-3 signal; degrades to flat without taker data (honest, like cross_asset).
    """
    if s.taker_buy_frac is None:
        return np.zeros(len(s), dtype="float64")
    t = np.nan_to_num(s.taker_buy_frac, nan=0.5)
    w = int(p["window"])
    flow = np.full(len(t), 0.5, dtype="float64")
    for i in range(w, len(t)):
        seg = t[i - w + 1: i + 1]
        flow[i] = seg.mean() if len(seg) else 0.5
    offset = float(p.get("offset", 0.05))
    mode = int(p.get("mode", 1.0))
    if mode == 0:
        # fade extremes: buy when flow is far below neutral, sell when far above.
        return np.where(flow < 0.5 - offset, 1.0,
                        np.where(flow > 0.5 + offset, -1.0, 0.0)).astype("float64")
    return np.where(flow > 0.5 + offset, 1.0,
                    np.where(flow < 0.5 - offset, -1.0, 0.0)).astype("float64")


def _funding_taker_interaction(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """FUNDING × TAKER interaction: fade funding stress ONLY when aggressive flow confirms.

    Positive funding (longs paying) + aggressive buying (taker_buy_frac > 0.5) = crowded longs
    being squeezed -> mean reversion stronger. Negative funding + aggressive selling = crowded
    shorts -> reversion. Only trades when both signals align.

    Level-3 signal; degrades to flat without funding OR taker data.
    """
    if s.funding is None or s.taker_buy_frac is None:
        return np.zeros(len(s), dtype="float64")
    f = np.nan_to_num(s.funding, nan=0.0)
    t = np.nan_to_num(s.taker_buy_frac, nan=0.5)
    w = int(p["window"])
    z_fund = np.zeros(len(f), dtype="float64")
    z_flow = np.zeros(len(t), dtype="float64")
    for i in range(w, len(f)):
        fseg = f[i - w + 1: i + 1]
        tseg = t[i - w + 1: i + 1]
        fd = fseg.std()
        td = tseg.std()
        z_fund[i] = (f[i] - fseg.mean()) / fd if fd > 0 else 0.0
        z_flow[i] = (tseg.mean() - 0.5) / td if td > 0 else 0.0
    thr = float(p.get("z_entry", 1.5))
    # Both z-scores must exceed threshold and agree in direction
    align = (z_fund > thr) & (z_flow > float(p.get("flow_thr", 0.5)))  # pos funding + buy pressure
    align |= (z_fund < -thr) & (z_flow < -float(p.get("flow_thr", 0.5)))  # neg funding + sell pressure
    pos = np.where(z_fund > thr, -1.0, np.where(z_fund < -thr, 1.0, 0.0)).astype("float64")
    return np.where(align, pos, 0.0)


def _basis_funding_interaction(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """BASIS × FUNDING interaction: true carry with basis convergence + funding direction.

    The carry trade (derivative_carry_basis) gets confirmation from basis: negative basis (perp
    cheap) + negative funding (longs paid) = strong long signal. Positive basis + positive
    funding = strong short. Both must align.

    Level-3 signal; degrades to flat without basis OR funding data.
    """
    if s.basis is None or s.funding is None:
        return np.zeros(len(s), dtype="float64")
    b = np.nan_to_num(s.basis, nan=0.0)
    f = np.nan_to_num(s.funding, nan=0.0)
    w = int(p["window"])
    b_mean = np.full(len(b), 0.0, dtype="float64")
    f_mean = np.full(len(f), 0.0, dtype="float64")
    for i in range(w, len(b)):
        bseg = b[i - w + 1: i + 1]
        fseg = f[i - w + 1: i + 1]
        b_mean[i] = bseg.mean() if len(bseg) else 0.0
        f_mean[i] = fseg.mean() if len(fseg) else 0.0
    entry = float(p.get("entry", 0.0002))
    # Both basis and funding must agree on direction
    long_cond = (b_mean < -entry) & (f_mean < -entry)
    short_cond = (b_mean > entry) & (f_mean > entry)
    return np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0)).astype("float64")


def _basis_taker_interaction(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """BASIS × TAKER interaction: basis mean-reversion when aggressive flow opposes it.

    Negative basis (perp cheap) + aggressive buying (taker_buy_frac > 0.5) = longs absorbing
    the discount -> basis convergence long. Positive basis + aggressive selling = shorts
    absorbing premium -> basis convergence short. Counter-trend flow confirms the reversion.

    Level-3 signal; degrades to flat without basis OR taker data.
    """
    if s.basis is None or s.taker_buy_frac is None:
        return np.zeros(len(s), dtype="float64")
    b = np.nan_to_num(s.basis, nan=0.0)
    t = np.nan_to_num(s.taker_buy_frac, nan=0.5)
    w = int(p["window"])
    b_mean = np.full(len(b), 0.0, dtype="float64")
    t_mean = np.full(len(t), 0.5, dtype="float64")
    for i in range(w, len(b)):
        bseg = b[i - w + 1: i + 1]
        tseg = t[i - w + 1: i + 1]
        b_mean[i] = bseg.mean() if len(bseg) else 0.0
        t_mean[i] = tseg.mean() if len(tseg) else 0.5
    offset = float(p.get("offset", 0.05))
    # Basis negative + buying = long; basis positive + selling = short
    long_cond = (b_mean < -float(p.get("basis_thr", 0.0001))) & (t_mean > 0.5 + offset)
    short_cond = (b_mean > float(p.get("basis_thr", 0.0001))) & (t_mean < 0.5 - offset)
    return np.where(long_cond, 1.0, np.where(short_cond, -1.0, 0.0)).astype("float64")


@dataclass(frozen=True)
class GeneratorSpec:
    """One generator, its budget partition, and its declared economics.

    ``family`` is the SEARCH-BUDGET PARTITION (see the module docstring): a runtime key that sets
    the DSR trial wall, the dedup identity and the campaign ordering. It is not the economic
    mechanism and must never be counted as one — :func:`census_class` is the authority for that.

    ``mechanism`` is the CRO's four-way prior type (structural / behavioral / risk-premium /
    liquidity), declared before testing. It is a label with no gate wired to its value; it is
    still held to the truth, because a declared prior that contradicts the implementation is the
    same overstatement one axis down from the family label.
    """

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
    # DECLARED carry, IS momentum. The Family.CARRY label is the frozen budget partition and is
    # NOT a claim that a carry test was run -- see FAMILY_MECHANISM_DIVERGENCE below. Its
    # MechanismType read RISK_PREMIUM until 2026-08-05, which was the same overstatement one axis
    # down: this rule is momentum_positions(lookback=200) on OHLC bars, sharing an implementation
    # with `time_series_mom`, so it is BEHAVIORAL for the same reason `time_series_mom` is.
    GeneratorSpec(Family.CARRY, "drift_proxy", _drift_proxy, _B,
                  "long-horizon price continuation at a 200-bar lookback. NOT CARRY: no funding, "
                  "swap or basis input exists in this generator -- census class "
                  "price_continuation, never derivative_carry_basis",
                  ["this is momentum wearing a carry label, so it is evidence about price "
                   "continuation and about nothing else",
                   "sharp reversals and crowding, exactly as for time_series_mom"],
                  [{"lookback": 200}]),
    # TRUE CARRY -- closes the census gap "the desk has run ZERO true carry tests in its
    # maximum-power campaign" (drift_proxy divergence record above). This spec is the first
    # generator that actually reads a funding rate (and, when present, basis) into its position
    # rule, so the CARRY family finally carries derivative_carry_basis census class evidence.
    GeneratorSpec(Family.CARRY, "derivative_carry_basis", _derivative_carry_basis, _R,
                  "harvest the funding stream: hold the perp leg that is PAID funding/basis "
                  "(positive funding -> short, negative -> long)",
                  ["needs funding data (absent -> flat)",
                   "funding can stay one-way in strong trends, and the carry flips sign slowly",
                   "basis disagreement gates the trade flat when it contradicts funding"],
                  [{"window": w, "entry": e, "basis_window": w, "basis_entry": 0.0}
                   for w in (7, 14, 30, 60) for e in (0.0001, 0.00015, 0.0002, 0.0003, 0.0005)]
                   + [{"window": w, "entry": e, "basis_window": w, "basis_entry": b}
                      for w in (14, 30) for e in (0.00015, 0.0002) for b in (0.0001, 0.0002)]),
    GeneratorSpec(Family.LIQUIDITY, "taker_flow", _taker_flow, _L,
                  "order-flow persistence: follow (or fade) sustained aggressive taker demand",
                  ["needs taker_buy_frac data (absent -> flat)",
                   "flow is noisy at low volume; follow variant whipsaws in chop"],
                  [{"window": w, "offset": o, "mode": m}
                   for w in (10, 20, 30, 50) for o in (0.03, 0.05, 0.08, 0.10) for m in (1.0, 0.0)]),
    # CROSS-AXIS INTERACTIONS -- genuine new mechanisms using multiple Level-3 columns together
    GeneratorSpec(Family.LIQUIDITY, "funding_taker_interaction", _funding_taker_interaction, _L,
                  "funding stress reversion confirmed by aggressive taker flow alignment",
                  ["needs funding AND taker_buy_frac data (absent -> flat)",
                   "both signals must agree; noisy when flow is weak"],
                  [{"window": w, "z_entry": z, "flow_thr": ft}
                   for w in (14, 30, 50) for z in (1.0, 1.5, 2.0) for ft in (0.3, 0.5, 0.7)]),
    GeneratorSpec(Family.CARRY, "basis_funding_interaction", _basis_funding_interaction, _R,
                  "true carry with basis+funding alignment: both must pay the same side",
                  ["needs basis AND funding data (absent -> flat)",
                   "both must agree on direction; no single-column fallback"],
                  [{"window": w, "entry": e}
                   for w in (14, 30, 60) for e in (0.0001, 0.00015, 0.0002, 0.0003)]),
    GeneratorSpec(Family.LIQUIDITY, "basis_taker_interaction", _basis_taker_interaction, _L,
                  "basis mean-reversion confirmed by counter-trend aggressive flow",
                  ["needs basis AND taker_buy_frac data (absent -> flat)",
                   "flow must oppose the basis direction (counter-trend confirmation)"],
                  [{"window": w, "offset": o, "basis_thr": bt}
                   for w in (14, 30, 50) for o in (0.03, 0.05, 0.08) for bt in (0.00005, 0.0001, 0.0002)]),
    GeneratorSpec(Family.REGIME_TRANSITION, "vol_onset_trend", _regime_transition, _S,
                  "regime persistence after a volatility break", ["false transition calls"],
                  [{"vol_window": 20, "trend": 20}]),
    GeneratorSpec(Family.LIQUIDITY, "shock_fade", _liquidity, _L,
                  "liquidity provision after a shock", ["trending continuation"],
                  [{"window": 20, "z_entry": 2.0}]),
    # Filed under LIQUIDITY, but its payer is the liquidated leveraged trader, not the immediacy
    # demander: census class `positioning_crowding_unwind`, not `liquidity_provision_immediacy`.
    # Recorded in FAMILY_MECHANISM_DIVERGENCE below; the family label stays because it is the
    # budget partition. This is the ONE spec in the library whose mechanism the four price-only
    # classes do not already own, which is why its label mattering is not a pedantic point.
    GeneratorSpec(Family.LIQUIDITY, "funding_stress_reversal", _funding_stress_reversal, _L,
                  "fade crowded perp leverage (funding stress) -> mean reversion (PROXY: crypto)",
                  ["needs funding data", "persistent one-way funding in strong trends",
                   "census class is positioning_crowding_unwind, NOT liquidity provision: the "
                   "payer is a trader liquidated on the venue's schedule"],
                  [{"window": w, "z_entry": z}
                   for w in (7, 14, 21, 30, 50) for z in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5)]),
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


# =================================================================================================
# FAMILY (budget partition)  vs  ECONOMIC MECHANISM (who pays).  The census is the authority.
# =================================================================================================
# Nothing below changes a signal, a parameter, a gate or a threshold. It exists so the two axes
# can never again be read as one number, and so that the corrected count is available in code
# rather than only after somebody remembers to run the census.

#: Families whose NAME is itself an economic claim — it names a PAYER — mapped to the census class
#: a fair reader would take that name to assert.
#:
#: The other eight families are deliberately ABSENT, and their absence is the substantive call.
#: `trend`, `momentum`, `breakout`, `volatility_expansion`, `volatility_compression`,
#: `mean_reversion`, `session` and `regime_transition` name a WAY OF WRITING A NUMBER DOWN — a
#: moving-average relationship, a z-score band, a clock gate — not a party who is compelled to
#: pay. They therefore cannot contradict the census: `mean_reversion/zscore_fade` classifying as
#: `liquidity_provision_immediacy` is the census supplying a payer the family name never claimed,
#: which is information, not a conflict. Only a family that asserts a payer can be wrong about one.
FAMILY_ECONOMIC_CLAIM: dict[Family, str] = {
    Family.CARRY: "derivative_carry_basis",
    Family.CROSS_ASSET: "relative_value_convergence",
    Family.LIQUIDITY: "liquidity_provision_immediacy",
    Family.RISK_PREMIA: "market_risk_premium",
}

#: Every spec whose family NAME claims an economic mechanism the census does not grant it, keyed
#: by subtype. EXHAUSTIVE AND EXACT: the fence recomputes this set from the census and fails both
#: on a MISSING entry (a new mislabel shipped silently) and on a STALE one (a divergence that was
#: fixed, so the register would be lying in the other direction). Adding a row here is a
#: deliberate, reviewed act that costs a written reason naming the real class — it is not a
#: suppression, because the census keeps classifying the spec correctly either way.
FAMILY_MECHANISM_DIVERGENCE: dict[str, str] = {
    "drift_proxy": (
        "FILED `carry`, IS `price_continuation`. It is momentum_positions(lookback=200) on OHLC "
        "bars — no funding, swap or basis input exists in the generator. The family label is the "
        "frozen budget partition; counting it as carry coverage would credit the desk with a "
        "carry test it has never run. (True carry coverage now lives in the separate spec "
        "`derivative_carry_basis`, which reads funding and basis; `drift_proxy` itself remains "
        "price continuation and is not carry evidence.)"
    ),
    "funding_stress_reversal": (
        "FILED `liquidity`, IS `positioning_crowding_unwind`. Fading funding stress is a claim "
        "about a leveraged trader liquidated on the VENUE'S schedule, not about a warehouse being "
        "paid for immediacy. Counting it under liquidity provision would add a sixth member to a "
        "class already tested to exhaustion while hiding the library's only occupant of a class "
        "the price-only classes do not own."
    ),
    "taker_flow": (
        "FILED `liquidity`, IS `informed_order_flow`. Following (or fading) aggressive taker "
        "flow is a claim about the uninformed counterparty who fills an informed order and "
        "learns its information only after the price has already moved -- not about a warehouse "
        "being paid for immediacy. The LIQUIDITY family label is the frozen budget partition; "
        "the census class is the mechanism that pays."
    ),
    "funding_taker_interaction": (
        "FILED `liquidity`, IS `positioning_crowding_unwind`. Fading funding stress when "
        "aggressive taker flow confirms the crowding is a claim about leveraged traders being "
        "squeezed on the venue's schedule, not about a warehouse being paid for immediacy. The "
        "LIQUIDITY family label is the frozen budget partition; the census class is the "
        "mechanism that pays."
    ),
    "basis_taker_interaction": (
        "FILED `carry`, IS `informed_order_flow`. Basis mean-reversion confirmed by counter-trend "
        "aggressive flow is a claim about the uninformed counterparty absorbing the basis "
        "discount/premium, not about the leveraged long paying funding. The CARRY family label "
        "is the frozen budget partition; the census class is the mechanism that pays."
    ),
}


def census_class(spec: GeneratorSpec) -> str:
    """The AUTHORITATIVE economic mechanism class of a spec, read from the census.

    Deliberately a lookup and not a second taxonomy: ``libs/research/mechanism_census`` owns the
    merge/split calls, and a copy here would be a third answer to a question that already has two.
    A construction the census has never classified raises rather than defaulting — an unclassified
    generator must not be silently absorbed into whichever class looks closest, because that is
    coverage the desk does not have.
    """
    known = CONSTRUCTION_CLASS.get(spec.subtype)
    if known is None:
        raise KeyError(
            f"generator '{spec.subtype}' has no entry in "
            f"libs/research/mechanism_census.CONSTRUCTION_CLASS: classify it there (in the "
            f"census, which owns the taxonomy) before shipping it, or it will be counted as "
            f"mechanism supply that nobody has placed"
        )
    return known


def mechanism_class_counts(specs: Sequence[GeneratorSpec] | None = None) -> dict[str, int]:
    """Distinct-mechanism counts for a generator set — the ONLY supported way to count supply here.

    Counting ``spec.family`` instead reports 12 where this reports 5, which is the specific
    self-deception this block exists to remove.

    ``None`` means the live library. Resolved HERE rather than as a default argument, which would
    bind the tuple at import and quietly measure a stale library for anyone who appends to
    ``GENERATORS`` — a counter that reads the wrong set is the failure mode this file is about.
    """
    counts: dict[str, int] = {}
    for spec in GENERATORS if specs is None else specs:
        cls = census_class(spec)
        counts[cls] = counts.get(cls, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def family_mechanism_divergences(
    specs: Sequence[GeneratorSpec] | None = None,
) -> dict[str, tuple[str, str]]:
    """``subtype -> (class the family NAME claims, class the census ASSIGNS)`` where they differ.

    Computed, never declared: :data:`FAMILY_MECHANISM_DIVERGENCE` is the human record of this
    function's output and the fence asserts the two agree exactly. A family that makes no economic
    claim contributes nothing here, so a legitimate new feature family passes untouched while a
    spec parked under a payer-naming family it does not earn fails immediately.

    ``None`` means the live library, resolved at call time for the same reason as above.
    """
    out: dict[str, tuple[str, str]] = {}
    for spec in GENERATORS if specs is None else specs:
        claimed = FAMILY_ECONOMIC_CLAIM.get(spec.family)
        if claimed is None:
            continue
        actual = census_class(spec)
        if actual != claimed:
            out[spec.subtype] = (claimed, actual)
    return out


def planned_hypotheses(
    symbols: Sequence[str], *, families: Sequence[Family] | None = None
) -> list[tuple[Hypothesis, GeneratorSpec]]:
    """Expand the fixed generator set x param variants x symbols into declared hypotheses.

    ``families`` restricts the universe to a focused set (committee T0): cutting crowded
    price-pattern families lowers the cumulative trial count and the deflation drag on the
    economically-grounded families that matter. ``None`` keeps all twelve.

    TWELVE FAMILIES IS NOT TWELVE MECHANISMS. Restricting to k families restricts the BUDGET
    PARTITION, and buys distinct economic supply only insofar as the families chosen sit in
    different census classes — which mostly they do not (:func:`mechanism_class_counts`).
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
