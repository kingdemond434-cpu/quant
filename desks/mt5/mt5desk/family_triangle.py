"""Three quotes that must agree, and the residual when they do not.

THE MECHANISM CLASS. Every other price family on this desk asks what ONE instrument's own history
implies about its future. This asks what TWO instruments imply about a THIRD, right now, through
a relationship that is an identity rather than a regularity: if EURUSD and USDJPY are quoted, then
EURJPY is determined. The residual between the quoted cross and the implied one is not a pattern
someone found in a backtest -- it is a disagreement between three prices that arithmetic says
cannot disagree.

That is what makes it orthogonal, and the orthogonality is structural rather than empirical: the
residual can be wide while every trend, breakout, calendar and jump family in the book is flat,
because it is not a fact about direction at all. Its failure mode is equally its own -- it loses
when the disagreement is REAL (one leg genuinely repricing, the others stale or illiquid) rather
than when a move exhausts or a range breaks.

WHAT THIS IS NOT, and the docstring says it plainly because the name invites the wrong idea. This
is NOT triangular arbitrage. Real triangular arbitrage is closed in microseconds by people with
co-located hardware, and none of it survives to an H1 bar close. What survives is a RESIDUAL that
moves with relative liquidity, stale quoting and one-sided flow, and the tradeable claim is that
it MEAN-REVERTS -- an ordinary statistical hypothesis that has to earn its certificate like any
other, against costs, on the gauntlet. A family that claimed free money here would be lying.

THE THRESHOLD IS THE WHOLE DESIGN. Crossing three spreads to collect a residual smaller than
three spreads is a machine for paying the broker, so the entry is gated on BOTH a rolling z-score
(is this large for this triangle?) and an absolute floor in basis points (is this large at all?).
The miner sets the floor from the three legs' measured median spreads; the default is 0 only so
the family is testable without a registry, and a search that leaves it there will be certifying
noise it cannot capture.

NO LOOKAHEAD, and two specific ways it could have crept in:
    The residual's scale is `rolling(...).std().shift(1)` -- a wide residual must not raise the
    bar it is measured against, or the family goes blind exactly when it should fire.
    The legs are aligned by EXACT index and never forward-filled. Forward-filling a missing leg
    quotes a price that did not exist at that bar, and every gap would manufacture a residual --
    the largest ones, at precisely the illiquid moments the hypothesis is least true.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1


def family_triangle(
    df: pd.DataFrame,
    *,
    leg_b: pd.DataFrame | None = None,
    leg_c: pd.DataFrame | None = None,
    leg_b_symbol: str = "",
    leg_c_symbol: str = "",
    sign_b: int = 1,
    sign_c: int = 1,
    entry_z: float = 2.5,
    min_abs_bp: float = 0.0,
    norm: int = 240,
    hold_bars: int = 6,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 12,
    cooldown_bars: int = 3,
) -> list[Signal]:
    """Fade the residual between `df`'s quoted price and the one its two legs imply.

    `sign_b`/`sign_c` are +1 when a leg enters the implied price as quoted and -1 when it enters
    inverted (GBPUSD against USDJPY needs one of each to imply GBPJPY). They are DECLARED by the
    enumerator that found the triangle, never searched here: the correct orientation is a fact
    about the two symbols' names, and a family that tried both would be running two hypotheses
    while reporting one.
    """
    if leg_b is None or leg_c is None or sign_b not in (1, -1) or sign_c not in (1, -1):
        return []
    d = _h1(df)
    if len(d) < max(norm + 2, atr_n + 2):
        return []
    b, c = _h1(leg_b), _h1(leg_c)
    if "close" not in b.columns or "close" not in c.columns:
        return []

    # EXACT ALIGNMENT, NEVER FORWARD-FILLED -- see the header. A bar where any leg is missing is
    # dropped rather than imputed, so the residual is only ever computed from three prices that
    # all existed at the same close.
    px = pd.DataFrame({"a": d["close"].astype(float)})
    px["b"] = b["close"].astype(float).reindex(d.index)
    px["c"] = c["close"].astype(float).reindex(d.index)
    px = px[(px > 0).all(axis=1)].dropna()
    if len(px) < norm + 2:
        return []

    implied = sign_b * np.log(px["b"]) + sign_c * np.log(px["c"])
    resid = np.log(px["a"]) - implied
    # The level of the residual absorbs the convention (a triangle quoted through a third
    # currency carries a constant offset); what is traded is the deviation from its own recent
    # centre, so a mis-declared sign shows up as a drifting centre rather than as a fake edge.
    centre = resid.rolling(norm, min_periods=norm).mean().shift(1)
    scale = resid.rolling(norm, min_periods=norm).std().shift(1)
    dev = resid - centre

    atr = _atr(d, atr_n)
    signals: list[Signal] = []
    armed_from = 0
    for pos in range(len(px)):
        ts = px.index[pos]
        if pos < armed_from:
            continue
        s = float(scale.iloc[pos]) if pd.notna(scale.iloc[pos]) else 0.0
        v = float(dev.iloc[pos]) if pd.notna(dev.iloc[pos]) else float("nan")
        if s <= 0 or not np.isfinite(v):
            continue
        if abs(v) < entry_z * s or abs(v) * 1e4 < min_abs_bp:
            continue
        # Quoted ABOVE implied -> sell the quote back toward the legs, and the mirror.
        side = -1 if v > 0 else 1
        a = float(atr.reindex([ts]).iloc[0]) if ts in atr.index else float("nan")
        if not np.isfinite(a) or a <= 0:
            continue
        p = float(px["a"].iloc[pos])
        stop = p - side * stop_atr * a
        target = p + side * stop_atr * rr * a
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=int(ttl_bars), tag="triangle", trigger=None,
                              wait_bars=1))
        armed_from = pos + max(1, int(cooldown_bars))
    return signals
