"""Proper scoring rules for the desk's forecasts: is the distribution it predicts the one it gets?

A point forecast that is right on average can still be a bad forecast -- too confident, too wide,
skewed the wrong way -- and squared error cannot see any of that. These are the standard proper
scoring rules for a Gaussian predictive distribution, plus the calibration check that does not
depend on any parametric form:

    log score   -log p(y | mu, sigma)      penalises confidence more than error
    CRPS        closed form for N(mu, s)   in the units of y; comparable across sharpness
    Brier       (p - 1[y > 0])^2           the directional claim alone
    PIT         F(y | forecast)            uniform on [0, 1] iff calibrated; its KS distance
                                          from uniform is the calibration number

PROPER, which is the whole point: each is minimised in expectation by the TRUE distribution and
nothing else, so a forecaster cannot improve its score by hedging or by exaggerating.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeAlias, cast

import numpy as np
import numpy.typing as npt

#: Anything the scoring rules accept: a plain sequence or an already-built float array.
_ArrayIn: TypeAlias = Sequence[float] | npt.NDArray[np.float64]

_SQRT2 = math.sqrt(2.0)
_SQRT_PI = math.sqrt(math.pi)
_erf = np.vectorize(math.erf)


def _phi(z: np.ndarray) -> np.ndarray:
    return cast("np.ndarray", np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi))


def _Phi(z: np.ndarray) -> np.ndarray:
    return cast("np.ndarray", 0.5 * (1.0 + _erf(np.asarray(z, dtype=float) / _SQRT2)))


def log_score(y: _ArrayIn, mu: _ArrayIn, sigma: _ArrayIn) -> np.ndarray:
    """-log N(y | mu, sigma), per observation. Lower is better."""
    y, mu, s = (np.asarray(v, dtype=float) for v in (y, mu, sigma))
    s = np.maximum(s, 1e-12)
    z = (y - mu) / s
    return cast("np.ndarray", 0.5 * z * z + np.log(s) + 0.5 * math.log(2.0 * math.pi))


def crps_gaussian(y: _ArrayIn, mu: _ArrayIn, sigma: _ArrayIn) -> np.ndarray:
    """CRPS for N(mu, sigma), per observation. Lower is better.

    CRPS = s * ( z (2 Phi(z) - 1) + 2 phi(z) - 1/sqrt(pi) ),  z = (y - mu) / s.
    """
    y, mu, s = (np.asarray(v, dtype=float) for v in (y, mu, sigma))
    s = np.maximum(s, 1e-12)
    z = (y - mu) / s
    return cast("np.ndarray", s * (z * (2.0 * _Phi(z) - 1.0) + 2.0 * _phi(z) - 1.0 / _SQRT_PI))


def brier(p_up: _ArrayIn, y: _ArrayIn) -> np.ndarray:
    p, yy = np.asarray(p_up, dtype=float), np.asarray(y, dtype=float)
    return cast("np.ndarray", (np.clip(p, 0.0, 1.0) - (yy > 0).astype(float)) ** 2)


def pit(y: _ArrayIn, mu: _ArrayIn, sigma: _ArrayIn) -> np.ndarray:
    y, mu, s = (np.asarray(v, dtype=float) for v in (y, mu, sigma))
    return _Phi((y - mu) / np.maximum(s, 1e-12))


def pit_ks(u: _ArrayIn) -> float:
    """KS distance of PIT values from uniform. 0 is perfectly calibrated."""
    u = np.sort(np.clip(np.asarray(u, dtype=float), 0.0, 1.0))
    n = u.size
    if n == 0:
        return float("nan")
    i = np.arange(1, n + 1)
    return float(max(np.max(i / n - u), np.max(u - (i - 1) / n)))


@dataclass(frozen=True)
class Scorecard:
    n: int
    log_score: float
    crps: float
    brier: float
    pit_ks: float
    #: Realised residual sd over forecast sd: >1 overconfident, <1 too wide.
    sharpness_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "log_score": round(self.log_score, 6), "crps": round(self.crps, 8),
                "brier": round(self.brier, 6), "pit_ks": round(self.pit_ks, 4),
                "sharpness_ratio": round(self.sharpness_ratio, 4)}


def scorecard(y: _ArrayIn, mu: _ArrayIn, sigma: _ArrayIn) -> Scorecard:
    ya, ma, sa = (np.asarray(v, dtype=float) for v in (y, mu, sigma))
    ok = np.isfinite(ya) & np.isfinite(ma) & np.isfinite(sa) & (sa > 0)
    ya, ma, sa = ya[ok], ma[ok], sa[ok]
    if ya.size == 0:
        return Scorecard(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))
    p_up = 1.0 - _Phi((0.0 - ma) / sa)
    u = pit(ya, ma, sa)
    resid_sd = float(np.std(ya - ma, ddof=1)) if ya.size > 1 else float("nan")
    return Scorecard(
        n=int(ya.size),
        log_score=float(np.mean(log_score(ya, ma, sa))),
        crps=float(np.mean(crps_gaussian(ya, ma, sa))),
        brier=float(np.mean(brier(p_up, ya))),
        pit_ks=pit_ks(u),
        sharpness_ratio=(float(resid_sd / np.mean(sa)) if np.mean(sa) > 0
                         and np.isfinite(resid_sd) else float("nan")),
    )


def paired_improvement(y: _ArrayIn, mu_a: _ArrayIn, s_a: _ArrayIn,
                       mu_b: _ArrayIn, s_b: _ArrayIn) -> dict[str, float]:
    """How much better forecast B is than A, per observation, with a paired t on the CRPS gap.

    Positive `crps_gain` means B is closer to the truth. The t is on the per-observation
    difference, so it respects the pairing -- both forecasts saw the same outcomes.
    """
    a = crps_gaussian(y, mu_a, s_a)
    b = crps_gaussian(y, mu_b, s_b)
    d = a - b
    d = d[np.isfinite(d)]
    if d.size < 2:
        return {"crps_gain": float("nan"), "t": float("nan"), "n": int(d.size),
                "log_score_gain": float("nan")}
    sd = float(d.std(ddof=1))
    return {"crps_gain": float(d.mean()),
            "t": float(d.mean() / (sd / math.sqrt(d.size))) if sd > 0 else 0.0,
            "n": int(d.size),
            "log_score_gain": float(np.mean(log_score(y, mu_a, s_a) - log_score(y, mu_b, s_b)))}
