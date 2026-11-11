"""Critical slowing down: the physics early-warning indicators of a coming state change.

GAP_MAP row 40 (Tier-1 gap thread, 2026-10-13). A system approaching a bifurcation recovers from
small shocks ever more slowly, and that shows in its noise before it shows in its level: the
lag-1 autocorrelation of its fluctuations rises toward 1, their variance rises, their
distribution skews toward the coming state, and near the transition it FLICKERS between two
basins (a bimodal distribution). Scheffer et al. (2009, Nature 461) and Dakos et al. (2012,
PLoS ONE 7) give the recipe used here: detrend, measure each indicator on a rolling window, and
read the TREND of each indicator with Kendall's tau, tested against shuffled-return surrogates
because overlapping windows make large taus common by chance. A significant rising tau is the
warning; a level alone
is not, because every instrument has its own normal autocorrelation and variance.

POINT IN TIME BY CONSTRUCTION. Every number at time t is computed from returns at or before t:
the windows are trailing, the detrending is a trailing mean, and the trend is measured over the
last `trend_windows` trailing windows. Nothing is fitted on the whole sample.

A STATE AXIS, NOT A SIGNAL. The output is a label per instrument (WARNING / RISING / CALM /
UNMEASURED) and the raw indicator taus. It is published for the allocator's state inputs and for
the regime cells to condition on; neither is wired here. When a cell uses it, it is a judged axis
and charged its trials like any other.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

#: Trailing window (observations) each indicator is measured on.
WINDOW = 60
#: Number of trailing window ends the Kendall trend is read over (180: at 60 the shuffled-null
#: tau is too wide for a real AR(1) approach to clear it; measured in the tests).
TREND_WINDOWS = 180
#: Below this many returns the instrument is UNMEASURED, never CALM.
MIN_OBS = WINDOW + TREND_WINDOWS
#: |tau| at or above this is a trend worth naming (Dakos et al. report 0.3-0.7 before transitions).
TAU_RISING = 0.3
#: Two or more of the four indicators rising together is a WARNING; one is RISING.
WARNING_COUNT = 2
#: Overlapping windows make every indicator series smooth, so a large tau arises by chance far
#: more often than for independent points. A trend counts only when it also beats this share of
#: shuffled-return surrogates (the iid null of Dakos et al. 2012), with a fixed seed so a pass
#: is reproducible.
SURROGATES = 100
SURROGATE_P = 0.05
SEED = 20261013
#: Sarle's bimodality coefficient above 5/9 (the uniform's value) suggests two basins.
BIMODAL_BC = 5.0 / 9.0
INDICATORS = ("ar1", "variance", "skew_abs", "bimodality")


def _ar1(x: np.ndarray) -> float:
    a, b = x[:-1], x[1:]
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _moments(x: np.ndarray) -> tuple[float, float, float]:
    """(variance, skewness, excess kurtosis) of one window; nan when the window is flat."""
    m = x.mean()
    d = x - m
    var = float((d * d).mean())
    if var <= 0:
        return var, float("nan"), float("nan")
    sd = math.sqrt(var)
    skew = float((d ** 3).mean() / sd ** 3)
    kurt = float((d ** 4).mean() / var ** 2 - 3.0)
    return var, skew, kurt


def bimodality_coefficient(skew: float, ex_kurt: float, n: int) -> float:
    """Sarle's finite-sample bimodality coefficient; nan when it cannot be formed."""
    if not (math.isfinite(skew) and math.isfinite(ex_kurt)) or n < 4:
        return float("nan")
    denom = ex_kurt + 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return float((skew * skew + 1.0) / denom) if denom > 0 else float("nan")


def kendall_tau(y: Sequence[float]) -> float:
    """Kendall's tau-a of `y` against time, ignoring non-finite points; nan below 8 points."""
    v = np.asarray([p for p in y if math.isfinite(p)], dtype=float)
    n = len(v)
    if n < 8:
        return float("nan")
    s = 0
    for i in range(n - 1):
        s += int(np.sign(v[i + 1:] - v[i]).sum())
    return float(2.0 * s / (n * (n - 1)))


def rolling_indicators(returns: Sequence[float], window: int = WINDOW
                       ) -> dict[str, np.ndarray]:
    """Each indicator on every trailing window end; index i uses returns[i-window+1 .. i]."""
    r = np.asarray([x for x in returns if math.isfinite(x)], dtype=float)
    n = len(r) - window + 1
    out = {k: np.full(max(n, 0), np.nan) for k in INDICATORS}
    for i in range(max(n, 0)):
        x = r[i:i + window]
        x = x - x.mean()                    # trailing detrend: the window's own mean
        var, skew, kurt = _moments(x)
        out["ar1"][i] = _ar1(x)
        out["variance"][i] = var
        out["skew_abs"][i] = abs(skew) if math.isfinite(skew) else float("nan")
        out["bimodality"][i] = bimodality_coefficient(skew, kurt, len(x))
    return out


def surrogate_p(returns: Sequence[float], taus: dict[str, float], window: int = WINDOW,
                trend_windows: int = TREND_WINDOWS, n: int = SURROGATES,
                seed: int = SEED) -> dict[str, float]:
    """Per indicator, the share of shuffled-return surrogates whose tau is >= the observed one."""
    rng = np.random.default_rng(seed)
    base = np.asarray(returns, dtype=float)
    hits = dict.fromkeys(INDICATORS, 0)
    for _ in range(n):
        ind = rolling_indicators(rng.permutation(base), window)
        for k, v in ind.items():
            t = kendall_tau(v[-trend_windows:])
            obs = taus.get(k, float("nan"))
            if math.isfinite(t) and math.isfinite(obs) and t >= obs:
                hits[k] += 1
    return {k: (hits[k] + 1) / (n + 1) for k in INDICATORS}


def early_warning(returns: Sequence[float], window: int = WINDOW,
                  trend_windows: int = TREND_WINDOWS,
                  surrogates: int = SURROGATES) -> dict[str, Any]:
    """The state label and its evidence for one return series, as of its last observation."""
    clean = [float(x) for x in returns if isinstance(x, (int, float)) and math.isfinite(x)]
    if len(clean) < window + trend_windows:
        return {"state": "UNMEASURED",
                "why": f"{len(clean)} return(s); need {window + trend_windows}",
                "n_obs": len(clean)}
    tail = clean[-(window + trend_windows - 1):]
    ind = rolling_indicators(tail, window)
    taus = {k: kendall_tau(v[-trend_windows:]) for k, v in ind.items()}
    pvals = surrogate_p(tail, taus, window, trend_windows, surrogates)
    last = {k: (float(v[-1]) if len(v) and math.isfinite(v[-1]) else None)
            for k, v in ind.items()}
    rising = sorted(k for k, t in taus.items()
                    if math.isfinite(t) and t >= TAU_RISING and pvals[k] <= SURROGATE_P)
    if not any(math.isfinite(t) for t in taus.values()):
        state = "UNMEASURED"
    elif len(rising) >= WARNING_COUNT:
        state = "WARNING"
    elif rising:
        state = "RISING"
    else:
        state = "CALM"
    pos = [max(t, 0.0) for t in taus.values() if math.isfinite(t)]
    score = sum(pos) / len(pos) if pos else float("nan")
    return {
        "state": state,
        "score": round(score, 4) if math.isfinite(score) else None,
        "rising": rising,
        "tau": {k: (round(t, 4) if math.isfinite(t) else None) for k, t in taus.items()},
        "p_surrogate": {k: round(v, 4) for k, v in pvals.items()},
        "last": {k: (round(v, 6) if v is not None else None) for k, v in last.items()},
        "flicker": bool(last["bimodality"] is not None and last["bimodality"] > BIMODAL_BC),
        "n_obs": len(clean),
    }
