"""Portfolio analytics — correlation, survival, stress, resilience, convexity, contribution, cost.

Thin orchestration over the platform's existing primitives (Monte-Carlo survival, stress
scenarios) plus portfolio-level measures. Every score is 0-100 unless noted; survival dominates.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.stress_scenario import stress_scenario
from libs.stage14.models import (
    ConvexityResult,
    CorrelationResult,
    EfficiencyResult,
    MarginalContribution,
    ResilienceResult,
    RiskBudget,
    StressResult,
    SurvivalResult,
)

_EPS = 1e-12


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class PortfolioCorrelationEngine:
    """Flags hidden concentration from the portfolio correlation matrix."""

    def evaluate(
        self, correlation: np.ndarray, *, budget: RiskBudget | None = None
    ) -> CorrelationResult:
        corr = np.asarray(correlation, dtype="float64")
        n = corr.shape[0]
        if corr.ndim != 2 or corr.shape[1] != n:
            raise ValueError("correlation must be square")
        if n < 2:
            return CorrelationResult(avg_pairwise=0.0, max_pairwise=0.0, concentration=0.0,
                                     acceptable=True)
        iu = np.triu_indices(n, k=1)
        off = np.abs(corr[iu])
        avg = float(off.mean())
        mx = float(off.max())
        limit = (budget or RiskBudget()).correlation_budget
        return CorrelationResult(
            avg_pairwise=avg, max_pairwise=mx, concentration=avg, acceptable=avg <= limit
        )


class PortfolioSurvivalEngine:
    """Probability of ruin / survival (reuses Monte-Carlo survival). Survival dominates return."""

    def evaluate(
        self, returns: np.ndarray, *, dd_limit: float = 0.20, cost_stress: float = 0.0005,
        seed: int = 0,
    ) -> SurvivalResult:
        base = monte_carlo_survival(returns, dd_limit=dd_limit, seed=seed)
        stressed = monte_carlo_survival(
            returns, dd_limit=dd_limit, cost_per_period=cost_stress, seed=seed
        )
        return SurvivalResult(
            survival_probability=base.survival_probability,
            probability_of_ruin=base.probability_of_ruin,
            stress_survival=stressed.survival_probability,
            survival_score=100.0 * base.survival_probability,
        )


class PortfolioStressEngine:
    """Historical-crisis stress (reuses the scenario engine: 2008/2020/flash/vol/liquidity)."""

    def evaluate(self, returns: np.ndarray, *, exposure: float = 1.0) -> StressResult:
        result = stress_scenario(returns, exposure=exposure)
        return StressResult(
            stress_score=result.stress_resilience_score,
            worst_drawdown=result.worst_drawdown,
            by_scenario=dict(result.by_scenario),
        )


class PortfolioResilienceEngine:
    """Blends regime / factor / capacity / execution resilience into one score."""

    def evaluate(
        self,
        *,
        regime_resilience: float,
        factor_resilience: float,
        capacity_resilience: float,
        execution_resilience: float,
    ) -> ResilienceResult:
        components = {
            "regime": _clip01(regime_resilience),
            "factor": _clip01(factor_resilience),
            "capacity": _clip01(capacity_resilience),
            "execution": _clip01(execution_resilience),
        }
        score = 100.0 * float(np.mean(list(components.values())))
        return ResilienceResult(resilience_score=score, components=components)


class PortfolioConvexityEngine:
    """Skew, convexity, and crisis alpha — prefer positive convexity and crash resilience."""

    def evaluate(self, returns: np.ndarray) -> ConvexityResult:
        arr = np.asarray(returns, dtype="float64")
        if len(arr) < 3:
            return ConvexityResult(skew=0.0, convexity=1.0, crisis_alpha=0.0, convexity_score=50.0)
        mu, sd = float(arr.mean()), float(arr.std())
        skew = float(((arr - mu) ** 3).mean() / (sd**3)) if sd > _EPS else 0.0
        up = arr[arr > 0]
        down = arr[arr < 0]
        up_semivar = float((up**2).mean()) if len(up) else 0.0
        down_semivar = float((down**2).mean()) if len(down) else _EPS
        convexity = up_semivar / down_semivar if down_semivar > _EPS else 1.0
        worst = np.quantile(arr, 0.1)
        crisis_alpha = float(arr[arr <= worst].mean()) if np.any(arr <= worst) else 0.0
        score = 100.0 * _clip01(0.5 * _clip01(convexity / 2.0) + 0.5 * _clip01(0.5 + skew / 2.0))
        return ConvexityResult(
            skew=skew, convexity=convexity, crisis_alpha=crisis_alpha, convexity_score=score
        )


class MarginalContributionEngine:
    """Marginal portfolio contribution per signal (allocate on contribution, not standalone)."""

    def contributions(
        self, *, weights: Mapping[str, float], metric: Mapping[str, float]
    ) -> MarginalContribution:
        by_signal = {k: float(weights.get(k, 0.0)) * float(metric.get(k, 0.0)) for k in weights}
        return MarginalContribution(by_signal=by_signal, total=sum(by_signal.values()))


class CapitalEfficiencyEngine:
    """Return per unit of risk and capacity; penalizes inefficient capital deployment."""

    def evaluate(
        self, *, expected_return: float, volatility: float, capacity_utilization: float
    ) -> EfficiencyResult:
        rpr = expected_return / volatility if volatility > _EPS else 0.0
        rpc = expected_return / capacity_utilization if capacity_utilization > _EPS else 0.0
        score = 100.0 * _clip01(0.6 * _clip01(rpr / 2.0) + 0.4 * _clip01(rpc))
        return EfficiencyResult(
            capital_efficiency_score=score, return_per_risk=rpr, return_per_capacity=rpc
        )
