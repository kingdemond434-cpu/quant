"""Concept evolution engine — automatically improve existing ideas.

Takes a base hypothesis and generates candidate improvements (add a regime filter, add a
volatility filter, improve capacity, improve robustness). The variants are *proposals* for the
research queue; they still must pass the full validation gauntlet before any production use.
"""

from __future__ import annotations

from libs.alpha_factory.models import Hypothesis
from libs.core.ids import generate_id

# (description suffix, feature added) mutations applied to a base concept.
_MUTATIONS: tuple[tuple[str, str], ...] = (
    ("with a regime filter", "regime_filter"),
    ("with a volatility filter", "volatility_filter"),
    ("with capacity-aware sizing", "capacity_sizing"),
    ("with robustness regularization", "robustness_reg"),
)


class ConceptEvolutionEngine:
    """Generates improvement variants of a base hypothesis."""

    def evolve(self, base: Hypothesis) -> list[Hypothesis]:
        variants: list[Hypothesis] = []
        for suffix, feature in _MUTATIONS:
            if feature in base.features:
                continue  # already present; do not duplicate the mutation
            variants.append(
                Hypothesis(
                    id=generate_id("hyp"),
                    statement=f"{base.statement} {suffix}",
                    category=base.category,
                    features=[*base.features, feature],
                    expected_edge=base.expected_edge,
                    rationale=f"evolution of {base.id}: added {feature}",
                )
            )
        return variants
