"""Portfolio construction engine — orchestrates allocation, controls, constraints, analytics.

Risk overrides alpha: this engine only *proposes* target weights respecting hard caps; the risk
gate disposes. Construction is deterministic (reproducible) and, when given a database, every
build is journaled to the immutable audit log.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.constraints import apply_constraints
from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.diversification import (
    apply_correlation_controls,
    diversification_ratio,
    effective_bets,
)
from libs.portfolio.errors import PortfolioError
from libs.portfolio.exposures import (
    calculate_factor_exposures,
    calculate_risk_contributions,
    calculate_strategy_exposures,
)
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.models import AlphaInput, PortfolioConstraints, PortfolioTarget
from libs.portfolio.optimize import optimize_portfolio
from libs.portfolio.risk_parity import allocate_risk


def build_portfolio(
    alphas: Sequence[AlphaInput],
    *,
    correlation: np.ndarray | None = None,
    constraints: PortfolioConstraints | None = None,
    method: str = "hrp",
) -> PortfolioTarget:
    """Construct a target allocation from alphas using ``method`` and enforce all constraints."""
    if not alphas:
        raise PortfolioError("at least one alpha is required")
    ids = [a.alpha_id for a in alphas]
    if len(set(ids)) != len(ids):
        raise PortfolioError("alpha ids must be unique")

    cov = covariance_from_alphas(alphas, correlation)
    constraints = constraints or PortfolioConstraints()

    if method == "risk_parity":
        base = allocate_risk(alphas, correlation=correlation)
    elif method == "hrp":
        weights_array = hrp_weights(cov)
        base = {i: float(w) for i, w in zip(ids, weights_array, strict=True)}
    elif method == "optimize":
        base = optimize_portfolio(alphas, correlation=correlation)
    else:
        raise PortfolioError("method must be 'risk_parity', 'hrp', or 'optimize'")

    binding: list[str] = []
    if correlation is not None:
        base, corr_binding = apply_correlation_controls(base, cov, ids)
        binding.extend(corr_binding)

    weights, constraint_binding = apply_constraints(base, alphas, constraints)
    binding.extend(constraint_binding)

    weights_array = np.array([weights[i] for i in ids], dtype="float64")
    return PortfolioTarget(
        weights=weights,
        method=method,
        factor_exposures=calculate_factor_exposures(weights, alphas),
        strategy_exposures=calculate_strategy_exposures(weights, alphas),
        risk_contributions=calculate_risk_contributions(weights, cov, ids),
        diversification_ratio=diversification_ratio(weights_array, cov),
        effective_bets=effective_bets(weights_array),
        binding_constraints=sorted(set(binding)),
    )


class PortfolioEngine:
    """Stateful wrapper that journals each portfolio build to the audit log."""

    def __init__(self, db: object | None = None) -> None:
        self._audit = None
        if db is not None:
            from libs.store.audit import AuditLog

            self._audit = AuditLog(db)  # type: ignore[arg-type]

    def build_portfolio(
        self,
        alphas: Sequence[AlphaInput],
        *,
        correlation: np.ndarray | None = None,
        constraints: PortfolioConstraints | None = None,
        method: str = "hrp",
    ) -> PortfolioTarget:
        target = build_portfolio(
            alphas, correlation=correlation, constraints=constraints, method=method
        )
        if self._audit is not None:
            self._audit.append(
                "portfolio_build", actor="portfolio_engine",
                inputs={"method": method, "n_alphas": len(alphas)},
                outcome=_summary(target.weights),
            )
        return target


def _summary(weights: Mapping[str, float]) -> str:
    return ", ".join(f"{k}={v:.3f}" for k, v in sorted(weights.items()))
