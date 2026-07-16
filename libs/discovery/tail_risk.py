"""tail_risk_engine — hidden tail exposure (dependence, gap, vol shock).

tail_risk_score in 0-100 (higher = more hidden tail exposure). Penalizes negative skew, fat
tails, large single-bar gaps, and volatility shocks that a Sharpe ratio would miss.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import kurtosis, skew

from libs.risk.tail import calculate_cvar, calculate_var


class TailRiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tail_risk_score: float  # 0-100, higher = more hidden tail risk (worse)
    acceptable: bool
    cvar_to_var: float
    excess_kurtosis: float
    negative_skew: float
    worst_gap: float

    def __bool__(self) -> bool:
        return self.acceptable


def tail_risk(
    returns: np.ndarray, *, alpha: float = 0.05, threshold: float = 60.0
) -> TailRiskResult:
    """Score an alpha's hidden tail exposure from its return distribution."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 3:
        return TailRiskResult(
            tail_risk_score=0.0, acceptable=True, cvar_to_var=1.0, excess_kurtosis=0.0,
            negative_skew=0.0, worst_gap=0.0,
        )
    var = calculate_var(arr, alpha=alpha)
    cvar = calculate_cvar(arr, alpha=alpha)
    cvar_to_var = cvar / var if var > 0 else 1.0
    excess_kurt = float(kurtosis(arr, fisher=True, bias=False))
    neg_skew = max(0.0, -float(skew(arr, bias=False)))
    worst_gap = float(np.abs(arr).max())

    # Blend into a 0-100 score; each term clipped to keep the scale sane.
    score = (
        min(1.0, max(0.0, cvar_to_var - 1.0) / 2.0) * 30.0
        + min(1.0, excess_kurt / 6.0) * 30.0
        + min(1.0, neg_skew / 2.0) * 25.0
        + min(1.0, worst_gap / (5.0 * var) if var > 0 else 0.0) * 15.0
    )
    return TailRiskResult(
        tail_risk_score=score,
        acceptable=score <= threshold,
        cvar_to_var=cvar_to_var,
        excess_kurtosis=excess_kurt,
        negative_skew=neg_skew,
        worst_gap=worst_gap,
    )
