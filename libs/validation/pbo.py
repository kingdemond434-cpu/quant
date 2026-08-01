"""Probability of Backtest Overfitting via Combinatorially-Symmetric Cross-Validation (CSCV).

Splits the sample into S blocks; for every way of choosing half as in-sample, picks the
in-sample-best configuration and measures its out-of-sample rank. PBO is the fraction of
splits where the chosen configuration lands below the OOS median — i.e. its in-sample edge was
overfit (López de Prado).

WHY THIS FILE IS WRITTEN THE WAY IT IS (2026-08-01). PBO was 87 of the 89 seconds of a single
`validate()` call, which put a 240-candidate real-data campaign at 3.6 hours and made the
per-gate death counts -- the one number that answers "why are there no survivors" -- too
expensive to ever actually measure. The desk was therefore reasoning about its own gates instead
of counting, which is the exact failure mode the campaign script was written to end.

The cost was structural, not incidental. With 16 blocks there are C(16,8) = 12,870 combinations,
and the reference implementation re-read the full return matrix and recomputed a Sharpe from
scratch for every strategy in both the in-sample and out-of-sample halves of every one of them:
12,870 x 90 x 2 = 2.3 million Python-level calls, each doing its own `.mean()` and `.std()` over
a fresh fancy-indexed copy. The same T observations were summed 12,870 times over.

They only need to be summed ONCE. Sharpe over any union of blocks is a function of three block
sufficient statistics -- count, sum, sum-of-squares -- so this precomputes those per block and
then assembles each combination by adding S/2 rows. The out-of-sample half is the complement, so
it is the grand total minus the in-sample total and costs nothing extra.

`_pbo_reference` is kept, and is not dead code: it is the naive definition, and
`test_pbo_vectorised_matches_the_naive_reference` asserts the fast path reproduces it exactly on
random and adversarial matrices. A speedup to a validation gate that silently moved the gate
would be far worse than a slow gate.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import rankdata

from libs.validation.dsr import sharpe_ratio
from libs.validation.errors import ValidationError


class PBOResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pbo: float
    n_combinations: int
    n_strategies: int
    median_logit: float

    @property
    def overfit(self) -> bool:
        return self.pbo > 0.5


def probability_backtest_overfitting(
    returns_matrix: np.ndarray, *, n_splits: int = 16
) -> PBOResult:
    """Compute PBO from a (T observations x N strategies) matrix of per-period returns."""
    matrix = np.asarray(returns_matrix, dtype="float64")
    _check(matrix, n_splits)
    n_obs, n_strategies = matrix.shape

    blocks = np.array_split(np.arange(n_obs), n_splits)

    # THE COLUMN MEAN IS REMOVED FIRST, and this is a numerical decision rather than a stylistic
    # one. Assembling a variance from block sums uses S2 - S1^2/n, which subtracts two nearly
    # equal numbers when the mean is large relative to the standard deviation. Daily returns have
    # mean/std around 0.01, so the raw form would throw away digits for no reason. Shifting a
    # column by a constant leaves its variance exactly unchanged and shifts its mean by exactly
    # that constant, so the shift is added back below and the algebra is exact.
    col_mean = matrix.mean(axis=0)
    centred = matrix - col_mean

    counts = np.array([len(b) for b in blocks], dtype="float64")            # (S,)
    s1 = np.stack([centred[b].sum(axis=0) for b in blocks])                 # (S, N)
    s2 = np.stack([np.square(centred[b]).sum(axis=0) for b in blocks])      # (S, N)
    tot_n, tot_s1, tot_s2 = counts.sum(), s1.sum(axis=0), s2.sum(axis=0)

    half = n_splits // 2
    logits: list[float] = []
    for is_block_ids in combinations(range(n_splits), half):
        idx = list(is_block_ids)
        n_is = float(counts[idx].sum())
        is_s1, is_s2 = s1[idx].sum(axis=0), s2[idx].sum(axis=0)
        # The complement, for free. Enumerating the out-of-sample blocks and re-summing them
        # would double the work to recover a number already implied by the totals.
        oos_s1, oos_s2 = tot_s1 - is_s1, tot_s2 - is_s2
        n_oos = float(tot_n - n_is)

        is_perf = _sharpe_from_moments(n_is, is_s1, is_s2, col_mean)
        oos_perf = _sharpe_from_moments(n_oos, oos_s1, oos_s2, col_mean)

        best = int(np.argmax(is_perf))
        rank = _average_rank_of(oos_perf, best)
        w = rank / (n_strategies + 1)
        logits.append(float(np.log(w / (1.0 - w))))

    return _result(logits, n_strategies)


def _average_rank_of(values: np.ndarray, index: int) -> float:
    """The tie-averaged 1..N rank of `values[index]`, without ranking anything else.

    `scipy.stats.rankdata` builds the whole rank vector, and CSCV then reads exactly one entry
    from it and discards the rest -- 12,870 times, which was 2.3 of the remaining 3.1 seconds.
    Under average-tie ranking the elements equal to x occupy ranks L+1 .. L+E where L is the count
    strictly below and E the count equal, so the answer is L + (E+1)/2. That is integer
    arithmetic on two counts and is exactly what rankdata returns for this element, ties included.
    """
    x = values[index]
    less = int(np.count_nonzero(values < x))
    equal = int(np.count_nonzero(values == x))
    return less + (equal + 1) / 2.0


def _sharpe_from_moments(
    n: float, s1: np.ndarray, s2: np.ndarray, shift: np.ndarray
) -> np.ndarray:
    """Per-column Sharpe from (count, sum, sum-of-squares) of the SHIFTED data.

    `shift` is the constant removed from each column before the sums were taken; it is added back
    to the mean and does not touch the variance. Zero standard deviation yields 0.0, matching
    `dsr.sharpe_ratio` -- a column that never moves has no Sharpe, not an infinite one.
    """
    if n < 2:
        return np.zeros_like(s1)
    mean = s1 / n + shift
    var = (s2 - s1 * s1 / n) / (n - 1.0)
    # Clipped because catastrophic cancellation can put a mathematically-zero variance a few ulps
    # below zero, and sqrt of that is nan -- which would propagate into argmax and silently pick
    # an arbitrary "best" strategy.
    sd = np.sqrt(np.maximum(var, 0.0))
    return np.where(sd > 0.0, mean / np.where(sd > 0.0, sd, 1.0), 0.0)


def _check(matrix: np.ndarray, n_splits: int) -> None:
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    if matrix.shape[0] < n_splits:
        raise ValidationError("not enough observations for the requested n_splits")


def _result(logits: list[float], n_strategies: int) -> PBOResult:
    logit_arr = np.array(logits, dtype="float64")
    return PBOResult(
        pbo=float(np.mean(logit_arr < 0.0)),
        n_combinations=len(logits),
        n_strategies=n_strategies,
        median_logit=float(np.median(logit_arr)),
    )


def _pbo_reference(returns_matrix: np.ndarray, *, n_splits: int = 16) -> PBOResult:
    """The naive definition, recomputing every Sharpe from the raw slice.

    NOT DEAD CODE. This is the specification the fast path is tested against; it is what makes
    the optimisation auditable rather than trusted. It is intentionally the literal transcription
    of the CSCV procedure, with no reuse of anything between combinations.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    _check(matrix, n_splits)
    n_obs, n_strategies = matrix.shape
    blocks = np.array_split(np.arange(n_obs), n_splits)
    logits: list[float] = []
    for is_block_ids in combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([blocks[i] for i in is_block_ids])
        oos_rows = np.concatenate([blocks[i] for i in range(n_splits) if i not in is_block_ids])
        is_perf = np.array([sharpe_ratio(matrix[is_rows, k]) for k in range(n_strategies)])
        oos_perf = np.array([sharpe_ratio(matrix[oos_rows, k]) for k in range(n_strategies)])
        best = int(np.argmax(is_perf))
        rank = float(rankdata(oos_perf)[best])
        w = rank / (n_strategies + 1)
        logits.append(float(np.log(w / (1.0 - w))))
    return _result(logits, n_strategies)
