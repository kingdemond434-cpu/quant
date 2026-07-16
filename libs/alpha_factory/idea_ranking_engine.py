"""Idea ranking engine — research the highest-value ideas first.

Scores future research ideas by expected edge, robustness, capacity, novelty, regime need, and
portfolio need, penalizing crowding, into a 0-100 priority. Ranking is total and deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha_factory.models import IdeaCandidate, IdeaScore

_WEIGHTS: dict[str, float] = {
    "expected_edge": 0.25,
    "expected_robustness": 0.15,
    "expected_capacity": 0.10,
    "novelty": 0.15,
    "regime_need": 0.10,
    "portfolio_need": 0.10,
    "uncrowded": 0.15,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class IdeaRankingEngine:
    """Prioritizes research ideas by expected value."""

    def score(self, candidate: IdeaCandidate) -> IdeaScore:
        components = {
            "expected_edge": _clip01(candidate.expected_edge),
            "expected_robustness": _clip01(candidate.expected_robustness),
            "expected_capacity": _clip01(candidate.expected_capacity),
            "novelty": _clip01(candidate.novelty),
            "regime_need": _clip01(candidate.regime_need),
            "portfolio_need": _clip01(candidate.portfolio_need),
            "uncrowded": 1.0 - _clip01(candidate.crowding),
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return IdeaScore(
            idea_id=candidate.idea_id, category=candidate.category,
            idea_priority_score=score, components=components,
        )

    def rank(self, candidates: Sequence[IdeaCandidate]) -> list[IdeaScore]:
        scores = [self.score(c) for c in candidates]
        return sorted(scores, key=lambda s: s.idea_priority_score, reverse=True)
