"""Naive-baseline scorecard (philosophy from microsoft/qlib's benchmark harness).

The gauntlet (DSR, SPA, CPCV) asks "is this edge statistically distinguishable from noise, given the
search?". It does NOT ask the blunter question a qlib-style benchmark harness always asks first:
**does it even beat a trivial baseline?** A strategy can clear DSR and still lose to buy-and-hold or
to equal-weight — in which case it is complexity with no reason to exist. This scores a candidate's
per-period return stream against those trivial nulls so a "significant" result that fails to beat
buy-and-hold is caught before promotion, not after deployment.

Owned, ~1 file: prevents deploying DSR-significant-but-baseline-losing strategies. No dependency.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError


def _sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype="float64")
    if len(r) < 2:
        return 0.0
    sd = float(r.std(ddof=1))
    return float(r.mean() / sd) if sd > 0 else 0.0


class BaselineScorecard(BaseModel):
    """A candidate's edge over each trivial baseline. ``beats_all`` is the promotion pre-gate."""

    model_config = ConfigDict(frozen=True)

    strategy_sharpe: float
    buy_hold_sharpe: float
    equal_weight_sharpe: float
    excess_over_buy_hold: float  # strategy total return minus buy-and-hold total return
    excess_over_equal_weight: float
    beats_all: bool

    def __bool__(self) -> bool:
        return self.beats_all


def _total_return(returns: np.ndarray) -> float:
    return float(np.prod(1.0 + np.asarray(returns, dtype="float64")) - 1.0)


def baseline_scorecard(
    strategy_returns: np.ndarray,
    *,
    buy_hold_returns: np.ndarray,
    universe_returns: np.ndarray | None = None,
) -> BaselineScorecard:
    """Score ``strategy_returns`` against buy-and-hold and (optionally) an equal-weight universe.

    ``buy_hold_returns`` is the per-period return of holding the benchmark instrument (e.g. BTC).
    ``universe_returns`` is a 2-D array (periods x instruments) whose cross-sectional mean forms the
    equal-weight baseline; if omitted, the equal-weight baseline falls back to buy-and-hold. A
    candidate ``beats_all`` only if its Sharpe strictly exceeds every baseline's Sharpe.

    Raises:
        ValidationError: if the strategy and buy-and-hold streams differ in length.
    """
    strat = np.asarray(strategy_returns, dtype="float64")
    bh = np.asarray(buy_hold_returns, dtype="float64")
    if len(strat) != len(bh):
        raise ValidationError("strategy and buy_hold return streams must be the same length")
    if universe_returns is not None:
        ew = np.asarray(universe_returns, dtype="float64").mean(axis=1)
    else:
        ew = bh
    strat_sr, bh_sr, ew_sr = _sharpe(strat), _sharpe(bh), _sharpe(ew)
    return BaselineScorecard(
        strategy_sharpe=strat_sr,
        buy_hold_sharpe=bh_sr,
        equal_weight_sharpe=ew_sr,
        excess_over_buy_hold=_total_return(strat) - _total_return(bh),
        excess_over_equal_weight=_total_return(strat) - _total_return(ew),
        beats_all=strat_sr > bh_sr and strat_sr > ew_sr,
    )
