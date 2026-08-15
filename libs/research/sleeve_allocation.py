"""What the sleeve book is worth under OPTIMAL weights, not equal ones.

THE GAP THIS MEASURES

`track_sleeve_correlation` reports the desk's diversification as

    k_eff = N / (1 + (N-1) * rho_bar)        rho_bar = mean pairwise correlation

That formula is exact under EQUICORRELATION -- every pair sharing one rho. The desk's book is
provably not that shape. Seven of eleven discretionary rules are `liquidity_provision_immediacy`,
so they are near-redundant WITH EACH OTHER, while `informed_order_flow` and
`treasury_cost_base_liquidation` are structurally unlike everything. Averaging a cluster of 0.9s
with a handful of 0.0s produces a middling rho_bar that describes NO pair in the book, and then
equal-weights every sleeve as though it did.

Under heterogeneous correlation the achievable Sharpe from N sleeves with individual Sharpes s is

    S* = sqrt(s^T C^-1 s)        at weights  w ∝ C^-1 s

which is what a book gets for down-weighting a redundant cluster and paying up for the sleeve
nobody else resembles. The equicorrelation number is a special case, and for a clustered book it
is an UNDERSTATEMENT -- the desk has been pricing its own diversification at the wrong figure and
leaving the difference unclaimed.

WHY THIS IS NOT A FREE LUNCH, WHICH IS MOST OF THIS MODULE

`C^-1` on a short sample is the classic error-maximizer. Markowitz optimisers are notorious for
loading precisely on the pairs whose correlation is most badly estimated, because an
underestimated correlation LOOKS like diversification. Estimating N(N-1)/2 correlations from n
daily observations is hopeless at the n this desk actually has, and the failure is not noisy --
it is BIASED TOWARD OPTIMISM, which is the single worst direction for a number that sets leverage.

So this module never inverts a raw sample matrix:

  * SHRINKAGE toward the equicorrelation target, weight rising as the sample shrinks. At the
    sample sizes the desk has, the shrunk estimate is mostly the honest equicorrelation answer
    and the optimiser is only allowed to act on structure the data can actually support.
  * A HARD FLOOR on observations per sleeve, below which it refuses to report an optimal Sharpe
    at all rather than reporting an inflated one.
  * The equicorrelation figure is ALWAYS reported alongside, so the gap between "what equal
    weights get" and "what optimal weights claim" is visible rather than substituted.

A number produced here can only ever be an upper bound on live improvement, and it is stated as
one. Weights fitted on a sample and applied to the same sample are in-sample by construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Observations per sleeve below which an inverted correlation matrix is not evidence. The
#: literature's rule of thumb for a stable inverse is n >> N; 10 is the lenient end of it and is
#: already generous for N=11 (110 days). Below this the optimal figure is suppressed, not shaded.
MIN_OBS_PER_SLEEVE = 10

#: Never trust the sample matrix completely, however long the sample. There is no n at which a
#: correlation estimated from a non-stationary market is exact, and the last increment of shrinkage
#: is cheap insurance against the one pair that decides the answer.
MIN_SHRINKAGE = 0.10

#: Largest condition number the inverted matrix may carry. A correlation matrix whose smallest
#: eigenvalue is a thousandth of its largest has a near-null direction, and `C^-1` loads on
#: exactly that direction because it looks like a portfolio with almost no variance. Capping the
#: condition number caps how much weight the optimiser can put on the axis the sample knows least
#: about. 50 is deliberately tight: the desk is sizing leverage off this.
MAX_CONDITION = 50.0


@dataclass(frozen=True)
class Allocation:
    """What the book is worth under each weighting, and whether to believe the difference."""

    n_sleeves: int
    n_obs: int
    equal_weight_sharpe: float
    equicorrelation_sharpe: float
    optimal_sharpe: float | None
    shrinkage: float
    weights: dict[str, float] = field(default_factory=dict)
    effective_bets: float | None = None
    usable: bool = False
    why: str = ""

    @property
    def uplift(self) -> float | None:
        """Sharpe the optimiser claims OVER equal weights. An upper bound, never a forecast."""
        if self.optimal_sharpe is None:
            return None
        return self.optimal_sharpe - self.equal_weight_sharpe


def equicorrelation_sharpe(sharpe: float, n: int, rho: float) -> float:
    """The desk's existing formula, kept here verbatim so the comparison is like-for-like."""
    if n <= 0:
        return 0.0
    rho = max(rho, -1.0 / (n - 1) + 1e-9) if n > 1 else 0.0
    k_eff = n / (1.0 + (n - 1) * rho)
    return float(sharpe) * math.sqrt(max(k_eff, 0.0))


def shrink_target(corr: np.ndarray) -> np.ndarray:
    """Equicorrelation matrix at the sample's own mean off-diagonal correlation.

    Shrinking toward THIS rather than toward the identity matters. The identity would assert the
    sleeves are independent, which is the optimistic direction and the exact claim under test;
    pulling toward equicorrelation pulls toward the desk's existing, conservative answer.
    """
    n = corr.shape[0]
    if n < 2:
        return np.eye(n)
    off = corr[~np.eye(n, dtype=bool)]
    rho = float(np.mean(off))
    t = np.full((n, n), rho)
    np.fill_diagonal(t, 1.0)
    return t


def shrinkage_weight(n_obs: int, n_sleeves: int) -> float:
    """How much to distrust the sample matrix, from how little sample there is per parameter.

    N(N-1)/2 correlations are being estimated from n observations. The ratio of parameters to data
    is the whole story, so the shrinkage is driven by it directly and saturates at 1.0 (use the
    equicorrelation answer outright) when there is less data than parameters.
    """
    if n_sleeves < 2:
        return 1.0
    params = n_sleeves * (n_sleeves - 1) / 2.0
    lam = params / (params + max(n_obs, 0))
    return float(min(1.0, max(MIN_SHRINKAGE, lam)))


def allocate(names: list[str], sharpes: np.ndarray, corr: np.ndarray, n_obs: int) -> Allocation:
    """Optimal-weight Sharpe under a shrunk correlation matrix, or an honest refusal."""
    n = len(names)
    s = np.asarray(sharpes, dtype="float64")
    mean_s = float(np.mean(s)) if n else 0.0
    off = corr[~np.eye(n, dtype=bool)] if n > 1 else np.array([0.0])
    rho_bar = float(np.mean(off)) if off.size else 0.0
    equi = equicorrelation_sharpe(mean_s, n, rho_bar)
    lam = shrinkage_weight(n_obs, n)

    base = Allocation(n_sleeves=n, n_obs=n_obs, equal_weight_sharpe=equi,
                      equicorrelation_sharpe=equi, optimal_sharpe=None, shrinkage=lam)
    if n < 2:
        return Allocation(**{**base.__dict__, "why": "one sleeve is not an allocation"})
    if n_obs < MIN_OBS_PER_SLEEVE * n:
        return Allocation(**{**base.__dict__, "why": (
            f"{n_obs} observations for {n} sleeves ({n * (n - 1) // 2} correlations). An inverted "
            f"matrix here is not a measurement -- it loads on whichever pair is most badly "
            f"estimated, because an UNDERSTATED correlation is indistinguishable from real "
            f"diversification. Needs {MIN_OBS_PER_SLEEVE * n} observations.")})

    # THE INPUT IS CHECKED BEFORE IT IS SHRUNK, because shrinkage would hide the defect. A
    # correlation matrix estimated pairwise-complete -- each cell from whatever dates that PAIR
    # shares -- need not be positive semi-definite at all, and a non-PSD matrix describes no
    # possible portfolio: it inverts to negative variances and prints a Sharpe of any size.
    #
    # THE FIRST VERSION OF THIS FUNCTION FLOORED THE EIGENVALUES AND CARRIED ON. On the test's
    # non-PSD fixture that returned an optimal Sharpe of 306 -- a riskless-arbitrage claim
    # manufactured out of an estimation artifact, which is precisely the error this module was
    # written to prevent, committed by the module itself. Repairing an invalid input silently is
    # never the answer; the input is refused.
    raw_min_eig = float(np.linalg.eigvalsh(corr).min())
    if raw_min_eig < -1e-8:
        return Allocation(**{**base.__dict__, "why": (
            f"correlation matrix is not positive semi-definite (min eigenvalue {raw_min_eig:.4f}). "
            f"No portfolio has this covariance, so an optimiser run on it does not find "
            f"diversification -- it finds the direction in which the estimate is self-"
            f"contradictory, and reports that as edge. Usually pairwise-complete estimation on "
            f"unequal date coverage; intersect the dates first.")})

    c = (1.0 - lam) * corr + lam * shrink_target(corr)
    np.fill_diagonal(c, 1.0)
    # Even a valid PSD matrix can be so ill-conditioned that its inverse is dominated by the
    # direction the sample knows least about. Bounding the condition number bounds how much
    # leverage the optimiser can place on that direction.
    vals, vecs = np.linalg.eigh(c)
    floor = float(vals.max()) / MAX_CONDITION
    if float(vals.min()) < floor:
        c = vecs @ np.diag(np.clip(vals, floor, None)) @ vecs.T
        d = np.sqrt(np.diag(c))
        c = c / np.outer(d, d)
    try:
        inv = np.linalg.inv(c)
    except np.linalg.LinAlgError:
        return Allocation(**{**base.__dict__, "why": "correlation matrix is singular"})

    quad = float(s @ inv @ s)
    if not math.isfinite(quad) or quad <= 0:
        return Allocation(**{**base.__dict__, "why": "no positive-Sharpe combination exists"})
    w = inv @ s
    tot = float(np.sum(np.abs(w)))
    w_norm = (w / tot) if tot > 0 else w
    # Effective number of bets under THESE weights: 1 / sum(w^2) on normalised weights, the
    # participation ratio. Says how much of the book's risk actually sits in distinct places.
    ssq = float(np.sum(w_norm ** 2))
    eff = (1.0 / ssq) if ssq > 0 else None

    return Allocation(
        n_sleeves=n, n_obs=n_obs, equal_weight_sharpe=equi, equicorrelation_sharpe=equi,
        optimal_sharpe=math.sqrt(quad), shrinkage=lam,
        weights={nm: round(float(x), 4) for nm, x in zip(names, w_norm, strict=True)},
        effective_bets=eff, usable=True,
        why=(f"shrunk {lam:.0%} toward equicorrelation; weights are IN-SAMPLE, so the uplift is "
             f"an upper bound on what live reweighting would earn, never a forecast of it"))


def report(a: Allocation) -> dict[str, Any]:
    d: dict[str, Any] = {
        "n_sleeves": a.n_sleeves, "n_obs": a.n_obs,
        "equicorrelation_sharpe": round(a.equal_weight_sharpe, 4),
        "shrinkage": round(a.shrinkage, 4),
        "usable": a.usable, "why": a.why,
    }
    if a.optimal_sharpe is not None:
        d.update({
            "optimal_sharpe": round(a.optimal_sharpe, 4),
            "uplift_sharpe": round(a.uplift or 0.0, 4),
            "effective_bets": round(a.effective_bets or 0.0, 2),
            "weights": a.weights,
            "caveat": ("weights fitted and scored on the same sample. Treat the uplift as the "
                       "CEILING of what reweighting can add, and confirm it forward before any "
                       "leverage step prices it in."),
        })
    return d
