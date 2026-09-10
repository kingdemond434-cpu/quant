"""Where this instrument stands against the others, rather than against its own past.

THE MISSING AXIS. Every price family registered on this desk is a TIME-SERIES claim: given this
instrument's history, trade this instrument. Not one of them ranks the universe at a point in
time. That absence is a real hole rather than a stylistic one, because a cross-sectional bet can
be right on a day when every time-series family is flat -- it is a claim about DISPERSION, not
about direction, and dispersion exists whether or not anything is trending.

WHY IT IS ORTHOGONAL BY CONSTRUCTION, not by measurement. The signal for EURUSD here depends on
how EURUSD stands against eighty-five other pairs. Two instruments can both be rising while one
ranks top and the other bottom, so this family can be short an instrument that every trend family
is long -- and that disagreement is the mechanism, not a defect. Its failure mode is its own too:
it loses when the whole cross-section moves together (a dollar day, a risk event), which is
exactly when a trend family is at its best.

WHAT IT IS NOT. It is not "buy the strongest trend". `analyst_rank.BaselineRanker` already does
that -- it sorts on measured trend strength -- and sorting a time-series property still leaves a
time-series bet. What is ranked here is RELATIVE displacement: an instrument enters the book
because it is extreme AGAINST ITS PEERS AT THIS BAR, and an instrument in a strong absolute trend
is declined when the rest of the universe is stronger.

WHY NOT `analyst_rank.build_brief`. It builds the identical dimensionless cross-section, on bars
at or before `i`, and it is the right implementation for the job it has: ONE call, at the live
bar, now. It slices `df.iloc[:i+1]` and recomputes ATR over the whole window per call, so it is
O(n) per bar per instrument -- fine once, quadratic across a backtest (86 instruments over 5,000
bars is billions of operations). The features below are deliberately the same quantities computed
vectorised, so the live ranker and this family are describing the same cross-section.

NO LOOKAHEAD, and the two ways it could enter here:
    A bar's rank uses only that bar's features, and every feature is a trailing window. Nothing
    reads across the row into the future.
    PEERS ARE ALIGNED EXACTLY AND NEVER FORWARD-FILLED. A forward-filled peer contributes a price
    that did not exist, and worse, it silently RE-RANKS everything else at that bar. An instrument
    that had not started trading yet must be absent from the cross-section, not carried backwards
    into it, or the ranking is decided partly by instruments that were not quotable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1

#: Below this many usable peers a "rank" is not a cross-section, it is a small sort. Ranking
#: against three instruments produces a top decile of one and a signal on almost every bar.
MIN_PEERS = 10

#: The displacement horizons this family will rank on, in bars. Named so a certificate carries
#: which one was earned, and kept few on purpose: one horizon per hypothesis.
HORIZONS: tuple[int, ...] = (6, 24, 120)


def _displacement(d: pd.DataFrame, horizon: int, atr_n: int) -> pd.Series:
    """Trailing move over `horizon` bars, expressed in ATRs so instruments are comparable.

    DIMENSIONLESS IS THE WHOLE POINT, and it is why a raw return will not do: USDJPY moves in
    figures and EURCHF in pips, so ranking raw returns ranks volatility. Dividing by the
    instrument's own ATR is what makes "further than its peers" mean the same thing on both.
    """
    a = _atr(d, atr_n)
    move = d["close"].astype(float) - d["close"].astype(float).shift(horizon)
    return (move / a.where(a > 0)).replace([np.inf, -np.inf], np.nan)


def family_cross_sectional(
    df: pd.DataFrame,
    *,
    peers: dict[str, pd.DataFrame] | None = None,
    symbol: str = "",
    horizon: int = 24,
    mode: str = "momentum",
    top_frac: float = 0.2,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 24,
    cooldown_bars: int = 6,
    min_peers: int = MIN_PEERS,
) -> list[Signal]:
    """Trade `symbol` when it sits in the extreme `top_frac` of the peer cross-section.

    `mode` is "momentum" (buy the top of the cross-section, sell the bottom) or "reversal" (the
    opposite). They are separate hypotheses and are kept as separate modes rather than one
    function that picks whichever fits, for the same reason `family_clock_transition` splits its
    three: a family that chooses its direction after seeing the data has tested nothing.
    """
    if peers is None or mode not in ("momentum", "reversal") or not 0 < top_frac < 0.5:
        return []
    if symbol not in peers or horizon < 1:
        return []
    d = _h1(df)
    if len(d) < horizon + atr_n + 2:
        return []

    # EXACT ALIGNMENT ON THE TRADED INSTRUMENT'S CLOCK, no reindex-and-fill. A peer with no bar
    # here is absent from this bar's ranking, which is what "not quotable" has to mean.
    cols: dict[str, pd.Series] = {}
    for sym, frame in peers.items():
        try:
            p = _h1(frame)
        except Exception:                                  # noqa: BLE001 -- a bad peer is not fatal
            continue
        if "close" not in p.columns or len(p) < horizon + atr_n + 2:
            continue
        cols[sym] = _displacement(p, horizon, atr_n).reindex(d.index)
    if symbol not in cols or len(cols) < min_peers:
        return []

    table = pd.DataFrame(cols, index=d.index)
    usable = table.notna().sum(axis=1)
    # `rank(pct=True)` over the row: 1.0 is the most displaced upward, 0.0 the most downward.
    pct = table.rank(axis=1, pct=True, na_option="keep")
    mine = pct[symbol]

    atr = _atr(d, atr_n)
    close = d["close"].astype(float)
    hi, lo = 1.0 - top_frac, top_frac
    signals: list[Signal] = []
    armed_from = 0
    for pos in range(len(d)):
        if pos < armed_from or int(usable.iloc[pos]) < min_peers:
            continue
        r = mine.iloc[pos]
        if not np.isfinite(r):
            continue
        if r >= hi:
            side = 1 if mode == "momentum" else -1
        elif r <= lo:
            side = -1 if mode == "momentum" else 1
        else:
            continue
        a = float(atr.iloc[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(close.iloc[pos])
        signals.append(Signal(time=d.index[pos], side=side,
                              stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr,
                              ttl_bars=int(ttl_bars), tag=f"xsec_{mode}_{horizon}",
                              trigger=None, wait_bars=1))
        armed_from = pos + max(1, int(cooldown_bars))
    return signals
