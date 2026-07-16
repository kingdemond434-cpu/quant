"""Expected value engine — EV after all frictions; EV > 0 is mandatory for consideration.

EV = WinRate * AvgWin - LossRate * AvgLoss, adjusted for spread, slippage, commission, market
impact, and execution-failure risk. The win/avg figures are the weighted blend of the
contributing alphas. A signal with EV <= 0 cannot be selected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.signal_engine.models import AlphaSignal, ExpectedValueResult

_EPS = 1e-12


def _weighted(signals: Sequence[AlphaSignal], weights: Mapping[str, float], attr: str) -> float:
    total = sum(weights.get(s.alpha_id, 0.0) for s in signals)
    if total <= _EPS:
        return 0.0
    return sum(weights.get(s.alpha_id, 0.0) * float(getattr(s, attr)) for s in signals) / total


class ExpectedValueEngine:
    """Computes per-trade expected value net of all execution frictions."""

    def estimate(
        self,
        signals: Sequence[AlphaSignal],
        weights: Mapping[str, float],
        *,
        spread_bps: float = 0.0,
        slippage_bps: float = 0.0,
        market_impact_bps: float = 0.0,
        commission_frac: float = 0.0,
        execution_failure_risk: float = 0.0,
    ) -> ExpectedValueResult:
        win_rate = _weighted(signals, weights, "win_rate")
        avg_win = _weighted(signals, weights, "avg_win")
        avg_loss = _weighted(signals, weights, "avg_loss")

        gross_ev = win_rate * avg_win - (1.0 - win_rate) * avg_loss

        base_cost = (spread_bps + slippage_bps + market_impact_bps) / 1e4 + commission_frac
        # Execution-failure risk inflates the effective cost (fail-closed bias).
        total_cost = base_cost * (1.0 + max(0.0, min(1.0, execution_failure_risk)))

        ev = gross_ev - total_cost
        return ExpectedValueResult(
            expected_value=ev,
            gross_ev=gross_ev,
            total_cost=total_cost,
            positive=ev > _EPS,
        )
