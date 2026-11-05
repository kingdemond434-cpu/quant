"""Footprint flows (sweep rows 4, 15, 17, 18): the dates are the rule's, the hedge flow is signed
and causal.

WHAT THIS PINS
  * the new calendar kinds land on the dates their rules name, in UTC, across the 2019 T+2 and
    2024 TSE-close changes: Nikkei dividend reinvestment, Japanese fiscal year-end, the CNY
    parity / PTAX / Banxico FIX windows, post-holiday reopenings, and the Nikkei, Hang Seng and
    ASX index-review closes;
  * every declared kind is counted, so a zero is a measurement;
  * the FX hedge-rebalancing modes trade the side the flow names (USD sold when US equities
    out-ran the home market period-to-date), the post-fix fade trades the mirror, and corrupting
    every bar after a signal on all three legs moves no signal.
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import forced_flow_calendar as cal  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import family_forced_flow as ff  # noqa: E402


def _one(kind: str, name_prefix: str, lo: date, hi: date) -> cal.Event:
    rows = [e for e in cal.events(lo, hi) if e.kind == kind and e.name.startswith(name_prefix)]
    assert len(rows) == 1, [e.name for e in rows]
    return rows[0]


def _utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)


def test_the_new_kinds_are_declared_and_counted():
    for kind in ("em_fixing", "dividend_reinvestment", "fiscal_year_end", "post_holiday"):
        assert kind in cal.KINDS
    counts = cal.by_kind(cal.events(date(2025, 1, 1), date(2025, 12, 31)))
    assert counts["dividend_reinvestment"] == 2 and counts["fiscal_year_end"] == 2
    assert counts["em_fixing"] == 3 * 261 and counts["post_holiday"] > 0


def test_nikkei_dividend_reinvestment_follows_the_settlement_cycle_and_the_close():
    # 2025: record 31 Mar (Mon), T+2 -> last cum-dividend day Thu 27 Mar, close 15:30 JST
    e = _one("dividend_reinvestment", "nikkei_dividend_reinvest_202503",
             date(2025, 3, 1), date(2025, 3, 31))
    assert e.date == date(2025, 3, 27) and e.window_start_utc == _utc(2025, 3, 27, 6, 0)
    # 2018: record 30 Mar (Fri), T+3 -> Tue 27 Mar, close 15:00 JST
    e = _one("dividend_reinvestment", "nikkei_dividend_reinvest_201803",
             date(2018, 3, 1), date(2018, 3, 31))
    assert e.date == date(2018, 3, 27) and e.window_start_utc == _utc(2018, 3, 27, 5, 30)


def test_japan_fiscal_year_end_is_the_last_tokyo_fix_of_march():
    e = _one("fiscal_year_end", "japan_fy_end_202503", date(2025, 3, 1), date(2025, 3, 31))
    assert e.date == date(2025, 3, 31) and e.window_start_utc == _utc(2025, 3, 31, 0, 45)
    assert "USDJPY" in e.instruments and all(s.endswith("JPY") for s in e.instruments)


def test_em_fixings_sit_at_their_local_minutes():
    day = date(2025, 7, 15)
    rows = {e.name.rsplit("_", 1)[0]: e for e in cal.events(day, day) if e.kind == "em_fixing"}
    assert rows["cny_parity_0915"].window_start_utc == _utc(2025, 7, 15, 1, 0)
    assert rows["brl_ptax"].window_start_utc == _utc(2025, 7, 15, 13, 0)
    assert rows["brl_ptax"].window_end_utc == _utc(2025, 7, 15, 16, 10)
    assert rows["banxico_fix"].window_start_utc == _utc(2025, 7, 15, 17, 30)
    assert rows["cny_parity_0915"].instruments == ("USDCNH",)
    assert not [e for e in cal.events(date(2025, 7, 19), date(2025, 7, 20))
                if e.kind == "em_fixing"]                     # a weekend has no fixing


def test_post_holiday_is_the_first_session_back():
    # 4 July 2025 is a Friday: the US venue reopens Monday 7 July, 09:30 New York = 13:30 UTC
    e = _one("post_holiday", "us_post_holiday_2025-07-07", date(2025, 7, 1), date(2025, 7, 31))
    assert e.window_start_utc == _utc(2025, 7, 7, 13, 30)


def test_index_reviews_for_nikkei_hang_seng_and_asx():
    e = _one("index_rebalance", "nikkei225_review_202504", date(2025, 3, 1), date(2025, 4, 30))
    assert e.date == date(2025, 3, 31) and e.window_start_utc == _utc(2025, 3, 31, 6, 0)
    e = _one("index_rebalance", "nikkei225_review_202404", date(2024, 3, 1), date(2024, 4, 30))
    assert e.window_start_utc == _utc(2024, 3, 29, 5, 30)    # the 15:00 close, pre-2024-11-05
    e = _one("index_rebalance", "hsi_quarterly_202503", date(2025, 2, 1), date(2025, 3, 31))
    assert e.date == date(2025, 2, 28)                       # the Friday before 3 March
    e = _one("index_rebalance", "asx200_quarterly_202503", date(2025, 3, 1), date(2025, 3, 31))
    assert e.date == date(2025, 3, 21) and e.instruments == ("AUS200",)


# ------------------------------------------------------------------ the hedge-rebalancing flow

def _walk(seed: int, drift: float, start: str = "2023-01-02", days: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.normal(drift, 0.002, len(idx))
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    frames = {"US500": _walk(1, 0.0001), "GER40": _walk(2, -0.00005), "EURUSD": _walk(3, 0.0),
              "USDJPY": _walk(4, 0.0), "JPN225": _walk(5, 0.0)}
    for sym, f in frames.items():
        f.to_parquet(tmp_path / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    xs._SERIES_CACHE.clear()
    yield frames
    xs._SERIES_CACHE.clear()


def _rel(frames: dict[str, pd.DataFrame], home: str, at: pd.Timestamp, months: int = 1) -> float:
    m0 = ((at.month - 1) // months) * months + 1
    base = pd.Timestamp(at.year, m0, 1, tz="UTC")

    def ret(sym: str) -> float:
        c = frames[sym]["close"]
        return float(np.log(c[c.index <= at].iloc[-1] / c[c.index < base].iloc[-1]))
    return ret("US500") - ret(home)


def test_the_pair_side_and_home_index():
    assert ff.usd_selling_side("EURUSD") == 1 and ff.usd_selling_side("USDJPY") == -1
    assert ff.usd_selling_side("EURGBP") == 0
    assert ff.home_equity("EURUSD") == "GER40" and ff.home_equity("USDJPY") == "JPN225"
    assert ff.home_equity("NZDUSD") == ""                    # no NZ index: no cell


@pytest.mark.parametrize("pair,home", [("EURUSD", "GER40"), ("USDJPY", "JPN225")])
def test_into_fix_trades_the_usd_selling_the_flow_names(store, pair, home):
    sigs = ff.family_forced_flow(store[pair], event_kind="month_end", mode="hedge_into_fix",
                                 symbol=pair, clock="bars")
    assert len(sigs) >= 10
    for s in sigs:
        rel = _rel(store, home, pd.Timestamp(s.time))
        assert s.side == ff.usd_selling_side(pair) * (1 if rel > 0 else -1)
    fade = ff.family_forced_flow(store[pair], event_kind="month_end",
                                 mode="hedge_post_fix_fade", symbol=pair, clock="bars")
    assert fade and all(s.time > max(x.time for x in sigs if x.time.month == s.time.month
                                     and x.time.year == s.time.year) for s in fade)
    short = ff.family_forced_flow(store[pair], -1, event_kind="month_end",
                                  mode="hedge_into_fix", symbol=pair, clock="bars")
    assert [s.side for s in short] == [-s.side for s in sigs]


def test_min_rel_only_removes_small_flows(store):
    every = ff.family_forced_flow(store["EURUSD"], event_kind="quarter_end",
                                  mode="hedge_into_fix", symbol="EURUSD", clock="bars")
    big = ff.family_forced_flow(store["EURUSD"], event_kind="quarter_end",
                                mode="hedge_into_fix", symbol="EURUSD", clock="bars",
                                min_rel=0.02)
    assert {s.time for s in big} <= {s.time for s in every}
    for s in big:
        assert abs(_rel(store, "GER40", pd.Timestamp(s.time), months=3)) > 0.02


def test_a_hedge_signal_never_reads_a_bar_after_itself(store, tmp_path):
    base = ff.family_forced_flow(store["EURUSD"], event_kind="month_end",
                                 mode="hedge_into_fix", symbol="EURUSD", clock="bars")
    cut = pd.Timestamp(base[len(base) // 2].time)
    rng = np.random.default_rng(7)
    for sym in ("US500", "GER40", "EURUSD"):
        f = store[sym].copy()
        after = f.index > cut
        f.loc[after, ["open", "high", "low", "close"]] *= rng.uniform(0.5, 1.5, (after.sum(), 1))
        f.to_parquet(tmp_path / f"{sym}_H1.parquet")
        store[sym] = f
    xs._SERIES_CACHE.clear()
    again = ff.family_forced_flow(store["EURUSD"], event_kind="month_end",
                                  mode="hedge_into_fix", symbol="EURUSD", clock="bars")
    keep = [(s.time, s.side) for s in base if pd.Timestamp(s.time) <= cut]
    assert keep and keep == [(s.time, s.side) for s in again if pd.Timestamp(s.time) <= cut]


def test_a_missing_leg_is_no_trade_never_a_guess(store, tmp_path):
    (tmp_path / "GER40_H1.parquet").unlink()
    xs._SERIES_CACHE.clear()
    assert ff.family_forced_flow(store["EURUSD"], event_kind="month_end",
                                 mode="hedge_into_fix", symbol="EURUSD", clock="bars") == []


# ------------------------------------------------------------------------ the specialist mint

NEW_MECHANISMS = ("fx_hedge_rebalance", "em_fixing_flow", "japan_fiscal_year_end",
                  "dividend_reinvestment", "post_holiday_drift", "index_review_flow")


def _plan(sym: str, klass: str) -> dict[str, list[dict]]:
    import specialist_cell as sc
    gen = sc.SPECIALISTS[klass][0]
    return {m: grid for m, fam, grid in gen(sym) if m in NEW_MECHANISMS and fam == "forced_flow"}


def test_each_niche_is_minted_only_where_the_calendar_names_the_symbol():
    import specialist_cell as sc
    assert set(_plan("EURUSD", "fx")) == {"fx_hedge_rebalance", "post_holiday_drift"}
    assert "japan_fiscal_year_end" in _plan("USDJPY", "fx")
    assert set(_plan("USDCNH", "fx")) >= {"em_fixing_flow"}
    assert "fx_hedge_rebalance" not in _plan("NZDUSD", "fx")      # no home index, no cell
    assert {"dividend_reinvestment", "index_review_flow"} <= set(_plan("JPN225", "indices"))
    assert "dividend_reinvestment" not in _plan("US500", "indices")
    for m in NEW_MECHANISMS:
        klass = "indices" if m in ("dividend_reinvestment", "index_review_flow") else "fx"
        assert sc.SPECIALISTS[klass][1].get(m), m                   # a prior, stated up front
        assert sc.culture(m, "JPN225")["source_culture"] != "UNMEASURED"


def test_every_new_cell_is_buildable_by_the_sealed_gauntlet():
    from research import gauntlet_buildability as gb
    for sym, klass in (("EURUSD", "fx"), ("USDJPY", "fx"), ("USDCNH", "fx"),
                       ("JPN225", "indices")):
        for m, grid in _plan(sym, klass).items():
            for params in grid:
                verdict, why = gb.cell_verdict("forced_flow", params, "H1")
                assert verdict == "BUILDABLE", (sym, m, params, why)
