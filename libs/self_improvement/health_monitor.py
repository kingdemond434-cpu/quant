"""Alpha health monitoring (reuses ``libs.alpha`` health, maps to a 0-100 score + level)."""

from __future__ import annotations

from libs.alpha.card import AlphaCard, ExpectedMetrics, LiveMetrics
from libs.alpha.health import calculate_alpha_health
from libs.self_improvement.models import HealthAssessment, HealthLevel


class AlphaHealthMonitor:
    """Scores live alpha health on a 0-100 scale using the existing health engine."""

    def assess(self, card: AlphaCard, live: LiveMetrics) -> HealthAssessment:
        health = calculate_alpha_health(ExpectedMetrics.from_card(card), live)
        score = round(health.overall * 100.0, 4)
        return HealthAssessment(
            alpha_id=card.id,
            health_score=score,
            level=HealthLevel.classify(score),
            components={k: round(v * 100.0, 4) for k, v in health.components.items()},
        )
