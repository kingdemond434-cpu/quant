"""Per-candidate multiplicity control: CSCV rank-consistency and Romano-Wolf stepdown.

WHY THIS EXISTS.  ``probability_backtest_overfitting`` and ``whites_reality_check`` both take
*only* the (T x N) campaign matrix -- the individual candidate's returns are never an input.  They
are therefore **campaign constants**: used as per-candidate gates they veto every candidate in a
batch identically, with probability 1, no matter how good any single one is.  That is not a strict
bar, it is a bar with zero information (2026-07-29 audit: dsr/pbo/reality_check each rejected
>=98% of 420 candidates, 0 survivors ever).

This module supplies the candidate-aware counterparts at the SAME thresholds:

* :func:`cscv_candidate_pbo` -- each candidate's own out-of-sample rank consistency across every
  combinatorially-symmetric split, instead of the campaign's in-sample-best.
* :func:`romano_wolf_stepdown` -- per-strategy significance with **family-wise error controlled at
  alpha across all N**, instead of one p-value describing only the maximum.

Neither is a loosening.  Romano-Wolf is a strictly more rigorous multiple-testing procedure than a
single campaign p-value: it still pays for every trial, it just attributes the result to the
candidate that earned it.  The campaign statistics remain valuable and are still reported, as
diagnostics of the *search procedure* -- which is what they actually measure.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import rankdata

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError

__all__ = [
    "CSCVResult",
    "StepdownResult",
    "cscv_candidate_pbo",
    "romano_wolf_stepdown",
]


class CSCVResult(BaseModel):
    """Per-candidate CSCV outcome plus the classic campaign statistic for reference."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    candidate_pbo: list[float]
    """For each candidate k: the fraction of CSCV splits where k's OOS rank fell below the
    median.  Low = k holds its relative standing out of sample; high = k's in-sample standing
    was an artefact of the split."""

    campaign_pbo: float
    """Classic Lopez de Prado PBO: how often the IN-SAMPLE-BEST lands below the OOS median.  A
    property of the SELECTION PROCEDURE, reported as a diagnostic, never a per-candidate gate."""

    n_combinations: int
    n_strategies: int


class StepdownResult(BaseModel):
    """Romano-Wolf stepdown outcome: per-candidate rejections at FWER <= alpha."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    rejected: list[bool]
    adjusted_p: list[float]
    raw_p: list[float] = []
    """UNADJUSTED per-candidate bootstrap p-value: the fraction of that candidate's OWN bootstrap
    null draws at least as extreme as its observed statistic. Added 2026-07-30 because the FDR
    screen (libs/validation/screen_select.py) needs raw p-values -- feeding it `adjusted_p` is a
    DOUBLE correction (FWER-adjusted, then FDR-adjusted again), which is statistically incoherent
    and measurably evicted a known Sharpe-3 winner from a 60-null batch in calibration. Same one
    bootstrap pass, no extra compute."""
    t_stat: list[float]
    alpha: float
    n_strategies: int
    n_boot: int


def _block_sufficient_stats(
    matrix: np.ndarray, n_splits: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-block count / sum / sum-of-squares, so any block union's Sharpe is O(1) to combine.

    The naive CSCV recomputes a Sharpe for every (split, strategy) pair -- C(16,8)=12870 splits
    x N strategies x 2 sides.  Sharpe depends on the sample only through (n, sum, sum-sq), all of
    which are additive over blocks, so we accumulate them once per block and then combine with a
    matrix product.  Exact, not an approximation.
    """
    blocks = np.array_split(np.arange(matrix.shape[0]), n_splits)
    counts = np.array([len(b) for b in blocks], dtype="float64")
    sums = np.stack([matrix[b].sum(axis=0) for b in blocks])
    sqs = np.stack([(matrix[b] ** 2).sum(axis=0) for b in blocks])
    return counts, sums, sqs


def _sharpe_from_stats(n: np.ndarray, s: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Vectorised per-period Sharpe (mean/std, ddof=1) from sufficient statistics."""
    n_col = n[:, None]
    mean = s / n_col
    var = (q - (s**2) / n_col) / (n_col - 1.0)
    std = np.sqrt(np.maximum(var, 0.0))
    out: np.ndarray = np.divide(mean, std, out=np.zeros_like(mean), where=std > 0)
    return out


def cscv_candidate_pbo(returns_matrix: np.ndarray, *, n_splits: int = 16) -> CSCVResult:
    """Combinatorially-symmetric cross-validation, scored PER CANDIDATE.

    For every way of choosing half the blocks as in-sample, each candidate is ranked by its
    out-of-sample Sharpe against its peers.  ``candidate_pbo[k]`` is the fraction of splits in
    which candidate k landed below the OOS median -- i.e. how often its standing failed to
    survive the split.  The classic campaign PBO (rank of the *in-sample-best*) is computed from
    the same pass and returned alongside as a diagnostic.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    n_obs, n_strategies = matrix.shape
    if n_obs < n_splits:
        raise ValidationError("not enough observations for the requested n_splits")

    counts, sums, sqs = _block_sufficient_stats(matrix, n_splits)
    combos = list(combinations(range(n_splits), n_splits // 2))
    is_mask = np.zeros((len(combos), n_splits), dtype="float64")
    for i, ids in enumerate(combos):
        is_mask[i, list(ids)] = 1.0
    oos_mask = 1.0 - is_mask

    below_median = np.zeros(n_strategies, dtype="float64")
    campaign_below = 0
    # Chunk the split loop so peak memory stays O(chunk x N) even for wide campaigns.
    chunk = max(1, int(4.0e6 // max(n_strategies, 1)))
    for start in range(0, len(combos), chunk):
        im = is_mask[start : start + chunk]
        om = oos_mask[start : start + chunk]
        is_sr = _sharpe_from_stats(im @ counts, im @ sums, im @ sqs)
        oos_sr = _sharpe_from_stats(om @ counts, om @ sums, om @ sqs)
        # rankdata along each split's row: 1 = worst, N = best.
        oos_rank = np.apply_along_axis(rankdata, 1, oos_sr)
        w = oos_rank / (n_strategies + 1.0)
        below_median += (w < 0.5).sum(axis=0)
        best = np.argmax(is_sr, axis=1)
        campaign_below += int((w[np.arange(len(im)), best] < 0.5).sum())

    n_comb = float(len(combos))
    return CSCVResult(
        candidate_pbo=(below_median / n_comb).tolist(),
        campaign_pbo=campaign_below / n_comb,
        n_combinations=len(combos),
        n_strategies=n_strategies,
    )


def romano_wolf_stepdown(
    performance: np.ndarray,
    *,
    alpha: float = 0.05,
    n_boot: int = 1000,
    mean_block: float = 10,
    seed: int = 0,
) -> StepdownResult:
    """Romano-Wolf (2005) stepwise multiple test: which strategies beat the benchmark.

    ``performance[t, k]`` is strategy k's edge over the benchmark at t (benchmark = 0 here).
    Controls the family-wise error rate at ``alpha`` across all N strategies while returning a
    verdict for EACH one -- the per-candidate counterpart to White's Reality Check, which only
    ever tests the maximum.  Studentised, and bootstrapped with the stationary block bootstrap so
    autocorrelation is preserved.
    """
    f = np.asarray(performance, dtype="float64")
    if f.ndim != 2 or f.shape[1] < 1:
        raise ValidationError("performance must be a 2-D (T x N) array")
    if not 0.0 < alpha < 1.0:
        raise ValidationError("alpha must be in (0, 1)")
    t_obs, n = f.shape

    d_bar = f.mean(axis=0)
    omega = f.std(axis=0, ddof=1)
    omega = np.where(omega <= 0, np.inf, omega)  # zero-variance strategies cannot be significant
    t_stat = np.sqrt(t_obs) * d_bar / omega

    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, n), dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        boot[b] = np.sqrt(t_obs) * (f[idx].mean(axis=0) - d_bar) / omega

    # RAW per-candidate p: each candidate against its OWN bootstrap null (no max-statistic,
    # no stepdown) -- the unadjusted input any downstream multiplicity procedure must start from.
    raw_p = np.array([float(np.mean(boot[:, k] >= t_stat[k])) for k in range(n)], dtype="float64")

    rejected = np.zeros(n, dtype=bool)
    adjusted_p = np.ones(n, dtype="float64")
    active = np.ones(n, dtype=bool)
    while active.any():
        max_null = boot[:, active].max(axis=1)
        crit = float(np.quantile(max_null, 1.0 - alpha))
        newly = active & (t_stat > crit)
        # Every still-active candidate's p-value is measured against the CURRENT null; the ones
        # rejected at this step have theirs frozen, the rest keep updating as the set shrinks.
        adjusted_p[active] = np.array(
            [float(np.mean(max_null >= t_stat[k])) for k in np.flatnonzero(active)]
        )
        if not newly.any():
            break
        rejected |= newly
        active &= ~newly

    # Stepdown p-values must be monotone in the test statistic (Romano-Wolf 2016 sec. 4).
    order = np.argsort(-t_stat)
    adjusted_p[order] = np.maximum.accumulate(adjusted_p[order])

    return StepdownResult(
        rejected=rejected.tolist(),
        adjusted_p=adjusted_p.tolist(),
        raw_p=raw_p.tolist(),
        t_stat=t_stat.tolist(),
        alpha=alpha,
        n_strategies=n,
        n_boot=n_boot,
    )
