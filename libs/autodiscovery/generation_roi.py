"""Generation-ROI falsification harness — does batch hypothesis generation actually pay?

The disciplined test to run before committing to an autonomous generator (RD-Agent style): push a
batch of candidate hypotheses through the SAME pipeline a real generator would face — the novelty
gate (skip the graveyard) then the DSR gauntlet with cumulative-trial deflation — and measure the
survivor rate and the cost per survivor.

The economics it exposes: the DSR bar (``sr0_threshold``) RISES with the number of trials, so
throwing more candidates at the SAME data lowers the survivor rate — mass generation is self-
defeating under honest multiple-testing correction. The novelty gate helps only by NOT paying to
backtest redundant candidates. This answers the ROI question with numbers, not argument, and is
cheap to run: point it at real (hypothesis, returns) pairs, or drive it with a Monte-Carlo null via
``scripts/run_generation_roi_test.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty
from libs.validation.dsr import deflated_sharpe_ratio


class Candidate(BaseModel):
    """One proposed hypothesis together with the return stream its backtest produced."""

    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    features: tuple[str, ...] = ()
    returns: tuple[float, ...]


class GenerationRoiReport(BaseModel):
    """The economics of one generation batch: what survived, at what cost, against what bar."""

    model_config = ConfigDict(frozen=True)

    proposed: int
    screened_out_redundant: int
    backtested: int
    survivors: int
    survivor_rate: float
    total_trials: int
    deflated_bar_sr0: float  # the DSR sr0 threshold at the batch's cumulative trial count
    cost_backtests: float
    cost_saved_by_novelty_gate: float
    cost_per_survivor: float  # inf when zero survivors


def generation_roi(
    candidates: Sequence[Candidate],
    *,
    variance_of_sharpes: float,
    priors: Sequence[PriorIdea] = (),
    n_trials_prior: int = 0,
    dsr_threshold: float = 0.95,
    novelty_threshold: float = 0.7,
    cost_per_backtest: float = 1.0,
) -> GenerationRoiReport:
    """Run a batch through novelty-gate → DSR gauntlet and report the ROI.

    ``variance_of_sharpes`` is the cross-trial Sharpe variance the DSR uses to set the deflated bar.
    ``n_trials_prior`` is the trials already spent this campaign — the batch deflates on top of it
    (cumulative-trial deflation). Redundant candidates (novelty-gated against ``priors``) are NOT
    backtested and cost nothing. All backtested candidates are judged against the SAME cumulative
    trial count, so the bar reflects everything searched.
    """
    novel: list[Candidate] = []
    redundant = 0
    for c in candidates:
        gate = hypothesis_novelty(
            c.statement, features=c.features, priors=priors, redundant_threshold=novelty_threshold
        )
        if gate.is_redundant:
            redundant += 1
        else:
            novel.append(c)

    total_trials = n_trials_prior + len(novel)
    survivors = 0
    sr0 = 0.0
    for c in novel:
        res = deflated_sharpe_ratio(
            np.asarray(c.returns, dtype="float64"),
            n_trials=max(2, total_trials),
            variance_of_sharpes=variance_of_sharpes,
            threshold=dsr_threshold,
        )
        sr0 = res.sr0_threshold
        if res.passed:
            survivors += 1

    cost_bt = len(novel) * cost_per_backtest
    return GenerationRoiReport(
        proposed=len(candidates),
        screened_out_redundant=redundant,
        backtested=len(novel),
        survivors=survivors,
        survivor_rate=(survivors / len(novel)) if novel else 0.0,
        total_trials=total_trials,
        deflated_bar_sr0=sr0,
        cost_backtests=cost_bt,
        cost_saved_by_novelty_gate=redundant * cost_per_backtest,
        cost_per_survivor=(cost_bt / survivors) if survivors else float("inf"),
    )
