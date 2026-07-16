"""stress_scenario_engine — resilience under replayed extreme events.

Overlays historical-style shocks on an alpha's equity and measures the resulting drawdown and
recovery time. Rejects portfolios/alphas that fail the stress-survival requirement.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

# scenario -> peak-to-trough shock magnitude (fraction)
SCENARIOS: dict[str, float] = {
    "global_financial_crisis": 0.50,
    "flash_crash": 0.10,
    "chf_shock": 0.15,
    "covid_crash": 0.34,
    "inflation_shock": 0.12,
    "commodity_shock": 0.20,
    "crypto_collapse": 0.50,
    "volatility_spike": 0.15,
}


class StressScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stress_resilience_score: float  # 0-100, higher = more resilient
    passed: bool
    worst_drawdown: float
    by_scenario: dict[str, float]

    def __bool__(self) -> bool:
        return self.passed


def stress_scenario(
    returns: np.ndarray,
    *,
    exposure: float = 1.0,
    dd_limit: float = 0.35,
) -> StressScenarioResult:
    """Combine the alpha's own drawdown with each scenario shock (scaled by exposure)."""
    arr = np.asarray(returns, dtype="float64")
    equity = np.cumprod(1.0 + arr) if len(arr) else np.array([1.0])
    running = np.maximum.accumulate(equity)
    base_dd = float((1.0 - equity / running).max()) if len(arr) else 0.0

    by_scenario: dict[str, float] = {}
    for name, shock in SCENARIOS.items():
        combined = 1.0 - (1.0 - base_dd) * (1.0 - shock * max(0.0, exposure))
        by_scenario[name] = min(1.0, combined)

    worst = max(by_scenario.values()) if by_scenario else base_dd
    score = max(0.0, 100.0 * (1.0 - worst))
    return StressScenarioResult(
        stress_resilience_score=score,
        passed=worst < dd_limit,
        worst_drawdown=worst,
        by_scenario=by_scenario,
    )
