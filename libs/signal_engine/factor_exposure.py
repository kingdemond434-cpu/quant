"""Factor exposure engine — net style/factor loadings and concentration control.

Aggregates the contributing alphas' factor loadings by their weights, reports the net exposures,
and flags excessive single-factor concentration so the engine does not pile risk into one style.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.signal_engine.models import AlphaSignal, FactorExposureResult

_FACTORS = (
    "momentum", "value", "growth", "quality", "carry", "volatility", "liquidity", "macro",
)


class FactorExposureEngine:
    """Computes net factor exposures and a concentration check."""

    def __init__(self, *, max_concentration: float = 0.40) -> None:
        self.max_concentration = max_concentration

    def assess(
        self,
        signals: Sequence[AlphaSignal],
        weights: Mapping[str, float],
        *,
        loadings: Mapping[str, Mapping[str, float]] | None = None,
    ) -> FactorExposureResult:
        loadings = loadings or {}
        exposures: dict[str, float] = dict.fromkeys(_FACTORS, 0.0)
        for s in signals:
            w = weights.get(s.alpha_id, 0.0)
            alpha_load = loadings.get(s.alpha_id, {})
            for factor, value in alpha_load.items():
                if factor in exposures:
                    exposures[factor] += w * float(value)
        gross = sum(abs(v) for v in exposures.values())
        concentration = (max(abs(v) for v in exposures.values()) / gross) if gross > 0 else 0.0
        nonzero = {k: v for k, v in exposures.items() if v != 0.0}
        return FactorExposureResult(
            exposures=nonzero,
            concentration=concentration,
            acceptable=concentration <= self.max_concentration,
        )
