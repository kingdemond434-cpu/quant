"""Edge estimator — estimate expected edge *before* capital is deployed.

Blends the contributing alphas' historical expectations (weighted by their dynamic weights) with
the live market context: regime fit, cross-asset and microstructure confirmation, and the
spread/volatility/liquidity frictions that erode realized edge. ``edge_score`` is 0-100.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.signal_engine.models import AlphaSignal, EdgeEstimate, MarketState

_EPS = 1e-12


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _weighted(signals: Sequence[AlphaSignal], weights: Mapping[str, float], attr: str) -> float:
    total = sum(weights.get(s.alpha_id, 0.0) for s in signals)
    if total <= _EPS:
        return 0.0
    return sum(weights.get(s.alpha_id, 0.0) * float(getattr(s, attr)) for s in signals) / total


class EdgeEstimator:
    """Estimates expected return/PF/Sharpe/Sortino/Calmar and a 0-100 edge score."""

    def estimate(
        self,
        signals: Sequence[AlphaSignal],
        weights: Mapping[str, float],
        state: MarketState,
    ) -> EdgeEstimate:
        exp_ret = _weighted(signals, weights, "expected_return")
        sharpe = _weighted(signals, weights, "sharpe")
        win_rate = _weighted(signals, weights, "win_rate")

        # Profit factor: use stated PF where present, else proxy from win rate.
        pf_total = sum(weights.get(s.alpha_id, 0.0) for s in signals if s.profit_factor is not None)
        if pf_total > _EPS:
            pf = (
                sum(
                    weights.get(s.alpha_id, 0.0) * float(s.profit_factor)
                    for s in signals
                    if s.profit_factor is not None
                )
                / pf_total
            )
        else:
            pf = 1.0 + max(0.0, sharpe) * 0.5

        # Frictions reduce realized edge; confirmations raise confidence in it.
        spread_pen = _clip01(state.spread_bps / 20.0)
        clean = _clip01(1.0 - 0.3 * spread_pen - 0.3 * state.volatility_state)
        friction = clean * state.liquidity_score
        confirm = 0.5 + 0.5 * (state.cross_asset_score * state.microstructure_score)

        # Downside-aware proxies derived from the expectation set (documented, not validated).
        sortino = sharpe * (1.0 + max(0.0, win_rate - 0.5))
        calmar = max(0.0, sharpe) * friction

        quality = _clip01(max(0.0, sharpe) / 2.0)  # Sharpe 2.0 -> full quality
        edge_score = 100.0 * _clip01(quality * confirm * friction)

        return EdgeEstimate(
            expected_return=exp_ret * friction,
            expected_pf=pf,
            expected_sharpe=sharpe,
            expected_sortino=sortino,
            expected_calmar=calmar,
            edge_score=edge_score,
        )
