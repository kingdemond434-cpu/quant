"""Allocation-side controls: drawdown-aware sizing, risk budgets, sleeves, leverage, reinvestment.

Capital is allocated by *risk* and at the *sleeve* level first, sized down during drawdowns and
instability, levered dynamically (never statically), and reinvested adaptively. Reuses the existing
drawdown governor; survival and growth always dominate return.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from libs.risk.drawdown import drawdown_governor
from libs.stage14.errors import Stage14Error
from libs.stage14.models import (
    AlphaSleeve,
    LeverageDecision,
    PortfolioState,
    ReinvestmentDecision,
    RiskBudget,
)

_EPS = 1e-12


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class DrawdownAwareAllocator:
    """Scales exposure down in drawdowns; only restores it after recovery is confirmed."""

    def scale(
        self,
        *,
        current_drawdown: float,
        recovered: bool = False,
        regime_stable: bool = True,
        signal_deteriorating: bool = False,
    ) -> float:
        scalar = drawdown_governor(current_drawdown).scalar
        if not regime_stable:
            scalar *= 0.75
        if signal_deteriorating:
            scalar *= 0.5
        # Increase only after recovery confirmation: while still drawn down, cap restoration.
        if current_drawdown > 0.05 and not recovered:
            scalar = min(scalar, 0.5)
        return _clip01(scalar)


class PortfolioRiskBudgetEngine:
    """Allocates risk (not capital): inverse-volatility weights within the vol budget."""

    def inverse_vol_weights(self, vols: Mapping[str, float]) -> dict[str, float]:
        inv = {k: (1.0 / v if v > _EPS else 0.0) for k, v in vols.items()}
        total = sum(inv.values())
        if total <= _EPS:
            return dict.fromkeys(vols, 0.0)
        return {k: w / total for k, w in inv.items()}

    def capital_from_risk(
        self, risk_weights: Mapping[str, float], vols: Mapping[str, float], *, budget: RiskBudget
    ) -> dict[str, float]:
        """Convert risk weights to capital weights targeting the portfolio vol budget."""
        # Crude but robust: scale each name so its risk contribution targets the vol budget.
        out: dict[str, float] = {}
        for k, rw in risk_weights.items():
            vol = vols.get(k, 0.0)
            out[k] = rw * (budget.vol_budget / vol) if vol > _EPS else 0.0
        total = sum(out.values())
        if total > 1.0:  # never allocate more than the available capital
            out = {k: v / total for k, v in out.items()}
        return out


class SleeveAllocator:
    """Budgets capital across alpha sleeves before sizing positions."""

    def __init__(self, *, max_sleeve_weight: float = 0.4) -> None:
        self.max_sleeve_weight = max_sleeve_weight

    def budgets(self, sleeve_scores: Mapping[AlphaSleeve, float]) -> dict[AlphaSleeve, float]:
        positive = {s: max(0.0, v) for s, v in sleeve_scores.items()}
        total = sum(positive.values())
        if total <= _EPS:
            n = len(positive)
            return dict.fromkeys(positive, 1.0 / n if n else 0.0)
        weights = {s: v / total for s, v in positive.items()}
        return self._cap(weights)

    def _cap(self, weights: dict[AlphaSleeve, float]) -> dict[AlphaSleeve, float]:
        w = dict(weights)
        for _ in range(50):
            over = {s: v for s, v in w.items() if v > self.max_sleeve_weight + _EPS}
            if not over:
                break
            excess = sum(v - self.max_sleeve_weight for v in over.values())
            for s in over:
                w[s] = self.max_sleeve_weight
            under = {s: w[s] for s in w if s not in over}
            headroom = sum(max(0.0, self.max_sleeve_weight - v) for v in under.values())
            if headroom <= _EPS:
                break
            for s in under:
                w[s] += excess * max(0.0, self.max_sleeve_weight - w[s]) / headroom
        return w


class DynamicLeverageEngine:
    """Leverage from vol, regime, drawdown, fragility, capacity, survival (never static)."""

    def __init__(self, *, max_leverage: float = 1.0) -> None:
        if max_leverage <= 0:
            raise Stage14Error("max_leverage must be positive")
        self.max_leverage = max_leverage

    def decide(
        self,
        *,
        volatility_state: float = 0.5,
        regime_certainty: float = 1.0,
        drawdown_scalar: float = 1.0,
        fragility: float = 0.0,
        capacity_health: float = 1.0,
        survival_score: float = 100.0,
    ) -> LeverageDecision:
        health = (
            (1.0 - _clip01(volatility_state))
            * _clip01(regime_certainty)
            * _clip01(drawdown_scalar)
            * (1.0 - _clip01(fragility))
            * _clip01(capacity_health)
            * _clip01(survival_score / 100.0)
        )
        leverage = self.max_leverage * health
        return LeverageDecision(
            leverage=max(0.0, min(self.max_leverage, leverage)),
            rationale=f"health={health:.3f} -> leverage scaled from max {self.max_leverage}",
        )


class AdaptiveReinvestmentEngine:
    """Adjusts the reinvestment rate up in stable favorable conditions, down under stress."""

    _STATE_CAP: ClassVar[dict[PortfolioState, float]] = {
        PortfolioState.NORMAL: 1.0,
        PortfolioState.CAUTION: 0.6,
        PortfolioState.DEFENSIVE: 0.3,
        PortfolioState.CRISIS: 0.0,
        PortfolioState.RECOVERY: 0.5,
    }

    def decide(
        self,
        *,
        growth_score: float,
        survival_score: float,
        fragility: float = 0.0,
        regime_uncertainty: float = 0.0,
        state: PortfolioState = PortfolioState.NORMAL,
    ) -> ReinvestmentDecision:
        favorable = _clip01(growth_score / 100.0) * _clip01(survival_score / 100.0)
        dampen = (1.0 - _clip01(fragility)) * (1.0 - _clip01(regime_uncertainty))
        rate = favorable * dampen
        cap = self._STATE_CAP.get(state, 0.5)
        rate = min(rate, cap)
        return ReinvestmentDecision(
            reinvestment_rate=_clip01(rate),
            rationale=f"favorable={favorable:.2f}, dampen={dampen:.2f}, state_cap={cap:.2f}",
        )

    @staticmethod
    def sleeve_of(text: str) -> AlphaSleeve:
        return AlphaSleeve.from_text(text)


def group_by_sleeve(items: Sequence[tuple[str, AlphaSleeve]]) -> dict[AlphaSleeve, list[str]]:
    """Group symbols by their assigned sleeve."""
    grouped: dict[AlphaSleeve, list[str]] = {}
    for symbol, sleeve in items:
        grouped.setdefault(sleeve, []).append(symbol)
    return grouped
