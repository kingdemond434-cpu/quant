"""The exit operators and the video-derived anchor family.

WHAT THESE PIN, and why each is worth a test rather than a comment:
  - the operator only ever SHORTENS a hold (it is an exit rule, never a licence to hold longer);
  - the conditional exit is CAUSAL -- the bar it exits on is the one after the bar the condition
    was readable on, never the condition bar itself and never earlier;
  - the anchor is strictly trailing, so a fine bar is never gated by an anchor bar that had not
    finished printing (this is the leak this shape of family has, and it leaks flatteringly);
  - the 4x multiple is a SWEPT GRID DIMENSION and not a constant anywhere in the money path;
  - both new families resolve through the one registry the sweep, the gauntlet, the forward clock
    and the gateway share -- an unresolvable family is an inert one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from mt5desk.exit_operators import (
    EXPANSION_MULT_GRID,
    anchor_direction,
    apply_exit_operators,
    exit_reasons,
    vol_expansion_bar,
)
from mt5desk.families import Signal, get_family_func, get_param_grid


def _frame(n: int = 2000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    step = rng.normal(0, 1.0, n).cumsum()
    # A deliberate volatility regime break two-thirds of the way in, so the expansion rule has
    # something real to fire on rather than firing on noise.
    step[int(n * 0.66):] += rng.normal(0, 6.0, n - int(n * 0.66)).cumsum()
    close = 100 + step
    high = close + np.abs(rng.normal(0, 0.5, n))
    low = close - np.abs(rng.normal(0, 0.5, n))
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                         "volume": 1.0}, index=idx)


def test_operator_only_shortens_never_extends():
    d = _frame()
    sigs = [Signal(time=d.index[i], side=1 if i % 2 else -1, stop=0.0, target=0.0,
                   ttl_bars=200, tag="t", trigger=None, wait_bars=1)
            for i in range(50, 1500, 50)]
    out = apply_exit_operators(d, sigs, expansion_mult=1.5)
    assert len(out) == len(sigs)
    for a, b in zip(sigs, out, strict=True):
        assert b.ttl_bars <= a.ttl_bars, "an exit operator may never extend a hold"
        assert b.side == a.side and b.stop == a.stop and b.target == a.target


def test_identity_when_both_operators_are_off():
    d = _frame()
    sigs = [Signal(time=d.index[100], side=1, stop=0.0, target=0.0, ttl_bars=50,
                   tag="t", trigger=None, wait_bars=1)]
    assert apply_exit_operators(d, sigs, expansion_mult=0.0)[0].ttl_bars == 50
    assert apply_exit_operators(d, sigs, expansion_mult=-1.0)[0].ttl_bars == 50


def test_vol_expansion_bar_is_strictly_after_entry_and_finds_the_first_crossing():
    atr = np.array([1.0] * 10 + [5.0] + [1.0] * 5 + [9.0] + [1.0] * 5, dtype=float)
    # Entry at position 0, ATR there is 1.0; 3x is first exceeded at position 10 (5.0), not 16.
    assert vol_expansion_bar(atr, 0, expansion_mult=3.0, horizon=30) == 10
    assert vol_expansion_bar(atr, 0, expansion_mult=6.0, horizon=30) == 16
    # Never returns the entry bar itself, however large that bar's own ATR: entry at 10 has
    # ATR 5.0 and a 0.5x threshold of 2.5, yet the answer is the LATER 9.0 bar, not bar 10.
    assert vol_expansion_bar(atr, 10, expansion_mult=0.5, horizon=30) == 16
    # And when the horizon covers only quiet bars, the rule does not fire at all.
    assert vol_expansion_bar(atr, 10, expansion_mult=0.5, horizon=1) is None
    # Outside the horizon it does not fire at all -- the hold ends on the entry rule's own terms.
    assert vol_expansion_bar(atr, 0, expansion_mult=3.0, horizon=5) is None


def test_truncated_ttl_exits_on_the_bar_after_the_condition():
    """`run_backtest` exits at open[fill_bar + ttl]; the condition is read at close of the bar
    before it. Getting this off by one is how a conditional exit becomes a look-ahead."""
    d = _frame()
    from mt5desk.families import _atr
    atr = _atr(d, 14).to_numpy(dtype=float)
    i0 = 1200
    sig = Signal(time=d.index[i0], side=1, stop=0.0, target=0.0, ttl_bars=400,
                 tag="t", trigger=None, wait_bars=1)
    fill = i0 + 1
    j = vol_expansion_bar(atr, fill, expansion_mult=1.5, horizon=400)
    assert j is not None, "the fixture must produce an expansion for this test to mean anything"
    out = apply_exit_operators(d, [sig], expansion_mult=1.5)[0]
    assert fill + out.ttl_bars == j + 1, "exit must be the OPEN of the bar after the condition bar"


def test_anchor_is_strictly_trailing():
    """The anchor published on bar i must be computable from bars strictly before i."""
    d = _frame(n=1200)
    a = anchor_direction(d, anchor_mult=4, anchor_n=20)
    assert len(a) == len(d)
    cut = 900
    a_trunc = anchor_direction(d.iloc[:cut], anchor_mult=4, anchor_n=20)
    # Recomputing on a truncated frame must give the same answers on the bars both frames share.
    assert np.allclose(a.iloc[:cut].to_numpy(), a_trunc.to_numpy()), (
        "the anchor on bar i changed when later bars were added: it is reading its own future")


def test_anchor_flip_exit_fires_only_against_the_position():
    d = _frame()
    a = anchor_direction(d, anchor_mult=4, anchor_n=20)
    flat = pd.Series(1.0, index=d.index)      # anchor permanently long
    sig_long = Signal(time=d.index[300], side=1, stop=0.0, target=0.0, ttl_bars=200,
                      tag="t", trigger=None, wait_bars=1)
    sig_short = Signal(time=d.index[300], side=-1, stop=0.0, target=0.0, ttl_bars=200,
                       tag="t", trigger=None, wait_bars=1)
    out_l = apply_exit_operators(d, [sig_long], exit_on_anchor_flip=True, anchor=flat)[0]
    out_s = apply_exit_operators(d, [sig_short], exit_on_anchor_flip=True, anchor=flat)[0]
    assert out_l.ttl_bars == 200, "a long is never flipped out by a permanently long anchor"
    assert out_s.ttl_bars < 200, "a short must be flipped out by a permanently long anchor"
    assert a.abs().max() <= 1.0


def test_both_new_families_resolve_through_the_shared_registry():
    for name in ("htf_anchor_trend", "exit_operated"):
        assert get_family_func(name) is not None, f"{name} is unresolvable and therefore inert"


def test_the_four_times_multiple_is_a_swept_dimension_and_never_a_constant():
    """A constant lifted from one person's search over one equity is a borrowed overfit."""
    for name in ("htf_anchor_trend", "exit_operated"):
        grid = get_param_grid(name)
        assert "expansion_mult" in grid, f"{name} must sweep the multiple, not assume it"
        assert len(set(grid["expansion_mult"])) >= 4, "a two-point grid is a constant with a hedge"
        assert 4.0 in grid["expansion_mult"], "the video's value must be IN the grid, unprivileged"
    assert len(EXPANSION_MULT_GRID) >= 5
    assert min(EXPANSION_MULT_GRID) > 1.0, (
        "below 1.0 is volatility COMPRESSION, a different mechanism that must not be mixed in")


def test_htf_anchor_trend_control_arm_and_operated_arm_share_their_entries():
    d = _frame(n=4000)
    fn = get_family_func("htf_anchor_trend")
    base = fn(d, expansion_mult=0.0, exit_on_anchor_flip=False, anchor_n=20)
    op = fn(d, expansion_mult=1.25, exit_on_anchor_flip=False, anchor_n=20)
    assert base, "the fixture must produce signals for this comparison to mean anything"
    assert [s.time for s in base] == [s.time for s in op], (
        "the operator must change exits only; a different entry set makes the two arms "
        "incomparable and the operator's contribution unmeasurable")
    r = exit_reasons(base, op)
    assert r["median_ttl_after"] <= r["median_ttl_before"]


def test_exit_operated_refuses_the_no_op_and_the_unwrappable():
    d = _frame()
    w = get_family_func("exit_operated")
    assert w(d, base_family="trend_ma_cross", expansion_mult=0.0,
             exit_on_anchor_flip=False) == [], "a no-op wrapper is a duplicate cell, not a claim"
    assert w(d, base_family="carry", expansion_mult=2.0) == []
    assert w(d, base_family="", expansion_mult=2.0) == []
    assert w(d, base_family="no_such_family", expansion_mult=2.0) == []


def test_anchor_gate_actually_gates():
    """Part 1 of the mechanism: entries must all agree with the anchor at their own bar."""
    d = _frame(n=4000)
    fn = get_family_func("htf_anchor_trend")
    sigs = fn(d, expansion_mult=0.0, exit_on_anchor_flip=False, anchor_n=20, anchor_mult=4)
    if not sigs:
        pytest.skip("fixture produced no signals")
    a = anchor_direction(d, anchor_mult=4, anchor_n=20)
    for s in sigs:
        assert float(a.loc[s.time]) * s.side > 0, "an entry fired against its own anchor"


def test_proposer_obeys_the_two_lanes_and_mints_no_single_name_equity():
    import research.universe_policy as policy
    from research.htf_anchor_proposer import build_candidates

    rows = build_candidates({"binding": [{"family": "trend_ma_cross", "chart": "H1",
                                          "expansion_mult": 1.5}]},
                            ["EURUSD", "XAUUSD"])
    assert rows
    for r in rows:
        assert r["kind"] == "hypothesis"
        assert isinstance(r["params"], dict) and r["symbols"]
        for sym in r["symbols"]:
            assert policy.may_hypothesise(sym), f"{sym} is not on the hypothesis lane"
        assert "1.87" not in r["title"]
    # The prior travels with the row: the video's number must never reach a certificate unlabelled.
    assert all("MAXIMUM of ~200" in r["mechanism"] for r in rows)
