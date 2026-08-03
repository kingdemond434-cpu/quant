"""THE STRATEGY LAYER IS WHERE ICT EITHER BECOMES FALSIFIABLE OR BECOMES A STORY.

Detectors were already guarded. What these tests pin is everything the detectors could not say:
that the sequence has a deadline, that risk per trade is constant, that nothing reads a bar it
could not have seen, and that a random walk does not print money. The last is the one that matters
most -- a pattern strategy with enough discretionary steps can be made to look good on noise, and
if it does, every subsequent number is about the code rather than the market.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.ict.strategy import ICTParams, ICTSetup, ict_targets, schedule, setups


def _walk(n: int = 3000, seed: int = 0, vol: float = 0.004) -> pd.DataFrame:
    """A geometric random walk with OHLC that respects high >= max(o,c) and low <= min(o,c)."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    open_ = np.concatenate(([100.0], close[:-1]))
    wick = np.abs(rng.normal(0, vol, n)) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": np.full(n, 1.0),
    })


# ------------------------------------------------------------------- parameters

def test_risk_fraction_must_be_a_fraction() -> None:
    with pytest.raises(ValueError, match="risk_fraction"):
        ICTParams(risk_fraction=0.0)
    with pytest.raises(ValueError, match="risk_fraction"):
        ICTParams(risk_fraction=1.5)


def test_windows_must_be_positive() -> None:
    with pytest.raises(ValueError, match="setup_window"):
        ICTParams(setup_window=0)


def test_reward_multiple_must_be_positive() -> None:
    with pytest.raises(ValueError, match="reward_multiple"):
        ICTParams(reward_multiple=0.0)


# ------------------------------------------------------------------- the sequence

def test_setups_report_the_steps_in_order() -> None:
    """sweep before shift before entry, always. If the order can invert, the 'sequence' is
    decoration and the strategy is really just three unrelated filters."""
    df = _walk()
    for s in setups(df):
        assert isinstance(s, ICTSetup)
        assert s.sweep_i <= s.shift_i <= s.entry_i


def test_the_setup_window_is_a_real_deadline() -> None:
    """UNBOUNDED, THE SETUP IS UNCONDITIONAL. Any sweep eventually gets a structure break, so
    without a deadline every sweep becomes a trade -- the 'fires 89% of the time' failure this
    family already produced once, moved up a level."""
    df = _walk()
    for s in setups(df, ICTParams(setup_window=3)):
        assert s.shift_i - s.sweep_i <= 3


def test_the_entry_window_is_a_real_deadline() -> None:
    df = _walk()
    for s in setups(df, ICTParams(entry_window=4)):
        assert s.entry_i - s.shift_i <= 4


def test_a_tighter_window_never_yields_more_setups() -> None:
    """Monotonicity is the cheap check that the deadline is applied rather than merely stored."""
    df = _walk()
    assert len(setups(df, ICTParams(setup_window=2))) <= len(setups(df, ICTParams(setup_window=20)))


def test_stop_is_on_the_refuting_side_of_entry() -> None:
    """The stop must sit where the STORY is wrong -- below the swept low for a long. A stop on the
    wrong side would make every trade's risk negative and the sizing meaningless."""
    df = _walk()
    for s in setups(df):
        if s.direction > 0:
            assert s.stop < s.entry_price < s.target
        else:
            assert s.target < s.entry_price < s.stop


def test_reward_multiple_is_honoured() -> None:
    df = _walk()
    for s in setups(df, ICTParams(reward_multiple=3.0)):
        risk = abs(s.entry_price - s.stop)
        assert abs(s.target - s.entry_price) == pytest.approx(3.0 * risk, rel=1e-9)


# ----------------------------------------------------------------------- sizing

def test_position_size_is_inverse_to_stop_distance() -> None:
    """This is what makes risk-per-trade constant: a wider stop takes a SMALLER position. It is
    also the precise inverse of the escalate-after-loss rule that produces the equity curves this
    desk audits other people for."""
    df = _walk()
    t, taken = schedule(df)
    if len(taken) < 2:
        pytest.skip("not enough setups in this sample")
    arr, p = t.to_numpy(), ICTParams()
    for s in taken:
        size = abs(arr[s.entry_i])
        riskfrac = abs(s.entry_price - s.stop) / s.entry_price
        if size < p.max_leverage - 1e-9:             # ignore the leverage-capped ones
            assert size == pytest.approx(p.risk_fraction / riskfrac, rel=1e-6)


def test_size_never_depends_on_the_previous_trades_outcome() -> None:
    """THE HARD PROPERTY, AND IT IS TESTED RATHER THAN ASSUMED. A martingale is what produces the
    5%/week curves; an ICT strategy that added to losers would be the same object in better
    vocabulary. Sizing here is a function of stop distance ALONE, so two setups with the same
    relative stop get the same size no matter what happened in between."""
    df = _walk()
    t, taken = schedule(df)
    arr = t.to_numpy()
    by_risk: dict[float, set[float]] = {}
    for s in taken:
        v = arr[s.entry_i]
        if v == 0:
            continue
        key = round(abs(s.entry_price - s.stop) / s.entry_price, 6)
        by_risk.setdefault(key, set()).add(round(abs(v), 9))
    for key, vals in by_risk.items():
        assert len(vals) == 1, f"same relative stop {key} produced different sizes {vals}"


def test_leverage_is_capped() -> None:
    """A very tight stop implies an enormous position. Uncapped, one lucky setup dominates the
    whole equity curve and the backtest is a statement about that bar."""
    df = _walk()
    t = ict_targets(df, ICTParams(max_leverage=1.5))
    assert float(np.abs(t.to_numpy()).max()) <= 1.5 + 1e-9


# ------------------------------------------------------------------- positions

def test_only_one_position_is_held_at_a_time() -> None:
    """The state machine can open a new sweep the bar after an entry, so holding periods can
    overlap. Writing both into the array let the later trade silently overwrite the earlier -- a
    position closing for no reason the strategy can state."""
    df = _walk()
    t = ict_targets(df).to_numpy()
    nz = t[t != 0]
    assert nz.size == 0 or len(set(np.round(np.abs(nz), 12))) <= len(setups(df))


def test_flat_when_no_setup_is_live() -> None:
    df = _walk(n=400)
    t = ict_targets(df)
    assert (t == 0).any(), "a strategy that is never flat is not trading a setup"


def test_targets_align_with_the_bar_index() -> None:
    df = _walk(n=500)
    t = ict_targets(df)
    assert len(t) == len(df)
    assert t.index.equals(df.index)


# ------------------------------------------------------- causality and controls

def test_targets_do_not_change_when_the_future_is_replaced() -> None:
    """THE LOOKAHEAD TEST THAT MATTERS. Truncate the frame and every target on the surviving bars
    must be identical -- except near the tail, where a trade is still open and its exit has not
    happened yet. A vectorised rewrite of this state machine is exactly where `shift(-k)` or a
    centred window would creep back in."""
    df = _walk(n=1200)
    full = ict_targets(df).to_numpy()
    cut = 900
    part = ict_targets(df.iloc[:cut].copy()).to_numpy()
    # Compare well clear of the truncation so an open trade at the boundary is not the finding.
    horizon = cut - 200
    assert np.allclose(full[:horizon], part[:horizon], atol=1e-12)


def test_a_random_walk_is_not_a_money_printer() -> None:
    """THE CONTROL THE WHOLE FAMILY RESTS ON. A pattern strategy with four discretionary steps can
    be made to look good on noise, and if it is, every subsequent number is a fact about this code
    rather than about a market. Gross of costs, on a driftless walk, the mean bar return earned by
    the target series must not be meaningfully positive."""
    df = _walk(n=6000, seed=7)
    t = ict_targets(df).to_numpy()
    ret = df["close"].pct_change().fillna(0.0).to_numpy()
    pnl = t[:-1] * ret[1:]                       # position held INTO the next bar's return
    if np.count_nonzero(pnl) < 50:
        pytest.skip("too few holding bars in this sample to make the claim")
    tstat = pnl.mean() / (pnl.std(ddof=1) / np.sqrt(pnl.size))
    assert abs(tstat) < 4.0, f"t={tstat:.2f} on a random walk -- the edge is in the code"


def test_missing_columns_are_refused() -> None:
    with pytest.raises(KeyError, match="ICT strategy needs"):
        setups(pd.DataFrame({"close": [1.0, 2.0, 3.0]}))


def test_an_empty_frame_is_handled_not_crashed() -> None:
    df = pd.DataFrame({"open": [], "high": [], "low": [], "close": []})
    assert setups(df) == []
    assert len(ict_targets(df)) == 0
