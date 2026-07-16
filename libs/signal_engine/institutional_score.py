"""Institutional signal score — the single 0-100 master score for ranking/selection.

Combines edge, confidence, capacity, persistence, stability, decay, portfolio contribution, and
execution quality as rewards, with tail risk and uncertainty as penalties. All ranking and final
selection ultimately key off this score.
"""

from __future__ import annotations

from libs.signal_engine.models import InstitutionalScore

# Component weights (sum to 1.0). Rewards positive, penalties enter as (1 - penalty).
_WEIGHTS: dict[str, float] = {
    "edge": 0.18,
    "confidence": 0.18,
    "portfolio_contribution": 0.12,
    "execution": 0.10,
    "capacity": 0.08,
    "persistence": 0.08,
    "stability": 0.08,
    "decay": 0.06,
    "tail": 0.06,
    "uncertainty": 0.06,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def institutional_signal_score(
    *,
    edge_score: float,
    confidence: float,
    capacity_score: float,
    persistence_score: float,
    stability_score: float,
    decay_weight_multiplier: float,
    portfolio_contribution: float,
    execution_score: float,
    tail_risk_score: float,
    uncertainty_score: float,
) -> InstitutionalScore:
    components = {
        "edge": _clip01(edge_score / 100.0),
        "confidence": _clip01(confidence),
        "portfolio_contribution": _clip01(portfolio_contribution / 100.0),
        "execution": _clip01(execution_score / 100.0),
        "capacity": _clip01(capacity_score / 100.0),
        "persistence": _clip01(persistence_score / 100.0),
        "stability": _clip01(stability_score / 100.0),
        "decay": _clip01(decay_weight_multiplier),
        "tail": _clip01(1.0 - tail_risk_score / 100.0),
        "uncertainty": _clip01(1.0 - uncertainty_score),
    }
    score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
    return InstitutionalScore(score=score, components=components)
