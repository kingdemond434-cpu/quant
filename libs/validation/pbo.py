"""Probability of Backtest Overfitting via Combinatorially-Symmetric Cross-Validation (CSCV).

Splits the sample into S blocks; for every way of choosing half as in-sample, picks the
in-sample-best configuration and measures its out-of-sample rank. PBO is the fraction of
splits where the chosen configuration lands below the OOS median — i.e. its in-sample edge was
overfit (López de Prado).
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
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValidationError("returns_matrix must be 2-D with >= 2 strategies")
    if n_splits % 2 != 0 or n_splits < 2:
        raise ValidationError("n_splits must be a positive even number")
    n_obs, n_strategies = matrix.shape
    if n_obs < n_splits:
        raise ValidationError("not enough observations for the requested n_splits")

    blocks = np.array_split(np.arange(n_obs), n_splits)
    logits: list[float] = []
    for is_block_ids in combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([blocks[i] for i in is_block_ids])
        oos_rows = np.concatenate([blocks[i] for i in range(n_splits) if i not in is_block_ids])

        is_perf = np.array([sharpe_ratio(matrix[is_rows, k]) for k in range(n_strategies)])
        oos_perf = np.array([sharpe_ratio(matrix[oos_rows, k]) for k in range(n_strategies)])

        best = int(np.argmax(is_perf))
        rank = float(rankdata(oos_perf)[best])  # 1..N
        w = rank / (n_strategies + 1)
        logits.append(float(np.log(w / (1.0 - w))))

    logit_arr = np.array(logits, dtype="float64")
    pbo = float(np.mean(logit_arr < 0.0))
    return PBOResult(
        pbo=pbo,
        n_combinations=len(logits),
        n_strategies=n_strategies,
        median_logit=float(np.median(logit_arr)),
    )
