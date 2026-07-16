"""Hypothesis engine — generate economically-motivated research hypotheses and learn from them.

Generates testable statements per category, optionally informing each hypothesis's expected edge
from the prior success rate recorded in research memory, and reports which hypothesis types have
historically succeeded so future generation favours productive directions.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha_factory.models import AlphaCategory, Hypothesis
from libs.alpha_factory.research_memory import ResearchMemory
from libs.core.ids import generate_id

# Templated, economically-anchored research statements per category.
_TEMPLATES: dict[AlphaCategory, list[tuple[str, list[str]]]] = {
    AlphaCategory.MOMENTUM: [
        ("momentum strengthens in low-volatility regimes", ["momentum", "volatility_regime"]),
        ("cross-sectional momentum predicts continuation", ["rel_strength", "dispersion"]),
    ],
    AlphaCategory.TREND_FOLLOWING: [
        ("trend signals improve through regime transitions", ["trend", "regime_transition"]),
    ],
    AlphaCategory.CARRY: [
        ("carry improves when filtered by a volatility gate", ["carry", "volatility_gate"]),
    ],
    AlphaCategory.MEAN_REVERSION: [
        ("mean reversion works in range regimes with high liquidity", ["zscore", "liquidity"]),
    ],
    AlphaCategory.VOLATILITY: [
        ("volatility compression precedes expansion breakouts", ["vol_compression", "breakout"]),
    ],
    AlphaCategory.CROSS_ASSET: [
        ("cross-asset dispersion predicts equity momentum", ["dispersion", "lead_lag"]),
    ],
}

_DEFAULT_EDGE = 0.5


class HypothesisEngine:
    """Generates research hypotheses and learns which categories succeed."""

    def generate(
        self,
        categories: Sequence[AlphaCategory],
        *,
        memory: ResearchMemory | None = None,
    ) -> list[Hypothesis]:
        hypotheses: list[Hypothesis] = []
        for category in categories:
            prior = (
                memory.success_rate(category.value) if memory is not None else _DEFAULT_EDGE
            )
            expected_edge = prior if prior > 0.0 else _DEFAULT_EDGE
            for statement, features in _TEMPLATES.get(category, []):
                hypotheses.append(
                    Hypothesis(
                        id=generate_id("hyp"),
                        statement=statement,
                        category=category.value,
                        features=list(features),
                        expected_edge=expected_edge,
                        rationale=(
                            f"{category.value}: prior success rate {expected_edge:.2f}; "
                            "must survive the validation gauntlet to be retained."
                        ),
                    )
                )
        return hypotheses

    def learn(self, memory: ResearchMemory) -> dict[str, float]:
        """Success rate per category seen in research memory (which types actually work)."""
        categories = {r.category for r in memory.all()}
        return {c: memory.success_rate(c) for c in sorted(categories)}
