"""alpha_fragility_engine — sensitivity to parameters, regime, cost, slippage, data.

fragility_score in 0-100 (higher = more fragile). Penalizes narrow parameter peaks,
over-optimization, regime dependence, and cost sensitivity; prefers wide robust plateaus. One of
the strongest protections against curve-fitting.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FragilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fragility_score: float  # 0-100, higher = more fragile
    robust: bool
    components: dict[str, float]

    def __bool__(self) -> bool:
        return self.robust


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def alpha_fragility(
    *,
    parameter_stability: float,
    regime_robustness: float,
    cost_sensitivity: float,
    slippage_sensitivity: float,
    data_sensitivity: float,
    threshold: float = 40.0,
) -> FragilityResult:
    """Aggregate five sensitivities (each in [0, 1]) into a fragility score."""
    components = {
        "parameter": 1.0 - _clip01(parameter_stability),
        "regime": 1.0 - _clip01(regime_robustness),
        "cost": _clip01(cost_sensitivity),
        "slippage": _clip01(slippage_sensitivity),
        "data": _clip01(data_sensitivity),
    }
    fragility = 100.0 * sum(components.values()) / len(components)
    return FragilityResult(
        fragility_score=fragility, robust=fragility <= threshold, components=components
    )
