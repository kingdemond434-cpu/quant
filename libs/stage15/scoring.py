"""Alpha quality score — 0-100, weighted toward durability, NOT raw returns.

Survival, capacity, diversification, stability, and economic logic dominate; out-of-sample Sharpe
contributes modestly; fragility and decay are penalties. Raw expected return is deliberately
excluded from the positive weighting — a high backtest return does not make a durable alpha.
"""

from __future__ import annotations

from libs.stage15.models import AlphaQualityScore, AlphaScores

_POSITIVE_WEIGHTS: dict[str, float] = {
    "survival": 0.22,
    "capacity": 0.15,
    "diversification": 0.15,
    "stability": 0.15,
    "economic": 0.13,
    "oos_sharpe": 0.10,
    "calmar": 0.05,
    "sortino": 0.05,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def alpha_quality_score(scores: AlphaScores) -> AlphaQualityScore:
    components = {
        "survival": _clip01(scores.survival_score / 100.0),
        "capacity": _clip01(scores.capacity_score / 100.0),
        "diversification": _clip01(scores.diversification_score / 100.0),
        "stability": _clip01(scores.stability_score / 100.0),
        "economic": _clip01(scores.economic_score / 100.0),
        "oos_sharpe": _clip01(scores.sharpe / 3.0),
        "calmar": _clip01(scores.calmar / 3.0),
        "sortino": _clip01(scores.sortino / 3.0),
    }
    positive = sum(_POSITIVE_WEIGHTS[k] * v for k, v in components.items())
    penalty = 0.5 * _clip01(scores.fragility_score / 100.0) + 0.5 * _clip01(
        scores.decay_score / 100.0
    )
    score = 100.0 * _clip01(positive - 0.25 * penalty)
    components["penalty"] = penalty
    return AlphaQualityScore(score=score, components=components)
