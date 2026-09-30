"""CLOSURE WORLDS (Tier S layer 16): the market shut, a session gone, the instrument halted.

Every world in `desks/mt5/research/synthetic_regimes.py` before these kept the venue OPEN: it
moved prices, widened spreads, dropped scattered bars or shifted the clock, but the market always
printed the next hour. Venues do not. A holiday closes a session for days, an exchange outage
shuts the market and it reopens somewhere else, a single instrument is halted on news and trades
again at a price nobody could reach in between. A sleeve holding through any of these meets a
gap its stop cannot fill at, and a sleeve whose signal needs the closed session never fires.

THE THREE WORLDS, each a NAMED, SEEDED transform of a sleeve's own bars (the seed and the sleeve's
name fix the world, on any box):

    market_closure_gap   the market shuts for 48 bars at one random point and reopens GAPPED:
                         those bars are gone, and every bar after the reopen is repriced by a
                         +/-2 sigma sqrt(48) shock -- the move that happened while nobody could
                         trade, landing on the first print
    session_closed       the tape's most active 8-hour session (by absolute return) is removed
                         every day for a 20-day stretch, the holiday/closed-venue regime: the
                         session's move arrives as the next session's opening gap
    instrument_halt      the instrument is halted for 24 bars: the bars stay on the clock but
                         print the pre-halt close flat with zero volume, then trading resumes
                         repriced by a +/-2 sigma sqrt(24) shock -- stale quotes, then a gap

Every transform scales whole bars by one positive factor or replaces them with a flat bar, so
OHLC ordering survives by construction. A world that cannot touch this tape (too few bars, no
dispersion) says why and is UNMEASURED for that sleeve, never a clean row. ONLY A FAILURE IS A
FINDING: an edge that earns more inside an invented closure has learned nothing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

MARKET_CLOSURE = "market_closure_gap"
SESSION_CLOSED = "session_closed"
INSTRUMENT_HALT = "instrument_halt"
NAMES: tuple[str, ...] = (MARKET_CLOSURE, SESSION_CLOSED, INSTRUMENT_HALT)

CLOSURE_BARS = 48
HALT_BARS = 24
SESSION_HOURS = 8
SESSION_DAYS = 20
GAP_SIGMAS = 2.0
MIN_BARS = 300

WHAT: dict[str, str] = {
    MARKET_CLOSURE: (f"the market shut for {CLOSURE_BARS} bars at one random point (bars "
                     f"removed) and reopened gapped by +/-{GAP_SIGMAS:g} sigma sqrt"
                     f"({CLOSURE_BARS})"),
    SESSION_CLOSED: (f"the tape's most active {SESSION_HOURS}-hour session removed every day "
                     f"for {SESSION_DAYS} days: its move arrives as the next session's gap"),
    INSTRUMENT_HALT: (f"the instrument halted {HALT_BARS} bars (flat stale prints, zero "
                      f"volume), then resumed gapped by +/-{GAP_SIGMAS:g} sigma sqrt"
                      f"({HALT_BARS})"),
}

_PX = ("open", "high", "low", "close")
_VOL = ("tick_volume", "real_volume", "volume")


@dataclass
class Closed:
    """The transformed bars, how many bars the world touched, and why when it touched none."""
    bars: pd.DataFrame
    applied: int
    why: str = ""


def _sigma(df: pd.DataFrame) -> float:
    c = np.asarray(df["close"], dtype="float64")
    if len(c) < 3:
        return 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(np.log(np.maximum(c, 1e-12)))
    r = r[np.isfinite(r)]
    return float(np.std(r)) if r.size > 2 else 0.0


def _shift_from(df: pd.DataFrame, start: int, shock: float) -> pd.DataFrame:
    """Every bar from `start` on repriced by exp(shock): the level moved while trading was shut."""
    out = df.copy()
    f = np.ones(len(out), dtype="float64")
    f[start:] = math.exp(shock)
    for col in _PX:
        if col in out.columns:
            out[col] = np.asarray(out[col], dtype="float64") * f
    return out


def market_closure_gap(bars: pd.DataFrame, rng: np.random.Generator) -> Closed:
    n = len(bars)
    sd = _sigma(bars)
    if n < MIN_BARS or sd <= 0:
        return Closed(bars, 0, f"{n} bars < {MIN_BARS}" if n < MIN_BARS else "no dispersion")
    i0 = int(rng.integers(200, n - CLOSURE_BARS - 20))
    shock = float(rng.choice([-1.0, 1.0])) * GAP_SIGMAS * sd * math.sqrt(CLOSURE_BARS)
    moved = _shift_from(bars, i0 + CLOSURE_BARS, shock)
    keep = np.ones(n, dtype=bool)
    keep[i0:i0 + CLOSURE_BARS] = False
    return Closed(moved.loc[keep], CLOSURE_BARS)


def _active_session(bars: pd.DataFrame) -> int:
    """The start hour of the 8-hour block (wrapping midnight) carrying the most absolute move."""
    c = np.asarray(bars["close"], dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.abs(np.diff(np.log(np.maximum(c, 1e-12)), prepend=np.log(max(c[0], 1e-12))))
    r = np.nan_to_num(r)
    hours = pd.DatetimeIndex(bars.index).hour.to_numpy()
    by_hour = np.bincount(hours, weights=r, minlength=24)
    best, score = 0, -1.0
    for h in range(24):
        s = float(sum(by_hour[(h + k) % 24] for k in range(SESSION_HOURS)))
        if s > score:
            best, score = h, s
    return best


def session_closed(bars: pd.DataFrame, rng: np.random.Generator) -> Closed:
    n = len(bars)
    if n < MIN_BARS:
        return Closed(bars, 0, f"{n} bars < {MIN_BARS}")
    idx = pd.DatetimeIndex(bars.index)
    days = idx.normalize()
    uniq = days.unique()
    if len(uniq) < SESSION_DAYS + 5:
        return Closed(bars, 0, f"{len(uniq)} trading days < {SESSION_DAYS + 5}")
    h0 = _active_session(bars)
    d0 = int(rng.integers(2, len(uniq) - SESSION_DAYS - 1))
    stretch = set(uniq[d0:d0 + SESSION_DAYS])
    hours = idx.hour.to_numpy()
    in_session = ((hours - h0) % 24) < SESSION_HOURS
    in_stretch = np.fromiter((d in stretch for d in days), dtype=bool, count=n)
    drop = in_session & in_stretch
    dropped = int(drop.sum())
    if dropped == 0:
        return Closed(bars, 0, "the active session never prints inside the stretch")
    if n - dropped < MIN_BARS // 2:
        return Closed(bars, 0, "closing the session would leave too little tape")
    return Closed(bars.loc[~drop], dropped)


def instrument_halt(bars: pd.DataFrame, rng: np.random.Generator) -> Closed:
    n = len(bars)
    sd = _sigma(bars)
    if n < MIN_BARS or sd <= 0:
        return Closed(bars, 0, f"{n} bars < {MIN_BARS}" if n < MIN_BARS else "no dispersion")
    i0 = int(rng.integers(200, n - HALT_BARS - 20))
    shock = float(rng.choice([-1.0, 1.0])) * GAP_SIGMAS * sd * math.sqrt(HALT_BARS)
    out = _shift_from(bars, i0 + HALT_BARS, shock)
    stale = float(np.asarray(bars["close"], dtype="float64")[i0 - 1])
    for col in _PX:
        if col in out.columns:
            vals = np.asarray(out[col], dtype="float64").copy()
            vals[i0:i0 + HALT_BARS] = stale
            out[col] = vals
    for col in _VOL:
        if col in out.columns:
            vals = np.asarray(out[col], dtype="float64").copy()
            vals[i0:i0 + HALT_BARS] = 0.0
            out[col] = vals
    return Closed(out, HALT_BARS)


BUILDERS = {MARKET_CLOSURE: market_closure_gap, SESSION_CLOSED: session_closed,
            INSTRUMENT_HALT: instrument_halt}
