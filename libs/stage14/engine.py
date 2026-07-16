"""Stage 14 portfolio construction engine — Signal Packages -> capital allocations.

Consumes approved Stage 13.5 ``SignalPackage`` objects and produces ``PortfolioPackage`` allocations
optimized for long-term compounded wealth: portfolio kill criteria first, then state-aware risk
scaling, fractional-Kelly sizing, sleeve budgeting, dynamic leverage, and a fail-closed governance
gate on every allocation. Named ``PortfolioConstructionEngine`` to avoid colliding with the existing
``libs.portfolio.PortfolioEngine`` (the weight-construction substrate); survival dominates return.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.signal_engine.models import SignalPackage
from libs.stage14.allocation import (
    AdaptiveReinvestmentEngine,
    DrawdownAwareAllocator,
    DynamicLeverageEngine,
    SleeveAllocator,
)
from libs.stage14.analytics import (
    PortfolioCorrelationEngine,
    PortfolioSurvivalEngine,
)
from libs.stage14.audit import PortfolioAudit
from libs.stage14.governance import PortfolioKillCriteria, portfolio_governance_gate
from libs.stage14.growth import GeometricGrowthEngine
from libs.stage14.kelly import FractionalKellyEngine, KellyEngine
from libs.stage14.models import (
    AlphaSleeve,
    PortfolioConstructionResult,
    PortfolioPackage,
    PortfolioState,
)
from libs.stage14.score import institutional_portfolio_score
from libs.stage14.state_machine import PortfolioStateMachine


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sleeve_of(signal: SignalPackage) -> AlphaSleeve:
    if not signal.factor_exposures:
        return AlphaSleeve.OTHER
    dominant = max(signal.factor_exposures, key=lambda k: abs(signal.factor_exposures[k]))
    return AlphaSleeve.from_text(dominant)


class PortfolioConstructionEngine:
    """Builds the final portfolio from approved signal packages (recommend-to-Risk-Engine)."""

    def __init__(
        self,
        *,
        max_leverage: float = 1.0,
        max_gross: float = 1.0,
        min_capacity_score: float = 20.0,
        survival_threshold: float = 60.0,
        max_fragility: float = 0.6,
        roi_edge_threshold: float = 65.0,
        roi_confidence_threshold: float = 0.6,
        roi_pf_threshold: float = 1.3,
        roi_capacity_threshold: float = 70.0,
        kill_criteria: PortfolioKillCriteria | None = None,
        audit: PortfolioAudit | None = None,
    ) -> None:
        self.max_leverage = max_leverage
        self.max_gross = max_gross
        self.min_capacity_score = min_capacity_score
        self.survival_threshold = survival_threshold
        self.max_fragility = max_fragility
        # Half-Kelly is earned, not default: only proven, high-ROI, robust, scalable signals
        # qualify (committee Kelly policy). Everything else sizes at the 1/3 base.
        self.roi_edge_threshold = roi_edge_threshold
        self.roi_confidence_threshold = roi_confidence_threshold
        self.roi_pf_threshold = roi_pf_threshold
        self.roi_capacity_threshold = roi_capacity_threshold
        self.kill_criteria = kill_criteria or PortfolioKillCriteria()
        self.audit = audit
        self.state_machine = PortfolioStateMachine()
        self.drawdown_allocator = DrawdownAwareAllocator()
        self.sleeve_allocator = SleeveAllocator()
        self.leverage_engine = DynamicLeverageEngine(max_leverage=max_leverage)
        self.reinvestment_engine = AdaptiveReinvestmentEngine()
        self.kelly = KellyEngine()
        self.fractional_kelly = FractionalKellyEngine()
        self.survival_engine = PortfolioSurvivalEngine()
        self.growth_engine = GeometricGrowthEngine()
        self.correlation_engine = PortfolioCorrelationEngine()

    def _roi_qualified(self, sp: SignalPackage, *, walk_forward_passed: bool) -> bool:
        """Whether a signal has earned the half-Kelly ceiling: proven, high-ROI, robust, scalable.

        Maps the deployable bar to the sizing decision -- only signals that clear ALL of these
        size up toward half-Kelly; the rest stay at the 1/3 base, which maximizes geometric growth
        under edge uncertainty (overbetting a marginal edge is catastrophic, underbetting is not).
        """
        return (
            walk_forward_passed
            and sp.expected_value > 0.0
            and sp.edge_score >= self.roi_edge_threshold
            and sp.confidence >= self.roi_confidence_threshold
            and sp.expected_pf >= self.roi_pf_threshold
            and sp.capacity_score >= self.roi_capacity_threshold
        )

    def construct(
        self,
        signals: Sequence[SignalPackage],
        *,
        capital: float,
        portfolio_returns: np.ndarray | None = None,
        correlation: np.ndarray | None = None,
        current_drawdown: float = 0.0,
        recovered: bool = False,
        regime_uncertainty: float = 0.0,
        volatility_state: float = 0.5,
        portfolio_dsr: float = 1.0,
        walk_forward_passed: bool = True,
    ) -> PortfolioConstructionResult:
        # --- portfolio-level metrics -------------------------------------------------
        if portfolio_returns is not None:
            survival = self.survival_engine.evaluate(portfolio_returns)
            survival_score = survival.survival_score
            growth_score = self.growth_engine.evaluate(portfolio_returns).geometric_growth_score
        else:
            survival_score = 100.0
            calmars = [s.expected_calmar for s in signals] or [0.0]
            growth_score = 100.0 * _clip01(float(np.mean(calmars)) / 3.0)
        if correlation is not None:
            corr = self.correlation_engine.evaluate(correlation)
            diversification_score = 100.0 * (1.0 - corr.avg_pairwise)
            correlation_ok = corr.acceptable
        else:
            diversification_score = 100.0
            correlation_ok = True

        # --- portfolio kill criteria (fail-closed) -----------------------------------
        kill = self.kill_criteria.evaluate(
            portfolio_dsr=portfolio_dsr, survival_score=survival_score,
            drawdown=current_drawdown, walk_forward_passed=walk_forward_passed,
        )
        if kill.halt:
            result = PortfolioConstructionResult(
                packages=[], rejected={s.symbol: "portfolio halt" for s in signals},
                state=PortfolioState.CRISIS, kill=kill, total_allocation=0.0,
            )
            if self.audit is not None:
                self.audit.record_result(result)
            return result

        state = self.state_machine.classify(
            drawdown=current_drawdown, survival_score=survival_score,
            regime_uncertainty=regime_uncertainty, recovering=recovered,
        )
        gross_mult = self.state_machine.risk_multiplier(state) * self.drawdown_allocator.scale(
            current_drawdown=current_drawdown, recovered=recovered,
            regime_stable=regime_uncertainty < 0.5,
        )

        # --- per-signal gate + raw Kelly sizing --------------------------------------
        rejected: dict[str, str] = {}
        raw: dict[str, float] = {}
        sleeves: dict[str, AlphaSleeve] = {}
        kept: dict[str, SignalPackage] = {}
        fragilities: list[float] = []
        for sp in signals:
            fragility = _clip01(sp.crowding_score / 100.0)
            capacity_available = sp.capacity_score >= self.min_capacity_score
            allowed, reason = portfolio_governance_gate(
                signal_approved=True, expected_value=sp.expected_value,
                portfolio_contribution=sp.portfolio_contribution,
                capacity_available=capacity_available, survival_score=survival_score,
                fragility=fragility, correlation_acceptable=correlation_ok,
                walk_forward_passed=walk_forward_passed,
                survival_threshold=self.survival_threshold, max_fragility=self.max_fragility,
            )
            if not allowed:
                rejected[sp.symbol] = reason
                continue
            win_rate = _clip01(0.5 + (sp.edge_score - 50.0) / 200.0)
            kelly_full = self.kelly.estimate(
                win_rate=win_rate, payoff_ratio=max(0.1, sp.expected_pf), confidence=sp.confidence
            ).full
            frac = self.fractional_kelly.fraction_of_kelly(
                volatility_state=volatility_state, regime_uncertainty=regime_uncertainty,
                capacity_deterioration=1.0 - sp.capacity_score / 100.0, fragility=fragility,
                roi_qualified=self._roi_qualified(sp, walk_forward_passed=walk_forward_passed),
            )
            raw[sp.symbol] = kelly_full * frac
            sleeves[sp.symbol] = _sleeve_of(sp)
            kept[sp.symbol] = sp
            fragilities.append(fragility)

        if not kept:
            result = PortfolioConstructionResult(
                packages=[], rejected=rejected, state=state, kill=kill, total_allocation=0.0
            )
            if self.audit is not None:
                self.audit.record_result(result)
            return result

        # --- sleeve budgeting --------------------------------------------------------
        sleeve_scores: dict[AlphaSleeve, float] = {}
        for sym, sleeve in sleeves.items():
            sleeve_scores[sleeve] = sleeve_scores.get(sleeve, 0.0) + raw[sym]
        sleeve_budgets = self.sleeve_allocator.budgets(sleeve_scores)

        leverage = self.leverage_engine.decide(
            volatility_state=volatility_state, regime_certainty=1.0 - regime_uncertainty,
            drawdown_scalar=self.drawdown_allocator.scale(
                current_drawdown=current_drawdown, recovered=recovered
            ),
            fragility=float(np.mean(fragilities)) if fragilities else 0.0,
            capacity_health=float(np.mean([kept[s].capacity_score for s in kept])) / 100.0,
            survival_score=survival_score,
        ).leverage

        weights: dict[str, float] = {}
        for sym, sleeve in sleeves.items():
            sleeve_raw = sleeve_scores[sleeve]
            within = raw[sym] / sleeve_raw if sleeve_raw > 0 else 0.0
            weights[sym] = sleeve_budgets.get(sleeve, 0.0) * within * gross_mult

        gross = sum(weights.values())
        if gross > self.max_gross and gross > 0:
            weights = {k: v * self.max_gross / gross for k, v in weights.items()}

        # --- build packages ----------------------------------------------------------
        packages: list[PortfolioPackage] = []
        for sym, sp in kept.items():
            allocation = weights[sym]
            fragility = _clip01(sp.crowding_score / 100.0)
            score = institutional_portfolio_score(
                survival_score=survival_score, geometric_growth_score=growth_score,
                expected_sharpe=sp.expected_sharpe, expected_calmar=sp.expected_calmar,
                capacity_score=sp.capacity_score, diversification_score=diversification_score,
                execution_score=sp.execution_score, drawdown_risk=_clip01(sp.expected_drawdown),
                fragility=fragility,
            ).score
            packages.append(
                PortfolioPackage(
                    symbol=sym, sleeve=sleeves[sym], allocation=allocation,
                    position_size=allocation * leverage * capital,
                    kelly_fraction=raw[sym], leverage=leverage,
                    expected_return=sp.expected_return, expected_sharpe=sp.expected_sharpe,
                    expected_sortino=sp.expected_sortino, expected_calmar=sp.expected_calmar,
                    expected_drawdown=sp.expected_drawdown, geometric_growth_score=growth_score,
                    survival_score=survival_score, capacity_score=sp.capacity_score,
                    diversification_score=diversification_score, fragility_score=fragility,
                    portfolio_contribution=sp.portfolio_contribution, institutional_score=score,
                )
            )

        result = PortfolioConstructionResult(
            packages=packages, rejected=rejected, state=state, kill=kill,
            total_allocation=sum(p.allocation for p in packages),
        )
        if self.audit is not None:
            self.audit.record_result(result)
        return result
