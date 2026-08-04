"""LEVEL, SWEEP, FAILURE -- defined so that no-look-ahead is a PROPERTY, not an intention.

This is the pattern half of the failed-breakout study. It deliberately contains no scoring, no
Sharpe and no verdict: it emits events, and everything that decides whether those events are worth
anything lives behind the validation protocol in the pre-registration.

THE ONE THING THAT MATTERS HERE IS THE LEVEL DEFINITION, AND THE STANDARD FORMULATION IS A TIME
MACHINE. Almost every published version of this pattern identifies swing highs with a CENTRED
window -- `rolling(2k+1, center=True).max()` -- which at bar t uses bars up to t+k. It looks
innocuous, it is what most charting libraries do, and it leaks exactly the future extremes the
pattern is supposed to be anticipating. A swing high at t-k is not KNOWN until t, so it is usable
from t+1 onward and not one bar sooner.

Every function here is checkable by truncation: recompute on data up to t and the value at t must
be unchanged. `tests/research/test_failed_breakout.py` asserts that rather than trusting it, and
that test is the reason to believe any number this study eventually produces.

Pure numpy/pandas. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "LevelParams",
    "SweepEvent",
    "atr",
    "find_events",
    "swing_levels",
]


@dataclass(frozen=True)
class LevelParams:
    """Every field here is a hyperparameter and every one counts against the trial budget.

    Declared as a dataclass rather than loose arguments so the sweep cannot quietly grow an axis
    that the deflation never hears about -- `len(fields)` is auditable, a call site is not.
    """

    k: int = 20                  # bars either side confirming a swing extreme
    n_touch: int = 1             # touches required before the level counts
    tol_atr: float = 0.10        # how close a bar must come to count as a touch, in ATR
    theta_atr: float = 0.25      # penetration beyond the level that counts as a SWEEP, in ATR
    n_fail: int = 3              # bars allowed for price to close back inside
    atr_window: int = 14


@dataclass(frozen=True)
class SweepEvent:
    """One observed sweep. `failed` is only known n_fail bars later and is NOT a feature."""

    level_idx: int               # bar the level formed at
    level_price: float
    confirmed_idx: int           # first bar the level was KNOWABLE -- level_idx + k
    sweep_idx: int
    side: str                    # "high" (resistance swept) or "low" (support swept)
    failed: bool
    failure_idx: int | None      # bar the close came back inside; None if it never did
    entry_idx: int | None        # NEXT bar's open -- never the failure bar's close

    def as_dict(self) -> dict[str, Any]:
        return {"level_idx": self.level_idx, "level_price": self.level_price,
                "confirmed_idx": self.confirmed_idx, "sweep_idx": self.sweep_idx,
                "side": self.side, "failed": self.failed,
                "failure_idx": self.failure_idx, "entry_idx": self.entry_idx}


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 14) -> np.ndarray:
    """Wilder true range, simple-mean smoothed, causal.

    Value at t uses bars <= t. NaN until the window fills rather than a partial mean, because a
    partial ATR is systematically small and would make early bars look like sweeps.
    """
    h, low_, c = (np.asarray(x, dtype="float64") for x in (high, low, close))
    prev_c = np.concatenate(([np.nan], c[:-1]))
    tr = np.maximum(h - low_, np.maximum(np.abs(h - prev_c), np.abs(low_ - prev_c)))
    out = np.full(tr.size, np.nan)
    for i in range(window, tr.size):
        seg = tr[i - window + 1:i + 1]
        if np.isfinite(seg).all():
            out[i] = seg.mean()
    return out


def swing_levels(high: np.ndarray, low: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """(is_swing_high, is_swing_low) marked at the bar the extreme OCCURRED.

    A swing high at index i requires i to be the max of [i-k, i+k]. That is a statement about the
    past ONLY once bar i+k has closed, so the caller must not use index i before i+k -- which is
    what `confirmed_idx` in SweepEvent enforces. Marking it at i is correct and useful (it is where
    the PRICE is); using it at i is the bug.

    Returned as boolean arrays over the original index so the caller can see both the occurrence
    bar and the confirmation bar, rather than a shifted series that hides the distinction.
    """
    h = np.asarray(high, dtype="float64")
    low_ = np.asarray(low, dtype="float64")
    n = h.size
    is_hi = np.zeros(n, dtype=bool)
    is_lo = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        w_h = h[i - k:i + k + 1]
        w_l = low_[i - k:i + k + 1]
        if h[i] == w_h.max() and np.isfinite(h[i]):
            is_hi[i] = True
        if low_[i] == w_l.min() and np.isfinite(low_[i]):
            is_lo[i] = True
    return is_hi, is_lo


def find_events(bars: pd.DataFrame, p: LevelParams) -> list[SweepEvent]:
    """Every sweep of a confirmed level, with its failure state resolved n_fail bars later.

    `bars` needs columns high/low/close. Index position is used throughout, not timestamps, so a
    caller with gaps must resample first -- a "3-bar failure window" across a two-hour data gap is
    not a 3-bar window, which is the same mistake the moat screen made with horizons.

    THE ORDER OF OPERATIONS IS THE NO-LOOK-AHEAD ARGUMENT:
      1. a level at i is CONFIRMED at i+k and usable from i+k+1
      2. a sweep is a bar strictly after confirmation that penetrates by theta*ATR(sweep bar)
      3. failure is resolved by closes at sweep+1 .. sweep+n_fail
      4. entry is the bar AFTER the failure bar -- the failure close is not obtainable
    Nothing at step j reads a bar later than step j's own index.
    """
    need = {"high", "low", "close"}
    missing = need - set(bars.columns)
    if missing:
        raise ValueError(f"bars is missing {sorted(missing)}")
    h = bars["high"].to_numpy(dtype="float64")
    low_ = bars["low"].to_numpy(dtype="float64")
    c = bars["close"].to_numpy(dtype="float64")
    n = len(bars)
    a = atr(h, low_, c, p.atr_window)
    is_hi, is_lo = swing_levels(h, low_, p.k)

    events: list[SweepEvent] = []
    for side, mask, price_arr in (("high", is_hi, h), ("low", is_lo, low_)):
        for i in np.flatnonzero(mask):
            confirmed = int(i) + p.k
            if confirmed + 1 >= n:
                continue
            lvl = float(price_arr[i])

            # Touches counted only on bars strictly after confirmation and before the sweep.
            touches = 0
            for j in range(confirmed + 1, n):
                if not np.isfinite(a[j]):
                    continue
                tol = p.tol_atr * a[j]
                near = (abs(h[j] - lvl) <= tol) if side == "high" else (abs(low_[j] - lvl) <= tol)
                penetrated = (h[j] > lvl + p.theta_atr * a[j]) if side == "high" \
                    else (low_[j] < lvl - p.theta_atr * a[j])
                if penetrated:
                    if touches < p.n_touch:
                        break                      # level never earned its status; not an event
                    failure_idx = None
                    for m in range(j + 1, min(j + 1 + p.n_fail, n)):
                        inside = (c[m] < lvl) if side == "high" else (c[m] > lvl)
                        if inside:
                            failure_idx = m
                            break
                    entry = failure_idx + 1 if (failure_idx is not None
                                                and failure_idx + 1 < n) else None
                    events.append(SweepEvent(
                        level_idx=int(i), level_price=lvl, confirmed_idx=confirmed,
                        sweep_idx=int(j), side=side, failed=failure_idx is not None,
                        failure_idx=failure_idx, entry_idx=entry))
                    break
                if near:
                    touches += 1
    events.sort(key=lambda e: e.sweep_idx)
    return events
