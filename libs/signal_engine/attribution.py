"""Signal attribution — decompose realized P&L by contributing alpha.

Answers "which alpha made/lost the money?" so weight optimization and retirement have ground
truth. Two modes: split a trade's realized return by alpha weight, or attribute when per-alpha
realized returns are known. Pure and deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class AttributionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_return: float
    by_alpha: dict[str, float]
    winners: list[str] = Field(default_factory=list)  # positive contributors, best first
    losers: list[str] = Field(default_factory=list)   # negative contributors, worst first
    top_contributor: str | None = None
    top_detractor: str | None = None


def _summarize(total: float, by_alpha: dict[str, float]) -> AttributionResult:
    winners = sorted((a for a, c in by_alpha.items() if c > 0), key=lambda a: by_alpha[a],
                     reverse=True)
    losers = sorted((a for a, c in by_alpha.items() if c < 0), key=lambda a: by_alpha[a])
    return AttributionResult(
        total_return=total, by_alpha=by_alpha, winners=winners, losers=losers,
        top_contributor=winners[0] if winners else None,
        top_detractor=losers[0] if losers else None,
    )


class SignalAttributionEngine:
    """Attributes realized P&L across the alphas that produced a signal."""

    def attribute(
        self, *, alpha_weights: Mapping[str, float], realized_return: float
    ) -> AttributionResult:
        """Split one trade's realized return across alphas by their (normalized) weights."""
        total_w = sum(alpha_weights.values())
        if total_w <= 0:
            by_alpha = dict.fromkeys(alpha_weights, 0.0)
            return _summarize(realized_return, by_alpha)
        by_alpha = {a: (w / total_w) * realized_return for a, w in alpha_weights.items()}
        return _summarize(realized_return, by_alpha)

    def attribute_detailed(
        self,
        *,
        alpha_weights: Mapping[str, float],
        alpha_returns: Mapping[str, float],
    ) -> AttributionResult:
        """Attribute when each alpha's own realized return is known (weight x return)."""
        by_alpha = {
            a: float(w) * float(alpha_returns.get(a, 0.0)) for a, w in alpha_weights.items()
        }
        return _summarize(sum(by_alpha.values()), by_alpha)
