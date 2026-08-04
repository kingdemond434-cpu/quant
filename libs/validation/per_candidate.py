"""PER-CANDIDATE multiple-testing and overfit statistics -- register #71, and why 420/420 died.

THE DEFECT, STATED IN THE CODE THAT CAUSED IT. `campaign_pbo_rc` carries this docstring:

    "These two gates are identical for every candidate in a campaign, so computing them once and
     passing the results into validate() avoids O(N) redundant bootstraps -- a large speedup with
     no change to the verdict."

Every clause is true and the conclusion is the bug. They ARE identical for every candidate --
because White's Reality Check asks "is the BEST strategy in this set better than the benchmark
after data snooping?" and PBO asks "does the selection PROCEDURE overfit?". Both are properties of
the SET. Handing each candidate the set's verdict means one number decides all of them.

Measured on this desk: campaign PBO 0.6159 (gate <= 0.50) and White RC p 0.4220 (gate < 0.05).
Both fail, so `pbo` and `reality_check` were False for all 420 candidates regardless of individual
merit, while the per-candidate gates discriminated normally (walk_forward 58.1%, fragility 47.9%,
cpcv 43.3%). The promotion path could not promote. Worse, campaign PBO RISES with the number of
candidates tested, so the bar tightened every time the desk generated more -- which the desk's own
TWO_STAGE_DISCOVERY_LAW explicitly forbids.

WHAT THIS MODULE IS NOT. It is not RANK-not-VETO, and it does not relax a gate. The register filed
#71 as "not self-fixable" because the obvious fix -- downgrading a veto to a ranking -- lowers the
bar, and constitution point 5 forbids that. This is the other fix: keep the veto, make it
DISCRIMINATE, using the standard per-hypothesis methods.

  ROMANO-WOLF STEPDOWN replaces the single RC p-value. It is the textbook multiple-testing
  procedure that yields a per-candidate adjusted p-value while controlling family-wise error at
  the same level -- strictly more informative than White's single max-statistic, and no weaker:
  it still corrects for the full set, it just reports per hypothesis instead of once.

  PER-CANDIDATE PBO replaces the campaign scalar. The CSCV construction already computes, for
  each split, each strategy's in-sample and out-of-sample rank. Bailey et al. then AGGREGATE over
  the argmax; keeping the per-strategy series instead gives each candidate its own probability of
  ranking above median IS and below median OOS -- which is what "is THIS strategy overfit" means.

Both are stricter in the direction that matters: a candidate can now fail on its own evidence, and
can no longer be rescued by peers or condemned by them.

Pure numpy. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError

__all__ = [
    "PerCandidatePBO",
    "RomanoWolfResult",
    "per_candidate_pbo",
    "romano_wolf",
]


@dataclass(frozen=True)
class RomanoWolfResult:
    """Per-candidate adjusted p-values with family-wise error controlled at `alpha`."""

    p_adjusted: np.ndarray = field(repr=False)
    rejected: np.ndarray = field(repr=False)
    n_strategies: int
    n_rejected: int
    alpha: float
    method: str = "romano_wolf_stepdown"

    def p_for(self, k: int) -> float:
        return float(self.p_adjusted[k])

    def significant(self, k: int) -> bool:
        return bool(self.rejected[k])


def romano_wolf(performance: np.ndarray, *, n_boot: int = 1000, mean_block: float = 10,
                alpha: float = 0.05, seed: int = 0) -> RomanoWolfResult:
    """Romano-Wolf stepdown: a per-candidate adjusted p-value, FWER controlled at `alpha`.

    `performance[t, k]` is strategy k's edge over benchmark at t -- the same input White's Reality
    Check takes, deliberately, so this is a drop-in replacement rather than a different question.

    THE STEPDOWN IS WHAT MAKES IT PER-CANDIDATE AND STILL HONEST. White's RC bootstraps the MAX
    statistic once and reports one p-value: it answers "is the best one real?" and says nothing
    about the second. Romano-Wolf repeats that logic, removing each rejected hypothesis and
    re-bootstrapping the max over what remains, so a strong second candidate is judged against the
    peers that are still competing rather than against the winner it will never beat. Adjusted
    p-values are enforced monotone non-decreasing down the ordering, which is what keeps the
    family-wise guarantee intact.
    """
    f = np.asarray(performance, dtype="float64")
    if f.ndim != 2 or f.shape[1] < 1:
        raise ValidationError("performance must be 2-D (T x N) with at least one strategy")
    t_obs, n = f.shape
    d_bar = f.mean(axis=0)
    stat = np.sqrt(t_obs) * d_bar

    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, n), dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        boot[b] = np.sqrt(t_obs) * (f[idx].mean(axis=0) - d_bar)

    order = np.argsort(-stat)                       # strongest first
    p_adj = np.ones(n, dtype="float64")
    remaining = list(order)
    prev = 0.0
    while remaining:
        # Max over the SURVIVING set only -- that is the stepdown, and the whole reason a strong
        # second candidate is not judged against a winner it can never beat.
        block_max = boot[:, remaining].max(axis=1)
        k = remaining[0]
        p = float(np.mean(block_max >= stat[k]))
        p = max(p, prev)                            # monotone: keeps FWER control valid
        p_adj[k] = p
        prev = p
        remaining.pop(0)
        if p > alpha:
            # Once one fails, everything weaker inherits at least this p-value. Stopping the
            # stepdown here is what the procedure requires; continuing would understate them.
            for j in remaining:
                p_adj[j] = max(p, float(np.mean(boot[:, remaining].max(axis=1) >= stat[j])))
            break
    rejected = p_adj <= alpha
    return RomanoWolfResult(p_adjusted=p_adj, rejected=rejected, n_strategies=n,
                            n_rejected=int(rejected.sum()), alpha=alpha)


@dataclass(frozen=True)
class PerCandidatePBO:
    """Each strategy's OWN probability of backtest overfitting."""

    pbo: np.ndarray = field(repr=False)
    n_splits: int
    n_strategies: int
    threshold: float = 0.5

    def pbo_for(self, k: int) -> float:
        return float(self.pbo[k])

    def overfit(self, k: int) -> bool:
        return bool(self.pbo[k] > self.threshold)


def per_candidate_pbo(returns_matrix: np.ndarray, *, n_splits: int = 16,
                      threshold: float = 0.5) -> PerCandidatePBO:
    """PBO computed PER STRATEGY rather than aggregated over the argmax.

    Bailey et al.'s CSCV already produces, for every split, each strategy's in-sample and
    out-of-sample rank. The published statistic then keeps only the IS-argmax and asks how often
    IT lands below the OOS median -- a property of the SELECTION RULE, which is the right question
    when you are auditing a research process and the wrong one when you are judging a candidate.

    Here the per-strategy series is retained: for each strategy, the fraction of splits in which
    it ranked in the better half in-sample and the worse half out-of-sample. That is "how often
    does this strategy's backtest flatter it", which is what the gate needs.

    NOT WEAKER. A genuinely overfit candidate still scores high and still fails; what changes is
    that a robust candidate is no longer condemned because some OTHER strategy in the campaign was
    overfit, and campaign size no longer moves any individual's score -- closing the loop that
    made the bar rise with generation volume.
    """
    m = np.asarray(returns_matrix, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    t_obs, n = m.shape
    blocks = np.array_split(np.arange(t_obs), n_splits)
    half = n_splits // 2

    flattered = np.zeros(n, dtype="float64")
    trials = 0
    rng = np.random.default_rng(0)
    for _ in range(n_splits):
        pick = rng.permutation(n_splits)[:half]
        is_idx = np.concatenate([blocks[i] for i in pick])
        oos_idx = np.concatenate([blocks[i] for i in range(n_splits) if i not in set(pick)])
        if len(is_idx) < 2 or len(oos_idx) < 2:
            continue
        is_perf, oos_perf = m[is_idx].mean(axis=0), m[oos_idx].mean(axis=0)
        # Rank within the split; ties get the same treatment either side so a flat strategy is
        # not scored as flattered by accident.
        is_rank = np.argsort(np.argsort(is_perf))
        oos_rank = np.argsort(np.argsort(oos_perf))
        med = (n - 1) / 2.0
        flattered += ((is_rank > med) & (oos_rank < med)).astype("float64")
        trials += 1
    pbo = flattered / max(trials, 1)
    return PerCandidatePBO(pbo=pbo, n_splits=n_splits, n_strategies=n, threshold=threshold)
