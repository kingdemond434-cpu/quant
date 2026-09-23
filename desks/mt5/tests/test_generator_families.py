"""Two mechanism classes the zoo could not try until 2026-09-08: the opening range and the jump.

The Tier-1 audit measured 76 registered = 76 executable families, FIVE that have ever produced a
certificate, and fifteen blueprint mechanism classes with no registered family -- so those
classes could not be TRIED at any bar. `opening_range` and `jump` need nothing but bars. What is
pinned here is the contract every family in the registry has to meet: registered, executable
through the gateway's own resolver, callable blind by the sweep, free of look-ahead under the
same metamorphic invariant `test_no_lookahead` runs over every price-only family, and doing the
thing its name says on a planted signal.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_no_lookahead as nl  # noqa: E402
from mt5desk import executables  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

NEW = ("opening_range", "jump")


def _hourly(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.2, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.15, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.15, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": 100.0, "spread": 10.0}, index=idx)


# ------------------------------------------------------------------ registered and executable
@pytest.mark.parametrize("name", NEW)
def test_the_family_is_registered_and_price_only(name: str) -> None:
    assert name in fo.ORTHOGONAL_FAMILIES
    assert fo.FAMILY_INPUTS[name][0] == "price only", (
        "'price only' is the sentinel the sweep's wiring test reads; prose here would declare a "
        "non-price input the sweep never passes")


@pytest.mark.parametrize("name", NEW)
def test_the_gateway_resolves_and_can_execute_it(name: str) -> None:
    fn = executables.resolve_family(name)
    assert fn is fo.ORTHOGONAL_FAMILIES[name]
    assert executables.population_of(name) == "orthogonal"
    for tf in ("M5", "H1"):
        assert executables.executor_gap(name, tf) is None, tf
        assert executables.gateway_can_execute(name, tf)


@pytest.mark.parametrize("name", NEW)
def test_the_sweep_can_call_it_blind(name: str) -> None:
    """No required keyword-only evidence: the sweep enumerates it from bars alone."""
    import orthogonal_sweep as osw

    assert osw._unsuppliable(fo.ORTHOGONAL_FAMILIES[name], {}) is None
    assert name not in osw.NOT_SOURCED_HERE


def test_both_are_inside_the_no_lookahead_sweep() -> None:
    """`test_no_lookahead` widened to the orthogonal registry the day these were added; a new
    price-only family is covered the moment it is registered, with no exception list."""
    ids = {n for n, _ in nl.FAMILIES}
    for name in NEW:
        assert f"orthogonal:{name}" in ids, ids


# ------------------------------------------------------------------ the invariant itself
@pytest.mark.parametrize("name", NEW)
def test_signals_do_not_change_when_the_future_changes(name: str) -> None:
    fn = fo.ORTHOGONAL_FAMILIES[name]
    clean = nl._synthetic()
    dirty = nl._corrupt_future(clean, nl.SPLIT)
    cutoff = clean.index[nl.SPLIT - 1]
    a = [s for s in fn(clean) if pd.Timestamp(s.time) <= cutoff]
    b = [s for s in fn(dirty) if pd.Timestamp(s.time) <= cutoff]
    assert a, f"{name} emitted nothing on the synthetic walk: the invariant would be vacuous"
    assert nl._key(a) == nl._key(b)


# ------------------------------------------------------------------ opening range
def test_opening_range_takes_one_trade_per_day_after_the_range_forms() -> None:
    d = _hourly()
    sigs = fo.family_opening_range(d, open_hour=10, range_bars=1, window_bars=6)
    assert sigs, "a random walk breaks its first-hour range on most days"
    days = [pd.Timestamp(s.time).date() for s in sigs]
    assert len(days) == len(set(days)), "more than one opening-range trade on one day"
    for s in sigs:
        ts = pd.Timestamp(s.time)
        assert 11 <= ts.hour <= 16, f"signal at {ts} is not inside the post-range window"
        # The stop is the range's OTHER edge and the target is rr ranges beyond the broken one:
        # for a long the stop sits below the entry bar's close and the target above.
        px = float(d.loc[ts, "close"])
        assert (s.stop < px < s.target) if s.side == 1 else (s.target < px < s.stop)
        assert s.trigger is None and s.wait_bars == 1


def test_opening_range_reads_only_bars_up_to_the_signal_bar() -> None:
    """Corrupt every bar AFTER a known signal bar: that signal must be byte-identical."""
    d = _hourly()
    base = fo.family_opening_range(d)
    assert len(base) > 20
    s = base[10]
    pos = d.index.get_loc(pd.Timestamp(s.time))
    dirty = d.copy()
    dirty.iloc[pos + 1:, :4] = dirty.iloc[pos + 1:, :4].to_numpy() * 1.5
    again = [x for x in fo.family_opening_range(dirty) if pd.Timestamp(x.time) <= s.time]
    assert nl._key(again) == nl._key([x for x in base if pd.Timestamp(x.time) <= s.time])


def test_opening_range_is_declared_off_the_charts_that_carry_no_stamp_hour() -> None:
    assert fo.timeframe_refusal("opening_range", "H4")
    assert fo.timeframe_refusal("opening_range", "D1")
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        assert fo.timeframe_refusal("opening_range", tf) is None, tf


def test_opening_range_runs_on_a_fine_chart_on_its_own_clock() -> None:
    """One M5 bar is the five-minute opening range: bar-relative by design (Question 1)."""
    rng = np.random.default_rng(3)
    n = 12 * 24 * 30
    close = 100.0 + np.cumsum(rng.normal(0, 0.05, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    idx = pd.date_range("2024-03-01", periods=n, freq="5min", tz="UTC")
    d = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.02,
                      "low": np.minimum(open_, close) - 0.02, "close": close}, index=idx)
    sigs = fo.family_opening_range(d, open_hour=10, range_bars=3, window_bars=12)
    assert sigs
    for s in sigs:
        ts = pd.Timestamp(s.time)
        assert ts.hour == 10 and ts.minute >= 15, ts


# ------------------------------------------------------------------ jump
def _with_jump(seed: int = 11, at: int = 1500, size: float = 0.04) -> tuple[pd.DataFrame, int]:
    rng = np.random.default_rng(seed)
    n = 3000
    r = rng.normal(0, 0.001, n)
    r[at] = size                                       # forty sigma, one bar
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]])
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    d = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                      "low": np.minimum(open_, close) * 0.9995, "close": close}, index=idx)
    return d, at


def test_jump_fires_on_the_planted_discontinuity_and_nowhere_near_it() -> None:
    d, at = _with_jump()
    sigs = fo.family_jump(d, jump_k=6.0, cooldown_bars=1)
    hit = [s for s in sigs if d.index.get_loc(pd.Timestamp(s.time)) == at]
    assert len(hit) == 1, [pd.Timestamp(s.time) for s in sigs]
    assert hit[0].side == 1 and hit[0].tag == "jump:continue"
    # Gaussian noise at six sigma: essentially nothing else should trigger.
    assert len(sigs) <= 3, len(sigs)


def test_jump_revert_takes_the_other_side_of_the_same_bar() -> None:
    d, at = _with_jump(size=-0.04)
    cont = [s for s in fo.family_jump(d, mode="continue", jump_k=6.0)
            if d.index.get_loc(pd.Timestamp(s.time)) == at]
    rev = [s for s in fo.family_jump(d, mode="revert", jump_k=6.0)
           if d.index.get_loc(pd.Timestamp(s.time)) == at]
    assert cont and rev
    assert cont[0].side == -1 and rev[0].side == 1


def test_jump_variance_excludes_the_bar_it_tests() -> None:
    """A bipower estimate that included bar i's own return would shrink the statistic on the
    very bar it is meant to flag. Two jumps twelve bars apart must BOTH be flagged: the first
    sits inside the second's window and bipower is what keeps it from masking the second."""
    d, at = _with_jump()
    r = np.log(d["close"]).diff().to_numpy(dtype="float64", copy=True)
    r[at + 12] = 0.04
    close = 100.0 * np.exp(np.nancumsum(r))
    d2 = d.copy()
    d2["close"] = close
    d2["open"] = np.concatenate([[100.0], close[:-1]])
    d2["high"] = np.maximum(d2["open"], d2["close"]) * 1.0005
    d2["low"] = np.minimum(d2["open"], d2["close"]) * 0.9995
    hits = {d2.index.get_loc(pd.Timestamp(s.time))
            for s in fo.family_jump(d2, jump_k=6.0, cooldown_bars=1)}
    assert {at, at + 12} <= hits, hits


def test_jump_refuses_an_unknown_mode_and_a_degenerate_window() -> None:
    d, _ = _with_jump()
    assert fo.family_jump(d, mode="sideways") == []
    assert fo.family_jump(d, lookback=2) == []


def test_jump_runs_on_every_chart() -> None:
    """A jump is a single bar against its own bars' diffusion; it needs no stamp-hour."""
    assert "jump" not in fo.FAMILY_TIMEFRAMES
    assert fo.timeframe_domain("jump") == ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def test_the_two_families_carry_their_defaults_as_integers_where_the_sweep_rescales() -> None:
    for name in NEW:
        params = inspect.signature(fo.ORTHOGONAL_FAMILIES[name]).parameters
        assert isinstance(params["ttl_bars"].default, int)
        assert isinstance(params["atr_n"].default, int)
