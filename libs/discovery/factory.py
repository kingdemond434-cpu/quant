"""The Alpha Discovery Factory orchestrator.

Generates hypotheses, backtests each, runs the trials-adjusted gauntlet plus every robustness
engine, scores by expected log utility under survival/robustness constraints, and outputs only
the accepted survivors. By design the output on noise is sparse or empty — that is the Skeptic
working correctly, not a failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
import pandas as pd

from libs.backtest.engine import run_signal_backtest
from libs.costs.errors import CostError
from libs.costs.model import estimate_trade_cost
from libs.costs.scenarios import CostScenario
from libs.discovery.acceptance import alpha_acceptance
from libs.discovery.capacity import capacity_estimate
from libs.discovery.fragility import alpha_fragility
from libs.discovery.half_life import alpha_half_life
from libs.discovery.hypotheses import HypothesisGenerator, param_sweep
from libs.discovery.models import (
    AlphaHypothesis,
    DiscoveryCandidate,
    DiscoveryReport,
    HypothesisCategory,
    RobustnessScores,
)
from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth
from libs.discovery.parameter_stability import parameter_stability
from libs.discovery.regime_diversification import regime_diversification
from libs.discovery.signals import build_generator
from libs.discovery.stress_scenario import stress_scenario
from libs.discovery.tail_risk import tail_risk
from libs.research.capacity_policy import (
    capacity_required,
    declared_allocation,
    live_book_usd,
    live_sleeves,
)
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.stress_costs import stress_cost_validation
from libs.validation.walk_forward import walk_forward_splits


class AlphaDiscoveryFactory:
    """Runs the discovery search over a panel of bar frames and returns accepted candidates."""

    def __init__(
        self,
        *,
        periods_per_year: float = 252.0,
        init_cash: float = 100_000.0,
        mc_sims: int = 400,
        adv_usd: float = 1e9,
        min_observations: int = 60,
        seed: int = 0,
        book_usd: float | None = None,
        n_sleeves: int | None = None,
    ) -> None:
        self.ppy = periods_per_year
        self.init_cash = init_cash
        self.mc_sims = mc_sims
        self.adv_usd = adv_usd
        self.min_observations = min_observations
        self.seed = seed
        # §42: the REAL book, which is what capacity must be judged against. Deliberately separate
        # from `init_cash` -- that is a backtest's notional, not the equity that will be deployed,
        # and defaulting capacity checks to a $100k simulation notional is how the flat $100k
        # floor survived a rewrite in the first place.
        self.book_usd = live_book_usd() if book_usd is None else book_usd
        self.n_sleeves = live_sleeves() if n_sleeves is None else n_sleeves

    # ------------------------------------------------------------ public API

    def discover(
        self,
        data: Mapping[str, pd.DataFrame],
        categories: Sequence[HypothesisCategory],
        *,
        symbols: Sequence[str] | None = None,
    ) -> DiscoveryReport:
        """Run the full discovery pipeline and return only accepted survivors."""
        chosen = [s for s in (symbols or list(data)) if s in data]
        hypotheses = HypothesisGenerator().generate(chosen, categories)
        candidates: list[DiscoveryCandidate] = []
        for hypothesis in hypotheses:
            candidates.append(self._evaluate(hypothesis, data[hypothesis.symbol]))

        accepted = sorted(
            (c for c in candidates if c.accepted), key=lambda c: c.score, reverse=True
        )
        ranked = [c.model_copy(update={"rank": i}) for i, c in enumerate(accepted, start=1)]
        return DiscoveryReport(
            n_generated=len(hypotheses),
            n_backtested=len(candidates),
            n_accepted=len(ranked),
            accepted=ranked,
            error_budget_note=(
                "Promotions are rare by design; a sparse or empty result on a given dataset is "
                "the gauntlet rejecting noise, not a malfunction."
            ),
        )

    # --------------------------------------------------------------- helpers

    def _returns(
        self, bars: pd.DataFrame, category: HypothesisCategory, params: Mapping[str, Any]
    ) -> np.ndarray:
        generator = build_generator(category, params)
        targets = generator(bars).tolist()
        result = run_signal_backtest(
            bars, targets, init_cash=self.init_cash, periods_per_year=self.ppy
        )
        returns = result.equity.pct_change(fill_method=None).dropna()
        return cast("np.ndarray", returns.to_numpy(dtype="float64"))

    def _sharpe(self, returns: np.ndarray) -> float:
        return sharpe_ratio(returns) * float(np.sqrt(self.ppy))

    def _oos_pass(self, returns: np.ndarray) -> bool:
        n = len(returns)
        test_size = max(5, n // 8)
        if n < 4 * test_size:
            return False
        try:
            splits = walk_forward_splits(n, n_splits=3, test_size=test_size, anchored=True)
        except Exception:
            return False
        oos = [sharpe_ratio(returns[s.test]) for s in splits if len(s.test) >= 3]
        return bool(oos) and float(np.median(oos)) > 0.0

    def _holdout_pass(self, returns: np.ndarray) -> bool:
        split = int(0.7 * len(returns))
        holdout = returns[split:]
        return len(holdout) >= 5 and sharpe_ratio(holdout) > 0.0

    def _cost(self, symbol: str, bars: pd.DataFrame, trade_pnls: list[float]) -> tuple[bool, float]:
        if not trade_pnls:
            return False, 1.0
        price = float(bars["close"].iloc[-1])
        try:
            base_cost = estimate_trade_cost(symbol, 0.1, price=price).total
        except CostError:
            base_cost = 0.0002 * price * 0.1  # nominal fallback for uncosted instruments
        gross = list(trade_pnls)
        costs = [base_cost] * len(gross)
        result = stress_cost_validation(gross, costs, required_scenario=CostScenario.X3)
        gross_total = sum(gross)
        net_5x = gross_total - 5.0 * sum(costs)
        sensitivity = (
            0.0 if gross_total <= 0
            else min(1.0, max(0.0, (gross_total - net_5x) / abs(gross_total)))
        )
        return result.passed, sensitivity

    def _regime_perf(self, bars: pd.DataFrame, returns: np.ndarray) -> dict[str, float]:
        close = bars["close"].to_numpy(dtype="float64")[1:][-len(returns):]
        if len(close) != len(returns) or len(returns) < 10:
            return {"trend": 0.0, "range": 0.0, "high_vol": 0.0, "low_vol": 0.0}
        sma = pd.Series(close).rolling(20, min_periods=1).mean().to_numpy()
        vol = pd.Series(returns).rolling(20, min_periods=1).std().to_numpy()
        median_vol = float(np.nanmedian(vol))
        trend_mask = close > sma
        high_mask = vol > median_vol

        def _mean(mask: np.ndarray) -> float:
            sel = returns[mask]
            return float(sel.mean()) if len(sel) else 0.0

        return {
            "trend": _mean(trend_mask), "range": _mean(~trend_mask),
            "high_vol": _mean(high_mask), "low_vol": _mean(~high_mask),
        }

    def _rolling_sharpe(self, returns: np.ndarray, window: int = 30) -> np.ndarray:
        series = pd.Series(returns)
        rolling = series.rolling(window).mean() / series.rolling(window).std()
        return cast("np.ndarray", rolling.dropna().to_numpy(dtype="float64"))

    def _reject(self, hypothesis: AlphaHypothesis, reasons: list[str]) -> DiscoveryCandidate:
        zero = RobustnessScores(
            fragility=100.0, parameter_stability=0.0, regime_diversification=0.0,
            stress_resilience=0.0, tail_risk=100.0, survival_probability=0.0,
            worst_case_drawdown=1.0, half_life_days=0.0, capacity_usd=0.0,
        )
        return DiscoveryCandidate(
            hypothesis=hypothesis, expected_cagr=0.0, expected_sharpe=0.0, dsr=0.0, pbo=1.0,
            cost_adjusted_return=0.0, log_utility=0.0, robustness=zero, accepted=False,
            rejection_reasons=reasons,
        )

    def _evaluate(self, hypothesis: AlphaHypothesis, bars: pd.DataFrame) -> DiscoveryCandidate:
        category, base = hypothesis.category, hypothesis.params
        result = run_signal_backtest(
            bars, build_generator(category, base)(bars).tolist(),
            init_cash=self.init_cash, periods_per_year=self.ppy,
        )
        returns = result.equity.pct_change(fill_method=None).dropna().to_numpy(dtype="float64")
        if len(returns) < self.min_observations or returns.std() == 0:
            return self._reject(hypothesis, ["insufficient_data_or_no_edge"])

        # Parameter grid for DSR variance / PBO / parameter stability.
        sweep = param_sweep(category, base)
        grid_sharpes = [sharpe_ratio(returns)]
        columns = [returns]
        for key, values in sweep.items():
            for value in values:
                variant = dict(base)
                variant[key] = value
                r = self._returns(bars, category, variant)
                grid_sharpes.append(sharpe_ratio(r))
                columns.append(r)
        length = min(len(c) for c in columns)
        matrix = np.column_stack([c[-length:] for c in columns])
        var_sharpes = float(np.var(grid_sharpes, ddof=1)) if len(grid_sharpes) >= 2 else 1e-4

        dsr = deflated_sharpe_ratio(
            returns, n_trials=max(2, len(grid_sharpes)),
            variance_of_sharpes=max(var_sharpes, 1e-6),
        )
        if matrix.shape[1] >= 2 and matrix.shape[0] >= 8:
            pbo = probability_backtest_overfitting(matrix, n_splits=8)
            pbo_value, pbo_pass = pbo.pbo, pbo.pbo <= 0.5
        else:
            pbo_value, pbo_pass = 1.0, False

        wf_pass = self._oos_pass(returns)
        holdout_pass = self._holdout_pass(returns)
        cost_pass, cost_sensitivity = self._cost(
            hypothesis.symbol, bars, [t.pnl for t in result.trades]
        )

        stability = parameter_stability(
            lambda p: self._sharpe(self._returns(bars, category, p)), base, sweep
        )
        regime = regime_diversification(self._regime_perf(bars, returns))
        tail = tail_risk(returns)
        survival = monte_carlo_survival(returns, n_sims=self.mc_sims, seed=self.seed)
        stress = stress_scenario(returns)
        half = alpha_half_life(self._rolling_sharpe(returns), period_days=1.0)
        capacity = capacity_estimate(
            adv_usd=self.adv_usd, edge_bps=max(1.0, self._sharpe(returns) * 5.0)
        )
        fragility = alpha_fragility(
            parameter_stability=stability.plateau_score / 100.0,
            regime_robustness=regime.regime_diversification_score / 100.0,
            cost_sensitivity=cost_sensitivity,
            slippage_sensitivity=cost_sensitivity,
            data_sensitivity=min(1.0, survival.worst_case_drawdown),
        )

        log_growth = expected_log_growth(returns, periods_per_year=self.ppy)
        score = discovery_score(
            log_growth=log_growth, survival_probability=survival.survival_probability,
            diversification_contribution=0.0, average_correlation=0.0,
            failure_dependency_score=0.0, half_life_days=half.half_life_days,
            capacity_usd=capacity.capacity_usd, fragility_score=fragility.fragility_score,
            tail_risk_score=tail.tail_risk_score,
            parameter_plateau_score=stability.plateau_score,
            deployed_equity_usd=self.book_usd, n_sleeves=self.n_sleeves,
            sleeve=hypothesis.name,
        )

        acceptance = alpha_acceptance(
            dsr_pass=dsr.passed, pbo_pass=pbo_pass, cpcv_pass=wf_pass, walk_forward_pass=wf_pass,
            holdout_pass=holdout_pass, cost_pass=cost_pass,
            parameter_stability_pass=stability.robust, fragility_pass=fragility.robust,
            # §42: was a flat `>= 1e5`, the SAME categorical exclusion the survival gate had --
            # fixing one and leaving this one meant sub-$100k edges still failed acceptance here.
            capacity_pass=capacity.capacity_usd >= capacity_required(
                _declared if (_declared := declared_allocation(hypothesis.name)) is not None
                else self.book_usd,
                1 if _declared is not None else self.n_sleeves),
            tail_pass=tail.acceptable,
            stress_pass=stress.passed, regime_pass=regime.robust,
        )
        robustness = RobustnessScores(
            fragility=fragility.fragility_score,
            parameter_stability=stability.plateau_score,
            regime_diversification=regime.regime_diversification_score,
            stress_resilience=stress.stress_resilience_score,
            tail_risk=tail.tail_risk_score,
            survival_probability=survival.survival_probability,
            worst_case_drawdown=survival.worst_case_drawdown,
            half_life_days=half.half_life_days,
            capacity_usd=capacity.capacity_usd,
        )
        return DiscoveryCandidate(
            hypothesis=hypothesis,
            expected_cagr=float(result.metrics.cagr),
            expected_sharpe=float(result.metrics.sharpe),
            dsr=dsr.dsr,
            pbo=pbo_value,
            cost_adjusted_return=log_growth,
            log_utility=log_growth,
            robustness=robustness,
            accepted=acceptance.passed,
            rejection_reasons=acceptance.reasons,
            score=score,
        )
