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
from mt5desk.causal_residual import causal_residual
from mt5desk.families import Signal, _atr, _h1
from mt5desk.universe_registry import REFERENCE_TIMEFRAME as _REFERENCE_TF
from mt5desk.universe_registry import TIMEFRAMES as _TIMEFRAMES
from mt5desk.universe_registry import scale_bars as _scale_bars

BASE = Path(__file__).resolve().parent.parent
TERMS = BASE / "data" / "tape" / "contract_terms"
_TERMS_CACHE: dict[str, dict] | None = None
COT = BASE / "data"


def _load_terms() -> dict[str, dict]:
    """Latest recorded terms per symbol, read ONCE per process.

    THE FORMAT MISMATCH THAT MADE CARRY DEAD CODE (fixed 2026-08-28). The tape recorder writes
    one PARQUET vintage per day -- `2026-08-27.parquet`, 1,908 rows carrying observed_at, symbol,
    swap_long and swap_short for the whole offering. The reader below globbed `*.json` and
    `*.jsonl` and nothing else, so it matched no file the producer has ever written, returned
    None for every symbol, and `family_carry` returned [] for every symbol as its docstring
    promises it will without terms.

    Nothing reported this. The sweep counted the cells as run, the gate report recorded 194 carry
    cells with `days: 0`, and "0 daily observations" reads like a mechanism that fires rarely
    rather than a reader that has never once opened a file. Carry is the desk's one genuinely
    non-directional mechanism -- the diversifier against a book of breakout and momentum sleeves
    -- so the whole orthogonal wing was silently absent from every hunt.

    Loaded once and cached: this is called per CELL, and the old code re-scanned the entire
    directory on every call.
    """
    global _TERMS_CACHE
    if _TERMS_CACHE is not None:
        return _TERMS_CACHE
    latest: dict[str, dict] = {}
    if TERMS.exists():
        # Chronological: later files win, so the newest observation is the one carry uses.
        for f in sorted(TERMS.glob("*.parquet")):
            try:
                frame = pd.read_parquet(f)
            except (OSError, ValueError, ImportError):
                continue
            if "symbol" not in frame.columns:
                continue
            if "observed_at" in frame.columns:
                frame = frame.sort_values("observed_at")
            for row in frame.to_dict("records"):
                sym = str(row.get("symbol", "")).upper()
                if sym:
                    latest[sym] = row
    _TERMS_CACHE = latest
    return latest


#: MT5 ENUM_SYMBOL_SWAP_MODE. 0 is DISABLED, not POINTS -- a confusion that reached this desk's
#: only written statement of the convention (libs/research/perishability.py, corrected 2026-08-29)
#: and the tests below. Measured on desks/mt5/data/tape/contract_terms: 0 symbols at mode 0.
SWAP_MODE_POINTS = 1


def _swap_terms(symbol: str) -> dict | None:
    """Point-in-time swap/contract terms the tape recorder already stores. None if unrecorded."""
    if not TERMS.exists():
        return None
    parquet_row = _load_terms().get(str(symbol).upper())
    if parquet_row is not None:
        return parquet_row
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


def swap_money_per_lot(terms: dict) -> tuple[float, float] | None:
    """(long, short) financing per lot per night in the PROFIT currency, or None to stand aside.

    THE UNIT LIVES IN A DIFFERENT FIELD FROM THE NUMBER, which is the shape of every cost defect
    this desk has paid for (gold's spread at 3%, CADJPY's commission at 1/184th, the pooled spread
    scalar). `swap_long` is a bare numeral whose meaning is set by `swap_mode`:

        swap_mode == 1  SYMBOL_SWAP_MODE_POINTS            110 symbols -- POINTS
        swap_mode == 5  SYMBOL_SWAP_MODE_INTEREST_CURRENT  138 symbols -- ANNUAL PERCENT

    counted on this desk's own contract-terms tape. Mode 0 is DISABLED and appears on ZERO
    symbols. In POINTS mode the money value is `swap * point * contract_size`; mode 5 needs a
    price and a day-count basis and is refused here rather than guessed.

    **THE RETURN IS PROFIT CURRENCY AND IS THEREFORE NOT COMPARABLE ACROSS SYMBOLS.** USDJPY's
    6.35 points is 635 JPY and EURUSD's -6.45 is -6.45 USD; a shared threshold applied to both
    is comparing yen to dollars. For an account-currency figure -- the one a cross-symbol gate
    actually needs -- use `desks/mt5/research/carry_state.money_per_lot_night`, which converts
    through `tick_value`. This function exists to give `family_carry` a self-consistent magnitude
    for ONE symbol and to make an unresolvable unit REFUSE instead of trading.

    None means the unit could not be established. It never means zero (L1.28a).
    """
    mode = terms.get("swap_mode")
    if mode is None:
        return None
    try:
        mode = int(mode)
        point = float(terms.get("point") or 0.0)
        contract = float(terms.get("contract_size") or 0.0)
        lo, sh = float(terms["swap_long"]), float(terms["swap_short"])
    except (KeyError, TypeError, ValueError):
        return None
    if mode != SWAP_MODE_POINTS:
        return None
    if point <= 0 or contract <= 0:
        return None
    scale = point * contract
    return lo * scale, sh * scale


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
    # THE MAGNITUDE GATE READ THE RAW FIELD (repaired 2026-08-29). `swap_long - swap_short` is
    # points on 110 symbols and annual percent on 138, and it was being compared against a
    # threshold named `min_edge_bp_per_day`: three dimensions, one constant. In practice the
    # gate was vacuous -- AUDHUF's raw differential is 1,580 and USDTRY's is 11,364 against a
    # bar of 0.5, so any symbol with enough decimal places passed unconditionally, while the
    # SIDE was picked by comparing two numerals whose scale is the broker's digit count.
    # Resolving the unit first makes an unresolvable symbol STAND ASIDE, which can only ever
    # emit fewer signals than before -- never a new one.
    money = swap_money_per_lot(terms)
    if money is None:
        return []
    swap_long, swap_short = money
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
    ttl_bars: int = 288,
) -> list[Signal]:
    """Source-faithful London Volatility Capture challenger on native M5 bars.

    ``source_shift`` reproduces the public EA's defect: it measures an Asia extreme's age from
    the London-window start, making a three-bar M5 lookback impossible across the one-hour gap.
    ``session_relative`` is the preregistered repair: "recent" means within the last three bars
    *of the Asia session*. ``off`` is the required ablation. All other defaults are pinned to
    public blob ``2868957900aa9a06e8d9eb6523f938947210f6e9``. The source has no default
    session-close exit, so ``ttl_bars`` is an explicit one-day replay bound rather than a hidden
    one-hour exit assumption.
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
                                                  target=asia_low, ttl_bars=ttl_bars,
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
                                                  target=asia_high, ttl_bars=ttl_bars,
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
                                              target=target, ttl_bars=ttl_bars,
                                              tag="lvc_asia_london", trigger=None,
                                              wait_bars=1))
                        consumed = True
                        break
                if elapsed == 0 and bars_from_start <= max_breakout_bars:
                    opposite_recent = bias_active(-breakout_side, bars_from_start)
                    prefer_reversal = bias_active(breakout_side, bars_from_start)
                    if not opposite_recent and not prefer_reversal:
                        stop = close - breakout_side * true_break_stop_atr * av
                        target = close + breakout_side * true_break_tp_atr * av
                        signals.append(Signal(time=d.index[pos], side=breakout_side, stop=stop,
                                              target=target, ttl_bars=ttl_bars,
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
    # CALENDAR, NOT THE REALIZED BAR SEQUENCE. This built `last_of_month` as
    # `month_ends != month_ends.shift(-1)` -- the last bar of a month AS THE DATASET HAPPENED TO
    # END IT -- and then scanned a window reaching `days_after * 24` bars FORWARD of the decision
    # bar. Those bars do not exist at decision time. The information wanted ("is a month boundary
    # near?") is knowable from the timestamp alone, so nothing about the hypothesis needed the
    # future; what leaked was bar AVAILABILITY -- whether the market turned out to be open, and
    # which bar turned out to be the month's last. A live implementation could not reproduce it,
    # which is the definition of a backtest that cannot be traded.
    #
    # Distance to the month boundary is now computed from each bar's own date. Identical
    # intention, zero lookahead, and the live and replayed rules are the same rule.
    idx_naive = d.index.tz_localize(None)
    month_end_day = (idx_naive + pd.offsets.MonthEnd(0)).normalize()
    month_start_day = idx_naive.to_period("M").to_timestamp()
    days_to_end = (month_end_day - idx_naive.normalize()).days.to_numpy()
    days_from_start = (idx_naive.normalize() - month_start_day).days.to_numpy()
    for i in range(atr_n, len(d) - 1):
        # "within `days_before` of a month end" OR "within `days_after` of a month start" --
        # the same turn-of-month window the original scan approximated.
        if not (days_to_end[i] <= days_before or days_from_start[i] <= days_after):
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
    #
    # `hour == 0` ALONE IS ONE DECISION PER DAY ONLY ON AN HOURLY CHART (2026-09-05). On M1 the
    # first hour of a day holds sixty bars that all satisfy it, so the family would take sixty
    # decisions where its own docstring promises one -- and it enters with `trigger=px,
    # wait_bars=0`, so those are sixty resting orders at sixty different prices. Requiring the
    # minute too makes it the day's FIRST bar on every chart. H1, H4 and D1 bars are all stamped
    # at minute 0, so no existing cell changes by a single signal.
    for i in range(max(atr_n, 1), len(d) - 1):
        ts = d.index[i]
        if ts.month != active_month or ts.hour != 0 or ts.minute != 0:
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
    beta_win: int | None = None,
    entry_z: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 72,
    side_mode: str = "revert",
    active_hours: tuple[int, ...] | list[int] | None = None,
) -> list[Signal]:
    """What is left of this instrument after removing SEVERAL common factors.

    A single-peer spread still carries whatever both legs share with the wider market. Projecting
    out multiple factors leaves a residual that is closer to instrument-specific, and an
    unusually large one is a genuinely different claim from a two-name spread.

    THE LOOKAHEAD THIS USED TO CONTAIN (fixed 2026-09-04). The hedge ratios were fitted with one
    `lstsq` over the WHOLE sample and the residual was then traded from the first bar onward, so
    the beta defining "unexplained" had seen every move it was calling unexplained -- on every
    bar of every out-of-sample fold the gauntlet later carved. `funnel_census` records what that
    bought: 348 failures, zero certificates, on the desk's one non-directional mechanism. Betas
    are now fitted strictly on bars before the one they price (`mt5desk.causal_residual`), and
    the regression carries a constant, so drift the factors do not explain is charged to the
    intercept instead of being read as a dislocation.

    NO COOLDOWN IS APPLIED HERE ON PURPOSE. `engine` holds one position at a time and skips any
    signal inside a live trade, so filtering overlaps here would double-count a discipline the
    execution layer already enforces, and would do it with a different rule.

    SIDE IS A HYPOTHESIS, NOT A CONVENTION. `side_mode` names which claim is being tested --
    "revert" fades the residual, "continue" follows it. Both are economically real (a dislocation
    closes; a genuine re-rating runs) and which one holds is exactly the sort of thing that must
    be MEASURED per instrument and per session rather than assumed. `active_hours` restricts
    entries to broker stamp-hours, which is how a session-conditional version of the same claim
    is stated without a second family.
    """
    if not factors:
        return []
    if side_mode not in {"revert", "continue"}:
        return []
    bwin = int(beta_win) if beta_win else int(lookback)
    d = _h1(df)
    frame = d[["close"]].astype(float).rename(columns={"close": "y"})
    for k, fac in enumerate(factors):
        f = _h1(fac)[["close"]].astype(float).rename(columns={"close": f"x{k}"})
        frame = frame.join(f, how="inner")
    frame = frame.dropna()
    # Causal betas cost `bwin` bars before the first residual exists and the z-score costs
    # `lookback` more on top of that, so the old `lookback * 2` floor no longer describes what
    # this needs. Refusing is the right answer: a cell with no room for both windows would
    # otherwise report a handful of trades as a verdict.
    if len(frame) < bwin + lookback * 2:
        return []
    y = np.log(frame["y"]).diff()
    xs = np.column_stack([np.log(frame[c]).diff() for c in frame.columns if c != "y"])
    ok = np.isfinite(y.to_numpy()) & np.isfinite(xs).all(axis=1)
    if ok.sum() < bwin + lookback * 2:
        return []
    yv, xv = y.to_numpy()[ok], xs[ok]
    resid = pd.Series(causal_residual(yv, xv, bwin), index=frame.index[ok])
    cum = resid.fillna(0.0).cumsum().where(resid.notna())
    mu = cum.rolling(lookback).mean()
    sd = cum.rolling(lookback).std(ddof=1)
    z = (cum - mu) / sd
    atr = _atr(d, atr_n).reindex(cum.index).ffill()
    hours = {int(h) for h in active_hours} if active_hours else None
    signals: list[Signal] = []
    for i in range(bwin + lookback, len(cum) - 1):
        zi = float(z.iloc[i]) if np.isfinite(z.iloc[i]) else np.nan
        if not np.isfinite(zi) or abs(zi) < entry_z:
            continue
        ts = cum.index[i]
        if hours is not None and int(ts.hour) not in hours:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = (-1 if zi > 0 else 1) if side_mode == "revert" else (1 if zi > 0 else -1)
        px = float(frame["y"].iloc[i])
        signals.append(Signal(time=ts, side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag=f"cross_asset_residual:{side_mode}", trigger=None, wait_bars=1))
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
    "relative_value": ("a peer instrument, on this cell's own chart",
                       "data/universe/<PEER>_<TF>.parquet"),
    "vol_transition": ("price only", None),
    "vol_mean_reversion": ("price only", None),
    "liquidity_regime": ("spread series from the tick tape", "data/tape/ticks/<SYM>"),
    "orderflow_imbalance": ("tick-derived flow imbalance", "data/tape/ticks/<SYM>"),
    "cot_positioning": ("COT net positioning", "data/cot*"),
    "cross_asset_residual": ("2+ factor instruments, on this cell's own chart",
                             "data/universe/*_<TF>.parquet"),
    "correlation_regime": ("a peer instrument, on this cell's own chart",
                           "data/universe/<PEER>_<TF>.parquet"),
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
FAMILY_INPUTS["pca_residual"] = ("4+ factor instruments on this cell's own chart (the more of "
                                 "the universe, the better the latent factors)",
                                 "data/universe/*_<TF>.parquet")


# THE EDGE QUEUE, REGISTERED THROUGH THE SAME DOOR AS EVERYTHING ELSE (2026-08-29).
#
# These four are the preregistered mechanisms in `libs/research/edge_queue.py` -- hedging-demand
# close flow, FX fixing reversal, gold session handoff, and liquidity/gamma reversal. Each names a
# PAYER: a participant who must trade for a reason that is not a forecast, which is the property
# arbitrage cannot compete away.
#
# REGISTERED HERE RATHER THAN BEHIND THEIR OWN ENTRY POINT, and that is the whole point. A family
# reachable only through a special path is a family with its own bar; this desk needed three
# verdict engines before anyone noticed two of them required no significance test at all. Coming
# through ORTHOGONAL_FAMILIES means the sweep enumerates them, admission authorises them, the
# gauntlet judges them and the forward engine clocks them -- with no special case anywhere.
#
# They need nothing beyond bars, so FAMILY_INPUTS records that explicitly. An absent entry would
# read as "nobody checked" rather than "nothing required".
from mt5desk.families_edge_queue import EDGE_QUEUE_FAMILIES  # noqa: E402

ORTHOGONAL_FAMILIES.update(EDGE_QUEUE_FAMILIES)
for _eq_name in EDGE_QUEUE_FAMILIES:
    # "price only" is the SENTINEL the sweep's wiring test reads, not a description. Writing
    # prose here declared a non-price input the sweep never passes, which
    # `test_every_family_needing_an_input_is_wired_to_one` correctly flagged: the family would
    # have returned [] on every symbol and read as a data gap. The session clock comes from the
    # bar index, so these genuinely need nothing beyond price.
    FAMILY_INPUTS[_eq_name] = ("price only", "data/universe/*_H1.parquet")


# THE GENERIC COORDINATE FAMILY (2026-08-29). One parameterised function that executes any
# semantic coordinate: when EVENT happens, in CONTEXT, if QUALITY exceeds a threshold, trade
# DIRECTION for OUTPUT.
#
# WHY IT IS REGISTERED HERE. `scripts/compile_proposals.py` turns a model's mechanism proposal
# into a choice of five axis values rather than into code, and this is the function that runs
# them. Without it every proposal after the four hand-written edge-queue families would have sat
# in `hypothesis_queue.jsonl` forever -- the same dead end as the queue never existing.
#
# NO MODEL-GENERATED CODE IS EXECUTED. The compiler picks axis values from a fixed vocabulary;
# the family was written by hand and reviewed once. That is the whole point of expressing
# mechanisms as coordinates instead of as programs: the search space is bounded by construction
# and every cell is inspectable as five names.
from mt5desk.family_generic import family_generic  # noqa: E402

ORTHOGONAL_FAMILIES["generic"] = family_generic
FAMILY_INPUTS["generic"] = ("price only", "data/universe/*_H1.parquet")

# THE REGIME CHANGE ITSELF AS A MECHANISM (2026-09-04). `vol_transition` trades a realised-vol
# ratio crossing, which is a proxy for "something is changing". This trades P(the regime ENDS
# within h) conditioned on how long it has already run -- the quantity the allocator's hazard
# layer already computes. A vol ratio can cross inside a stable regime; a mature trend can be one
# bar from exhaustion with its vol ratio quiet. Different claim, different failure mode.
from mt5desk.family_regime_transition import family_regime_transition  # noqa: E402

ORTHOGONAL_FAMILIES["regime_transition"] = family_regime_transition
FAMILY_INPUTS["regime_transition"] = ("price only", "data/universe/*_H1.parquet")

# THE MARKET'S PLUMBING AS A MECHANISM CLASS (2026-09-04). A fix, a settlement, a handoff, a
# rollover: moments when flow is FORCED rather than chosen, which is the most reliable source of
# temporary mispricing there is. Takes the STAMP HOUR explicitly so the certificate is exact
# whatever anyone later believes about time zones; `plumbing_miner` does the conversion once.
from mt5desk.family_clock_transition import family_clock_transition  # noqa: E402

ORTHOGONAL_FAMILIES["clock_transition"] = family_clock_transition
FAMILY_INPUTS["clock_transition"] = ("price only", "data/universe/*_H1.parquet")

# TIME-SERIES MOMENTUM AT SEVERAL SPEEDS (2026-09-04) -- AQR's published TSMOM and Man AHL's
# multi-speed trend, vol-scaled, with the crisis-alpha variant. The mirror of a breakout's
# failure mode, which is what makes it the textbook pairing for an uncorrelated book.
from mt5desk.family_multi_speed_trend import family_multi_speed_trend  # noqa: E402

ORTHOGONAL_FAMILIES["multi_speed_trend"] = family_multi_speed_trend
FAMILY_INPUTS["multi_speed_trend"] = ("price only", "data/universe/*_H1.parquet")

# MANY SUB-COST PREDICTORS AS ONE CANDIDATE (2026-09-04) -- Brown's public statement of the
# Medallion architecture. Members are ordinary cells named on the certificate; the family runs
# them through the gauntlet's own cell builder and votes. Frozen weights, never fitted here.
from mt5desk.family_ensemble import family_ensemble  # noqa: E402

ORTHOGONAL_FAMILIES["ensemble"] = family_ensemble
FAMILY_INPUTS["ensemble"] = ("member cells rebuilt via the gauntlet's build_cell",
                             "reports/universal_gates_external.json")

# THE BROKER'S OWN SPREAD STATE AS A MECHANISM (2026-09-04). Every H1 bar carries Fusion's
# spread and tick_volume; every cost model read the spread only to charge it. A spread is the
# venue saying how much it wants to be paid to take the other side, which is information.
from mt5desk.family_spread_state import family_spread_state  # noqa: E402

ORTHOGONAL_FAMILIES["spread_state"] = family_spread_state
# No FAMILY_INPUTS entry: the spread is a COLUMN OF THE BARS the sweep already passes, not a
# runtime input to source. The family refuses bars without it, which is the only guard needed.

# FORMULAIC ALPHA (2026-09-04) -- one expression from the alpha grammar, z-scored and
# thresholded. The expression is the recipe; `alpha_evolution` is the only proposer that names
# one. Driver terminals (usd, rates, risk, gold, oil, growth) are supplied by family_inputs.
from mt5desk.family_formula import family_formula  # noqa: E402

ORTHOGONAL_FAMILIES["formula"] = family_formula
FAMILY_INPUTS["formula"] = ("economic driver bars for any driver terminal the expression names",
                            "data/universe/*_H1.parquet via economic_drivers.ROLES")

# THE CROSS-ASSET INFORMATION GRAPH'S EXECUTOR (2026-09-04): trade the laggard after the
# leader moved, at the lag the graph measured. The driver is named on the recipe.
from mt5desk.family_lead_lag import family_lead_lag  # noqa: E402

ORTHOGONAL_FAMILIES["lead_lag"] = family_lead_lag
FAMILY_INPUTS["lead_lag"] = ("the driver instrument's bars (driver_symbol on the recipe)",
                             "data/universe/*_H1.parquet")

# AQR'S SIX STYLES AND THEIR PUBLIC COMBINATIONS (2026-09-04): trend, carry (Fusion's own
# rollover), value, defensive (BAB against the risk driver), volatility, momentum.
from mt5desk.family_style_premia import family_style_premia  # noqa: E402

ORTHOGONAL_FAMILIES["style_premia"] = family_style_premia
FAMILY_INPUTS["style_premia"] = ("swap_diff (broker_swaps) for carry; risk-driver bars for "
                                 "defensive", "data/intelligence/broker_swaps + universe")


# ==============================================================================================
# EVERY MECHANISM ON EVERY CHART -- and the two questions that decides (2026-09-05)
#
# The principal's order is "m1 m5 m15 m30 h1 h4 d1 all possible every type of mechanism n chart
# for all always ... this was a serious flaw we had abt the h1 only". Handing every family seven
# charts is one line. Handing every family seven charts and getting seven MEANINGFUL cells out of
# it is the work, and it turns on two questions asked once per family and written down here.
#
# ------------------------------- QUESTION 1: what does "20 bars" mean? ------------------------
#
# Every bar-counted default in this file was written for an hourly bar. There are exactly two
# honest readings of such a number on another chart, and which one applies is a fact about the
# MECHANISM, not a preference:
#
#   BAR-RELATIVE (the default; nothing is rescaled). A window that defines a STATISTIC over the
#   chart's own bars -- a z-score lookback, a correlation window, an ATR window, a factor
#   estimation window, a refit stride, a holding TTL. `lookback=120` is a 120-bar spread z-score
#   on every chart: five days of it on H1, ten hours of it on M5, six months of it on D1. Those
#   are three different, well-posed, economically distinct questions, and PRESERVING that
#   difference is the entire reason to hunt seven charts instead of one. Force them all to a
#   fixed wall-clock span and the M1 cell and the D1 cell compute the same number -- seven times
#   the compute for one mechanism, which is exactly the "thousands of meaningless cells" outcome.
#   It is also what makes the ladder produce the lanes the principal named: the same family is a
#   scalp on M1, an intraday on M15, a swing on D1, without a second family being written.
#
#   WALL-CLOCK (declared in `WALL_CLOCK_PARAMS`, rescaled by `universe_registry.scale_bars`). A
#   parameter that counts bars only in order to express a duration THE MECHANISM'S OWN CAUSE IS
#   DATED BY: a financing night, the days around a month turn, a weekly report's shelf life, a
#   macro print's, the hours either side of a named clock moment. Those causes do not resample.
#   `family_carry`'s `hold_bars=120` is five days of rollover; left alone on M1 it is two hours
#   and collects no financing at all, so the family would be measuring something it is not named
#   for -- a quiet-regime momentum sleeve wearing the word "carry", which is the exact failure
#   the family's own docstring refuses.
#
# The rescale is the IDENTITY at H1 by construction (`scale_bars(n, "H1") == n`), so declaring a
# parameter wall-clock moves no hourly cell by anything. `test_timeframe_identity` pins that.
#
# ------------------------- QUESTION 2: can this family speak on that chart? -------------------
#
# `FAMILY_TIMEFRAMES` records, per family, the charts on which its claim is EXPRESSIBLE, with the
# reason. Only exceptions are listed; everything absent runs on all seven. An exclusion here is
# not a gate and not a screen -- no cell that runs faces a different bar, and the ten gates are
# untouched. It is the same statement `NOT_SOURCED_HERE` already makes one layer out: a family
# that would return [] on every symbol of a chart, and be filed as a data gap, is worse than one
# that says out loud where it cannot speak (WS-005, absence read as a clean verdict).
# ==============================================================================================

#: Charts a family may be enumerated on, and WHY it is not all seven. Absent = all seven.
#: The value is (timeframes, reason); a test asserts every reason is worth reading.
FAMILY_TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = {
    # ---- bounded ABOVE: the claim names ONE HOUR, and a bar that spans four cannot locate it.
    # These gate on `d.index.hour == <a named hour>`. On H4 the stamp hours are 0/4/8/12/16/20 so
    # a close_hour of 22 never matches and the family returns [] on every symbol; on D1 there is
    # one stamp a day. Below the hour the same gate selects every bar inside the named hour,
    # which is a FINER statement of the same claim and is exactly what the fine charts are for.
    "hedging_demand_close": (
        ("M1", "M5", "M15", "M30", "H1"),
        "fires in the institutional closing HOUR (close_hour, a broker stamp-hour); a chart whose "
        "bars span four hours or a day cannot carry that hour, so the family would return [] on "
        "every symbol and be filed as a data gap rather than as an inexpressible claim"),
    "fx_fixing_reversal": (
        ("M1", "M5", "M15", "M30", "H1"),
        "the claim is about the hour containing the 16:00 London fix; a four-hour or daily bar "
        "cannot locate a fix, and the pre-fix window it measures is minutes to an hour wide"),
    "session_handoff": (
        ("M1", "M5", "M15", "M30", "H1"),
        "reads one session's first bars and trades a later session's named hour; both ends of the "
        "claim are stamp-hours, which a bar spanning four hours or a day does not resolve"),
    "generic": (
        ("M1", "M5", "M15", "M30", "H1"),
        "its CONTEXT vocabulary is broker-hour session windows (asia/london/new_york/overlap); on "
        "a four-hour bar those masks resolve to two or three stamps a day and on a daily bar to "
        "none at all, so a coordinate naming a session would be tested somewhere else entirely. "
        "The OUTPUT horizons ('1h', '4h', 'daily') are converted to the chart's own bars by "
        "`family_generic._hold_bars`, so they mean the same market time on every chart here"),
    "clock_transition": (
        ("M1", "M5", "M15", "M30", "H1"),
        "the whole mechanism is ONE named stamp-hour -- a fix, a settlement, a handoff, a rollover "
        "-- and it already refuses a stamp hour the bars do not carry; declaring the domain says "
        "so before the sweep spends a pass discovering it on every symbol"),
    "lvc_asia_london": (
        ("M5",),
        "a source-faithful reproduction of a public EA whose defaults are pinned to a named blob "
        "and whose windows are M5-bar counts (recent_extreme_bars=3 is fifteen minutes). Run on "
        "another chart it is no longer the thing it reproduces, and the ablation it exists to "
        "settle would be answered about a different strategy"),
    "style_premia": (
        ("H1",),
        "AQR's six styles are defined on daily-to-annual horizons, and this implementation spells "
        "them as HOURLY BAR COUNTS INLINE rather than as parameters -- a 48-bar vol, a 252-bar "
        "momentum, 500/1000-bar value and beta windows. They cannot be re-expressed from outside "
        "the family, so on M1 '252' would mean four hours and on D1 a year; declared H1 rather "
        "than run somewhere those numbers are silently a different claim"),
    # ---- bounded BELOW: the INFORMATION does not arrive that fast.
    "macro_conditional": (
        ("H1", "H4", "D1"),
        "the conditioning variable is a DAILY FRED print, lagged a publication day and forward-"
        "filled; emitting a decision on every M1 bar asserts 1,440 independent decisions a day "
        "from a number that moves once. Below the hour this multiplies cells without adding one "
        "bit of information, which is the definition of a meaningless cell"),
    "relative_value": (
        ("H1", "H4", "D1"),
        "joins this instrument to a peer BAR FOR BAR. Below the hour that join measures "
        "non-synchronous trading rather than a common factor -- an equity CFD prints only in its "
        "cash session while an FX cross prints around the clock -- so the inner join collapses and "
        "the residual is an artifact of quoting hours (the Scholes-Williams problem)"),
    "correlation_regime": (
        ("H1", "H4", "D1"),
        "same bar-for-bar join as relative_value: a correlation BREAKDOWN measured on M1 bars "
        "across instruments with different quoting hours is a measurement of the quoting hours"),
    "cross_asset_residual": (
        ("H1", "H4", "D1"),
        "projects out several factor instruments bar for bar; below the hour the factor betas are "
        "biased toward zero by non-synchronous quoting and the 'unexplained' residual is mostly "
        "the asynchrony. The same reason keeps the eight-frame factor basket off the fine charts"),
    "pca_residual": (
        ("H1", "H4", "D1"),
        "extracts the universe's latent factors from a correlation matrix of factor instruments; "
        "at sub-hourly sampling that matrix is dominated by asynchronous quoting, and a "
        "Marchenko-Pastur cut on a noise structure that is not sampling noise keeps the wrong "
        "eigenvalues"),
    "lead_lag": (
        ("H1", "H4", "D1"),
        "trades the laggard against a DRIVER instrument bar for bar at a measured lag; a lag "
        "measured across instruments with different quoting hours below the hour is the quoting "
        "difference, not the information flow"),
}

#: Parameters whose bar count expresses a WALL-CLOCK duration the mechanism's cause is dated by.
#: Everything not listed is bar-relative and is left exactly as written. See the essay above.
WALL_CLOCK_PARAMS: dict[str, tuple[str, ...]] = {
    # Financing is paid per NIGHT. A hold that does not span nights collects no carry.
    "carry": ("hold_bars",),
    # The month-turn flow window is days wide; the hold has to reach across it.
    "turn_of_month": ("ttl_bars",),
    # "One decision per UTC day", and the hold is that day.
    "calendar_month": ("ttl_bars",),
    # A weekly report's positioning extreme unwinds over days, not over N bars of any chart.
    "cot_positioning": ("ttl_bars",),
    # A daily macro regime persists for days; the hold is stated in that clock.
    "macro_conditional": ("ttl_bars",),
    # The hours either side of a named clock moment. Each of these is a genuine BAR OFFSET in its
    # family (`j = i - pre_window_bars`, `j = i - lead_bars`, `ttl_bars=hold_bars`), so rescaling
    # holds the wall-clock span the mechanism names.
    "hedging_demand_close": ("hold_bars",),
    "fx_fixing_reversal": ("pre_window_bars", "hold_bars"),
    "session_handoff": ("hold_bars",),
    "clock_transition": ("lead_bars", "hold_bars"),
    # CONSIDERED AND DELIBERATELY ABSENT, because "bars" in a parameter name is not evidence that
    # the family counts bars with it:
    #
    #   session_handoff.source_bars -- reads as a bar count and is used as an HOUR OFFSET:
    #       `hours == source_start_hour + source_bars - 1`. Rescaled to 60 on M1 it would ask for
    #       stamp-hour 62, which no bar carries, and the family would return [] on every symbol
    #       of every fine chart -- filed as a data gap, the failure mode this whole file is built
    #       to avoid. Left unscaled, the source window is the chart's own first bar of the
    #       session, which is a finer statement of the same claim rather than a broken one.
    #       (The naming is the family's to fix; scaling around it would hide it.)
}


def timeframe_domain(family: str) -> tuple[str, ...]:
    """The charts `family` may be enumerated on. Every family that does not declare gets all."""
    declared = FAMILY_TIMEFRAMES.get(family)
    return declared[0] if declared else tuple(_TIMEFRAMES)


def timeframe_refusal(family: str, timeframe: str) -> str | None:
    """Why `family` is not run on `timeframe`, or None when it is. Never a silent skip."""
    declared = FAMILY_TIMEFRAMES.get(family)
    if declared is None or str(timeframe).upper() in declared[0]:
        return None
    return f"{family} runs on {'/'.join(declared[0])} only -- {declared[1]}"


def timeframe_overrides(family: str, timeframe: str) -> dict[str, int]:
    """This family's WALL-CLOCK defaults re-expressed on `timeframe`. `{}` at H1, always.

    Read from the function's OWN signature rather than restated here, so a family that changes a
    default cannot silently keep being scheduled with the old one; and returned as explicit
    numbers so the candidate's identity carries what actually ran. Nothing downstream has to know
    this function exists -- the gauntlet and the forward engine rebuild the cell from the params
    on the certificate, which are already the scaled ones.
    """
    names = WALL_CLOCK_PARAMS.get(family)
    if not names or str(timeframe).upper() == _REFERENCE_TF:
        return {}
    fn = ORTHOGONAL_FAMILIES.get(family)
    if fn is None:
        return {}
    import inspect
    params = inspect.signature(fn).parameters
    out: dict[str, int] = {}
    for name in names:
        p = params.get(name)
        if p is None or p.default is inspect.Parameter.empty:
            continue
        if not isinstance(p.default, int) or isinstance(p.default, bool):
            continue
        out[name] = _scale_bars(p.default, timeframe)
    return out
