"""Rebalancing — time-based, threshold-based, and risk-based."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.portfolio.errors import PortfolioError
from libs.portfolio.exposures import calculate_risk_contributions
from libs.portfolio.models import RebalanceResult


def _trades(current: Mapping[str, float], target: Mapping[str, float]) -> dict[str, float]:
    keys = sorted(set(current) | set(target))
    return {k: float(target.get(k, 0.0) - current.get(k, 0.0)) for k in keys}


def rebalance(
    current: Mapping[str, float],
    target: Mapping[str, float],
    *,
    method: str = "threshold",
    threshold: float = 0.05,
    cov: np.ndarray | None = None,
) -> RebalanceResult:
    """Decide whether to rebalance and compute the trades.

    * ``time``: always rebalance (the caller owns the schedule).
    * ``threshold``: rebalance if any weight has drifted beyond ``threshold``.
    * ``risk``: rebalance if any risk contribution has drifted beyond ``threshold`` (needs ``cov``).
    """
    trades = _trades(current, target)
    turnover = sum(abs(v) for v in trades.values()) / 2.0

    if method == "time":
        rebalanced, reason = True, "scheduled rebalance"
    elif method == "threshold":
        max_drift = max((abs(v) for v in trades.values()), default=0.0)
        rebalanced = max_drift > threshold
        reason = f"max weight drift {max_drift:.4f} vs threshold {threshold}"
    elif method == "risk":
        if cov is None:
            raise PortfolioError("risk-based rebalancing requires a covariance matrix")
        order = sorted(set(current) | set(target))
        cur_rc = calculate_risk_contributions(
            {k: current.get(k, 0.0) for k in order}, cov, order
        )
        tgt_rc = calculate_risk_contributions(
            {k: target.get(k, 0.0) for k in order}, cov, order
        )
        max_rc_drift = max((abs(cur_rc[k] - tgt_rc[k]) for k in order), default=0.0)
        rebalanced = max_rc_drift > threshold
        reason = f"max risk-contribution drift {max_rc_drift:.4f} vs threshold {threshold}"
    else:
        raise PortfolioError("method must be 'time', 'threshold', or 'risk'")

    if not rebalanced:
        return RebalanceResult(
            rebalanced=False, trades=dict.fromkeys(trades, 0.0), turnover=0.0, reason=reason
        )
    return RebalanceResult(rebalanced=True, trades=trades, turnover=turnover, reason=reason)
