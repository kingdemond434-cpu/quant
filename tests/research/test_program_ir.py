"""The program IR's contract: what it refuses, what it cannot see, and what it compiles to.

The three properties worth a test here are the three a reviewer cannot check by reading:

  REFUSAL IS BY NAME. An unknown node, an out-of-range window, a reserved slot name, a transition
  that is not a comparison -- each comes back as a named reason, before any data is touched.

  LOOK-AHEAD IS IMPOSSIBLE, not merely unintended. Every node is evaluated twice: once on the
  whole frame and once on a prefix, and again on a frame whose FUTURE bars were replaced with
  different prices. A past output that moves either way is a leak, whatever the docstring says.

  A PROGRAM IS A FAMILY. `compile_program` produces the desk's own `Signal` objects with the
  side, the ATR-scaled stop and the reward-to-risk the slots asked for -- so a program reaching
  the forward engine is indistinguishable from a registered family.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.research import program_ir as ir


def _bars(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    """Hourly tz-aware OHLC, the shape `families._h1` hands every family."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1800.0 * np.exp(np.cumsum(rng.normal(0.0, 0.001, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0.0, 0.6, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.0, 0.6, n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)


def _breakout(window: ir.Slot | int = 24) -> ir.Node:
    """+1 above the prior window's high, -1 below its low, flat between."""
    return ir.Cond(
        ir.Compare("gt", ir.Series("close"), ir.Rolling("max", ir.Series("high"), window, 1)),
        ir.Const(1.0),
        ir.Cond(ir.Compare("lt", ir.Series("close"),
                           ir.Rolling("min", ir.Series("low"), window, 1)),
                ir.Const(-1.0), ir.Const(0.0)))


def _machine() -> ir.State:
    up = ir.Compare("gt", ir.Series("close"), ir.Rolling("max", ir.Series("high"), 24, 1))
    down = ir.Compare("lt", ir.Series("close"), ir.Rolling("mean", ir.Series("close"), 24))
    return ir.State((ir.StateDef("flat", 0, (ir.Transition("long", up),)),
                     ir.StateDef("long", 1, (ir.Transition("flat", down),))))


# --------------------------------------------------------------------------- refusal
def test_validate_accepts_every_node_shape() -> None:
    tree = ir.Binary("add", _breakout(), ir.Binary("mul", ir.EventClock("month_end", "to"),
                                                  ir.CrossRef("GBPUSD", "close")))
    assert ir.validate(tree) == []
    assert ir.validate(_machine()) == []
    assert ir.validate(ir.Adaptive(ir.Series("range"), 120, 0.9)) == []


def test_validate_refuses_unknown_nodes() -> None:
    """Anything not in the allowlist, however tree-shaped, is refused BY NAME."""
    for alien in ({"node": "exec"}, ["mul", "close", 2], object(), "close", 3):
        errs = ir.validate(alien)
        assert errs and "unknown node" in errs[0]
    with pytest.raises(ir.ProgramError, match="unknown node"):
        ir.from_json({"node": "eval", "code": "1"})
    with pytest.raises(ir.ProgramError, match="must be an object"):
        ir.from_json("close")


def test_validate_refuses_bad_vocabulary() -> None:
    assert any("unknown field" in e for e in ir.validate(ir.Series("vwap")))
    assert any("unknown rolling op" in e
               for e in ir.validate(ir.Rolling("kurtosis", ir.Series("close"), 24)))
    assert any("unknown binary op" in e
               for e in ir.validate(ir.Binary("pow", ir.Series("close"), ir.Const(2.0))))
    assert any("unknown calendar kind" in e for e in ir.validate(ir.EventClock("lunar_new_year")))
    assert any("unknown clock mode" in e
               for e in ir.validate(ir.EventClock("month_end", "around")))


def test_validate_refuses_oversize_and_out_of_range() -> None:
    deep: ir.Node = ir.Series("close")
    for _ in range(ir.MAX_DEPTH + 4):
        deep = ir.Binary("add", deep, ir.Const(1.0))
    errs = ir.validate(deep)
    assert any("deeper than" in e or "larger than" in e for e in errs)
    assert any("outside" in e for e in ir.validate(ir.Rolling("mean", ir.Series("close"),
                                                              ir.MAX_WINDOW + 1)))
    assert any("Rolling.window must be a Slot or an int" in e
               for e in ir.validate(ir.Rolling("mean", ir.Series("close"), 24.5)))  # type: ignore[arg-type]


def test_validate_refuses_reserved_and_inconsistent_slots() -> None:
    assert any("RESERVED" in e for e in ir.validate(ir.Slot("stop_atr", 1.0, 2.0, 1.5)))
    assert any("outside" in e for e in ir.validate(ir.Slot("w", 5.0, 50.0, 500.0)))
    clash = ir.Binary("add", ir.Rolling("mean", ir.Series("close"), ir.Slot("w", 5, 50, 20)),
                      ir.Rolling("mean", ir.Series("close"), ir.Slot("w", 5, 90, 20)))
    assert any("declared twice" in e for e in ir.validate(clash))


def test_validate_refuses_broken_state_machines() -> None:
    lone = ir.State((ir.StateDef("only", 0, ()),))
    assert any("2.." in e for e in ir.validate(lone))
    bad_target = ir.State((
        ir.StateDef("a", 0, (ir.Transition("nowhere",
                                           ir.Compare("gt", ir.Series("close"), ir.Const(1.0))),)),
        ir.StateDef("b", 1, ())))
    assert any("unknown state" in e for e in ir.validate(bad_target))


def test_evaluate_refuses_before_it_computes() -> None:
    with pytest.raises(ir.ProgramError):
        ir.evaluate(ir.Series("vwap"), _bars(200))


# --------------------------------------------------------------------------- no look-ahead
def _nodes_under_test() -> dict[str, ir.Node]:
    spread = ir.Binary("sub", ir.Series("close"), ir.CrossRef("PEER", "close"))
    return {
        "breakout": _breakout(),
        "state": _machine(),
        "adaptive": ir.Compare("gt", ir.Series("range"),
                               ir.Adaptive(ir.Series("range"), 120, 0.85)),
        "clock_to": ir.EventClock("month_end", "to"),
        "clock_since": ir.EventClock("month_end", "since"),
        "cross": ir.Cond(ir.Compare("gt", spread, ir.Const(0.0)), ir.Const(1.0), ir.Const(-1.0)),
        "zscore": ir.Rolling("zscore", ir.Series("close"), 96),
        "rank": ir.Rolling("rank", ir.Series("ret"), 48),
        "atr": ir.Binary("div", ir.Series("range"), ir.Series("atr")),
    }


def _extras(bars: pd.DataFrame) -> ir.Extras:
    cal = [{"kind": "month_end", "window_start_utc": t.isoformat()}
           for t in pd.date_range("2024-01-31", periods=8, freq="ME", tz="UTC")]
    return ir.Extras(cross={"PEER": _bars(len(bars), seed=21)}, calendar=cal, symbol="XAUUSD")


@pytest.mark.parametrize("name", sorted(_nodes_under_test()))
def test_no_lookahead_on_truncation_and_on_rewritten_future(name: str) -> None:
    """Shifting the future never moves the past. The property, not a claim about it."""
    bars = _bars(1200)
    tree = _nodes_under_test()[name]
    extras = _extras(bars)
    cut = 700
    full = ir.evaluate(tree, bars, extras).to_numpy(dtype=float)[:cut]
    prefix = ir.evaluate(tree, bars.iloc[:cut], extras).to_numpy(dtype=float)

    future = bars.copy()
    rng = np.random.default_rng(3)
    for col in ("open", "high", "low", "close"):
        future.iloc[cut:, future.columns.get_loc(col)] *= 1.0 + rng.normal(0.0, 0.05,
                                                                          len(bars) - cut)
    rewritten = ir.evaluate(tree, future, extras).to_numpy(dtype=float)[:cut]

    for other, why in ((prefix, "truncating the frame"), (rewritten, "rewriting future bars")):
        assert np.array_equal(np.isnan(full), np.isnan(other)), f"{why} changed which bars are NaN"
        ok = ~np.isnan(full)
        assert np.allclose(full[ok], other[ok], atol=1e-9), f"{why} changed a past output"


# --------------------------------------------------------------------------- the nodes
def test_state_machine_transitions_on_the_bar_that_fires() -> None:
    """A hand-built ladder: the machine latches on the up-cross and releases on the down-cross."""
    idx = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    close = [10.0, 10.0, 12.0, 12.0, 12.0, 8.0, 8.0, 13.0, 13.0, 8.0]
    bars = pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)
    up = ir.Compare("gt", ir.Series("close"), ir.Const(11.0))
    down = ir.Compare("lt", ir.Series("close"), ir.Const(9.0))
    machine = ir.State((ir.StateDef("flat", 0, (ir.Transition("live", up),)),
                        ir.StateDef("live", 1, (ir.Transition("flat", down),))))
    got = ir.evaluate(machine, bars).tolist()
    assert got == [0, 0, 1, 1, 1, 0, 0, 1, 1, 0]
    # The value at bar i reflects bar i and no later one: it changes ON the crossing bar.
    assert got[2] == 1 and got[1] == 0
    # A negative state value is how a machine says "short"; nothing special-cases it.
    shorting = ir.State((ir.StateDef("flat", 0, (ir.Transition("bear", down),)),
                         ir.StateDef("bear", -1, (ir.Transition("flat", up),))))
    assert min(ir.evaluate(shorting, bars).tolist()) == -1


def test_state_transition_priority_is_declaration_order() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 5.0}, index=idx)
    always = ir.Compare("gt", ir.Series("close"), ir.Const(0.0))
    machine = ir.State((ir.StateDef("a", 0, (ir.Transition("b", always),
                                             ir.Transition("c", always))),
                        ir.StateDef("b", 1, ()), ir.StateDef("c", 2, ())))
    assert set(ir.evaluate(machine, bars).tolist()) == {1.0}


def test_event_clock_counts_to_and_since_a_synthetic_calendar() -> None:
    bars = _bars(240)
    event = bars.index[100]
    cal = [{"kind": "central_bank", "window_start_utc": event.isoformat(),
            "instruments": ["XAUUSD", "EURUSD"]}]
    extras = ir.Extras(calendar=cal, symbol="XAUUSD")
    to = ir.evaluate(ir.EventClock("central_bank", "to"), bars, extras)
    since = ir.evaluate(ir.EventClock("central_bank", "since"), bars, extras)
    assert to.iloc[100] == pytest.approx(0.0)
    assert to.iloc[90] == pytest.approx(10.0)
    assert np.isnan(to.iloc[101])                       # nothing scheduled after it
    assert since.iloc[110] == pytest.approx(10.0)
    assert np.isnan(since.iloc[99])                     # nothing had happened yet
    # AN INSTRUMENT THE EVENT DOES NOT NAME IS NOT AFFECTED BY IT.
    other = ir.evaluate(ir.EventClock("central_bank", "to"), bars,
                        ir.Extras(calendar=cal, symbol="AUS200"))
    assert other.isna().all()
    # An absent calendar is UNMEASURED, never a substituted one.
    assert ir.evaluate(ir.EventClock("central_bank", "to"), bars).isna().all()
    assert ir.load_calendar(Path("no_such_calendar.json")) == []


def test_adaptive_threshold_tracks_the_recent_distribution() -> None:
    bars = _bars(800)
    q_hi = ir.evaluate(ir.Adaptive(ir.Series("range"), 200, 0.9), bars)
    q_lo = ir.evaluate(ir.Adaptive(ir.Series("range"), 200, 0.1), bars)
    both = q_hi.notna() & q_lo.notna()
    assert both.sum() > 500
    assert (q_hi[both] >= q_lo[both]).all()
    # It is a QUANTILE of the trailing window, so roughly a tenth of bars exceed the 0.9 line --
    # a fixed constant could not make that statement on two instruments at once.
    share = float((bars["high"] - bars["low"])[both].gt(q_hi[both]).mean())
    assert 0.02 < share < 0.25
    assert q_hi.iloc[:199].isna().all()                 # trailing, so no value before the window


def test_dynamic_lookback_changes_with_the_slot() -> None:
    bars = _bars(600)
    tree = ir.Rolling("mean", ir.Series("close"), ir.Slot("w", 5, 200, 20))
    short = ir.evaluate(tree, bars, ir.Extras(slots={"w": 5.0}))
    long = ir.evaluate(tree, bars, ir.Extras(slots={"w": 200.0}))
    assert not np.allclose(short.dropna().to_numpy()[-50:], long.dropna().to_numpy()[-50:])
    # A slot cannot be pushed outside its own bounds by the value handed in.
    clamped = ir.evaluate(tree, bars, ir.Extras(slots={"w": 10_000.0}))
    assert np.allclose(clamped.dropna().to_numpy(), long.dropna().to_numpy())


def test_rolling_lag_is_what_makes_a_breakout_expressible() -> None:
    """Without `lag`, `close > max(high, w)` is false on every bar -- a rule that cannot fire."""
    bars = _bars(600)
    degenerate = ir.Compare("gt", ir.Series("close"), ir.Rolling("max", ir.Series("high"), 24))
    honest = ir.Compare("gt", ir.Series("close"), ir.Rolling("max", ir.Series("high"), 24, 1))
    assert float(ir.evaluate(degenerate, bars).sum()) == 0.0
    assert float(ir.evaluate(honest, bars).sum()) > 0.0


def test_cross_reference_is_forward_filled_and_never_substituted() -> None:
    bars = _bars(300)
    peer = _bars(300, seed=31)
    tree = ir.CrossRef("EURUSD", "close")
    got = ir.evaluate(tree, bars, ir.Extras(cross={"EURUSD": peer}))
    assert np.allclose(got.to_numpy(), peer["close"].to_numpy())
    assert ir.evaluate(tree, bars).isna().all()         # a symbol nobody supplied is UNMEASURED


# --------------------------------------------------------------------------- serialisation
def test_json_round_trip_and_stable_fingerprint() -> None:
    tree = ir.Binary("add", _breakout(ir.Slot("w", 5, 200, 24)), _machine())
    back = ir.from_json(ir.to_json(tree))
    assert back == tree
    assert ir.fingerprint(back) == ir.fingerprint(tree)
    # Stable across processes, not just within one: the hash is of canonical JSON, not of id().
    assert ir.fingerprint(tree) == ir.fingerprint(ir.from_json(ir.to_json(back)))
    assert len(ir.fingerprint(tree)) == 16
    # A DIFFERENT PROGRAM IS A DIFFERENT HASH. One changed comparison is a different hypothesis.
    other = _breakout(ir.Slot("w", 5, 200, 25))
    assert ir.fingerprint(other) != ir.fingerprint(tree)


def test_slots_and_describe_are_readable() -> None:
    tree = _breakout(ir.Slot("w", 5, 200, 24))
    assert [s.name for s in ir.slots(tree)] == ["w"]
    assert [s.name for s in ir.exec_slots()] == list(ir.RESERVED)
    text = ir.describe(tree)
    assert "close >" in text and "max(high, w[5..200], lag=1)" in text
    assert "state{" in ir.describe(_machine())
    assert ir.describe(ir.EventClock("month_end", "to")) == "bars_to(month_end)"


# --------------------------------------------------------------------------- compilation
def test_compile_program_emits_desk_signals_with_atr_stops() -> None:
    from mt5desk.engine import Signal
    from mt5desk.families import _atr

    bars = _bars(1500)
    fn = ir.compile_program(_breakout(24), tag="unit")
    sigs = fn(bars, 1, stop_atr=1.5, rr=2.0, ttl_bars=6, atr_n=14)
    assert sigs and all(isinstance(s, Signal) for s in sigs)
    atr = _atr(bars, 14)
    close = bars["close"]
    for s in sigs[:25]:
        assert s.side in (1, -1)
        assert s.ttl_bars == 6 and s.wait_bars == 1 and s.trigger is None
        assert s.tag.startswith("unit:")
        a, px = float(atr.loc[s.time]), float(close.loc[s.time])
        assert s.stop == pytest.approx(px - s.side * 1.5 * a)
        assert s.target == pytest.approx(px + s.side * 1.5 * a * 2.0)
        # Stop below entry for a long, above for a short; reward is rr times the risk.
        assert (s.target - px) * s.side > 0 > (s.stop - px) * s.side
        assert abs(s.target - px) == pytest.approx(2.0 * abs(px - s.stop))


def test_compiled_side_is_the_polarity_the_caller_asked_for() -> None:
    bars = _bars(1500)
    fn = ir.compile_program(_breakout(24))
    forward = fn(bars, 1)
    reversed_ = fn(bars, -1)
    assert forward and len(forward) == len(reversed_)
    for a, b in zip(forward, reversed_, strict=True):
        assert a.time == b.time and a.side == -b.side


def test_compiled_signals_fire_on_edges_not_on_every_bar() -> None:
    """A state that stays long for 300 bars is one trade, not 300 pieces of evidence."""
    bars = _bars(1500)
    series = ir.evaluate(_machine(), bars)
    live = int((series != 0).sum())
    sigs = ir.compile_program(_machine())(bars, 1)
    assert 0 < len(sigs) < live / 3
    assert len({s.time for s in sigs}) == len(sigs)


def test_compile_refuses_an_invalid_tree() -> None:
    with pytest.raises(ir.ProgramError):
        ir.compile_program(ir.Rolling("kurtosis", ir.Series("close"), 24))


# --------------------------------------------------------------------------- logic revision
def test_mutate_logic_keeps_trees_valid_and_changes_them() -> None:
    bars = _bars(400)
    rng = np.random.default_rng(11)
    tree = _breakout(ir.Slot("w", 5, 200, 24))
    changed = 0
    for _ in range(40):
        child = ir.mutate_logic(tree, rng)
        assert ir.validate(child) == [], ir.describe(child)
        ir.evaluate(child, bars)                        # and it still runs on real bars
        changed += int(ir.fingerprint(child) != ir.fingerprint(tree))
        tree = child if ir.fingerprint(child) != ir.fingerprint(tree) else tree
    assert changed > 20, "a mutation operator that never mutates is a no-op with a docstring"


def test_mutate_logic_never_moves_a_slot_value() -> None:
    """Logic revision and numeric tuning are separate halves; this pins the separation."""
    rng = np.random.default_rng(5)
    tree = _breakout(ir.Slot("w", 5, 200, 24))
    for _ in range(30):
        child = ir.mutate_logic(tree, rng)
        for s in ir.slots(child):
            if s.name == "w":
                assert (s.lo, s.hi, s.default) == (5, 200, 24)
