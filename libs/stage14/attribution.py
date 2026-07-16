"""Portfolio attribution — decompose realized performance by sleeve, factor, regime, and cost.

Feeds future allocation decisions: which sleeves/factors/regimes earned (or lost) the money, net
of costs. Pure and deterministic (weight x return); complements Stage 13.5 per-alpha attribution.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class PortfolioAttribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    gross_return: float
    cost: float
    net_return: float
    by_sleeve: dict[str, float] = Field(default_factory=dict)
    by_factor: dict[str, float] = Field(default_factory=dict)
    by_regime: dict[str, float] = Field(default_factory=dict)


def _split(weights: Mapping[str, float], gross: float) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return dict.fromkeys(weights, 0.0)
    return {k: (w / total) * gross for k, w in weights.items()}


class PortfolioAttributionEngine:
    """Attributes realized portfolio return across sleeves, factors, and regime."""

    def attribute(
        self,
        *,
        gross_return: float,
        cost: float = 0.0,
        sleeve_weights: Mapping[str, float] | None = None,
        factor_weights: Mapping[str, float] | None = None,
        regime: str | None = None,
    ) -> PortfolioAttribution:
        net = gross_return - cost
        by_regime = {regime: net} if regime is not None else {}
        return PortfolioAttribution(
            gross_return=gross_return,
            cost=cost,
            net_return=net,
            by_sleeve=_split(sleeve_weights or {}, gross_return),
            by_factor=_split(factor_weights or {}, gross_return),
            by_regime=by_regime,
        )
