"""The retail stop-cluster map: causal levels, honest clusters, both trades at the sweep."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as FO  # noqa: E402
from mt5desk import family_stop_cluster as SC  # noqa: E402


def _bars(n: int = 1500, seed: int = 7, start: float = 1.0800) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="h")
    close = start + np.cumsum(rng.normal(0, 0.0012, n))
    opn = np.concatenate(([start], close[:-1]))
    spread = np.abs(rng.normal(0, 0.0008, n))
    high = np.maximum(opn, close) + spread
    low = np.minimum(opn, close) - spread
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close}, index=idx)


def test_round_step_is_the_big_figure_of_each_market() -> None:
    assert SC.round_step(1.0832) == pytest.approx(0.01)
    assert SC.round_step(151.3) == pytest.approx(1.0)
    assert SC.round_step(2650.0) == pytest.approx(10.0)
    assert SC.round_step(42150.0) == pytest.approx(100.0)
    assert np.isnan(SC.round_step(0.0))


def test_every_level_row_is_unchanged_when_the_future_is_cut_off() -> None:
    df = _bars()
    full = SC.level_map(df)
    cut = 900
    part = SC.level_map(df.iloc[:cut])
    for src in (*SC._SOURCES, "prev_close", "prev_atr"):
        np.testing.assert_array_equal(full[src][:cut], part[src][:cut], err_msg=src)


def test_a_swing_is_not_usable_before_its_confirmation_bars_close() -> None:
    df = _bars(300)
    k = 10
    is_hi, _ = SC.swing_levels(df["high"].to_numpy(), df["low"].to_numpy(), k)
    first = int(np.flatnonzero(is_hi)[0])
    m = SC.level_map(df, k_swing=k)
    assert np.isnan(m["swing"][first + k, 0])
    assert m["swing"][first + k + 1, 0] == pytest.approx(df["high"].iloc[first])


def test_the_asian_range_only_exists_after_the_session_closes() -> None:
    df = _bars(200)
    m = SC.level_map(df, asia_end_h=9)
    hours = df.index.hour
    assert np.isnan(m["asia"][hours < 9]).all()
    day0 = df.index[0].floor("D")
    sel = (df.index.floor("D") == day0) & (hours < 9)
    after = int(np.flatnonzero((df.index.floor("D") == day0) & (hours == 9))[0])
    assert m["asia"][after, 0] == pytest.approx(df["high"][sel].max())


def test_the_half_figure_never_double_counts_the_big_figure() -> None:
    df = _bars(100, start=1.0985)
    m = SC.level_map(df)
    t = 50
    assert not set(np.round(m["half"][t], 6)) & set(np.round(m["round"][t], 6))


def test_a_cluster_needs_distinct_sources_not_repeated_ones() -> None:
    lv = [(1.1000, "round"), (1.1002, "round"), (1.2000, "swing")]
    assert SC.nearest_cluster(lv, 1.0950, 1, 0.001, 2, 0.5) is None
    lv.append((1.1003, "prior_day"))
    edge, dens = SC.nearest_cluster(lv, 1.0950, 1, 0.001, 2, 0.5)
    assert dens == 2 and edge == pytest.approx(1.1003)      # the OUTERMOST level of the group
    edge, _ = SC.nearest_cluster([(1.09, "round"), (1.0898, "asia")], 1.0950, -1, 0.001, 2, 0.5)
    assert edge == pytest.approx(1.0898)


def _engineered_sweep(revert: bool) -> pd.DataFrame:
    """Flat tape under 1.1000 with yesterday's high on it, then one bar through it."""
    n = 120
    idx = pd.date_range("2025-03-03 00:00", periods=n, freq="h")
    base = np.full(n, 1.0985)
    df = pd.DataFrame({"open": base, "high": base + 0.0006, "low": base - 0.0006,
                       "close": base}, index=idx)
    df.loc[idx[5], "high"] = 1.1001                          # day 1 high sits on the big figure
    t = 40                                                   # day 2, 16:00: after the Asian range
    df.loc[idx[t], ["open", "high"]] = [1.0980, 1.1012]
    df.loc[idx[t], "close"] = 1.0985 if revert else 1.1010
    df.loc[idx[t], "low"] = 1.0975
    if not revert:
        df.loc[idx[t + 1:], ["open", "high", "low", "close"]] = (
            df.loc[idx[t + 1:], ["open", "high", "low", "close"]] + 0.0040)
    return df


def test_revert_fades_a_sweep_that_closes_back_inside() -> None:
    df = _engineered_sweep(revert=True)
    sigs = SC.family_stop_cluster_revert(df, k_swing=3)
    hit = [s for s in sigs if s.time == df.index[40]]
    assert hit and hit[0].side == -1 and hit[0].stop > 1.1012
    assert hit[0].wait_bars == 1 and hit[0].trigger is None  # next bar's open, never this close


def test_cascade_follows_a_hard_close_through_the_cluster() -> None:
    df = _engineered_sweep(revert=False)
    sigs = SC.family_stop_cluster_cascade(df, k_swing=3)
    hit = [s for s in sigs if s.time == df.index[40]]
    assert hit and hit[0].side == 1 and hit[0].stop < 1.1010
    assert not [s for s in SC.family_stop_cluster_revert(df, k_swing=3) if s.time == df.index[40]]


def test_both_families_are_registered_for_the_sweep_and_the_gauntlet() -> None:
    for name in ("stop_cluster_revert", "stop_cluster_cascade"):
        assert FO.ORTHOGONAL_FAMILIES[name] is SC.STOP_CLUSTER_FAMILIES[name]
        assert FO.FAMILY_INPUTS[name][0] == "price only"
        assert FO.timeframe_refusal(name, "D1") and FO.timeframe_refusal(name, "M5") is None


def test_the_compiler_routes_stop_hunt_prose_to_the_family() -> None:
    from research.miner_candidate_compiler import text_families
    fams = dict(text_families("Classic stop hunt above the Asian high before London"))
    assert "stop_cluster_revert" in fams


def test_an_unknown_mode_is_refused_rather_than_guessed() -> None:
    with pytest.raises(ValueError):
        SC._stop_cluster(_bars(200), mode="both", k_swing=10, n_swings=2, asia_end_h=9,
                         tol_atr=0.25, buffer_atr=0.1, min_confluence=2, max_dist_atr=1.5,
                         n_fail=3, momentum_atr=0.5, stop_atr=1.0, rr=1.5, hold_bars=12,
                         atr_n=14)
