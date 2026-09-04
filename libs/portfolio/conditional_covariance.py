"""How much the book's dependence actually changes by regime, and what that implies for crisis.

WHAT WAS ALREADY RIGHT, so it is not rebuilt here. `sample_worlds` resamples whole ROWS of the
sleeve matrix inside a regime's own days, so contemporaneous dependence is already conditional on
regime -- and it is conditional non-parametrically, keeping the real tails, which is strictly
better than fitting a Sigma(Z) and then repairing its positive-definiteness. The crisis overlay
already loads a common factor onto every sleeve so correlations converge. None of that needed
replacing.

WHAT WAS MISSING. Two numbers governing how bad a crisis is were CONSTANTS:

    crisis_vol_mult     = 2.5
    crisis_common_share = 0.55

Nobody had measured either against this book. A one-factor overlay in which each sleeve is
sqrt(s)*common + sqrt(1-s)*idio has pairwise correlation exactly s, so `crisis_common_share` IS
the pairwise correlation the crisis worlds assume -- a quantity the desk's own return matrix can
simply be asked about. Guessing a number the data will answer is the kind of thing that survives
in a risk model precisely because it is never wrong out loud.

THE MEASUREMENT MAY ONLY MAKE THE CRISIS WORSE, NEVER MILDER. `calibrate` takes the maximum of
the standing constant and the shrunk measurement. A measured correlation of 0.30 in the stress
regime does not license modelling crises as gentler than the desk has been assuming -- that would
be relaxing a risk assumption on the strength of a quiet sample, which is exactly how a book
discovers its true correlations at the worst possible moment. It can only ratchet upward.

SHRUNK BY SAMPLE, LIKE EVERY OTHER ESTIMATE HERE. The stress regime is whichever regime carries
the highest mean sleeve volatility -- data-driven, no label parsing, so it moves when the
classifier's vocabulary does. Its correlation estimate is shrunk toward the standing constant by
n/(n+k) on the number of days in the pool, so a twelve-day stress pool moves nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

#: Days in a regime pool before its correlation estimate is trusted over the standing constant.
CORR_K = 60.0
#: A pool below this is not measured at all: a handful of days cannot describe dependence across
#: a book, and pretending otherwise is how a risk model acquires false confidence.
MIN_POOL_DAYS = 20


@dataclass(frozen=True)
class RegimeCov:
    """The dependence and scale one regime actually produced."""

    regime: str
    n_days: int
    #: Mean off-diagonal Pearson correlation across sleeve pairs.
    mean_corr: float
    #: Mean per-sleeve standard deviation, in the matrix's own units (R).
    mean_vol: float
    #: Correlation of the equally-weighted book with itself is meaningless; this is the ratio of
    #: book variance to the sum of sleeve variances -- 1/N under independence, 1.0 under perfect
    #: dependence. The number that says what diversification actually survives in this regime.
    diversification_ratio: float


@dataclass(frozen=True)
class Calibration:
    """What the crisis overlay should assume, and where each number came from."""

    crisis_common_share: float
    crisis_vol_mult: float
    stress_regime: str
    by_regime: dict[str, RegimeCov] = field(default_factory=dict)
    unconditional: RegimeCov | None = None
    note: str = ""

    def as_overrides(self) -> dict[str, float]:
        return {"crisis_common_share": self.crisis_common_share,
                "crisis_vol_mult": self.crisis_vol_mult}


def _mean_offdiag_corr(hist: np.ndarray) -> float:
    """Mean pairwise correlation, ignoring sleeves that never move."""
    if hist.ndim != 2 or hist.shape[1] < 2 or hist.shape[0] < 3:
        return float("nan")
    sd = hist.std(axis=0)
    live = sd > 0
    if int(live.sum()) < 2:
        return float("nan")
    c = np.corrcoef(hist[:, live], rowvar=False)
    if not np.isfinite(c).all():
        c = np.nan_to_num(c, nan=0.0)
    k = c.shape[0]
    off = c[~np.eye(k, dtype=bool)]
    return float(off.mean()) if off.size else float("nan")


def _cov_of(hist: np.ndarray, regime: str) -> RegimeCov:
    sd = hist.std(axis=0)
    live = sd > 0
    book_var = float(hist[:, live].sum(axis=1).var()) if int(live.sum()) else 0.0
    sum_var = float((sd[live] ** 2).sum()) if int(live.sum()) else 0.0
    return RegimeCov(
        regime=regime, n_days=int(hist.shape[0]),
        mean_corr=_mean_offdiag_corr(hist),
        mean_vol=float(sd[live].mean()) if int(live.sum()) else float("nan"),
        diversification_ratio=float(book_var / sum_var) if sum_var > 0 else float("nan"),
    )


def by_regime(hist: np.ndarray, labels: Sequence[str]) -> dict[str, RegimeCov]:
    """Per-regime dependence, over the rows each regime actually produced."""
    out: dict[str, RegimeCov] = {}
    lab = np.asarray(labels, dtype=object)
    if lab.size != hist.shape[0]:
        return out
    for name in sorted({str(x) for x in lab if str(x)}):
        rows = np.flatnonzero(lab == name)
        if rows.size < MIN_POOL_DAYS:
            continue
        out[name] = _cov_of(hist[rows], name)
    return out


def calibrate(hist: np.ndarray, labels: Sequence[str] | None,
              *, standing_share: float, standing_vol_mult: float,
              corr_k: float = CORR_K) -> Calibration:
    """What the crisis overlay should assume for THIS book, ratcheting only upward.

    `hist` is the (days, sleeves) return matrix the worlds are drawn from -- the same object
    `sample_worlds` bootstraps, so the calibration describes the population being sampled rather
    than some other estimate of it.
    """
    hist = np.asarray(hist, dtype=float)
    if hist.ndim != 2 or hist.shape[1] < 2 or hist.shape[0] < MIN_POOL_DAYS:
        return Calibration(crisis_common_share=standing_share,
                           crisis_vol_mult=standing_vol_mult, stress_regime="",
                           note="matrix too small to measure dependence; standing constants kept")

    uncond = _cov_of(hist, "")
    per = by_regime(hist, labels) if labels is not None else {}
    if not per:
        return Calibration(crisis_common_share=standing_share,
                           crisis_vol_mult=standing_vol_mult, stress_regime="",
                           unconditional=uncond,
                           note=("no regime pool reached "
                                 f"{MIN_POOL_DAYS} days; standing constants kept"))

    # THE STRESS REGIME IS THE MOST VOLATILE ONE, not the one whose label contains a scary word.
    # Labels come from a classifier whose vocabulary changes; volatility is the thing the crisis
    # overlay is actually about.
    stress = max(per.values(), key=lambda c: (c.mean_vol if np.isfinite(c.mean_vol) else -1.0))
    lam = stress.n_days / (stress.n_days + corr_k)

    share = standing_share
    if np.isfinite(stress.mean_corr):
        measured = float(np.clip(stress.mean_corr, 0.0, 0.95))
        share = float(lam * measured + (1.0 - lam) * standing_share)

    # THE REFERENCE IS THE CALM REGIME, NOT THE UNCONDITIONAL POOL. "How much worse than normal
    # does a crisis get" is a comparison against normal, and the unconditional pool CONTAINS the
    # stress days -- using it as the denominator lets a turbulent history quietly argue that
    # crises are only slightly worse than average, which is the wrong direction for a risk
    # assumption to be wrong in.
    calm = min(per.values(), key=lambda c: (c.mean_vol if np.isfinite(c.mean_vol) else 1e9))
    vol_mult = standing_vol_mult
    if np.isfinite(stress.mean_vol) and np.isfinite(calm.mean_vol) and calm.mean_vol > 0:
        measured_mult = float(stress.mean_vol / calm.mean_vol)
        vol_mult = float(lam * measured_mult + (1.0 - lam) * standing_vol_mult)

    # RATCHET. A quiet sample may not license a gentler crisis than the desk has been assuming.
    share = max(standing_share, share)
    vol_mult = max(standing_vol_mult, vol_mult)

    gap = ""
    if calm.regime != stress.regime and np.isfinite(calm.mean_corr):
        gap = (f"; pairwise correlation {calm.mean_corr:.2f} in {calm.regime} vs "
               f"{stress.mean_corr:.2f} in {stress.regime}")
    return Calibration(
        crisis_common_share=round(share, 4), crisis_vol_mult=round(vol_mult, 4),
        stress_regime=stress.regime, by_regime=per, unconditional=uncond,
        note=(f"stress regime {stress.regime} ({stress.n_days}d, shrink weight {lam:.2f})"
              f"{gap}"),
    )
