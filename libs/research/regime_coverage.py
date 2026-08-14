"""HOW MANY REGIMES DID THIS CLOCK ACTUALLY RUN THROUGH, AND HOW STICKY ARE ITS OBSERVATIONS.

THE FREE HALVING THIS EXISTS TO COLLECT. `evidence_clock.regime_penalty` charges 0.5 for
UNMEASURED and 0.5 for MEASURED-AS-ONE, deliberately -- untested is treated as concentrated. But
no forward artifact on this desk publishes `distinct_regimes`, so EVERY clock pays the
single-regime penalty regardless of what it actually lived through. Measured on the live box
2026-08-14: nine axis clocks, every one at 0.50 effective observations per day, every one binding
on "regime concentration (x0.5)", and not one of them had ever been asked how many regimes it
covered.

A clock that genuinely spanned three regimes is paying double for a fact nobody recorded. Making
it publish the count halves its remaining wait the same day -- and LOWERS NO BAR, because the
deflator was always meant to be measured. That is the entire economic case for this file: it is
not a shortcut past the evidence requirement, it is the requirement finally being computed on
real inputs instead of on a placeholder.

The same argument holds for `autocorrelation`, in the opposite direction and worth saying because
it is the honest half: a clock whose observations are POSITIVELY autocorrelated is currently being
CREDITED too much, since the unmeasured default of 0.0 leaves the serial deflator at 1.0. Turning
these on can make a clock slower, and a measurement that can only ever help is not a measurement.

**THE REGIME DEFINITION IS BORROWED, NOT INVENTED.** trend = sign of the 50-day change, vol =
30-day realised vol against its own 180-day median. Those are exactly `crypto_regime.regime_labels`'
first two axes, reproduced here on a single close series because the axis clocks are single-symbol
and cannot assemble the cross-sectional frame that function needs. Writing a second, subtly
different regime definition would give the desk two answers to one question, which is the defect
`slot_registry` was written to end for the cohort count.

**THIS IS A COVERAGE COUNT, NOT A ROBUSTNESS PARTITION, and the distinction is L1.63.** That law
was written because three gates certified "regime robust" on vol terciles that were structurally
INCAPABLE of producing a failing group -- welded open by their choice of axis. Nothing here
certifies anything: it counts which cells the observation window touched. A count cannot be welded
open, because it makes no accept/reject decision, and no promotion path reads it as a verdict.

Stdlib + numpy. import from libs.research.regime_coverage.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = [
    "TREND_LOOKBACK",
    "VOL_MEDIAN_WINDOW",
    "VOL_WINDOW",
    "lag1_autocorr",
    "regime_coverage",
]

#: Borrowed verbatim from `crypto_regime.regime_labels` so the desk has ONE regime definition.
TREND_LOOKBACK = 50
VOL_WINDOW = 30
VOL_MEDIAN_WINDOW = 180


def lag1_autocorr(x: np.ndarray | list[float]) -> float | None:
    """Lag-1 autocorrelation of the observation series, or None when it cannot be estimated.

    NONE IS A REAL ANSWER AND IS NOT ZERO. Zero is the value at which `_serial_deflator` credits
    the full raw count, so returning it for a series too short to estimate would hand every new
    clock the most generous possible deflator on no evidence -- the same defaulted-zero-reads-as-
    measurement defect that published a flat 213x cross-section gain.

    NEGATIVE VALUES ARE RETURNED HONESTLY and the deflator clamps them at zero itself. Clamping
    here as well would hide the fact that a mean-reverting clock carries MORE information per
    observation than the deflator is willing to credit.
    """
    a = np.asarray(x, dtype="float64")
    a = a[np.isfinite(a)]
    if a.size < 8:
        return None
    s = float(a.std())
    if not np.isfinite(s) or s <= 0.0:
        return None
    c = float(np.corrcoef(a[:-1], a[1:])[0, 1])
    return None if not np.isfinite(c) else round(c, 4)


def regime_coverage(
    closes: list[float],
    observed_idx: list[int] | None = None,
) -> tuple[int, dict[str, Any]]:
    """(distinct regimes covered, detail). `closes` is the ASCENDING daily close series.

    `observed_idx` names the positions the clock actually accrued an observation at; None means
    every bar. THAT DISTINCTION IS THE WHOLE POINT -- a clock born last week has not covered the
    regimes its price history contains, and counting them from the series rather than from the
    clock's own observations would credit it with evidence it never collected.

    RETURNS 0, NOT 1, WHEN THE SERIES IS TOO SHORT TO LABEL. `regime_penalty` treats 0 (unmeasured)
    and 1 (measured single) identically today, so the choice costs nothing now -- but they are
    different claims, and folding "we could not tell" into "we measured one" is the substitution
    that put every clock at 0.5 in the first place.
    """
    c = np.asarray(closes, dtype="float64")
    need = max(TREND_LOOKBACK, VOL_WINDOW) + 2
    if c.size < need:
        return 0, {"status": "UNMEASURED",
                   "why": (f"{c.size} closes, need {need} to label a trend and a volatility "
                           "state -- too short to tell, which is not the same as one regime")}

    ret = np.zeros_like(c)
    ret[1:] = c[1:] / c[:-1] - 1.0

    # LAGGED, mirroring crypto_regime: a regime label that used the current bar would describe a
    # state the clock could not have known it was in.
    trend = np.full(c.size, "", dtype=object)
    for i in range(TREND_LOOKBACK + 1, c.size):
        trend[i] = "bull" if c[i - 1] > c[i - 1 - TREND_LOOKBACK] else "bear"

    rv = np.full(c.size, np.nan)
    for i in range(VOL_WINDOW + 1, c.size):
        rv[i] = float(np.std(ret[i - VOL_WINDOW:i]))

    vol = np.full(c.size, "", dtype=object)
    for i in range(c.size):
        if not np.isfinite(rv[i]):
            continue
        lo = max(0, i - VOL_MEDIAN_WINDOW)
        hist = rv[lo:i + 1]
        hist = hist[np.isfinite(hist)]
        if hist.size < 2:
            continue
        vol[i] = "high_vol" if rv[i] > float(np.median(hist)) else "low_vol"

    idx = list(range(c.size)) if observed_idx is None else [
        i for i in observed_idx if 0 <= i < c.size]
    cells: dict[str, int] = {}
    for i in idx:
        if not trend[i] or not vol[i]:
            continue
        cells[f"{trend[i]}/{vol[i]}"] = cells.get(f"{trend[i]}/{vol[i]}", 0) + 1
    if not cells:
        return 0, {"status": "UNMEASURED",
                   "why": ("no observed bar could be labelled -- the clock's observations all "
                           "fall before the trend and volatility windows fill")}
    return len(cells), {
        "status": "MEASURED",
        "cells": dict(sorted(cells.items())),
        "definition": (f"trend = sign of the {TREND_LOOKBACK}-day change, vol = {VOL_WINDOW}-day "
                       f"realised vol against its own {VOL_MEDIAN_WINDOW}-day median -- the first "
                       "two axes of crypto_regime.regime_labels, on one close series"),
        "why": ("A COVERAGE COUNT, NOT A ROBUSTNESS CERTIFICATE (L1.63). It makes no accept or "
                "reject decision and no promotion path reads it as a verdict; it records which "
                "regime cells this clock's OWN observations fell in, so evidence_clock stops "
                "charging a single-regime penalty for a fact nobody had measured."),
    }
