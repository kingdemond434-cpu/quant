"""Is this a trending market right now, which way, and has the trend died?

WHY NOT "DAYS WITH A 100-POINT RANGE"

Because that is three separate mistakes. It is only knowable at the close, so
any rule trained on it is reading the future. It is an absolute number, so it
means something different at gold 1,800 and gold 4,500 and nothing at all on
EURUSD. And it is a threshold, so a 95-point day -- indistinguishable in every
respect that matters -- is filed as the opposite category.

Every quantity here is therefore a RATIO: a move in units of the current ATR, a
range against its own trailing median, a count against its own total. Multiply
every price in the input by three and the output is unchanged. That is what
makes a quiet Tuesday's trend and an FOMC day's trend the same object, measured
in each one's own units, and it is why the small trend days are not thrown away.

SYMMETRY IS AN INVARIANT, NOT AN INTENTION

`strength` is direction-agnostic and `direction` carries the sign, so a
short-side trend is not an afterthought bolted onto a long-side detector. The
test suite mirrors the price series and requires strength to be identical and
direction to flip. A detector that quietly works better on rallies is the most
expensive kind of bug on an instrument that falls faster than it rises.

CAUSALITY

Every array is built with trailing windows only, and the trailing statistics are
rolling rather than full-sample -- a quantile taken over the whole history is a
number from the future wearing the clothes of a constant. tests/ corrupts the
bars after i and requires the reads at or before i to be byte-identical.

WHAT IT IS FOR

Two jobs, and they are different. `strength`/`direction` gate whether a runner
should be given room at all. `dying` is the separate question of whether the
move that justified the room has stopped, and it is deliberately not the mirror
of the entry condition: getting in wants evidence, getting out wants the absence
of it, and requiring symmetric evidence to exit is how a runner gives back
everything it made.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["TrendRead", "efficiency_ratio", "atr", "read"]


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder true range, simple-averaged. NaN until there are n+1 bars."""
    out = np.full(len(c), np.nan)
    if len(c) < 2:
        return out
    tr = np.maximum(h[1:] - l[1:],
                    np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    out[1:] = pd.Series(tr).rolling(n).mean().to_numpy()
    return out


def efficiency_ratio(c: np.ndarray, n: int) -> np.ndarray:
    """Kaufman's ratio: net distance over path length, in [0, 1].

    1.0 is a straight line and 0.0 is a round trip. It is the cleanest available
    statement of "trend or chop" precisely because it is a ratio of two lengths
    and so has no units to be wrong about.
    """
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    step = np.abs(np.diff(c, prepend=c[0]))
    path = pd.Series(step).rolling(n).sum().to_numpy()
    net = np.abs(c - np.concatenate([np.full(n, np.nan), c[:-n]]))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(path > 0, net / path, 0.0)
    out[:n] = np.nan
    return out


@dataclass(frozen=True)
class TrendRead:
    """Per-bar arrays. Every element uses bars at or before its own index."""
    strength: np.ndarray      # 0..1, direction-agnostic
    direction: np.ndarray     # -1 / 0 / +1
    dying: np.ndarray         # bool: the move that earned the room has stopped
    er: np.ndarray
    expansion: np.ndarray     # ATR against its own trailing median
    displacement: np.ndarray  # |net move| in ATRs
    persistence: np.ndarray   # agreement of the bars with the net direction


def read(df: pd.DataFrame, *, n: int = 12, atr_n: int = 14,
         regime_n: int = 240, floor: float = 0.35,
         decay: float = 0.6, shock_k: float = 1.0) -> TrendRead:
    """Score trendiness at every bar.

    `floor` is the strength below which direction is reported as 0 -- not a
    prediction threshold, just the point past which calling something a trend
    stops meaning anything. `decay` is the fraction of its OWN recent peak that
    strength must fall to before the trend is called dead, so a violent regime
    is allowed to decay violently and a quiet one quietly. `shock_k` is a
    counter-trend bar big enough to end it outright, in ATRs.

    None of these are point values and none of them are fitted; they are the
    three shapes the mechanism needs and they are arguments so that
    research/trend_gate.py can sweep them and report the trial count.
    """
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    m = len(c)

    a = atr(h, l, c, atr_n)
    er = efficiency_ratio(c, n)

    # Range expansion: today's volatility against its own trailing normal.
    # Rolling, not full-sample -- a median over all history is a fact from the
    # future, and it is exactly the kind that never announces itself.
    med = pd.Series(a).rolling(regime_n, min_periods=atr_n * 3).median().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        expansion = np.where(med > 0, a / med, np.nan)

    net = c - np.concatenate([np.full(n, np.nan), c[:-n]])
    with np.errstate(invalid="ignore", divide="ignore"):
        displacement = np.where(a > 0, np.abs(net) / a, np.nan)

    # Persistence: do the individual bars agree with the net move, or did it
    # get there by accident? Rescaled so 0.5 (a coin flip) maps to 0.
    step = np.sign(np.diff(c, prepend=c[0]))
    agree = np.full(m, np.nan)
    sgn = np.sign(net)
    up = pd.Series((step > 0).astype(float)).rolling(n).mean().to_numpy()
    for i in range(n, m):
        if not np.isfinite(sgn[i]) or sgn[i] == 0:
            agree[i] = 0.0
        else:
            frac = up[i] if sgn[i] > 0 else 1.0 - up[i]
            agree[i] = max(0.0, 2.0 * (frac - 0.5))

    def squash(x, cap):
        return np.clip(np.where(np.isfinite(x), x, 0.0) / cap, 0.0, 1.0)

    # Unweighted mean. The weights are NOT fitted, because fitting four weights
    # on the same sample the result is read from is how a detector scores well
    # once and never again. Equal weights is a decision, and a defensible one.
    strength = (squash(er, 1.0) + squash(expansion, 2.0)
                + squash(displacement, 3.0) + squash(agree, 1.0)) / 4.0
    strength = np.where(np.isfinite(a) & np.isfinite(er), strength, 0.0)

    direction = np.where(strength >= floor, np.sign(net), 0.0)
    direction = np.where(np.isfinite(direction), direction, 0.0).astype(int)

    # --- dying ------------------------------------------------------------
    # MEASURED AGAINST THE DIRECTION THAT WAS IN FORCE, not against the current
    # one. The first version compared everything to sign(net) and so could not
    # see a reversal at all: when a long trend rolls over into a clean short
    # trend, `net` flips with it and the detector cheerfully reports a strong
    # trend, strength intact, nothing dying. That is the exact moment a runner
    # has to be banked, and it was the one moment the flag stayed silent.
    #
    # So the established direction is carried forward, and three different
    # deaths are recognised against it: the move fades to `decay` of its own
    # recent peak, a single bar goes `shock_k` ATRs the wrong way, or the
    # direction outright flips -- which is not a warning, it is the obituary.
    held = np.zeros(m, dtype=int)
    cur = 0
    for i in range(m):
        if direction[i] != 0:
            cur = int(direction[i])
        held[i] = cur

    peak = pd.Series(strength).rolling(n, min_periods=1).max().to_numpy()
    faded = strength < decay * peak

    bar = np.diff(c, prepend=c[0])
    with np.errstate(invalid="ignore", divide="ignore"):
        adverse = np.where(a > 0, -held * bar / a, 0.0) >= shock_k

    flipped = np.zeros(m, dtype=bool)
    flipped[1:] = ((direction[1:] != 0) & (held[:-1] != 0)
                   & (direction[1:] != held[:-1]))

    dying = (faded | adverse | flipped) & (held != 0)

    return TrendRead(strength=strength, direction=direction,
                     dying=np.asarray(dying, dtype=bool), er=er,
                     expansion=expansion, displacement=displacement,
                     persistence=agree)
