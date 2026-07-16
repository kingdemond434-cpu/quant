"""InstitutionalPortfolioScore — one 0-100 score that all selection ultimately uses.

Survival is the dominant term; tail, drawdown, and fragility are penalties. Deterministic.
"""

from __future__ import annotations

from libs.stage14.models import InstitutionalPortfolioScore

_POSITIVE_WEIGHTS: dict[str, float] = {
    "survival": 0.30,
    "geometric_growth": 0.20,
    "sharpe": 0.10,
    "calmar": 0.10,
    "capacity": 0.10,
    "diversification": 0.10,
    "resilience": 0.05,
    "execution": 0.05,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def institutional_portfolio_score(
    *,
    survival_score: float,
    geometric_growth_score: float,
    expected_sharpe: float,
    expected_calmar: float,
    capacity_score: float,
    diversification_score: float,
    resilience_score: float = 50.0,
    execution_score: float = 100.0,
    tail_risk: float = 0.0,        # 0..1 (higher = worse)
    drawdown_risk: float = 0.0,    # 0..1
    fragility: float = 0.0,        # 0..1
) -> InstitutionalPortfolioScore:
    components = {
        "survival": _clip01(survival_score / 100.0),
        "geometric_growth": _clip01(geometric_growth_score / 100.0),
        "sharpe": _clip01(expected_sharpe / 3.0),
        "calmar": _clip01(expected_calmar / 3.0),
        "capacity": _clip01(capacity_score / 100.0),
        "diversification": _clip01(diversification_score / 100.0),
        "resilience": _clip01(resilience_score / 100.0),
        "execution": _clip01(execution_score / 100.0),
    }
    positive = sum(_POSITIVE_WEIGHTS[k] * v for k, v in components.items())
    penalty = 0.5 * _clip01(tail_risk) + 0.3 * _clip01(drawdown_risk) + 0.2 * _clip01(fragility)
    score = 100.0 * _clip01(positive - 0.3 * penalty)
    components["penalty"] = penalty
    return InstitutionalPortfolioScore(score=score, components=components)
