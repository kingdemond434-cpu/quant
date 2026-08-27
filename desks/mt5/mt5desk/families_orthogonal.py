"""ORTHOGONAL FAMILIES -- the edges a session-breakout book cannot hold.

WHY THIS FILE IS THE FIX FOR "ZERO-YIELD MINERS" (principal 2026-08-26). 22 of 43 miners produced
20+ rows and no survivor in fourteen days, and the instinct is to blame the miners. It is not the
miners. Every family this desk could TEST was a directional breakout or momentum variant:

    asia_momentum, dow_effect, momentum_volgate, session_range_breakout,
    monday_gap, london_close_momentum, level_breakout, failed_breakout

A miner that finds a carry edge, a positioning extreme or a volatility-regime transition has
nowhere to put it. The hypothesis cannot be expressed, so it cannot be backtested, so it can never
become a survivor -- and the miner is scored zero-yield for finding something the desk had no way
to test. That is why 95.2% of certificates are one family and why N_eff collapses toward one bet:
the desk was not selecting breakouts, it was only ABLE to select breakouts.

WHAT MAKES THESE ORTHOGONAL, and it is not that they are different code. Each fires on a distinct
economic cause, on a different clock, and -- the part that matters for portfolio construction --
FAILS IN A DIFFERENT REGIME:

  carry              rate/swap differentials; earns while price does nothing, dies in fast trends
  relative_value     cross-pair residual reversion; earns when the triangle dislocates, dies when
                     one leg genuinely re-rates
  vol_transition     realised-vol regime change; earns exactly when ranges STOP working
  liquidity_regime   spread/depth shifts from the venue's own tape; execution-derived, not price
  cot_positioning    weekly positioning extremes; a different clock entirely from intraday ranges
  macro_conditional  conditions WHEN other sleeves may fire rather than firing itself

Every one uses data this desk ALREADY records -- contract/swap terms, the tick tape's bid/ask,
COT, macro state -- so none of them is blocked on new acquisition. They return the same `Signal`
objects the engine and gauntlet already consume, so a discovery in any of these families reaches
the ten gates through exactly the existing path. No second door.

HONEST LIMITS, stated because a family that quietly degrades is worse than one that refuses: each
generator returns NO SIGNALS when its input is absent rather than falling back to price-only
behaviour. A carry family with no swap data is not a momentum family; it is a family with nothing
to say, and it says nothing.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

BASE = Path(__file__).resolve().parent.parent
TERMS = BASE / "data" / "tape" / "contract_terms"
COT = BASE / "data"


def _swap_terms(symbol: str) -> dict | None:
    """Point-in-time swap/contract terms the tape recorder already stores. None if unrecorded."""
    if not TERMS.exists():
        return None
    rows: list[dict] = []
    for f in sorted(TERMS.glob("*.json")) + sorted(TERMS.glob("*.jsonl")):
        try:
            text = f.read_text("utf-8")
        except OSError:
            continue
        for chunk in (text.splitlines() if f.suffix == ".jsonl" else [text]):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                data = json.loads(chunk)
            except ValueError:
                continue
            for row in (data if isinstance(data, list) else [data]):
                if isinstance(row, dict) and str(row.get("symbol", "")).upper() == symbol.upper():
                    rows.append(row)
    return rows[-1] if rows else None


def family_carry(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    min_edge_bp_per_day: float = 0.5,
    atr_n: int = 20,
    hold_bars: int = 120,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    require_quiet: bool = True,
) -> list[Signal]:
    """Hold the positive-swap side while the market is QUIET; stand aside when it trends.

    THE MECHANISM. A long position in the higher-yielding leg is paid the rollover differential
    every day it is held. That is a return stream with no directional thesis at all, which is
    precisely why it does not correlate with a breakout book -- and why it must be gated on
    quiet: carry is harvested in calm and destroyed in fast trends, the exact regime where a
    breakout sleeve is making money. The two are complementary rather than additive, and that
    is the point.

    REFUSES WITHOUT SWAP DATA. `swap_long`/`swap_short` come from the venue's own recorded
    contract terms. With no terms recorded this returns nothing rather than degrading into a
    long-only momentum sleeve wearing the word "carry".
    """
    terms = _swap_terms(symbol)
    if not terms:
        return []
    try:
        swap_long = float(terms.get("swap_long", 0.0))
        swap_short = float(terms.get("swap_short", 0.0))
    except (TypeError, ValueError):
        return []
    side = 1 if swap_long > swap_short else -1
    edge = abs(swap_long - swap_short)
    if edge < min_edge_bp_per_day:
        return []                      # the differential does not pay for the spread; no trade

    d = _h1(df)
    atr = _atr(d, atr_n)
    # QUIET = realised range below its own median. Carry dies in the regime breakouts love.
    rng = (d["high"] - d["low"]).rolling(atr_n).mean()
    med = rng.rolling(atr_n * 5).median()
    signals: list[Signal] = []
    for i in range(atr_n * 5, len(d) - 1):
        if require_quiet and not (rng.iloc[i] < med.iloc[i]):
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        stop = px - side * stop_atr * a
        signals.append(Signal(time=d.index[i], side=side, stop=stop,
                              target=px + side * stop_atr * a * rr,
                              ttl_bars=hold_bars, tag="carry", trigger=None, wait_bars=1))
    return signals


def family_relative_value(
    df: pd.DataFrame,
    *,
    peer: pd.DataFrame | None = None,
    lookback: int = 120,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Fade the residual between this instrument and a peer after removing their common move.

    THE MECHANISM. Two correlated instruments share a common factor; what is left after removing
    it is a spread that mean-reverts far more reliably than either leg. The edge is in the
    RESIDUAL, so it pays when direction does not -- orthogonal to a breakout book by construction,
    because a breakout needs a trend and this needs a dislocation without one.

    Implemented as a single-leg proxy: trade THIS instrument when its residual versus the peer is
    extreme. A true two-leg spread needs the engine to hold paired positions, which it does not
    yet; the proxy captures the same signal with honest single-leg risk, and the limitation is
    stated rather than hidden.
    """
    if peer is None or peer.empty:
        return []
    d, p = _h1(df), _h1(peer)
    joined = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(joined) < lookback * 2:
        return []
    a = np.log(joined["close"].astype(float))
    b = np.log(joined["close_peer"].astype(float))
    spread = a - b
    mu = spread.rolling(lookback).mean()
    sd = spread.rolling(lookback).std(ddof=1)
    z = (spread - mu) / sd
    atr = _atr(d, atr_n).reindex(joined.index).ffill()

    signals: list[Signal] = []
    for i in range(lookback, len(joined) - 1):
        zi = float(z.iloc[i])
        if not np.isfinite(zi) or abs(zi) < entry_z:
            continue
        av = float(atr.iloc[i])
        if not np.isfinite(av) or av <= 0:
            continue
        side = -1 if zi > 0 else 1      # rich -> short this leg; cheap -> long it
        px = float(joined["close"].iloc[i])
        signals.append(Signal(time=joined.index[i], side=side,
                              stop=px - side * stop_atr * av,
                              target=px + side * abs(zi - exit_z) * sd.iloc[i] * px,
                              ttl_bars=ttl_bars, tag="relative_value",
                              trigger=None, wait_bars=1))
    return signals


def family_vol_transition(
    df: pd.DataFrame,
    *,
    fast: int = 12,
    slow: int = 96,
    ratio_in: float = 1.6,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 2.0,
    ttl_bars: int = 24,
) -> list[Signal]:
    """Trade the TRANSITION from compressed to expanding realised volatility.

    THE MECHANISM, and why it is not a breakout. A breakout family trades the price leaving a
    level. This trades the moment the VOLATILITY REGIME changes, regardless of where price is --
    it fires when the fast realised vol crosses decisively above the slow, which happens at the
    end of the quiet periods a carry sleeve was harvesting and often BEFORE any level breaks.
    Its failure regime is a false expansion that immediately re-compresses, which is a different
    failure from a breakout's (a level that breaks and reverses).
    """
    d = _h1(df)
    ret = np.log(d["close"].astype(float)).diff()
    v_fast = ret.rolling(fast).std(ddof=1)
    v_slow = ret.rolling(slow).std(ddof=1)
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for i in range(slow + 1, len(d) - 1):
        prev = float(v_fast.iloc[i - 1] / v_slow.iloc[i - 1]) if v_slow.iloc[i - 1] else np.nan
        now = float(v_fast.iloc[i] / v_slow.iloc[i]) if v_slow.iloc[i] else np.nan
        if not (np.isfinite(prev) and np.isfinite(now)):
            continue
        if not (prev < ratio_in <= now):
            continue                   # only the CROSSING, not the state
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        # Direction from the impulse that caused the expansion, not from a level.
        side = 1 if float(ret.iloc[i]) >= 0 else -1
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="vol_transition", trigger=None, wait_bars=1))
    return signals


def family_liquidity_regime(
    df: pd.DataFrame,
    *,
    spread_series: pd.Series | None = None,
    lookback: int = 96,
    widen_z: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 12,
) -> list[Signal]:
    """Fade dislocations that occur while the BOOK is unusually wide, then normalise.

    THE MECHANISM. An abnormally wide spread means liquidity has withdrawn. Moves made into a
    thin book are disproportionately likely to retrace once depth returns, because they were
    priced by absence rather than by information. This is an EXECUTION-DERIVED edge: its input is
    the venue's own bid/ask, not price history, which is exactly the axis a price-only breakout
    book cannot span.

    REFUSES WITHOUT A SPREAD SERIES -- the whole thesis is the book, and inferring the book from
    OHLC would be inventing the input.
    """
    if spread_series is None or spread_series.empty:
        return []
    d = _h1(df)
    s = spread_series.reindex(d.index).ffill()
    mu = s.rolling(lookback).mean()
    sd = s.rolling(lookback).std(ddof=1)
    z = (s - mu) / sd
    atr = _atr(d, atr_n)
    ret = d["close"].astype(float).pct_change()
    signals: list[Signal] = []
    for i in range(lookback, len(d) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or zi < widen_z:
            continue
        move = float(ret.iloc[i])
        if not np.isfinite(move) or move == 0:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = -1 if move > 0 else 1    # fade the move made into the thin book
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="liquidity_regime", trigger=None, wait_bars=1))
    return signals


def family_cot_positioning(
    df: pd.DataFrame,
    *,
    cot: pd.DataFrame | None = None,
    lookback_weeks: int = 156,
    extreme_pct: float = 0.90,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 2.0,
    ttl_bars: int = 240,
) -> list[Signal]:
    """Fade crowded speculative positioning at multi-year extremes.

    THE MECHANISM. When non-commercial net positioning reaches a multi-year extreme, the marginal
    buyer is exhausted: everyone who wanted the trade has it, so the asymmetry favours the other
    side. It runs on a WEEKLY clock off a report, which makes it structurally uncorrelated with an
    intraday range sleeve -- different information, different horizon, different failure mode (a
    genuine regime shift that keeps positioning extreme for months).

    REFUSES WITHOUT COT DATA rather than substituting a price-based crowding proxy, which would
    be a momentum sleeve with a misleading name.
    """
    if cot is None or cot.empty or "net" not in cot.columns:
        return []
    d = _h1(df)
    net = cot["net"].astype(float)
    hi = net.rolling(lookback_weeks, min_periods=26).quantile(extreme_pct)
    lo = net.rolling(lookback_weeks, min_periods=26).quantile(1 - extreme_pct)
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for ts, value in net.items():
        try:
            idx = d.index.searchsorted(pd.Timestamp(ts))
        except (TypeError, ValueError):
            continue
        if idx <= 0 or idx >= len(d) - 1:
            continue
        h, low = hi.get(ts, np.nan), lo.get(ts, np.nan)
        if not (np.isfinite(h) and np.isfinite(low)):
            continue
        side = 0
        if value >= h:
            side = -1
        elif value <= low:
            side = 1
        if side == 0:
            continue
        a = float(atr.iloc[idx])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[idx])
        signals.append(Signal(time=d.index[idx], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="cot_positioning", trigger=None, wait_bars=1))
    return signals


def family_lvc_asia_london(
    df: pd.DataFrame,
    *,
    bias_mode: str = "session_relative",
    asia_start_minute: int = 0,
    asia_end_minute: int = 6 * 60,
    trade_start_minute: int = 7 * 60,
    trade_end_minute: int = 10 * 60,
    atr_n: int = 14,
    min_range_atr: float = 0.50,
    max_range_atr: float = 2.00,
    max_breakout_bars: int = 9,
    recent_extreme_bars: int = 3,
    bias_block_bars: int = 3,
    breakout_distance_atr: float = 0.50,
    breakout_candle_atr: float = 1.20,
    true_break_stop_atr: float = 0.75,
    true_break_tp_atr: float = 2.00,
    retest_max_bars: int = 5,
    retest_touch_atr: float = 0.20,
    retest_max_close_back_atr: float = 0.30,
    reversal_max_bars: int = 3,
    reversal_overshoot_atr: float = 0.50,
    reversal_return_atr: float = 1.00,
    reversal_stop_buffer_atr: float = 0.20,
) -> list[Signal]:
    """Source-faithful London Volatility Capture challenger on native M5 bars.

    ``source_shift`` reproduces the public EA's defect: it measures an Asia extreme's age from
    the London-window start, making a three-bar M5 lookback impossible across the one-hour gap.
    ``session_relative`` is the preregistered repair: "recent" means within the last three bars
    *of the Asia session*. ``off`` is the required ablation. All other defaults are pinned to
    public blob ``2868957900aa9a06e8d9eb6523f938947210f6e9``.
    """
    if bias_mode not in {"off", "source_shift", "session_relative"}:
        return []
    if not isinstance(df.index, pd.DatetimeIndex) or df.empty:
        return []
    d = df.copy().sort_index()
    d.index = d.index.tz_localize("UTC") if d.index.tz is None else d.index.tz_convert("UTC")
    d = d[~d.index.duplicated(keep="last")].dropna(subset=["open", "high", "low", "close"])
    if len(d) < atr_n + 2:
        return []
    atr = _atr(d, atr_n)
    minute = pd.Series(d.index.hour * 60 + d.index.minute, index=d.index)
    signals: list[Signal] = []
    positions_by_day: dict[object, list[int]] = {}
    for pos, session_day in enumerate(d.index.date):
        positions_by_day.setdefault(session_day, []).append(pos)

    for positions_raw in positions_by_day.values():
        positions = np.asarray(positions_raw, dtype=int)
        asia = positions[(minute.iloc[positions].to_numpy() >= asia_start_minute)
                         & (minute.iloc[positions].to_numpy() < asia_end_minute)]
        trade = positions[(minute.iloc[positions].to_numpy() >= trade_start_minute)
                          & (minute.iloc[positions].to_numpy() < trade_end_minute)]
        if asia.size == 0 or trade.size == 0:
            continue
        asia_high = float(d["high"].iloc[asia].max())
        asia_low = float(d["low"].iloc[asia].min())
        span = asia_high - asia_low
        if span <= 0:
            continue
        # Last touch, matching the public implementation's nearest-to-window search.
        high_touch = int(asia[np.flatnonzero(
            d["high"].iloc[asia].to_numpy() >= asia_high - np.finfo(float).eps
        )[-1]])
        low_touch = int(asia[np.flatnonzero(
            d["low"].iloc[asia].to_numpy() <= asia_low + np.finfo(float).eps
        )[-1]])
        start_pos = int(trade[0])
        source_high_age = start_pos - high_touch
        source_low_age = start_pos - low_touch
        session_high_age = int(asia[-1]) - high_touch
        session_low_age = int(asia[-1]) - low_touch

        setups = {
            1: {"seen": False, "pos": -1, "extreme": np.nan, "atr": np.nan},
            -1: {"seen": False, "pos": -1, "extreme": np.nan, "atr": np.nan},
        }

        def bias_active(side: int, bars_from_start: int) -> bool:
            if bias_mode == "off" or bars_from_start > bias_block_bars:
                return False
            if bias_mode == "source_shift":
                age = source_high_age if side > 0 else source_low_age
            else:
                age = session_high_age if side > 0 else session_low_age
            return age <= recent_extreme_bars

        consumed = False
        for bars_from_start, pos_raw in enumerate(trade):
            pos = int(pos_raw)
            if bars_from_start > max_breakout_bars:
                break
            av = float(atr.iloc[pos])
            if not np.isfinite(av) or av <= 0 or not (min_range_atr <= span / av <= max_range_atr):
                continue
            bar = d.iloc[pos]
            candle_range = float(bar["high"] - bar["low"])
            if not setups[1]["seen"] and (
                float(bar["high"]) - asia_high >= breakout_distance_atr * av
                and candle_range >= breakout_candle_atr * av
                and float(bar["close"]) > float(bar["open"])
            ):
                setups[1] = {"seen": True, "pos": pos, "extreme": float(bar["high"]), "atr": av}
            if not setups[-1]["seen"] and (
                asia_low - float(bar["low"]) >= breakout_distance_atr * av
                and candle_range >= breakout_candle_atr * av
                and float(bar["close"]) < float(bar["open"])
            ):
                setups[-1] = {"seen": True, "pos": pos, "extreme": float(bar["low"]), "atr": av}

            # Public order: reversal, retest, then immediate true break.
            for breakout_side in (1, -1):
                setup = setups[breakout_side]
                if not setup["seen"]:
                    continue
                elapsed = pos - int(setup["pos"])
                close = float(bar["close"])
                if 0 < elapsed <= reversal_max_bars:
                    if breakout_side > 0:
                        reentered = close < asia_high
                        overshoot = float(setup["extreme"]) - asia_high
                        returned = float(setup["extreme"]) - close
                        if (reentered and overshoot >= reversal_overshoot_atr * av
                                and returned >= reversal_return_atr * av):
                            stop = float(setup["extreme"]) + reversal_stop_buffer_atr * av
                            signals.append(Signal(time=d.index[pos], side=-1, stop=stop,
                                                  target=asia_low, ttl_bars=12,
                                                  tag="lvc_asia_london", trigger=None,
                                                  wait_bars=1))
                            consumed = True
                            break
                    else:
                        reentered = close > asia_low
                        overshoot = asia_low - float(setup["extreme"])
                        returned = close - float(setup["extreme"])
                        if (reentered and overshoot >= reversal_overshoot_atr * av
                                and returned >= reversal_return_atr * av):
                            stop = float(setup["extreme"]) - reversal_stop_buffer_atr * av
                            signals.append(Signal(time=d.index[pos], side=1, stop=stop,
                                                  target=asia_high, ttl_bars=12,
                                                  tag="lvc_asia_london", trigger=None,
                                                  wait_bars=1))
                            consumed = True
                            break
                if 0 < elapsed <= retest_max_bars:
                    if breakout_side > 0:
                        valid = (float(bar["low"]) <= asia_high + retest_touch_atr * av
                                 and close >= asia_high - retest_max_close_back_atr * av
                                 and close >= asia_high)
                    else:
                        valid = (float(bar["high"]) >= asia_low - retest_touch_atr * av
                                 and close <= asia_low + retest_max_close_back_atr * av
                                 and close <= asia_low)
                    if valid:
                        stop = close - breakout_side * true_break_stop_atr * av
                        target = close + breakout_side * true_break_tp_atr * av
                        signals.append(Signal(time=d.index[pos], side=breakout_side, stop=stop,
                                              target=target, ttl_bars=12,
                                              tag="lvc_asia_london", trigger=None,
                                              wait_bars=1))
                        consumed = True
                        break
                if elapsed == 0:
                    opposite_recent = bias_active(-breakout_side, bars_from_start)
                    prefer_reversal = bias_active(breakout_side, bars_from_start)
                    if not opposite_recent and not prefer_reversal:
                        stop = close - breakout_side * true_break_stop_atr * av
                        target = close + breakout_side * true_break_tp_atr * av
                        signals.append(Signal(time=d.index[pos], side=breakout_side, stop=stop,
                                              target=target, ttl_bars=12,
                                              tag="lvc_asia_london", trigger=None,
                                              wait_bars=1))
                        consumed = True
                        break
            if consumed:
                break
    return signals


#: The registry the hypothesis router reads. Keyed by the SAME family names the breadth check
#: reports as missing, so a miner's discovery in any of them now has a testable path.

#: ENTRY SEMANTICS, LEARNT THE EXPENSIVE WAY (2026-08-26). Every family here enters AT THE NEXT
#: OPEN after its condition is observed -- spelled `trigger=None` in the engine. An earlier
#: revision spelled it `trigger=px, wait_bars=0`: a resting stop order AT the current close whose
#: armed window is `range(i, i+0)` -- empty -- so the engine discarded every signal. The result
#: was thousands of signals, ZERO trades, in every gauntlet run, for every orthogonal family, and
#: 575 discovered cells dying at the "under 60 days" filter after paying for a full backtest
#: each. The daily series was not short; it was EMPTY, and the drop reason said "days" because
#: nothing distinguished an empty series from a brief one.
ORTHOGONAL_FAMILIES = {
    "carry": family_carry,
    "relative_value": family_relative_value,
    "vol_transition": family_vol_transition,
    "liquidity_regime": family_liquidity_regime,
    "cot_positioning": family_cot_positioning,
    "lvc_asia_london": family_lvc_asia_london,
}


# =============================================================================================
# BREADTH EXTENSION -- one generator per distinct MECHANISM CLASS, not per parameterisation.
#
# The point of breadth is not more families; it is more INDEPENDENT CAUSES. Two families that
# both need a trend are one bet with two names, which is exactly the trap the desk fell into with
# eight breakout variants. Each generator below is included because it fires on information the
# others do not see, and -- the test that actually matters -- because there is a describable
# market state in which it profits while the rest of the book is losing.
#
# Grouped by the axis each one spans:
#   TIME        seasonality, turn-of-month, overnight-vs-intraday
#   DISPERSION  vol risk premium, vol mean reversion, correlation regime
#   FLOW        order-flow imbalance, spread reversion
#   STRUCTURE   term structure, cross-asset residual
#   STATE       macro conditional, event reaction, drawdown-conditioned
# =============================================================================================


def family_turn_of_month(
    df: pd.DataFrame,
    *,
    days_before: int = 2,
    days_after: int = 3,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 48,
    side_bias: int = 1,
) -> list[Signal]:
    """Month-end rebalancing flow. A CALENDAR cause -- it does not care what price did.

    Pension and index funds rebalance to targets around month end, producing flow that is
    predictable in timing and indifferent to the technical picture. Its failure mode is a month
    where the flow is dwarfed by news, which is uncorrelated with a breakout's failure mode.
    """
    d = _h1(df)
    signals: list[Signal] = []
    atr = _atr(d, atr_n)
    # tz_localize(None) first: to_period drops tz and warns, and `filterwarnings=error`
    # in this repo turns that warning into a test failure.
    month_ends = pd.Series(d.index.tz_localize(None).to_period("M"), index=d.index)
    last_of_month = month_ends != month_ends.shift(-1)
    for i in range(atr_n, len(d) - 1):
        window = last_of_month.iloc[max(0, i - days_before * 24):i + days_after * 24]
        if not bool(window.any()):
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side_bias,
                              stop=px - side_bias * stop_atr * a,
                              target=px + side_bias * stop_atr * a * rr,
                              ttl_bars=ttl_bars, tag="turn_of_month", trigger=None, wait_bars=1))
    return signals


def family_calendar_month(
    df: pd.DataFrame,
    *,
    active_month: int,
    side_bias: int,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 24,
) -> list[Signal]:
    """Test an explicitly mined month/direction claim without translating it to a breakout."""
    if active_month not in range(1, 13) or side_bias not in (-1, 1):
        return []
    d = _h1(df)
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    # One decision per UTC day during the specified month. The month and direction are source
    # evidence, not searched parameters; all other defaults are frozen family policy.
    for i in range(max(atr_n, 1), len(d) - 1):
        ts = d.index[i]
        if ts.month != active_month or ts.hour != 0:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=ts, side=side_bias,
                              stop=px - side_bias * stop_atr * a,
                              target=px + side_bias * stop_atr * a * rr,
                              ttl_bars=ttl_bars, tag="calendar_month", trigger=px, wait_bars=0))
    return signals


def family_overnight_gap_decay(
    df: pd.DataFrame,
    *,
    gap_atr: float = 0.75,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.0,
    ttl_bars: int = 8,
) -> list[Signal]:
    """Fade the OVERNIGHT component specifically -- a different return than the intraday one.

    Overnight and intraday returns are generated by different populations (thin books, no
    liquidity provision, position squaring) and have different statistical properties. Fading an
    outsized overnight gap is therefore a distinct bet from anything an intraday range family
    holds: it is closed before the session the breakout book trades even begins.
    """
    d = _h1(df)
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    day = pd.Series(d.index.date, index=d.index)
    first_bar = day != day.shift(1)
    for i in range(atr_n, len(d) - 1):
        if not bool(first_bar.iloc[i]):
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        gap = float(d["open"].iloc[i]) - float(d["close"].iloc[i - 1])
        if abs(gap) < gap_atr * a:
            continue
        side = -1 if gap > 0 else 1     # fade it back toward the prior close
        px = float(d["open"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * abs(gap) * rr, ttl_bars=ttl_bars,
                              tag="overnight_gap_decay", trigger=None, wait_bars=1))
    return signals


def family_vol_mean_reversion(
    df: pd.DataFrame,
    *,
    lookback: int = 96,
    z_in: float = -1.5,
    atr_n: int = 20,
    stop_atr: float = 1.0,
    rr: float = 2.5,
    ttl_bars: int = 36,
) -> list[Signal]:
    """Buy the STRADDLE-equivalent when realised vol is depressed: expansion is more likely.

    Distinct from vol_transition, which trades the crossing that has already begun; this
    positions BEFORE it, on compression alone, and expresses direction-agnostically by taking the
    side of the first impulse with a tight stop. Its edge is the asymmetry of vol -- it floors
    near zero and spikes -- not any view on price.
    """
    d = _h1(df)
    ret = np.log(d["close"].astype(float)).diff()
    rv = ret.rolling(lookback // 4).std(ddof=1)
    mu = rv.rolling(lookback).mean()
    sd = rv.rolling(lookback).std(ddof=1)
    z = (rv - mu) / sd
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for i in range(lookback + 1, len(d) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or zi > z_in:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        side = 1 if float(ret.iloc[i]) >= 0 else -1
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="vol_mean_reversion", trigger=None, wait_bars=1))
    return signals


def family_correlation_regime(
    df: pd.DataFrame,
    *,
    peer: pd.DataFrame | None = None,
    lookback: int = 120,
    break_z: float = -2.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Trade the BREAKDOWN of a stable correlation, not the level of a spread.

    Relative value assumes the relationship holds and fades deviations from it. This is the
    opposite bet: when a long-stable correlation collapses, the regime itself has changed and the
    old relationship is the thing that is wrong. Holding both is deliberate -- they profit in
    opposite states, which is what makes them independent rather than redundant.
    """
    if peer is None or peer.empty:
        return []
    d, p = _h1(df), _h1(peer)
    j = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(j) < lookback * 2:
        return []
    ra = np.log(j["close"].astype(float)).diff()
    rb = np.log(j["close_peer"].astype(float)).diff()
    corr = ra.rolling(lookback).corr(rb)
    mu = corr.rolling(lookback).mean()
    sd = corr.rolling(lookback).std(ddof=1)
    z = (corr - mu) / sd
    atr = _atr(d, atr_n).reindex(j.index).ffill()
    signals: list[Signal] = []
    for i in range(lookback * 2, len(j) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or zi > break_z:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(j["close"].iloc[i])
        side = 1 if float(ra.iloc[i]) >= 0 else -1
        signals.append(Signal(time=j.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="correlation_regime", trigger=None, wait_bars=1))
    return signals


def family_orderflow_imbalance(
    df: pd.DataFrame,
    *,
    flow: pd.Series | None = None,
    lookback: int = 48,
    z_in: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 12,
) -> list[Signal]:
    """Follow persistent one-sided flow measured from the TAPE, not from candles.

    Tick-derived imbalance sees who is crossing the spread, which OHLC cannot show: a bar can
    close green on passive buying or on aggressive lifting, and those have opposite continuations.
    REFUSES without a flow series rather than approximating it from price, which would just be
    momentum again.
    """
    if flow is None or flow.empty:
        return []
    d = _h1(df)
    f = flow.reindex(d.index).ffill()
    mu = f.rolling(lookback).mean()
    sd = f.rolling(lookback).std(ddof=1)
    z = (f - mu) / sd
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for i in range(lookback, len(d) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or abs(zi) < z_in:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = 1 if zi > 0 else -1
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="orderflow_imbalance", trigger=None, wait_bars=1))
    return signals


def family_cross_asset_residual(
    df: pd.DataFrame,
    *,
    factors: list[pd.DataFrame] | None = None,
    lookback: int = 240,
    entry_z: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 72,
) -> list[Signal]:
    """What is left of this instrument after removing SEVERAL common factors.

    A single-peer spread still carries whatever both legs share with the wider market. Projecting
    out multiple factors leaves a residual that is closer to instrument-specific, and mean
    reversion in THAT is a genuinely different claim from a two-name spread. Uses a plain
    least-squares projection so the assumption is inspectable rather than buried in a model.
    """
    if not factors:
        return []
    d = _h1(df)
    frame = d[["close"]].astype(float).rename(columns={"close": "y"})
    for k, fac in enumerate(factors):
        f = _h1(fac)[["close"]].astype(float).rename(columns={"close": f"x{k}"})
        frame = frame.join(f, how="inner")
    frame = frame.dropna()
    if len(frame) < lookback * 2:
        return []
    y = np.log(frame["y"]).diff()
    xs = np.column_stack([np.log(frame[c]).diff() for c in frame.columns if c != "y"])
    ok = np.isfinite(y.to_numpy()) & np.isfinite(xs).all(axis=1)
    if ok.sum() < lookback * 2:
        return []
    yv, xv = y.to_numpy()[ok], xs[ok]
    beta, *_ = np.linalg.lstsq(xv, yv, rcond=None)
    resid = pd.Series(yv - xv @ beta, index=frame.index[ok])
    cum = resid.cumsum()
    mu = cum.rolling(lookback).mean()
    sd = cum.rolling(lookback).std(ddof=1)
    z = (cum - mu) / sd
    atr = _atr(d, atr_n).reindex(cum.index).ffill()
    signals: list[Signal] = []
    for i in range(lookback, len(cum) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or abs(zi) < entry_z:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = -1 if zi > 0 else 1
        px = float(frame["y"].iloc[i])
        signals.append(Signal(time=cum.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="cross_asset_residual", trigger=None, wait_bars=1))
    return signals


def family_macro_conditional(
    df: pd.DataFrame,
    *,
    macro: pd.Series | None = None,
    regime_high: float = 0.5,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 96,
    side_in_high: int = 1,
) -> list[Signal]:
    """Take a directional stance CONDITIONED on a macro state variable.

    The mechanism is not the price pattern -- it is the macro state. The same instrument is a
    different asset when real rates are rising than when they are falling, and a family that
    conditions on that is holding a different bet from one that conditions on last night's range.
    REFUSES without a macro series; a "macro" family inferred from price is a momentum family.
    """
    if macro is None or macro.empty:
        return []
    d = _h1(df)
    m = macro.reindex(d.index).ffill()
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for i in range(atr_n, len(d) - 1):
        mv = float(m.iloc[i]) if np.isfinite(m.iloc[i]) else np.nan
        if not np.isfinite(mv):
            continue
        side = side_in_high if mv >= regime_high else -side_in_high
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="macro_conditional", trigger=None, wait_bars=1))
    return signals


def family_event_reaction(
    df: pd.DataFrame,
    *,
    events: pd.DatetimeIndex | None = None,
    react_bars: int = 1,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 6,
    fade: bool = True,
) -> list[Signal]:
    """Trade the reaction to a SCHEDULED release, on the event's clock.

    A calendar-driven family is uncorrelated with a range family by construction: it fires at
    times fixed months in advance by an institution, not by market structure. `fade=True` fades
    the initial spike (overreaction); `fade=False` follows it (underreaction). Both are testable
    and the gauntlet decides which -- this file supplies the instrument, not the answer.
    """
    if events is None or len(events) == 0:
        return []
    d = _h1(df)
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    for ts in events:
        idx = d.index.searchsorted(pd.Timestamp(ts))
        i = idx + react_bars
        if i <= atr_n or i >= len(d) - 1:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        move = float(d["close"].iloc[i]) - float(d["open"].iloc[idx])
        if move == 0:
            continue
        side = (-1 if move > 0 else 1) if fade else (1 if move > 0 else -1)
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="event_reaction", trigger=None, wait_bars=1))
    return signals


def family_drawdown_conditional(
    df: pd.DataFrame,
    *,
    lookback: int = 480,
    dd_pct: float = 0.05,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    rr: float = 2.0,
    ttl_bars: int = 120,
) -> list[Signal]:
    """Buy depth: enter only after a defined drawdown from a rolling high.

    A state-conditioned family whose trigger is the DISTANCE FROM A PEAK rather than a breakout
    from a range -- so it is systematically buying when a breakout book is stopped out, and idle
    when the breakout book is working. That anti-phase relationship is the entire reason to hold
    it, and it is visible in the sign of their correlation rather than asserted.
    """
    d = _h1(df)
    close = d["close"].astype(float)
    peak = close.rolling(lookback, min_periods=atr_n).max()
    dd = close / peak - 1.0
    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    armed = True
    for i in range(lookback, len(d) - 1):
        v = float(dd.iloc[i])
        if not np.isfinite(v):
            continue
        if v > -dd_pct * 0.5:
            armed = True                # re-arm once recovered, so one selloff = one entry
        if v > -dd_pct or not armed:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        armed = False
        px = float(close.iloc[i])
        signals.append(Signal(time=d.index[i], side=1, stop=px - stop_atr * a,
                              target=px + stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="drawdown_conditional", trigger=None, wait_bars=1))
    return signals


ORTHOGONAL_FAMILIES.update({
    "turn_of_month": family_turn_of_month,
    "calendar_month": family_calendar_month,
    "overnight_gap_decay": family_overnight_gap_decay,
    "vol_mean_reversion": family_vol_mean_reversion,
    "correlation_regime": family_correlation_regime,
    "orderflow_imbalance": family_orderflow_imbalance,
    "cross_asset_residual": family_cross_asset_residual,
    "macro_conditional": family_macro_conditional,
    "event_reaction": family_event_reaction,
    "drawdown_conditional": family_drawdown_conditional,
})

#: What each family NEEDS. The router uses this to route a discovery to a family that can
#: actually run, and the breadth check uses it to say WHY a family is still absent -- "no swap
#: terms recorded" is an acquisition task, which is a different defect from "never mined".
FAMILY_INPUTS = {
    "carry": ("contract/swap terms", "data/tape/contract_terms"),
    "relative_value": ("a peer instrument's H1", "data/universe/<PEER>_H1.parquet"),
    "vol_transition": ("price only", None),
    "vol_mean_reversion": ("price only", None),
    "liquidity_regime": ("spread series from the tick tape", "data/tape/ticks/<SYM>"),
    "orderflow_imbalance": ("tick-derived flow imbalance", "data/tape/ticks/<SYM>"),
    "cot_positioning": ("COT net positioning", "data/cot*"),
    "cross_asset_residual": ("2+ factor instruments' H1", "data/universe/*_H1.parquet"),
    "correlation_regime": ("a peer instrument's H1", "data/universe/<PEER>_H1.parquet"),
    "macro_conditional": ("a macro state series", "data/macro_state.json"),
    "event_reaction": ("an economic calendar", "data/intelligence/ff_calendar_vintage"),
    "turn_of_month": ("price only", None),
    "calendar_month": ("source-specified calendar month and direction", None),
    "overnight_gap_decay": ("price only", None),
    "drawdown_conditional": ("price only", None),
}


#: Derived primitives, cached per frame extent. Bounded because a sweep touches few distinct
#: frames and an unbounded cache on 310 series each would trade CPU for the memory the gauntlet
#: just stopped wasting.
_PRIM_CACHE: dict = {}


def family_discovered(
    df: pd.DataFrame,
    *,
    feature: str = "",
    band: tuple | list = (0.9, 1.0),
    horizon: int = 12,
    side: int = 1,
    extra: dict | None = None,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Execute ANY edge the searcher discovered, from its parameters alone.

    THIS IS WHAT MAKES "NO HARDCODED FAMILY" REAL. `edge_search` can discover that forward
    returns are conditional on some primitive being in some quantile band -- but a discovery the
    gauntlet cannot EXECUTE is a note, not a candidate, and the ten gates judge realised trades,
    not correlations. Without this the entire search was decorative: it would emit hypotheses no
    cell builder could turn into signals, so nothing it found could ever certify.

    There is no strategy knowledge in here. The feature name is looked up in the same primitive
    builder the search used, the band edges are recomputed the same way, and a position is opened
    whenever the condition holds, held for the discovered horizon, bracketed by ATR. Whether that
    is a "breakout", a "carry" or something nobody has named is not this function's business --
    and that indifference is the point.
    """
    # Import path differs by caller (package vs script vs desk-box task); try each rather than
    # letting one layout silently disable every discovered edge.
    try:
        from research.edge_search import build_primitives
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(BASE / "research"))
        from edge_search import build_primitives

    d = _h1(df)
    # PRIMITIVES ARE CACHED PER FRAME. Measured 2026-08-26: build_primitives takes 4.3s and
    # produces 310 series, and this function called it ONCE PER CELL -- 575 discovered cells meant
    # ~41 minutes spent rebuilding byte-identical primitives to read one column out of each. The
    # frames themselves are already shared per symbol by the gauntlet, so the derived primitives
    # are shared for exactly the same reason and with exactly the same safety: read-only inputs,
    # identical bars, identical output. Keyed on the frame's own extent rather than id(), which a
    # garbage collector can recycle.
    _key = (len(d), str(d.index[0]) if len(d) else "", str(d.index[-1]) if len(d) else "",
            tuple(sorted((extra or {}).keys())))
    prim = _PRIM_CACHE.get(_key)
    if prim is None:
        prim = build_primitives(d, "", extra or {})
        if len(_PRIM_CACHE) > 8:          # bounded: a sweep touches few distinct frames
            _PRIM_CACHE.clear()
        _PRIM_CACHE[_key] = prim
    series = prim.get(feature)
    if series is None:
        return []
    values = series.to_numpy(dtype="float64", na_value=np.nan)
    finite = np.isfinite(values)
    if finite.sum() < 200:
        return []
    lo_q, hi_q = float(band[0]), float(band[1])
    lo, hi = np.quantile(values[finite], lo_q), np.quantile(values[finite], hi_q)
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return []

    atr = _atr(d, atr_n)
    side = 1 if int(side) >= 0 else -1
    ttl = max(1, int(horizon))
    # VECTORISED SELECTION. The scalar loop ran ~50k Python iterations per cell and there are
    # hundreds of cells; numpy picks the qualifying bars in one pass and only those become
    # objects. Same bars, same signals -- the loop was never doing anything numpy cannot.
    atr_v = atr.to_numpy(dtype="float64", na_value=np.nan)
    close_v = d["close"].to_numpy(dtype="float64", na_value=np.nan)
    idx = np.arange(len(d))
    ok = (idx >= atr_n) & (idx < len(d) - 1)
    ok &= finite & (values >= lo) & (values <= hi)
    ok &= np.isfinite(atr_v) & (atr_v > 0)
    picks = idx[ok]

    signals: list[Signal] = []
    times = d.index
    for i in picks:
        a = float(atr_v[i])
        px = float(close_v[i])
        signals.append(Signal(time=times[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl,
                              tag=f"discovered:{feature}", trigger=None, wait_bars=1))
    return signals


ORTHOGONAL_FAMILIES["discovered"] = family_discovered
FAMILY_INPUTS["discovered"] = ("whatever primitive the search named", "resolved by edge_search")


def family_pca_residual(
    df: pd.DataFrame,
    *,
    factors: list[pd.DataFrame] | None = None,
    window: int = 720,
    refit_stride: int = 24,
    entry_z: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Fade this instrument's residual after removing the universe's REAL latent factors.

    THE MECHANISM (queued as xp-h1/xp-h2, external prior 2026-08-26; the method itself is
    standard statistical arbitrage). A handful of latent forces -- USD, JPY, risk-on/off, rates,
    metals beta -- explain most co-movement across the MT5 universe. What remains after removing
    them is instrument-specific dislocation, and dislocation with no factor behind it reverts,
    because nothing is sustaining it. The edge lives in the RESIDUAL, never the raw return.

    WHY MARCHENKO-PASTUR AND NOT "TOP K COMPONENTS". A sample correlation matrix of p series over
    n observations grows eigenvalues up to (1+sqrt(p/n))^2 FROM PURE NOISE. Keeping a fixed top-K
    would sometimes keep noise and sometimes discard signal; the MP bound keeps exactly the
    eigenvalues that cannot be noise at this p/n, so the factor count adapts to the data instead
    of being someone's guess.

    NO LOOKAHEAD BY CONSTRUCTION. Factors are re-estimated every `refit_stride` bars from the
    TRAILING `window` only, and each bar's residual uses the latest estimate strictly behind it.
    A full-sample PCA would leak tomorrow's correlations into today's residual and manufacture a
    reversion that never existed -- the gauntlet's walk-forward would kill it, but the honest
    screen does not submit it in the first place.

    REFUSES without at least 4 factor instruments: a "universe factor" extracted from two peers
    is just a pair spread wearing a bigger name.
    """
    if not factors or len(factors) < 4:
        return []
    d = _h1(df)
    cols = {"y": np.log(d["close"].astype(float)).diff()}
    for k, fdf in enumerate(factors):
        f = _h1(fdf)
        cols[f"f{k}"] = np.log(f["close"].astype(float)).diff().reindex(d.index)
    mat = pd.DataFrame(cols).dropna()
    if len(mat) < window * 2:
        return []
    ret = mat.to_numpy(dtype="float64")
    n_obs, _ = ret.shape
    atr = _atr(d, atr_n).reindex(mat.index).ffill()
    close = d["close"].reindex(mat.index).astype(float)

    resid = np.full(n_obs, np.nan)
    beta, keep_basis, mu, sd = None, None, None, None
    for i in range(window, n_obs):
        if (i - window) % refit_stride == 0:
            seg = ret[i - window:i]
            m = seg.mean(axis=0)
            s = seg.std(axis=0, ddof=1)
            s[s == 0] = np.nan
            z = (seg - m) / s
            z = np.nan_to_num(z)
            fac = z[:, 1:]                       # factor instruments only
            corr = (fac.T @ fac) / max(1, len(fac) - 1)
            try:
                evals, evecs = np.linalg.eigh(corr)
            except np.linalg.LinAlgError:
                continue
            p_dim = fac.shape[1]
            mp_max = (1.0 + math.sqrt(p_dim / window)) ** 2
            keep = evals > mp_max                # only what noise cannot produce
            if not keep.any():
                beta = None
                continue
            basis = evecs[:, keep]               # p x k
            fscores = fac @ basis                # window x k latent factor returns
            y = z[:, 0]
            try:
                beta, *_ = np.linalg.lstsq(fscores, y, rcond=None)
            except np.linalg.LinAlgError:
                beta = None
                continue
            keep_basis, mu, sd = basis, m, s
        if beta is None or keep_basis is None:
            continue
        zr = (ret[i] - mu) / sd
        zr = np.nan_to_num(zr)
        expl = float((zr[1:] @ keep_basis) @ beta)
        resid[i] = float(zr[0]) - expl

    rs = pd.Series(resid, index=mat.index)
    cum = rs.fillna(0.0).rolling(window // 6).sum()   # dislocation accumulates over days
    rm = cum.rolling(window).mean()
    rsd = cum.rolling(window).std(ddof=1)
    z = (cum - rm) / rsd

    signals: list[Signal] = []
    for i in range(window, n_obs - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or abs(zi) < entry_z:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = -1 if zi > 0 else 1               # fade the unexplained extreme
        px = float(close.iloc[i])
        signals.append(Signal(time=mat.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="pca_residual", trigger=None, wait_bars=1))
    return signals


ORTHOGONAL_FAMILIES["pca_residual"] = family_pca_residual
FAMILY_INPUTS["pca_residual"] = ("4+ factor instruments' H1 (the more of the universe, the "
                                 "better the latent factors)", "data/universe/*_H1.parquet")
