"""Regime exposure engine — maintain alpha-family exposure across all regimes.

Measures how evenly portfolio exposure is spread across regimes (trending / range / high-vol /
low-vol / crisis) and flags uncovered regimes. A balanced book survives regime transitions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.stage14_5.models import RegimeExposureResult

_DEFAULT_REGIMES = ("trending", "range", "high_vol", "low_vol", "crisis")


def _gini_evenness(values: list[float]) -> float:
    """1 = perfectly even, 0 = fully concentrated."""
    arr = np.array([max(0.0, v) for v in values], dtype="float64")
    total = float(arr.sum())
    n = len(arr)
    if total <= 0 or n < 2:
        return 0.0
    shares = arr / total
    return float(1.0 - np.sum(shares**2) * n / (n - 1) + 1.0 / (n - 1))


class RegimeExposureEngine:
    """Scores regime balance and identifies uncovered regimes."""

    def __init__(
        self, *, required_regimes: Sequence[str] = _DEFAULT_REGIMES, min_exposure: float = 0.05,
        threshold: float = 50.0,
    ) -> None:
        self.required_regimes = list(required_regimes)
        self.min_exposure = min_exposure
        self.threshold = threshold

    def evaluate(self, regime_weights: Mapping[str, float]) -> RegimeExposureResult:
        by_regime = {r: float(regime_weights.get(r, 0.0)) for r in self.required_regimes}
        total = sum(by_regime.values())
        shares = {r: (v / total if total > 0 else 0.0) for r, v in by_regime.items()}
        evenness = _gini_evenness(list(by_regime.values()))
        score = 100.0 * max(0.0, min(1.0, evenness))
        uncovered = [r for r, s in shares.items() if s < self.min_exposure]
        return RegimeExposureResult(
            by_regime=shares, regime_balance_score=score, uncovered_regimes=uncovered,
            balanced=not uncovered and score >= self.threshold,
        )
