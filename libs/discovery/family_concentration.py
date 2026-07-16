"""alpha_family_concentration_engine — control hidden factor concentration.

Tracks exposure across alpha families (trend, momentum, breakout, mean reversion, volatility,
session, lead-lag, relative strength, carry, seasonal) and penalizes over-exposure to one family.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class FamilyConcentrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    family_concentration_score: float  # 0-100 (HHI*100); higher = more concentrated (worse)
    balanced: bool
    max_family_share: float
    by_family: dict[str, float]

    def __bool__(self) -> bool:
        return self.balanced


def family_concentration(
    weights_by_family: Mapping[str, float], *, max_family_share: float = 0.50
) -> FamilyConcentrationResult:
    """Herfindahl concentration across alpha families."""
    total = sum(abs(w) for w in weights_by_family.values())
    if total <= 0:
        return FamilyConcentrationResult(
            family_concentration_score=0.0, balanced=True, max_family_share=0.0, by_family={}
        )
    shares = {k: abs(w) / total for k, w in weights_by_family.items()}
    hhi = sum(s**2 for s in shares.values())
    max_share = max(shares.values())
    return FamilyConcentrationResult(
        family_concentration_score=hhi * 100.0,
        balanced=max_share <= max_family_share,
        max_family_share=max_share,
        by_family=shares,
    )
