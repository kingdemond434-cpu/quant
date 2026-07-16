"""Concentration engine — monitor symbol / alpha / family / factor / regime concentration.

Reuses the portfolio layer's Herfindahl concentration on each weight vector and reports the worst
as a 0-100 score (higher = more concentrated). Prevents hidden concentration of any kind.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.portfolio.diversification import concentration as _herfindahl
from libs.stage14_5.models import ConcentrationResult


def _normalized_hhi(weights: Mapping[str, float]) -> float:
    values = np.array([abs(v) for v in weights.values()], dtype="float64")
    total = float(values.sum())
    if total <= 0 or len(values) == 0:
        return 0.0
    return _herfindahl(values / total)  # in [1/n, 1]


class ConcentrationEngine:
    """Scores portfolio concentration across five dimensions."""

    def __init__(self, *, threshold: float = 60.0) -> None:
        self.threshold = threshold

    def evaluate(
        self,
        *,
        symbol_weights: Mapping[str, float],
        alpha_weights: Mapping[str, float],
        family_weights: Mapping[str, float],
        factor_weights: Mapping[str, float],
        regime_weights: Mapping[str, float],
    ) -> ConcentrationResult:
        sym = _normalized_hhi(symbol_weights)
        alpha = _normalized_hhi(alpha_weights)
        family = _normalized_hhi(family_weights)
        factor = _normalized_hhi(factor_weights)
        regime = _normalized_hhi(regime_weights)
        score = 100.0 * max(sym, alpha, family, factor, regime)
        return ConcentrationResult(
            symbol_concentration=sym, alpha_concentration=alpha, family_concentration=family,
            factor_concentration=factor, regime_concentration=regime,
            concentration_score=score, acceptable=score <= self.threshold,
        )
