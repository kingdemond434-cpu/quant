"""`orthogonal_sweep._tape_series` reads the accumulated micro_ series through DataHub, and the
30-day tick read stays the fallback.

The defect: the two tape families (`liquidity_regime`, `orderflow_imbalance`) were conditioned on
the last 30 tick-day files only, so no cell could clear the judge's 60-day history floor. The
hourly `flow_toxicity` leg accumulates the same per-bar aggregates into
`data/lake/series/micro_<SYM>.parquet` (DataHub `micro.flow_bars`). These tests pin that:
  1. on the same days the two reads agree (the series is the same arithmetic, re-assembled);
  2. inside the tick window the old values are unchanged; the series only lengthens the past;
  3. the longer series yields more judgeable history for the families' own z-score;
  4. every malformed, absent or unservable case falls back to the tick read exactly;
  5. the judge's runtime resolver (`family_inputs.resolve`) reads through the same path.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import datahub_desk as dd  # noqa: E402
from research import flow_toxicity_miner as ftm  # noqa: E402
from research import orthogonal_sweep as osw  # noqa: E402

SYM = "EURUSD"
POINT = 1e-5
DAYS = ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12")


def _day_ticks(day: str, seed: int, n: int = 16_000, step_s: float = 5.0) -> pd.DataFrame:
    """One UTC day of quotes (~22h), no duplicates, both sides positive."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(f"{day} 00:30", periods=n, freq=pd.Timedelta(seconds=step_s), tz="UTC")
    moves = rng.choice([-1, 0, 1], n, p=[0.3, 0.4, 0.3])
    mid = 1.1 + seed * 1e-3 + np.cumsum(moves) * POINT
    sp = rng.integers(1, 4, n) * POINT
    return pd.DataFrame({"ts": ts, "bid": mid - sp / 2, "ask": mid + sp / 2})


def _clear() -> None:
    osw._ticks.cache_clear()
    osw._micro.cache_clear()


@pytest.fixture()
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict]:
    ticks, series, uni = tmp_path / "ticks", tmp_path / "series", tmp_path / "universe"
    (ticks / SYM).mkdir(parents=True)
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps({SYM: {"tick_size": POINT}}))
    for i, day in enumerate(DAYS):
        _day_ticks(day, seed=i).to_parquet(ticks / SYM / f"{day}.parquet")
    state: dict = {}
    r = ftm.accumulate(SYM, POINT, state, tick_root=ticks, series_root=series)
    assert r["status"] == "MEASURED" and r["days_folded"] == len(DAYS)
    monkeypatch.setattr(osw, "TAPE", ticks)
    monkeypatch.setattr(osw, "UNIVERSE", uni)
    monkeypatch.setattr(dd, "SERIES_DIR", series)
    _clear()
    idx = pd.date_range(f"{DAYS[0]} 00:00", f"{DAYS[-1]} 23:00", freq="1h", tz="UTC")
    yield {"ticks": ticks, "series": series, "idx": idx, "tmp": tmp_path}
    _clear()


def _old_read(rig: dict, tf: str = "H1", index=None):
    """The pre-change reader: ticks only (the series made unreachable)."""
    saved = dd.SERIES_DIR
    dd.SERIES_DIR = rig["tmp"] / "no_series_here"
    _clear()
    try:
        return osw._tape_series(SYM, rig["idx"] if index is None else index, tf)
    finally:
        dd.SERIES_DIR = saved
        _clear()


def _series_only(rig: dict, tf: str = "H1", index=None):
    """The accumulated series alone (the tape made unreachable)."""
    saved = osw.TAPE
    osw.TAPE = rig["tmp"] / "no_tape_here"
    _clear()
    try:
        return osw._tape_series(SYM, rig["idx"] if index is None else index, tf)
    finally:
        osw.TAPE = saved
        _clear()


def _day_first_bars(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    firsts = [pd.Timestamp(f"{d} 00:00", tz="UTC") for d in DAYS[1:]]
    return pd.DatetimeIndex([t for t in index if t.floor("D") in firsts and t == t.floor("D")])


@pytest.mark.parametrize("tf", ["H1", "H4", "D1"])
def test_old_and_new_reads_agree_on_the_same_days(rig: dict, tf: str) -> None:
    from mt5desk.universe_registry import timeframe_minutes
    rule = f"{timeframe_minutes(tf)}min"
    index = pd.date_range(f"{DAYS[0]} 00:00", f"{DAYS[-1]} 23:00", freq=rule, tz="UTC")
    o_spread, o_flow = _old_read(rig, tf, index)
    n_spread, n_flow = _series_only(rig, tf, index)
    assert o_spread is not None and n_spread is not None and o_flow is not None
    both = o_spread.notna() & n_spread.notna()
    assert both.sum() >= (len(index) // 2)
    # Spread: the same mean quote, re-assembled from (sum of points, count) times the point.
    np.testing.assert_allclose(n_spread[both].to_numpy(), o_spread[both].to_numpy(),
                               rtol=1e-12, atol=0.0)
    # Flow: identical on every bar, except that the series folds each day file on its own, so a
    # day's very first quote has no predecessor there (the tick read diffs it against the previous
    # day's last quote). That is one revision on the bar holding a day's first quote, and only
    # when that quote moved -- never more than one unit. On H1 it is the day's first bar; on a
    # coarser chart it is the bin that holds midnight.
    diff = (n_flow[both] - o_flow[both]).abs()
    if tf == "H1":
        seam = diff.index.isin(_day_first_bars(diff.index))
        assert (diff[~seam] == 0).all()
        assert (diff[seam] <= 1).all()
    else:
        assert (diff <= 1).all()
        assert (diff[diff.index.hour != 0] == 0).all()


def test_inside_the_tick_window_nothing_changes_and_the_past_gets_longer(rig: dict) -> None:
    # archive the first four days off the box: the tape now holds two, the series all six
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    _clear()
    o_spread, o_flow = _old_read(rig)
    n_spread, n_flow = osw._tape_series(SYM, rig["idx"], "H1")
    window = o_spread.notna()
    pd.testing.assert_series_equal(n_spread[window], o_spread[window])
    pd.testing.assert_series_equal(n_flow[o_flow.notna()], o_flow[o_flow.notna()])
    start = pd.Timestamp(f"{DAYS[4]} 00:00", tz="UTC")
    before = rig["idx"] < start
    assert o_spread[before].isna().all() and o_flow[before].isna().all()
    assert n_spread[before].notna().sum() > 70 and n_flow[before].notna().sum() > 70


def test_the_longer_series_yields_more_judgeable_history(rig: dict) -> None:
    """The families' own z-score needs `lookback` bars (96 for liquidity_regime) before it states
    a number; two tape days barely reach it, six accumulated days clear it by four days."""
    from mt5desk.families_orthogonal import family_liquidity_regime, family_orderflow_imbalance
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    _clear()
    o_spread, o_flow = _old_read(rig)
    n_spread, n_flow = osw._tape_series(SYM, rig["idx"], "H1")

    def finite_z(s: pd.Series, lookback: int = 96) -> int:
        z = (s - s.rolling(lookback).mean()) / s.rolling(lookback).std(ddof=1)
        return int(np.isfinite(z.to_numpy()).sum())

    start = pd.Timestamp(f"{DAYS[4]} 00:00", tz="UTC")

    def days_before_window(s: pd.Series) -> int:
        return int(s[s.index < start].dropna().index.normalize().nunique())

    # the z-score states a number on ~one bar of the tape read, and on ~a hundred more of the
    # series read: every one of the extra bars is history the judge can now evaluate
    for old, new in ((o_spread, n_spread), (o_flow, n_flow)):
        assert finite_z(new) >= finite_z(old) + 70
        assert days_before_window(old) == 0 and days_before_window(new) == 4
    # and the families themselves run on the longer input as they do on the short one
    rng = np.random.default_rng(3)
    close = 1.1 + np.cumsum(rng.normal(0, 4e-4, len(rig["idx"])))
    bars = pd.DataFrame({"open": close, "high": close + 3e-4, "low": close - 3e-4,
                         "close": close}, index=rig["idx"])
    for spread in (o_spread, n_spread):
        assert isinstance(family_liquidity_regime(bars, spread_series=spread), list)
    for flow in (o_flow, n_flow):
        assert isinstance(family_orderflow_imbalance(bars, flow=flow), list)


def test_a_series_no_longer_than_the_tape_changes_nothing(rig: dict) -> None:
    o = _old_read(rig)
    n = osw._tape_series(SYM, rig["idx"], "H1")
    pd.testing.assert_series_equal(n[0], o[0])
    pd.testing.assert_series_equal(n[1], o[1])


@pytest.mark.parametrize("damage", ["missing_column", "naive_index", "unreadable"])
def test_a_malformed_series_falls_back_to_the_tick_read(rig: dict, damage: str) -> None:
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    p = rig["series"] / f"micro_{SYM}.parquet"
    frame = pd.read_parquet(p)
    if damage == "missing_column":
        frame.drop(columns=["tr_flow_moves"]).to_parquet(p)
    elif damage == "naive_index":
        frame.index = frame.index.tz_localize(None)
        frame.to_parquet(p)
    else:
        p.write_bytes(b"not a parquet file")
    _clear()
    o = _old_read(rig)
    n = osw._tape_series(SYM, rig["idx"], "H1")
    pd.testing.assert_series_equal(n[0], o[0])
    pd.testing.assert_series_equal(n[1], o[1])


def test_an_unknown_point_extends_flow_but_never_guesses_a_spread(
        rig: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    (osw.UNIVERSE / "universe.json").write_text(json.dumps({SYM: {}}))
    _clear()
    o_spread, o_flow = _old_read(rig)
    n_spread, n_flow = osw._tape_series(SYM, rig["idx"], "H1")
    pd.testing.assert_series_equal(n_spread, o_spread)
    assert n_flow.notna().sum() > o_flow.notna().sum()


def test_a_sub_hour_chart_reads_the_ticks_alone(rig: dict) -> None:
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    _clear()
    idx = pd.date_range(f"{DAYS[0]} 00:00", f"{DAYS[-1]} 23:55", freq="5min", tz="UTC")
    o = _old_read(rig, "M5", idx)
    n = osw._tape_series(SYM, idx, "M5")
    pd.testing.assert_series_equal(n[0], o[0])
    pd.testing.assert_series_equal(n[1], o[1])
    assert not osw._micro_chart_ok("M30") and osw._micro_chart_ok("H4")
    assert osw._micro_chart_ok("D1")


def test_no_tape_reads_the_series_and_no_series_reads_the_tape(rig: dict) -> None:
    s_spread, s_flow = _series_only(rig)
    assert s_spread is not None and s_spread.notna().any()
    assert s_flow is not None and s_flow.notna().any()
    saved_tape, saved_series = osw.TAPE, dd.SERIES_DIR
    osw.TAPE, dd.SERIES_DIR = rig["tmp"] / "none1", rig["tmp"] / "none2"
    _clear()
    try:
        assert osw._tape_series(SYM, rig["idx"], "H1") == (None, None)
    finally:
        osw.TAPE, dd.SERIES_DIR = saved_tape, saved_series
        _clear()


def test_the_judges_runtime_resolver_reads_through_the_same_path(rig: dict) -> None:
    from mt5desk import family_inputs
    for day in DAYS[:4]:
        (rig["ticks"] / SYM / f"{day}.parquet").unlink()
    _clear()
    bars = pd.DataFrame({"open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1}, index=rig["idx"])
    want_spread, want_flow = osw._tape_series(SYM, rig["idx"], "H1")
    extra, why = family_inputs.resolve(SYM, "liquidity_regime", {}, bars)
    assert why == "ok" and extra is not None
    pd.testing.assert_series_equal(extra["spread_series"], want_spread)
    extra, why = family_inputs.resolve(SYM, "orderflow_imbalance", {}, bars)
    assert why == "ok" and extra is not None
    pd.testing.assert_series_equal(extra["flow"], want_flow)
    start = pd.Timestamp(f"{DAYS[4]} 00:00", tz="UTC")
    assert extra["flow"][extra["flow"].index < start].notna().sum() > 70


@pytest.mark.parametrize("row", [{"tick_size": 0.01}, {"point": 1e-3}, {"digits": 5},
                                 {"tick_size": "x", "digits": 3}, {}, {"tick_size": -1.0}])
def test_the_sweep_reads_the_same_point_the_miner_divided_by(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict) -> None:
    (tmp_path / "universe.json").write_text(json.dumps({SYM: row}))
    monkeypatch.setattr(osw, "UNIVERSE", tmp_path)
    assert osw._micro_point(SYM) == ftm.point_of(SYM, {SYM: row})
