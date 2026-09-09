"""A D1 state, an H1 setup and an M5 execution, and the lookahead that makes them hard.

The load-bearing test in this file is `test_the_naive_alignment_leaks_and_this_one_does_not`.
Everything else checks that a chain reports where it vanished; that one checks that the module
is not a lookahead generator, which is the only way a cross-frequency tool is worse than no tool
at all. It plants a "state" that is PURE FUTURE INFORMATION -- today's daily return, known only
at midnight -- and shows the natural implementation scoring it as a perfect edge on bars traded
twenty-one hours earlier, while `align_down` scores it at nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import cross_frequency as cf  # noqa: E402

H1_BARS = 24 * 400


def _h1(seed: int = 0, drift_when: np.ndarray | None = None, drift: float = 0.0):
    """400 days of H1 bars. `drift_when` marks the hours that get an extra drift."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=H1_BARS, freq="h", tz="UTC")
    step = rng.normal(0.0, 0.001, size=H1_BARS)
    if drift_when is not None:
        step = step + drift * drift_when.astype("float64")
    close = 100.0 * np.exp(np.cumsum(step))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)


def _daily(h1: pd.DataFrame) -> pd.DataFrame:
    d = h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    return d.dropna()


# ------------------------------------------------------------------- the clocks are declared
def test_the_three_clocks_are_three_fields_and_must_run_coarse_to_fine():
    """G17's whole finding: a cell had ONE timeframe. A chain declares three, and the ordering
    is checked at construction rather than assumed."""
    spec = cf.CrossFrequencySpec("D1", "H1", "M5", lambda d: d["close"] > 0,
                                 lambda h: h["close"] > 0, name="ok")
    assert spec.clocks == ("D1", "H1", "M5")

    with pytest.raises(ValueError, match="strictly coarser"):
        cf.CrossFrequencySpec("H1", "D1", "M5", lambda d: d["close"] > 0,
                              lambda h: h["close"] > 0)
    with pytest.raises(ValueError, match="coarser than the signal clock"):
        cf.CrossFrequencySpec("D1", "M5", "H1", lambda d: d["close"] > 0,
                              lambda h: h["close"] > 0)
    with pytest.raises(ValueError, match="unknown timeframe"):
        cf.CrossFrequencySpec("D2", "H1", "M5", lambda d: d["close"] > 0,
                              lambda h: h["close"] > 0)


def test_executing_on_the_signal_bar_is_allowed_but_never_coarser():
    cf.CrossFrequencySpec("D1", "H1", "H1", lambda d: d["close"] > 0, lambda h: h["close"] > 0)
    with pytest.raises(ValueError):
        cf.CrossFrequencySpec("D1", "H1", "H4", lambda d: d["close"] > 0, lambda h: h["close"] > 0)


# ------------------------------------------------------------------------ THE LOOKAHEAD RULE
def test_align_down_uses_only_bars_that_had_closed():
    h1 = _h1()
    d1 = _daily(h1)
    # A daily state that is simply the day's index: the value carried onto an H1 bar must be
    # the PREVIOUS day's, because today's daily bar has not closed yet.
    marker = pd.Series(np.arange(len(d1), dtype="float64"), index=d1.index)
    got = cf.align_down(marker, pd.DatetimeIndex(h1.index), bar="D1")
    assert got.iloc[:24].isna().all(), "the first day used a bar that had not closed"
    # 00:00 on day 1 is exactly day 0's close: available, and it is day 0's value.
    assert got.iloc[24] == 0.0
    assert got.iloc[47] == 0.0, "23:00 on day 1 used day 1's own state"
    assert got.iloc[48] == 1.0


def test_the_naive_alignment_leaks_and_this_one_does_not():
    """THE TEST THIS MODULE EXISTS FOR. The state is the day's OWN return -- pure hindsight at
    any hour before midnight. A forward-fill onto the H1 index scores it as a large edge; the
    as-of join on close times scores it at noise, because it never sees it in time."""
    h1 = _h1(seed=3)
    d1 = _daily(h1)
    future = (d1["close"] / d1["open"] - 1.0 > 0).astype("float64")   # today's own outcome

    naive = future.reindex(pd.DatetimeIndex(h1.index), method="ffill")
    honest = cf.align_down(future, pd.DatetimeIndex(h1.index), bar="D1")

    fwd = h1["close"].pct_change().shift(-1).to_numpy()
    ok = np.isfinite(fwd)

    def _edge(state: pd.Series) -> float:
        m = ok & state.notna().to_numpy() & (state.to_numpy() > 0.5)
        n = ok & state.notna().to_numpy() & (state.to_numpy() <= 0.5)
        return float(np.mean(fwd[m]) - np.mean(fwd[n]))

    leaked, clean = _edge(naive), _edge(honest)
    assert leaked > 5 * abs(clean), (
        f"the naive alignment scored {leaked:.2e} and the as-of join {clean:.2e}; the planted "
        f"lookahead is no longer visible, so this test has stopped protecting anything")
    assert abs(clean) < 0.2 * leaked


def test_align_down_returns_nan_before_the_first_close_and_never_fills_it():
    h1 = _h1()
    d1 = _daily(h1)
    got = cf.align_down(pd.Series(1.0, index=d1.index), pd.DatetimeIndex(h1.index), bar="D1")
    assert got.iloc[0] != got.iloc[0], "the first bar was filled from a state nobody had"
    assert got.iloc[24:].notna().all()


def test_align_down_survives_an_empty_side():
    idx = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    assert cf.align_down(pd.Series(dtype="float64"), idx, bar="D1").isna().all()
    assert len(cf.align_down(pd.Series([1.0]), pd.DatetimeIndex([]), bar="D1")) == 0


# ---------------------------------------------------------------- the chain measures the lift
def test_a_state_that_really_gates_the_edge_shows_a_positive_lift():
    """Planted: the signal pays ONLY on days the state holds. The chain must recover that, and
    the comparison is against the same signal on days the state does not hold."""
    rng = np.random.default_rng(11)
    day_of = np.arange(H1_BARS) // 24
    good_day = (rng.random(H1_BARS // 24) < 0.4)
    hour = np.arange(H1_BARS) % 24
    fires = hour == 9
    # THE FIXTURE MUST OBEY THE SAME LOOKAHEAD RULE THE MODULE ENFORCES, and getting this wrong
    # once was instructive: planting the drift on days whose OWN state was good measured nothing
    # (lift +3.5e-5 on a 0.004 drift), because `align_down` correctly gives an hour-9 bar the
    # PREVIOUS day's state -- so the chain was being asked to trade on information it is
    # designed never to have. A state is knowable the day AFTER it forms, so that is the day it
    # can gate.
    paid = fires & np.concatenate([[False], good_day])[day_of]
    # And the drift goes where the trade actually earns it: the hour-9 signal closes at hour 10,
    # so the chain enters on the hour-10 bar and exits on hour 11 -- the return between them is
    # `step[11]`, two indices on from the signal.
    h1 = _h1(seed=5, drift_when=np.roll(paid, 2), drift=0.004)
    d1 = _daily(h1)
    good_by_date = {d.date(): bool(good_day[i]) for i, d in enumerate(d1.index)}

    spec = cf.CrossFrequencySpec(
        "D1", "H1", "H1",
        state=lambda d: pd.Series([good_by_date.get(x.date(), False) for x in d.index],
                                  index=d.index),
        signal=lambda h: pd.Series(h.index.hour == 9, index=h.index),
        name="planted")
    got = cf.evaluate(spec, {"D1": d1, "H1": h1})
    assert got, got.why
    assert got.lift is not None and got.lift > 0.001, got.to_dict()
    assert got.edge_with > got.edge_without


def test_a_state_that_gates_nothing_shows_no_lift_and_says_the_chain_was_wasted():
    """A chain whose coarse clock earns nothing is a one-clock hypothesis wearing three, and it
    paid three clocks of multiplicity to be so."""
    rng = np.random.default_rng(2)
    h1 = _h1(seed=7)
    d1 = _daily(h1)
    coin = {d.date(): bool(rng.random() < 0.5) for d in d1.index}
    spec = cf.CrossFrequencySpec(
        "D1", "H1", "H1",
        state=lambda d: pd.Series([coin[x.date()] for x in d.index], index=d.index),
        signal=lambda h: pd.Series(h.index.hour == 9, index=h.index), name="coin")
    got = cf.evaluate(spec, {"D1": d1, "H1": h1})
    assert got, got.why
    assert abs(got.lift) < 0.002, got.to_dict()


# -------------------------------------------------------------------------- the refusals
def test_a_chain_that_fires_too_rarely_is_refused_and_names_the_floor():
    """Three rungs divide a sample fast, and the shrinkage is invisible in the statistic."""
    h1 = _h1()
    d1 = _daily(h1)
    rare = {d.date(): (i < 3) for i, d in enumerate(d1.index)}
    spec = cf.CrossFrequencySpec(
        "D1", "H1", "H1",
        state=lambda d: pd.Series([rare[x.date()] for x in d.index], index=d.index),
        signal=lambda h: pd.Series(h.index.hour == 9, index=h.index), name="rare")
    got = cf.evaluate(spec, {"D1": d1, "H1": h1})
    assert not got and got.lift is None
    assert "below the floor of 60" in got.why and "is not measured" in got.why
    assert got.triggers < cf.MIN_TRIGGERS


def test_each_rung_reports_its_own_count_so_a_vanished_chain_says_where():
    h1 = _h1()
    d1 = _daily(h1)
    spec = cf.CrossFrequencySpec(
        "D1", "H1", "H1", state=lambda d: pd.Series(True, index=d.index),
        signal=lambda h: pd.Series(h.index.hour == 9, index=h.index), name="counts")
    got = cf.evaluate(spec, {"D1": d1, "H1": h1})
    # POSITIONALLY, not by clock name: a chain may execute on the clock it signals on, and
    # keying a dict by name would silently collapse the two rungs into whichever came last --
    # which is how a report of three rungs becomes a report of two without saying so.
    state_r, signal_r, exec_r = got.rungs
    assert (state_r.clock, signal_r.clock, exec_r.clock) == ("D1", "H1", "H1")
    assert state_r.fired == state_r.bars == len(d1)
    assert signal_r.fired == pytest.approx(len(h1) / 24, rel=0.02)
    assert 0.0 < signal_r.rate < 0.1
    assert signal_r.fired - 2 <= exec_r.bars <= signal_r.fired, (
        "the execution rung counts the signal bars that produced a usable forward return; the "
        "last one or two fall off the end of the series and must be dropped, not filled")


def test_a_rule_that_never_holds_is_refused_at_its_own_rung():
    h1 = _h1()
    d1 = _daily(h1)
    never = cf.CrossFrequencySpec("D1", "H1", "H1", lambda d: pd.Series(False, index=d.index),
                                  lambda h: pd.Series(True, index=h.index), name="dead_state")
    got = cf.evaluate(never, {"D1": d1, "H1": h1})
    assert not got and "state rule never held" in got.why
    dead_sig = cf.CrossFrequencySpec("D1", "H1", "H1", lambda d: pd.Series(True, index=d.index),
                                     lambda h: pd.Series(False, index=h.index), name="dead_sig")
    got = cf.evaluate(dead_sig, {"D1": d1, "H1": h1})
    assert not got and "signal rule never held" in got.why


def test_a_missing_clock_is_refused_by_name():
    h1 = _h1()
    spec = cf.CrossFrequencySpec("D1", "H1", "M5", lambda d: pd.Series(True, index=d.index),
                                 lambda h: pd.Series(True, index=h.index), name="x")
    got = cf.evaluate(spec, {"H1": h1})
    assert not got and "no bars for the D1 clock" in got.why
    got = cf.evaluate(spec, {"D1": _daily(h1), "H1": h1})
    assert not got and "no bars for the M5 clock" in got.why


def test_a_state_that_always_holds_has_nothing_to_be_compared_against():
    h1 = _h1()
    d1 = _daily(h1)
    spec = cf.CrossFrequencySpec("D1", "H1", "H1", lambda d: pd.Series(True, index=d.index),
                                 lambda h: pd.Series(h.index.hour == 9, index=h.index),
                                 name="always")
    got = cf.evaluate(spec, {"D1": d1, "H1": h1})
    assert got.lift is None and "nothing to compare" in got.why
    assert got.edge_with is not None, "the conditional edge is still measured and reported"


def test_the_reading_serialises_with_its_clocks_and_its_rungs():
    h1 = _h1()
    d1 = _daily(h1)
    spec = cf.CrossFrequencySpec("D1", "H1", "H1", lambda d: pd.Series(True, index=d.index),
                                 lambda h: pd.Series(h.index.hour == 9, index=h.index), name="s")
    d = cf.evaluate(spec, {"D1": d1, "H1": h1}).to_dict()
    assert d["clocks"] == ["D1", "H1", "H1"] and d["spec"] == "s"
    assert [r["clock"] for r in d["rungs"]] == ["D1", "H1", "H1"]
    assert d["min_triggers"] == cf.MIN_TRIGGERS
