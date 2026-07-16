"""Crowding intelligence — steer research away from crowded concepts.

Blends strategy, factor, and style crowding into a 0..1 score and a research-priority multiplier
(<1 dampens crowded concepts, >0 favours uncrowded ones).
"""

from __future__ import annotations

from libs.alpha_factory.models import CrowdingEstimate


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class CrowdingIntelligence:
    """Estimates concept crowding and the research-priority adjustment it implies."""

    def assess(
        self,
        *,
        strategy_crowding: float,
        factor_crowding: float,
        style_crowding: float,
    ) -> CrowdingEstimate:
        score = _clip01(
            0.4 * strategy_crowding + 0.3 * factor_crowding + 0.3 * style_crowding
        )
        return CrowdingEstimate(
            strategy_crowding=_clip01(strategy_crowding),
            factor_crowding=_clip01(factor_crowding),
            style_crowding=_clip01(style_crowding),
            crowding_score=score,
            priority_multiplier=1.0 - score,
        )
