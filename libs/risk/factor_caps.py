"""Factor exposure caps — the diversification enforcer.

Aggregates risk by factor (so gold + silver count as one precious-metals bet) and rejects any
factor whose total risk exceeds its cap as a fraction of equity. Prevents hidden concentration
through correlated symbols.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from libs.risk.errors import RiskError
from libs.risk.instruments import Factor, get_factor


class FactorBreach(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor: Factor
    exposure: float
    cap: float


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    by_factor: dict[Factor, float]
    breaches: list[FactorBreach]

    def __bool__(self) -> bool:
        return self.ok


def check_factor_exposure(
    exposures: Mapping[str, float],
    *,
    equity: float,
    factor_caps: Mapping[Factor, float],
) -> FactorExposureResult:
    """Aggregate per-symbol risk into factors and compare to caps (fraction of equity)."""
    if equity <= 0:
        raise RiskError("equity must be positive")
    by_factor: dict[Factor, float] = {}
    for symbol, risk_amount in exposures.items():
        factor = get_factor(symbol)
        by_factor[factor] = by_factor.get(factor, 0.0) + abs(float(risk_amount))

    breaches: list[FactorBreach] = []
    for factor, exposure in by_factor.items():
        cap_frac = factor_caps.get(factor)
        if cap_frac is None:
            continue
        cap_amount = cap_frac * equity
        if exposure > cap_amount:
            breaches.append(FactorBreach(factor=factor, exposure=exposure, cap=cap_amount))
    return FactorExposureResult(ok=not breaches, by_factor=by_factor, breaches=breaches)
