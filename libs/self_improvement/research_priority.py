"""Research priority engine — guide future research toward the highest-value areas.

Reuses the discovery layer's research-ROI ranking and combines it with decaying-family signals:
families that are decaying (and would leave portfolio/regime gaps) get higher research priority.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.discovery.research_roi import CategoryStat, rank_categories
from libs.self_improvement.models import ResearchPriority


class ResearchPriorityEngine:
    """Ranks research categories by need (decay) and expected yield (ROI)."""

    def prioritize(
        self,
        *,
        decaying_by_category: Mapping[str, float],
        roi_stats: Mapping[str, CategoryStat] | None = None,
    ) -> list[ResearchPriority]:
        yields = dict(rank_categories(dict(roi_stats))) if roi_stats else {}
        categories = set(decaying_by_category) | set(yields)
        priorities: list[ResearchPriority] = []
        for category in categories:
            decay = float(decaying_by_category.get(category, 0.0))
            yield_score = float(yields.get(category, 0.0))
            score = decay + yield_score  # decay = need now, yield = expected payoff
            reason = (
                f"decay_pressure={decay:.2f}, expected_yield={yield_score:.2f}"
                if score > 0
                else "no current research pressure"
            )
            priorities.append(
                ResearchPriority(category=category, priority_score=score, reason=reason)
            )
        return sorted(priorities, key=lambda p: p.priority_score, reverse=True)
