"""Research score engine — a single 0-100 score for a research program's promise."""

from __future__ import annotations

from libs.alpha_factory.models import ResearchScoreResult

_WEIGHTS: dict[str, float] = {
    "novelty": 0.20,
    "expected_robustness": 0.20,
    "expected_capacity": 0.15,
    "portfolio_need": 0.15,
    "research_confidence": 0.20,
    "uncrowded": 0.10,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ResearchScoreEngine:
    """Combines research-quality signals into a 0-100 research score."""

    def score(
        self,
        *,
        novelty: float,
        expected_robustness: float,
        expected_capacity: float,
        portfolio_need: float,
        research_confidence: float,
        crowding_risk: float,
    ) -> ResearchScoreResult:
        components = {
            "novelty": _clip01(novelty),
            "expected_robustness": _clip01(expected_robustness),
            "expected_capacity": _clip01(expected_capacity),
            "portfolio_need": _clip01(portfolio_need),
            "research_confidence": _clip01(research_confidence),
            "uncrowded": 1.0 - _clip01(crowding_risk),
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return ResearchScoreResult(research_score=score, components=components)
