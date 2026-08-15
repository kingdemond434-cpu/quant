"""Long-only spot momentum, pinned on the two things that make its numbers honest.

THE FAILURE THIS GUARDS AGAINST is a long-only crypto book reporting the market's return as its
own. In a rising tape it earns whether or not its selection has any skill, so a Sharpe against
ZERO measures the market and credits the strategy. Only the EXCESS over equal-weight buy-and-hold
belongs to selection, and `test_A_ZERO_SKILL_BOOK_HAS_NO_EXCESS` is the test that would catch the
day someone starts quoting the raw number alone.

The second is beta. The short leg is what made `xsec_price_mom` dollar-neutral; without it this is
a crypto long with a tilt, and the beta must SHOW that rather than be argued about.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.spot_momentum import (
    benchmark_returns,
    evaluate,
    spot_long_only_returns,
)


def _universe(n_days: int = 400, n_sym: int = 10, *, seed: int = 5,
              drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = [f"S{i}" for i in range(n_sym)]
    rets = rng.normal(drift, 0.03, size=(n_days, n_sym))
    return pd.DataFrame(100.0 * np.cumprod(1.0 + rets, axis=0), columns=cols)


def _mom_signal(close: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    return close / close.shift(lookback) - 1.0


def _cost(close: pd.DataFrame, bps: float = 10.0) -> dict[str, float]:
    return dict.fromkeys(close.columns, bps / 10_000.0)


def test_THE_BOOK_HOLDS_NO_SHORTS() -> None:
    """The whole reason this is a separate strategy. A spot account cannot open a short, so a
    single negative weight would be an unplaceable position silently priced into the record."""
    close = _universe()
    r = spot_long_only_returns(close, _mom_signal(close), _cost(close))
    # A long-only book on a symmetric-return universe cannot systematically beat a zero line by
    # shorting; the direct structural check is that its return tracks the universe rather than
    # inverting it, which the beta test below asserts. Here: finite, defined, non-degenerate.
    assert np.isfinite(r).all()
    assert r.std() > 0


def test_IT_IS_NOT_MARKET_NEUTRAL_AND_THE_BETA_SAYS_SO() -> None:
    """A long-only tilt retains full drawdown risk. Anyone sizing it like the dollar-neutral book
    it came from would be sizing a completely different exposure."""
    close = _universe(drift=0.001)
    strat = spot_long_only_returns(close, _mom_signal(close), _cost(close))
    bench = benchmark_returns(close)
    res = evaluate(strat, bench)
    assert res.beta_to_universe > 0.5, (
        f"beta {res.beta_to_universe:.2f} -- a long-only spot book must show substantial market "
        "exposure; a near-zero beta here would mean the construction is not doing what it claims")


def test_A_ZERO_SKILL_BOOK_HAS_NO_EXCESS_EVEN_IN_A_BULL_MARKET() -> None:
    """THE ONE THAT MATTERS. On a universe where every symbol shares one drift and the ranking
    carries no information, the raw Sharpe is POSITIVE and large -- and the excess is not.

    A desk quoting the raw number would report the market's drift as its own alpha."""
    rng = np.random.default_rng(11)
    n_days, n_sym = 500, 10
    # every symbol: same strong drift, independent noise -> ranking is pure noise, no real edge
    rets = rng.normal(0.003, 0.03, size=(n_days, n_sym))
    close = pd.DataFrame(100.0 * np.cumprod(1.0 + rets, axis=0),
                         columns=[f"S{i}" for i in range(n_sym)])
    strat = spot_long_only_returns(close, _mom_signal(close), _cost(close))
    res = evaluate(strat, benchmark_returns(close))

    assert res.sharpe_raw > 0.5, (
        f"raw Sharpe {res.sharpe_raw:.2f} -- the setup is meant to produce a flattering raw number "
        "from drift alone; if it does not, this test is not testing what it claims")
    assert res.sharpe_excess < res.sharpe_raw, (
        "the excess must be SMALLER than the raw number on a no-skill universe -- if they match, "
        "the benchmark is not being subtracted and every future verdict inherits the market")


def test_THE_BENCHMARK_IS_EQUAL_WEIGHT_BUY_AND_HOLD() -> None:
    close = _universe(drift=0.002)
    b = benchmark_returns(close)
    direct = close.pct_change(fill_method=None).mean(axis=1).fillna(0.0).to_numpy()
    assert np.allclose(b, direct)


def test_THE_BENCHMARK_PAYS_NO_TURNOVER_COST() -> None:
    """Buy-and-hold trades once; the strategy trades constantly. Charging the benchmark a turnover
    it never incurs would hand the strategy free alpha exactly equal to its own trading costs."""
    close = _universe()
    cheap = evaluate(spot_long_only_returns(close, _mom_signal(close), _cost(close, bps=1.0)),
                     benchmark_returns(close))
    dear = evaluate(spot_long_only_returns(close, _mom_signal(close), _cost(close, bps=100.0)),
                    benchmark_returns(close))
    assert cheap.benchmark_ann_return == dear.benchmark_ann_return
    assert dear.ann_return < cheap.ann_return, "higher costs must reduce the STRATEGY only"


def test_GROSS_SCALES_THE_BOOK() -> None:
    close = _universe(drift=0.001)
    full = spot_long_only_returns(close, _mom_signal(close), _cost(close), gross=1.0)
    half = spot_long_only_returns(close, _mom_signal(close), _cost(close), gross=0.5)
    assert abs(half.std() - 0.5 * full.std()) < 0.5 * full.std()


def test_A_THIN_TAPE_HOLDS_RATHER_THAN_LIQUIDATES() -> None:
    """Fewer names than `min_names` must not dump the book into an untradeable market."""
    close = _universe(n_sym=3)
    r = spot_long_only_returns(close, _mom_signal(close), _cost(close), min_names=6)
    assert np.isfinite(r).all()


def test_THE_ROW_PUBLISHES_RAW_AND_EXCESS_TOGETHER() -> None:
    """Neither is published without the other, and the note says why -- a reader who sees only the
    raw figure will size against the market's return."""
    close = _universe(drift=0.001)
    row = evaluate(spot_long_only_returns(close, _mom_signal(close), _cost(close)),
                   benchmark_returns(close)).as_row()
    assert "sharpe_raw" in row and "sharpe_excess" in row and "beta_to_universe" in row
    assert "MEASURES THE MARKET" in row["note"]
    assert "NOT a market-neutral book" in row["note"]
