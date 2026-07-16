"""research_roi_engine — allocate research effort to the highest-yield areas.

Tracks ideas generated/tested/validated, time consumed, and (expected) production contribution,
and ranks research categories by expected alpha yield so effort flows to the best opportunities.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class ResearchROIResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    research_roi_score: float  # 0-100
    validated_rate: float
    contribution_per_hour: float


def research_roi(
    *,
    ideas_generated: int,
    ideas_tested: int,
    ideas_validated: int,
    time_hours: float,
    production_contribution: float,
    expected_future_contribution: float,
) -> ResearchROIResult:
    """Score research efficiency from validation rate and contribution per hour."""
    validated_rate = ideas_validated / ideas_tested if ideas_tested else 0.0
    total_contribution = production_contribution + expected_future_contribution
    contribution_per_hour = total_contribution / time_hours if time_hours > 0 else 0.0
    # Blend the (capped) validation rate with normalized contribution into 0-100.
    score = 100.0 * (0.5 * min(1.0, validated_rate) + 0.5 * min(1.0, contribution_per_hour))
    return ResearchROIResult(
        research_roi_score=score,
        validated_rate=validated_rate,
        contribution_per_hour=contribution_per_hour,
    )


class CategoryStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    tested: int
    validated: int
    contribution: float


def rank_categories(stats: Mapping[str, CategoryStat]) -> list[tuple[str, float]]:
    """Rank research categories by expected yield = validation rate x contribution."""
    yields = {
        name: (stat.validated / stat.tested if stat.tested else 0.0) * (1.0 + stat.contribution)
        for name, stat in stats.items()
    }
    return sorted(yields.items(), key=lambda kv: kv[1], reverse=True)
