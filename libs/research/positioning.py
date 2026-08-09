"""POSITIONING MECHANISMS FROM OPEN INTEREST AND LONG/SHORT RATIO -- the crypto form of the one
idea the options webinar was most emphatic about.

THE SOURCE CLAIM (WorldQuant BRAIN options webinar, 2026-08-01 batch): "rather than only looking
at volumes of options traded, you must look at OPEN INTEREST. The number of shares outstanding in
a stock is constant; options contracts can be UNDERWRITTEN, so the count itself changes." The
put/call open-interest ratio is then read as positioning: more puts underwritten means more
participants are positioned for a fall.

WHY IT PORTS TO THIS DESK WHEN THE FORMULAS DO NOT. Perpetual futures have no puts and no calls,
so the specific ratio is meaningless here. But the STRUCTURE is identical and the desk already
records both halves of it:
  OPEN INTEREST -- the notional actually outstanding, which rises when new positions are opened
  and falls when they are closed. Volume counts churn; OI counts commitment. Recorded by
  scripts/run_recorder_bybit.py as `openInterest`.
  LONG/SHORT ACCOUNT RATIO -- the venue's own published split of accounts positioned each way.
  This is the perp analogue of put/call: it is a direct read of which side the crowd is on.

AND THE DESK HAS BEEN CARRYING THESE AS SLOT NAMES WITH NO MECHANISM BEHIND THEM.
libs/research/slot_registry.py lists `oi_divergence` and `ls_contrarian` in _DERIVATIVE_BUILTIN
and maps them to evidence paths, but `grep -rn "def oi_divergence"` across the entire repo
returns NOTHING. They are forward-slot candidates that cannot be tested because no function
computes them -- rubric class 5, "a required input nobody produces", lesson L0040. This file is
the missing producer.

THE TWO MECHANISMS, each with the reason someone is forced to trade against it:

  1. OI DIVERGENCE. Price rises while open interest FALLS. New money is not arriving; the move is
     being made by shorts closing. That is buying by the FORCED, and it exhausts -- once the
     shorts are out there is no bid left. The mirror case (price falls on falling OI) is longs
     capitulating and exhausts the same way.
     MECHANISM: a short closing must buy regardless of price or view. A rally made of forced
     buying has no informed marginal buyer behind it, so it reverts when the forcing stops.
     FALSIFIER: OI-divergent moves revert no more often than OI-confirmed ones.

  2. LONG/SHORT CONTRARIAN. The retail account ratio at an extreme, faded. This is the perp
     put/call analogue, and it is the only one of the two with a well-documented crowd behind it.
     MECHANISM: crowded leverage on one side is fuel. Liquidation cascades run toward the crowd,
     because that is where the stops are, and the venue publishes exactly where they are.
     FALSIFIER: extremes in the ratio carry no forward information once funding is controlled for
     -- i.e. it is a repackaged funding signal, which the desk already trades.

DELIBERATELY BUILT WITHOUT A DATA FETCH. These take arrays. The recorder owns acquisition and the
campaign owns scoring; a signal module that also fetches would silently hide a missing feed as a
flat signal, which is the failure mode this desk has already paid for twice (heartbeat-not-data,
and the frozen series that produced a 1.4e31 premium).

EVERY FUNCTION RETURNS A POSITION SERIES in [-1, 1] aligned to its inputs, computed only from
information at or before each bar, applied to the NEXT bar's return by
transcript_candidates.positions_to_returns.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "CANDIDATES",
    "LS_EXTREME_PCT",
    "ls_contrarian",
    "oi_divergence",
    "oi_price_state",
]

#: Percentile of the TRAILING long/short distribution beyond which the crowd counts as extreme.
#: 15/85 rather than 5/95: a 5% tail on daily data fires a handful of times a year, which cannot
#: reach validate()'s 250-observation floor on any history this desk owns. Chosen for testability
#: and stated rather than swept -- sweeping it here would fit the threshold on the same data the
#: hypothesis is about, and the gauntlet counts every swept cell as a trial.
LS_EXTREME_PCT = 15.0

#: Below this the divisor is treated as having no measurable magnitude. Not `> 0`: numpy returns
#: floating-point dust rather than exactly zero for the variance of a frozen series, and dividing
#: dust by dust produced a 1.4e31 signal here on 2026-08-01.
_FLOOR = 1e-12


def _pct_change(x: np.ndarray) -> np.ndarray:
    """Trailing fractional change, first element zero. Guarded against a zero denominator by
    magnitude, so a symbol whose OI feed reports 0 does not produce an infinite signal."""
    a = np.asarray(x, dtype="float64")
    out = np.zeros(len(a))
    if len(a) < 2:
        return out
    prev = a[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        d = np.where(np.abs(prev) > _FLOOR, (a[1:] - prev) / prev, np.nan)
    out[1:] = np.nan_to_num(d, nan=0.0, posinf=0.0, neginf=0.0)
    return out


def oi_price_state(close: np.ndarray, open_interest: np.ndarray, *,
                   n: int = 5) -> np.ndarray:
    """Label each bar by the sign pair (price change, OI change) over `n` bars: 0..3, -1 if short.

        0  price up,   OI up    -- new longs opening. CONFIRMED advance.
        1  price up,   OI down  -- shorts closing. FORCED buying, unconfirmed.
        2  price down, OI up    -- new shorts opening. CONFIRMED decline.
        3  price down, OI down  -- longs closing. FORCED selling, unconfirmed.

    The 1 and 3 cells are the hypothesis; 0 and 2 are the control. Reporting all four rather than
    only the interesting pair is deliberate -- a signal that only ever labels its own thesis
    cannot be checked against the cases where the thesis does not apply.
    """
    c = np.asarray(close, dtype="float64")
    oi = np.asarray(open_interest, dtype="float64")
    if len(c) != len(oi):
        raise ValueError("close and open_interest must be the same length")
    out = np.full(len(c), -1, dtype="int64")
    if len(c) <= n:
        return out
    dp = c[n:] - c[:-n]
    do = oi[n:] - oi[:-n]
    up_p = dp > 0
    up_o = do > 0
    out[n:] = np.where(up_p, np.where(up_o, 0, 1), np.where(up_o, 2, 3))
    # A bar where either series did not move is not one of the four states; leave it unlabelled
    # rather than assigning it to whichever branch the comparison happens to fall through to.
    flat = (np.abs(dp) <= _FLOOR) | (np.abs(do) <= _FLOOR)
    out[n:][flat] = -1
    return out


def oi_divergence(close: np.ndarray, open_interest: np.ndarray, *,
                  n: int = 5) -> np.ndarray:
    """Fade moves that open interest does NOT confirm.

    Short when price rose on falling OI (a rally made of shorts covering); long when price fell on
    falling OI (a decline made of longs capitulating). Flat in the confirmed states, which is most
    of the time -- the signal is deliberately sparse because its mechanism only describes the two
    unconfirmed cells.

    SIGN CONVENTION STATED, because an inverted sign silently tests the opposite hypothesis. The
    claim is that FORCED flow exhausts: a short closing must buy regardless of view, so the rally
    it produces has no informed marginal buyer and reverts once the forcing stops. If the measured
    edge is significant with the sign reversed, the mechanism is REFUTED even though the strategy
    "works", and that must be reported as a refutation rather than banked.
    """
    state = oi_price_state(close, open_interest, n=n)
    pos = np.zeros(len(state))
    pos[state == 1] = -1.0     # price up on falling OI  -> fade the rally
    pos[state == 3] = 1.0      # price down on falling OI -> fade the decline
    return pos


def ls_contrarian(long_short_ratio: np.ndarray, *, window: int = 90,
                  pct: float = LS_EXTREME_PCT) -> np.ndarray:
    """Fade the crowd when the venue's own long/short account ratio reaches a trailing extreme.

    The perp analogue of the put/call open-interest ratio: a direct read of which side retail is
    positioned on, published by the venue.

    THRESHOLDS ARE TRAILING PERCENTILES, NOT LEVELS. A fixed ratio (say 3.0) means something
    different on BTC than on a low-float altcoin, and different in a bull market than a bear one.
    Comparing today's reading against the last `window` bars of its OWN history makes the signal
    scale-free across symbols and regimes -- and, critically, uses only data that existed at the
    time. Ranking against the full sample would leak the future into every early bar and is the
    single most common way a positioning study looks better than it is.

    MECHANISM: crowded leverage is fuel. Liquidation cascades run toward the crowd because that is
    where the stops sit, and the venue publishes their location. Nobody is forced to trade against
    a mild imbalance, which is why only the extremes are traded.
    """
    r = np.asarray(long_short_ratio, dtype="float64")
    pos = np.zeros(len(r))
    for i in range(window, len(r)):
        hist = r[i - window:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) < window // 2 or not np.isfinite(r[i]):
            continue
        lo, hi = np.percentile(hist, [pct, 100.0 - pct])
        if hi - lo <= _FLOOR:
            continue           # a frozen feed is not a consensus
        if r[i] >= hi:
            pos[i] = -1.0      # crowd is long -> fade
        elif r[i] <= lo:
            pos[i] = 1.0       # crowd is short -> fade
    return pos


#: name -> the inputs it needs. Unlike the price-only candidate registries, these take TWO series,
#: so the campaign runner must supply positioning data rather than silently scoring price alone.
CANDIDATES: dict[str, tuple[str, ...]] = {
    "oi_divergence": ("close", "open_interest"),
    "ls_contrarian": ("long_short_ratio",),
}
