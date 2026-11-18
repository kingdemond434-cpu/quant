"""The Tier-1 idea families (U2, U4, U5, N1): what fires, when, and nothing from the future."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from mt5desk import families_cross_sectional as xs
from mt5desk import families_orthogonal as fo
from mt5desk import families_tier1 as t1
from mt5desk import local_clock as lc


def _bars(n_days: int, seed: int, *, weekends: bool = True, start: str = "2023-01-02",
          scale: float = 0.002) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n_days * 24, freq="1h", tz="UTC")
    if not weekends:
        idx = idx[idx.dayofweek < 5]
    r = np.random.default_rng(seed).normal(0, scale, len(idx))
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[100.0], close[:-1]]) * np.exp(
        np.random.default_rng(seed + 1).normal(0, scale / 2, len(idx)))
    hi = np.maximum(open_, close) * 1.001
    lo = np.minimum(open_, close) * 0.999
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close}, index=idx)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    xs._SERIES_CACHE.clear()
    t1._GAP_CACHE.clear()
    yield tmp_path
    xs._SERIES_CACHE.clear()
    t1._GAP_CACHE.clear()


def test_registered_where_the_gauntlet_resolves_families() -> None:
    for name in t1.TIER1_FAMILIES:
        assert fo.ORTHOGONAL_FAMILIES[name] is t1.TIER1_FAMILIES[name]
        assert name in fo.FAMILY_INPUTS
    assert "M5" not in fo.FAMILY_TIMEFRAMES["weekend_driver_gap"][0], "no sub-hour lookahead"
    assert "D1" not in fo.FAMILY_TIMEFRAMES["overnight_intraday_tug"][0]


# ------------------------------------------------------------------------------------ U2 ---
def test_tug_fires_only_when_the_legs_disagree_and_fades_the_night() -> None:
    df = _bars(400, 3, weekends=False)
    sigs = t1.family_overnight_intraday_tug(df, min_leg_atr=0.0)
    assert sigs, "a random walk has disagreeing legs"
    om = lc.window_mask(df.index, "America/New_York", "09:30", "contains")
    cm = lc.window_mask(df.index, "America/New_York", "16:00", "contains")
    _m, ymd = lc.local_frame(df.index, "America/New_York")
    opens = t1._first_per_date(om, ymd)
    closes = t1._first_per_date(cm, ymd)
    dates = sorted(opens)
    pos = {df.index[i]: i for i in range(len(df))}
    for s in sigs:
        i = pos[s.time]
        d = int(ymd[i])
        prev = dates[dates.index(d) - 1]
        night = df["open"].iloc[i] - df["close"].iloc[closes[prev]]
        day = df["close"].iloc[closes[prev]] - df["open"].iloc[opens[prev]]
        assert np.sign(night) != np.sign(day)
        assert s.side == -int(np.sign(night))
    mirror = t1.family_overnight_intraday_tug(df, min_leg_atr=0.0, direction=1)
    assert [s.side for s in mirror] == [-s.side for s in sigs]


def test_tug_refuses_a_malformed_clock() -> None:
    assert t1.family_overnight_intraday_tug(_bars(60, 1), open_at="25:00") == []


# ------------------------------------------------------------------------------------ U4 ---
def test_weekend_move_fires_on_the_first_bar_back_with_its_sign(store) -> None:
    target = _bars(400, 5, weekends=False)
    driver = _bars(400, 6, weekends=True, scale=0.004)
    driver.to_parquet(store / "BTCUSD_H1.parquet")
    sigs = t1.family_weekend_driver_gap(target, driver_symbol="BTCUSD", entry_z=0.5)
    assert sigs
    t = target.index
    first_back = {t[i] for i in range(1, len(t)) if t[i] - t[i - 1] >= pd.Timedelta(hours=36)}
    for s in sigs:
        assert s.time in first_back
        i = t.get_loc(s.time)
        dc = driver["close"]
        move = np.log(dc.asof(t[i]) / dc.asof(t[i - 1]))
        assert s.side == int(np.sign(move))
    assert min(s.time for s in sigs) > sorted(first_back)[25], "needs prior weekends first"


def test_weekend_driver_reads_nothing_from_after_the_decision(store) -> None:
    target = _bars(300, 7, weekends=False)
    driver = _bars(300, 8, weekends=True, scale=0.004)
    driver.to_parquet(store / "BTCUSD_H1.parquet")
    base = t1.family_weekend_driver_gap(target, driver_symbol="BTCUSD", entry_z=0.5)
    cut = base[len(base) // 2].time
    late = driver.copy()
    late.loc[late.index > cut, ["open", "high", "low", "close"]] *= 3.0
    late.to_parquet(store / "BTCUSD_H1.parquet")
    xs._SERIES_CACHE.clear()
    again = t1.family_weekend_driver_gap(target, driver_symbol="BTCUSD", entry_z=0.5)
    early = [(s.time, s.side) for s in base if s.time <= cut]
    assert [(s.time, s.side) for s in again if s.time <= cut] == early


def test_weekend_driver_without_bars_is_silent(store) -> None:
    assert t1.family_weekend_driver_gap(_bars(200, 1, weekends=False),
                                        driver_symbol="NOPE") == []


# ------------------------------------------------------------------------------------ U5 ---
def test_gap_breadth_fires_on_the_day_the_class_gaps(store, monkeypatch) -> None:
    names = [f"EQ{k}" for k in range(25)]
    planted = 20230315
    for k, n in enumerate(names):
        f = _bars(120, 100 + k, weekends=False, scale=0.0005)
        _m, ymd = lc.local_frame(f.index, "America/New_York")
        after = ymd >= planted
        f.loc[after, ["open", "high", "low", "close"]] *= 1.06
        f.to_parquet(store / f"{n}_H1.parquet")
    monkeypatch.setattr(t1, "_members", lambda _c: names)
    idx = _bars(120, 9, weekends=False)
    sigs = t1.family_equity_gap_breadth(idx, min_names=20, entry_breadth=0.5)
    _m, ymd = lc.local_frame(idx.index, "America/New_York")
    fired = {int(ymd[idx.index.get_loc(s.time)]): s.side for s in sigs}
    assert fired == {planted: 1}
    short = t1.family_equity_gap_breadth(idx, min_names=26, entry_breadth=0.5)
    assert short == [], "fewer reporting names than min_names fires nothing"


# ------------------------------------------------------------------------------------ N1 ---
def test_holiday_rules_match_the_published_2025_calendars() -> None:
    nyse = {date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
            date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
            date(2025, 11, 27), date(2025, 12, 25)}
    lse = {date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 5),
           date(2025, 5, 26), date(2025, 8, 25), date(2025, 12, 25), date(2025, 12, 26)}
    xetra = {date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 1),
             date(2025, 12, 24), date(2025, 12, 25), date(2025, 12, 26), date(2025, 12, 31)}
    assert t1.holidays("NYSE", 2025) == nyse
    assert t1.holidays("LSE", 2025) == lse
    assert t1.holidays("XETRA", 2025) == xetra
    assert t1.holidays("JPX", 2025) == set()
    assert t1.easter(2024) == date(2024, 3, 31)


def test_pre_holiday_enters_at_the_close_before_the_pre_holiday_session() -> None:
    df = _bars(365, 11, weekends=False, start="2025-01-01")
    sigs = t1.family_pre_holiday_drift(df, venue="NYSE", days_before=1)
    _m, ymd = lc.local_frame(df.index, "America/New_York")
    got = {int(ymd[df.index.get_loc(s.time)]) for s in sigs}
    # Jul 4 (Fri): pre-holiday session Thu Jul 3, entry at Wed Jul 2's close; Thanksgiving
    # Thu Nov 27: pre session Wed Nov 26, entry Tue Nov 25; Christmas Thu: entry Tue Dec 23
    assert {20250702, 20251125, 20251223} <= got
    assert all(s.side == 1 for s in sigs)
    two = t1.family_pre_holiday_drift(df, venue="NYSE", days_before=2)
    got2 = {int(ymd[df.index.get_loc(s.time)]) for s in two}
    assert 20250701 in got2 and 20250702 not in got2
    assert t1.family_pre_holiday_drift(df, venue="JPX") == []


def test_the_sealed_build_cell_builds_the_price_only_ones() -> None:
    import sys
    from pathlib import Path
    desk = Path(__file__).resolve().parents[1]
    for p in (str(desk / "research"), str(desk / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import external_gauntlet as eg
    df = _bars(400, 21, weekends=False, start="2023-01-02")
    for fam, params in (("overnight_intraday_tug", {"min_leg_atr": 0.0}),
                        ("pre_holiday_drift", {"venue": "NYSE"})):
        cell = eg.build_cell("US500", fam, dict(params), {}, h1_override=df)
        assert cell is not None, (fam, eg.LAST_BUILD_FAILURE)
        assert cell["sigs"], fam
