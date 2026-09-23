"""The four preregistered mechanisms, as runnable signal functions.

WHY THIS EXISTS (principal, 2026-08-29)

`libs/research/edge_queue.py` holds four mechanisms as PREREGISTRATIONS -- claim, payer,
falsifiers, distinguishing test. A preregistration cannot be tested. These are the implementations
that make them candidates the gauntlet can actually judge, and they are deliberately separate
files so the claim cannot be edited to match the code after results arrive.

EACH FUNCTION IMPLEMENTS THE CLAIM AND NOTHING ELSE. That is what `tri_alignment` checks and what
this desk has no other defence against: a gamma story implemented as RSI passes ten gates on the
strength of the RSI and enters the book carrying a rationale that is fiction. So every function
here conditions on the thing its claim names -- a session clock, a fix window, a liquidity state --
and would be REJECTED by tri-alignment if it did not.

THEY ARE ORDINARY CANDIDATES. No promotion authority, no special path, no exemption. They enter
the docket where everything else does and face the identical gauntlet. The reason to expect more
from them is not that they are privileged but that each names a PAYER -- a participant who must
trade for a reason that is not a forecast -- which is the property arbitrage cannot compete away.

WHAT IS DELIBERATELY MISSING. None of these has an options-implied input, because this desk has
no options data. The gamma-conditioned families use realised volatility as an ACKNOWLEDGED PROXY
and say so in their parameter names; a proxy called by its real name is a limitation, while a
proxy called by the name of the thing it proxies is a lie the whole desk then believes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

#: Broker clock is UTC+3 for Fusion. Every session constant below is in BROKER hours, because the
#: bars are, and converting per-signal is where an off-by-three-hours bug hides for months.
_BROKER_OFFSET_H = 3


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _session_return(df: pd.DataFrame, start_h: int, end_h: int) -> pd.Series:
    """Return accumulated from `start_h` to each bar within the same session day."""
    h = df.index.hour
    day = df.index.floor("D")
    mask = (h >= start_h) & (h <= end_h)
    base = df["close"].where(h == start_h).groupby(day).transform("first")
    return (df["close"] / base - 1.0).where(mask)


def family_hedging_demand_close(
    df: pd.DataFrame,
    *,
    close_hour: int = 22,               # broker hour of the institutional close
    rod_start_hour: int = 1,            # rest-of-day measured from here
    min_displacement_atr: float = 0.75,  # abnormal move, in ATR -- the QUALITY axis
    vol_n: int = 20,
    stop_atr: float = 1.2,
    rr: float = 1.5,
    hold_bars: int = 2,
    require_elevated_vol: bool = True,   # realised vol as an ACKNOWLEDGED gamma proxy
) -> list[Signal]:
    """H-2026-0001: rest-of-day displacement predicts the final bars, same direction.

    The payer is a short-gamma dealer who must rebalance WITH the move before the close and
    cannot wait for a better price. So the signal fires only in the closing hour, only when the
    day has actually displaced, and only when volatility says the hedging need is large.

    `require_elevated_vol` is a PROXY for the gamma environment and is named as one -- this desk
    has no options data, and a proxy wearing the name of the thing it proxies is a lie.
    """
    if df.empty or len(df) < vol_n * 5:
        return []
    d = df.copy()
    atr = _atr(d, vol_n)
    rod = _session_return(d, rod_start_hour, close_hour)
    rv = d["close"].pct_change().rolling(vol_n).std()
    rv_med = rv.rolling(vol_n * 5).median()

    out: list[Signal] = []
    hours = d.index.hour
    for i in range(vol_n * 5, len(d) - 1):
        if hours[i] != close_hour:
            continue
        a = float(atr.iloc[i])
        r = float(rod.iloc[i]) if np.isfinite(rod.iloc[i]) else np.nan
        px = float(d["close"].iloc[i])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(r):
            continue
        # The displacement must be abnormal relative to the instrument's own range, not merely
        # non-zero: "the day moved" is true every day and is not the claim.
        if abs(r) * px < min_displacement_atr * a:
            continue
        if require_elevated_vol and not (float(rv.iloc[i]) > float(rv_med.iloc[i])):
            continue
        side = 1 if r > 0 else -1          # CONTINUATION, per the preregistration
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold_bars,
                          tag="hedging_demand_close", trigger=None, wait_bars=1))
    return out


def family_fx_fixing_reversal(
    df: pd.DataFrame,
    *,
    fix_hour: int = 19,                 # broker hour containing the fix (16:00 London = 19 broker)
    pre_window_bars: int = 2,
    min_displacement_atr: float = 0.6,
    vol_n: int = 20,
    stop_atr: float = 1.0,
    rr: float = 1.2,
    hold_bars: int = 3,
) -> list[Signal]:
    """H-2026-0002: abnormal pre-fix displacement REVERSES after the fix, in proportion.

    The payer is a benchmark tracker who must transact AT the fix regardless of price. The
    reversal is the temporary impact decaying once that demand is gone, so the signal is the
    OPPOSITE sign to the pre-fix move and fires only in the bar after the fix.

    Note the direction: this family and `family_hedging_demand_close` make OPPOSITE predictions
    about a displacement. They are different claims about different payers at different clocks,
    and if both survive on the same instrument at the same hour, one of them is wrong.
    """
    if df.empty or len(df) < vol_n * 5:
        return []
    d = df.copy()
    atr = _atr(d, vol_n)
    hours = d.index.hour
    out: list[Signal] = []
    for i in range(vol_n * 5, len(d) - 1):
        if hours[i] != fix_hour:
            continue
        j = i - pre_window_bars
        if j < 0:
            continue
        a = float(atr.iloc[i])
        px = float(d["close"].iloc[i])
        pre = px - float(d["close"].iloc[j])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(pre):
            continue
        if abs(pre) < min_displacement_atr * a:
            continue
        side = -1 if pre > 0 else 1        # REVERSAL of the pre-fix displacement
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold_bars,
                          tag="fx_fixing_reversal", trigger=None, wait_bars=1))
    return out


def family_session_handoff(
    df: pd.DataFrame,
    *,
    source_start_hour: int = 3,         # first bars of the informative session
    source_bars: int = 1,
    trade_hour: int = 10,               # later session where the information is priced
    min_info_atr: float = 0.5,
    vol_n: int = 20,
    stop_atr: float = 1.2,
    rr: float = 1.5,
    hold_bars: int = 6,
    direction: int = 1,                 # +1 continuation, -1 reversal -- LEARNED, not assumed
) -> list[Signal]:
    """H-2026-0003: the segment that first processes global information predicts the later session.

    `direction` is a PARAMETER rather than a constant on purpose. The preregistration says to
    learn P(continuation|state) and P(reversal|state) separately, because assuming momentum would
    hide whichever regime is the smaller half. The sweep tests both signs and the gauntlet decides.
    """
    if df.empty or len(df) < vol_n * 5:
        return []
    d = df.copy()
    atr = _atr(d, vol_n)
    hours = d.index.hour
    day = d.index.floor("D")

    src_close = d["close"].where(hours == source_start_hour + source_bars - 1)
    src_open = d["open"].where(hours == source_start_hour)
    info = (src_close.groupby(day).transform("first")
            - src_open.groupby(day).transform("first"))

    out: list[Signal] = []
    for i in range(vol_n * 5, len(d) - 1):
        if hours[i] != trade_hour:
            continue
        a = float(atr.iloc[i])
        v = float(info.iloc[i]) if np.isfinite(info.iloc[i]) else np.nan
        px = float(d["close"].iloc[i])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(v):
            continue
        if abs(v) < min_info_atr * a:
            continue
        side = direction * (1 if v > 0 else -1)
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold_bars,
                          tag="session_handoff", trigger=None, wait_bars=1))
    return out


def family_liquidity_gamma_reversal(
    df: pd.DataFrame,
    *,
    min_displacement_atr: float = 1.5,
    vol_n: int = 20,
    liquidity_n: int = 20,
    require_high_liquidity: bool = True,
    require_failed_continuation: bool = True,
    stop_atr: float = 1.0,
    rr: float = 1.2,
    hold_bars: int = 4,
) -> list[Signal]:
    """H-2026-0004: large displacement reverses when liquidity is AMPLE, persists when thin.

    The conditional IS the claim. Unconditional "large move reverses" is short-horizon mean
    reversion with a story attached, and the distinguishing test in the preregistration is the
    SIGN of the liquidity interaction -- so `require_high_liquidity` must be a real filter and the
    sweep must also run it False, or the falsifier cannot fire.

    Liquidity proxy is the bar's own range relative to its recent median: a tight range on normal
    volume is a liquid tape. This desk has no depth data, and the proxy is named for what it is.
    """
    if df.empty or len(df) < max(vol_n, liquidity_n) * 5:
        return []
    d = df.copy()
    atr = _atr(d, vol_n)
    rng = (d["high"] - d["low"])
    rng_med = rng.rolling(liquidity_n * 5).median()
    ret = d["close"].diff()

    out: list[Signal] = []
    start = max(vol_n, liquidity_n) * 5
    for i in range(start, len(d) - 1):
        a = float(atr.iloc[i])
        px = float(d["close"].iloc[i])
        disp = float(ret.iloc[i])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(disp):
            continue
        if abs(disp) < min_displacement_atr * a:
            continue
        liquid = float(rng.iloc[i]) < float(rng_med.iloc[i]) * 1.5
        if require_high_liquidity and not liquid:
            continue
        # FAILED CONTINUATION: the move did not extend into the close of its own bar, which is
        # the observable the preregistration names as the quality axis.
        body = float(d["close"].iloc[i]) - float(d["open"].iloc[i])
        extended = (np.sign(body) == np.sign(disp)) and abs(body) > 0.7 * abs(disp)
        if require_failed_continuation and extended:
            continue
        side = -1 if disp > 0 else 1       # REVERSAL
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold_bars,
                          tag="liquidity_gamma_reversal", trigger=None, wait_bars=1))
    return out


#: Registered under the SAME registry every other family uses, so admission, the sweep and the
#: gauntlet reach them with no special case. A family behind its own door is a family with its
#: own bar, which is the defect that took three verdict engines to notice.
EDGE_QUEUE_FAMILIES = {
    "hedging_demand_close": family_hedging_demand_close,
    "fx_fixing_reversal": family_fx_fixing_reversal,
    "session_handoff": family_session_handoff,
    "liquidity_gamma_reversal": family_liquidity_gamma_reversal,
}
