"""Research ROI engine — allocate research effort to the highest-yield areas.

Reuses the discovery layer's ROI scoring (``research_roi``) and category ranking
(``rank_categories``). The factory tracks effort/cost vs alpha quality produced and reports a
0-100 ROI score per research program so resources flow to the best opportunities.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.discovery.research_roi import (
    CategoryStat,
    ResearchROIResult,
    rank_categories,
    research_roi,
)


class ResearchROIEngine:
    """Scores research efficiency and ranks categories by expected yield."""

    def score(
        self,
        *,
        ideas_generated: int,
        ideas_tested: int,
        ideas_validated: int,
        time_hours: float,
        production_contribution: float,
        expected_future_contribution: float = 0.0,
    ) -> ResearchROIResult:
        return research_roi(
            ideas_generated=ideas_generated,
            ideas_tested=ideas_tested,
            ideas_validated=ideas_validated,
            time_hours=time_hours,
            production_contribution=production_contribution,
            expected_future_contribution=expected_future_contribution,
        )

    def rank(self, stats: Mapping[str, CategoryStat]) -> list[tuple[str, float]]:
        """Rank research categories by expected yield (validation rate x contribution)."""
        return rank_categories(stats)
