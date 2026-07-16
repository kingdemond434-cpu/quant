"""Kelly sizing for compounding — full estimate, never full deployment.

``KellyEngine`` computes the Bernoulli Kelly fraction from win rate and payoff (with a confidence
haircut) and exposes half/quarter. ``FractionalKellyEngine`` converts that into a *survivable*
fraction of capital: third-Kelly (1/3) is the base/standard, scaled toward zero under high
volatility, regime uncertainty, capacity deterioration, or fragility, and allowed up to half-Kelly
(1/2) ONLY when the candidate is roi_qualified (good ROI meeting the deployable bar). Full Kelly is
never used.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.stage14.errors import Stage14Error


class KellyEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    full: float
    half: float
    quarter: float


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class KellyEngine:
    """Bernoulli Kelly with a confidence haircut. Full Kelly is reported, never deployed."""

    def estimate(
        self, *, win_rate: float, payoff_ratio: float, confidence: float = 1.0
    ) -> KellyEstimate:
        if payoff_ratio <= 0:
            raise Stage14Error("payoff_ratio must be positive")
        p = _clip01(win_rate)
        # f* = p - (1 - p) / b  (Kelly for a binary payoff with reward/risk ratio b)
        full = max(0.0, p - (1.0 - p) / payoff_ratio) * _clip01(confidence)
        return KellyEstimate(full=full, half=full * 0.5, quarter=full * 0.25)


class FractionalKellyEngine:
    """Turns full-Kelly into a survivable capital fraction (third-Kelly base, half-Kelly cap)."""

    def __init__(self, *, base_fraction: float = 1 / 3, max_fraction: float = 0.5) -> None:
        if not 0.0 < base_fraction <= max_fraction <= 1.0:
            raise Stage14Error("require 0 < base_fraction <= max_fraction <= 1")
        self.base_fraction = base_fraction
        self.max_fraction = max_fraction

    def fraction_of_kelly(
        self,
        *,
        volatility_state: float = 0.5,
        regime_uncertainty: float = 0.5,
        capacity_deterioration: float = 0.0,
        fragility: float = 0.0,
        roi_qualified: bool = False,
    ) -> float:
        """The fraction of full Kelly to deploy.

        The ceiling is the base fraction (1/3) normally, and rises to the max (1/2) only when
        ``roi_qualified`` (good ROI meeting the deployable bar). Within that ceiling, health
        (low vol / regime certainty / capacity / robustness) scales it; best conditions reach the
        ceiling, deteriorating ones fall toward zero. Half-Kelly is never exceeded.
        """
        health = (
            (1.0 - _clip01(volatility_state))
            * (1.0 - _clip01(regime_uncertainty))
            * (1.0 - _clip01(capacity_deterioration))
            * (1.0 - _clip01(fragility))
        )
        ceiling = self.max_fraction if roi_qualified else self.base_fraction
        return max(0.0, min(self.max_fraction, ceiling * health))

    def size(
        self,
        full_kelly: float,
        *,
        volatility_state: float = 0.5,
        regime_uncertainty: float = 0.5,
        capacity_deterioration: float = 0.0,
        fragility: float = 0.0,
        roi_qualified: bool = False,
    ) -> float:
        """Capital fraction = full Kelly x fraction-of-Kelly (always <= half Kelly)."""
        frac = self.fraction_of_kelly(
            volatility_state=volatility_state, regime_uncertainty=regime_uncertainty,
            capacity_deterioration=capacity_deterioration, fragility=fragility,
            roi_qualified=roi_qualified,
        )
        return max(0.0, full_kelly * frac)
