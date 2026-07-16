"""Data Opportunity Engine — rank the datasets that would most increase alpha-discovery odds.

Information advantage, not dataset count. Each missing dataset is scored by
``expected_alpha_value / implementation_cost`` (with diversification and maintenance factored into
the value), and the ranked list is the continuously-updated Data Opportunity Report. This is the
honest answer to "what data should we acquire next?" — and it surfaces the data the current MT5-only
feed lacks (the reason carry/cross-asset/rates families currently run as proxies).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class DatasetOpportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    information_value: float       # 0..1
    alpha_contribution: float      # 0..1 expected new edge
    diversification_benefit: float  # 0..1 (low correlation to current OHLC edges)
    implementation_cost: float     # 1..10 (engineering + sourcing)
    maintenance_burden: float      # 1..10
    unlocks: list[str] = Field(default_factory=list)  # families it would make real (not proxy)

    @property
    def expected_alpha_value(self) -> float:
        # Value blends information, raw alpha potential, and diversification; cost dampens it.
        return (
            0.4 * self.information_value
            + 0.4 * self.alpha_contribution
            + 0.2 * self.diversification_benefit
        ) / (1.0 + 0.1 * self.maintenance_burden)

    @property
    def roi_score(self) -> float:
        return self.expected_alpha_value / self.implementation_cost


class DataOpportunityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ranked: list[dict[str, float | str | list[str]]]
    top_recommendation: str


# Curated catalog of the institutional datasets the MT5-only feed currently lacks. Scores reflect
# typical information content / crowding, NOT a backtested promise — they rank acquisition effort.
_CATALOG: tuple[DatasetOpportunity, ...] = (
    DatasetOpportunity(name="funding_rates", information_value=0.85, alpha_contribution=0.8,
                       diversification_benefit=0.8, implementation_cost=3.0, maintenance_burden=3.0,
                       unlocks=["carry"]),
    DatasetOpportunity(name="yield_curves", information_value=0.85, alpha_contribution=0.75,
                       diversification_benefit=0.85, implementation_cost=4.0,
                       maintenance_burden=3.0,
                       unlocks=["carry", "regime_transition", "risk_premia"]),
    DatasetOpportunity(name="futures_term_structure", information_value=0.8, alpha_contribution=0.8,
                       diversification_benefit=0.8, implementation_cost=5.0, maintenance_burden=4.0,
                       unlocks=["carry", "risk_premia"]),
    DatasetOpportunity(name="currency_indices_dxy", information_value=0.7, alpha_contribution=0.6,
                       diversification_benefit=0.75, implementation_cost=2.0,
                       maintenance_burden=2.0, unlocks=["cross_asset"]),
    DatasetOpportunity(name="volatility_indices_vix", information_value=0.75,
                       alpha_contribution=0.65, diversification_benefit=0.8,
                       implementation_cost=2.0, maintenance_burden=2.0,
                       unlocks=["regime_transition", "risk_premia"]),
    DatasetOpportunity(name="options_implied_vol_surface", information_value=0.9,
                       alpha_contribution=0.85, diversification_benefit=0.85,
                       implementation_cost=8.0, maintenance_burden=7.0, unlocks=["risk_premia"]),
    DatasetOpportunity(name="cot_positioning", information_value=0.7, alpha_contribution=0.6,
                       diversification_benefit=0.8, implementation_cost=3.0, maintenance_burden=3.0,
                       unlocks=["regime_transition", "liquidity"]),
    DatasetOpportunity(name="etf_flows", information_value=0.65, alpha_contribution=0.55,
                       diversification_benefit=0.7, implementation_cost=5.0, maintenance_burden=5.0,
                       unlocks=["liquidity"]),
    DatasetOpportunity(name="macro_release_calendar", information_value=0.6, alpha_contribution=0.5,
                       diversification_benefit=0.65, implementation_cost=3.0,
                       maintenance_burden=3.0, unlocks=["regime_transition"]),
    DatasetOpportunity(name="sentiment_news", information_value=0.55, alpha_contribution=0.5,
                       diversification_benefit=0.7, implementation_cost=7.0, maintenance_burden=7.0,
                       unlocks=["liquidity"]),
)


class DataOpportunityEngine:
    """Ranks missing datasets by expected alpha value per unit implementation cost."""

    def __init__(self, catalog: Sequence[DatasetOpportunity] = _CATALOG) -> None:
        self.catalog = list(catalog)

    def report(self) -> DataOpportunityReport:
        ranked = sorted(self.catalog, key=lambda d: d.roi_score, reverse=True)
        rows: list[dict[str, float | str | list[str]]] = [
            {"name": d.name, "roi_score": round(d.roi_score, 4),
             "expected_alpha_value": round(d.expected_alpha_value, 4),
             "implementation_cost": d.implementation_cost, "unlocks": d.unlocks}
            for d in ranked
        ]
        return DataOpportunityReport(
            ranked=rows, top_recommendation=ranked[0].name if ranked else "",
        )
