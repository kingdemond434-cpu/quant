"""Crisis alpha engine — find and prioritize alphas that perform when markets break.

Scores an alpha by its performance across crisis scenarios (crashes, volatility spikes, liquidity
shocks, correlation breakdowns). Crisis alpha carries strategic portfolio value beyond standalone
return: it pays when everything else is failing.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.stage14_5.models import CrisisAlphaResult

_CRISIS_SCENARIOS = ("market_crash", "volatility_spike", "liquidity_shock", "correlation_breakdown")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class CrisisAlphaEngine:
    """Scores crisis alpha from per-scenario performance (positive = pays during crises)."""

    def __init__(self, *, threshold: float = 55.0, return_scale: float = 0.10) -> None:
        self.threshold = threshold
        self.return_scale = return_scale  # return that maps to a full 0..1 scenario score

    def evaluate(self, scenario_returns: Mapping[str, float]) -> CrisisAlphaResult:
        by_scenario = {
            s: _clip01(0.5 + float(scenario_returns.get(s, 0.0)) / (2.0 * self.return_scale))
            for s in _CRISIS_SCENARIOS
        }
        score = 100.0 * float(np.mean(list(by_scenario.values())))
        return CrisisAlphaResult(
            crisis_alpha_score=score, by_scenario=by_scenario,
            is_crisis_alpha=score >= self.threshold,
        )
