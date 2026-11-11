"""`earnings_breadth`: the breadth of 8-K 2.02 reactions as a dated event on the US index CFDs.

  0. the family fires on a constructed positive-breadth and a negative-breadth day;
  1. it refuses BY NAME when the cache or the share bars are absent (a TypeError the builder names);
  2. a reporter whose reaction window has not closed is not counted (look-ahead);
  3. the z-score reads only prior days;
  4. fewer than min_reporters gives no event;
  5. no share symbol is ever a traded symbol or a cell, and index cells route to the hypothesis
     lane;
  6. the family, its proposer and the hourly leg are wired, and the proposer writes its report.
All inputs are synthetic; nothing touches the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_earnings_breadth as F  # noqa: E402

START, END = "2026-01-05", "2026-03-27"
#: Filing days: Monday..Thursday, so each breadth day (the next business day) is its own day.
FILE_DAYS = [d for d in pd.bdate_range("2026-01-12", "2026-03-19") if d.weekday() < 4]
PER_DAY = 20
POS_DAY = FILE_DAYS[30]          # every reporter rises
NEG_DAY = FILE_DAYS[34]          # every reporter falls


def _session_index() -> pd.DatetimeIndex:
    """Share-CFD style bars: 16:00..22:00 broker on business days."""
    days = pd.bdate_range(START, END, tz="UTC")
    return pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in days for h in range(16, 23)])


SIDX = _session_index()


def _reporter(file_day: pd.Timestamp, r: float) -> pd.DataFrame:
    """Flat at 100 until the first full session after `file_day`, 100*e^r from it on."""
    react_day = (pd.Timestamp(file_day) + pd.offsets.BDay(1)).tz_localize("UTC")
    close = np.where(react_day <= SIDX, 100.0 * np.exp(r), 100.0)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close},
                        index=SIDX)


def _book(n_per_day: int = PER_DAY, skip: frozenset[tuple[int, int]] = frozenset()):
    """Ordinary days: 8..12 of 20 reporters up by 1%, the rest down 1% (bounded, so no ordinary
    day reaches 3 sigma); POS_DAY all up 3%, NEG_DAY all down 6%."""
    filings, frames, tmap = [], {}, {}
    for k, day in enumerate(FILE_DAYS):
        n_pos = 10 + ((k * 7) % 5 - 2)
        for i in range(n_per_day):
            if (k, i) in skip:
                continue
            if day == POS_DAY:
                r = 0.03
            elif day == NEG_DAY:
                r = -0.06
            else:
                r = 0.01 if i < n_pos else -0.01
            sym, tick = f"S{k}_{i}", f"T{k}X{i}"
            tmap[tick] = sym
            frames[sym] = _reporter(day, r)
            filings.append({"tickers": [tick], "cik": str(k * 100 + i),
                            "filed": str(day.date()), "accepted": ""})
    return filings, frames, tmap


def _index(n_days: int = 90, seed: int = 9) -> pd.DataFrame:
    idx = pd.date_range("2026-01-02", periods=24 * n_days, freq="h", tz="UTC")
    idx = idx[idx.weekday < 5]
    rng = np.random.default_rng(seed)
    c = pd.Series(5000 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx)))), index=idx)
    return pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]), "high": c * 1.001,
                         "low": c * 0.999, "close": c, "tick_volume": 1.0}, index=idx)


@pytest.fixture
def book(monkeypatch):
    filings, frames, tmap = _book()
    monkeypatch.setattr(F, "ticker_cfd", lambda: tmap)
    return filings, frames


def _complete(day: pd.Timestamp) -> pd.Timestamp:
    """Day d's breadth is complete at the close of the reaction day's 22:00 bar."""
    react = (pd.Timestamp(day) + pd.offsets.BDay(1)).tz_localize("UTC")
    return react + pd.Timedelta(hours=23)


# ---------------------------------------------------------------------------- 0. it fires
def test_fires_long_on_a_positive_breadth_day_and_short_on_a_negative_one(book):
    filings, frames = book
    d = _index()
    for stat in F.STATS:
        up = F.family_earnings_breadth(d, stat=stat, move="up", direction="long", min_abs=3.0,
                                       filings=filings, reporters=frames, hold_bars=4)
        assert [s.side for s in up] == [1], stat
        assert up[0].time == _complete(POS_DAY)       # the first bar opening after the close
        dn = F.family_earnings_breadth(d, stat=stat, move="down", direction="short",
                                       min_abs=3.0, filings=filings, reporters=frames,
                                       hold_bars=4)
        assert [s.side for s in dn] == [-1], stat
        assert dn[0].time == _complete(NEG_DAY)
        assert up[0].tag.startswith("earnings_breadth:")


def test_a_reaction_runs_from_the_last_close_before_to_the_first_full_session_after():
    f = _reporter(pd.Timestamp("2026-02-10"), 0.05)
    # an acceptance instant after the US close (21:05 UTC): the next session is the first full
    early, late = F.release_bounds({"accepted": "2026-02-10T21:05:00Z"})
    r, closed = F.reaction(f, early, late)
    assert np.isclose(r, 0.05) and closed == pd.Timestamp("2026-02-11 23:00", tz="UTC")
    # a pre-market acceptance that day: its own session (16:00 broker) opens after it
    early, late = F.release_bounds({"accepted": "2026-02-11T12:00:00+00:00"})
    r, closed = F.reaction(f, early, late)
    assert closed == pd.Timestamp("2026-02-11 23:00", tz="UTC")
    # a day-only filing is knowable from the next day's 00:00 UTC + the 3h broker offset
    early, late = F.release_bounds({"filed": "2026-02-10"})
    assert late == pd.Timestamp("2026-02-11 03:00", tz="UTC")
    assert early < pd.Timestamp("2026-02-10", tz="UTC")


# ------------------------------------------------------------------------ 1. named refusal
def test_refuses_by_name_when_the_cache_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "CACHE", tmp_path / "edgar_cache")
    F._cached_filings.cache_clear()
    with pytest.raises(F.EarningsBreadthUnavailable, match=F.ABSENT) as exc:
        F.family_earnings_breadth(_index(), direction="long")
    assert isinstance(exc.value, TypeError)
    (tmp_path / "edgar_cache").mkdir()
    (tmp_path / "edgar_cache" / "fulltext_x.json").write_text(json.dumps(
        {"hits": [{"form": "10-Q", "filed": "2026-02-10", "items": []}]}), "utf-8")
    F._cached_filings.cache_clear()
    with pytest.raises(TypeError, match=F.ABSENT):          # filings, but no 8-K 2.02 ticker
        F.cached_filings()


def test_refuses_by_name_when_no_reporter_has_share_bars(book):
    filings, _frames = book
    with pytest.raises(F.EarningsBreadthUnavailable, match=F.ABSENT):
        F.family_earnings_breadth(_index(), direction="long", filings=filings, reporters={})


def test_reads_both_cache_shapes(tmp_path, monkeypatch):
    raw = {"hits": {"hits": [
        {"_source": {"form": "8-K", "file_date": "2026-02-10", "items": ["2.02", "9.01"],
                     "ciks": ["0000320193"],
                     "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"]}},
        {"_source": {"form": "8-K", "file_date": "2026-02-10", "items": ["5.02"],
                     "display_names": ["Other (OTH)"]}}]}}
    rows = F.filing_rows(raw)
    assert rows == [{"tickers": ["AAPL"], "cik": "0000320193", "filed": "2026-02-10",
                     "accepted": ""}]
    own = {"hits": [{"form": "8-K", "filed": "2026-02-10", "items": ["2.02"], "ticker": "msft",
                     "accepted": "2026-02-10T21:05:00Z"},
                    {"form": "8-K", "filed": "2026-02-10", "items": ["2.02"]}]}   # no ticker
    assert [r["tickers"] for r in F.filing_rows(own)] == [["MSFT"]]
    assert F.ticker_cfd()["AAPL"] == "Apple"


# ---------------------------------------------------------------------------- 2. look-ahead
def test_a_reporter_whose_window_has_not_closed_is_not_counted(book):
    filings, frames = book
    f = frames["S0_0"]
    react_day = pd.Timestamp(FILE_DAYS[0] + pd.offsets.BDay(1)).tz_localize("UTC")
    # the bars end inside the reaction session: its window has not closed
    cut = f[f.index < react_day + pd.Timedelta(hours=20)]
    early, late = F.release_bounds(filings[0])
    assert F.reaction(cut, early, late) is None
    # the bars end at the session's last bar: the day may still be open, so still not closed
    cut = f[f.index <= react_day + pd.Timedelta(hours=22)]
    assert F.reaction(cut, early, late) is None
    assert F.reaction(f, early, late) is not None
    # every counted reporter's window closed by the end of its breadth day, never later
    rx = F.reporter_reactions(_index(), filings, frames)
    day = pd.DatetimeIndex(rx["closed_at"]).normalize()
    assert (pd.DatetimeIndex(rx["closed_at"]) <= day + pd.Timedelta(days=1)).all()
    # a reporter filed on the breadth day itself (window closes the NEXT day) changes nothing
    # on that day
    b0 = F.daily_breadth(rx, "share_up", 1)
    d = FILE_DAYS[10] + pd.offsets.BDay(1)
    late_row = {"tickers": ["LATE"], "cik": "9", "filed": str(d.date()), "accepted": ""}
    more = dict(frames, LATE_SYM=_reporter(d, 0.5))
    F_t = F.ticker_cfd()
    F_t["LATE"] = "LATE_SYM"
    import unittest.mock as um
    with um.patch.object(F, "ticker_cfd", lambda: F_t):
        b1 = F.daily_breadth(F.reporter_reactions(_index(), [*filings, late_row], more),
                             "share_up", 1)
    day_d = pd.Timestamp(d).tz_localize("UTC")
    assert b0.loc[day_d, "n"] == b1.loc[day_d, "n"]
    assert b0.loc[day_d, "breadth"] == b1.loc[day_d, "breadth"]


# ---------------------------------------------------------------------------- 3. prior z
def test_the_z_score_reads_only_prior_days(book):
    z1 = F.prior_z(pd.Series(np.r_[np.sin(np.arange(30.0)), 0.9]), 10)
    z2 = F.prior_z(pd.Series(np.r_[np.sin(np.arange(30.0)), 1e9]), 10)
    assert z1.iloc[:-1].equals(z2.iloc[:-1])
    assert len(z1) == 31 - 10                    # the first `window` days have no prior
    # a later extreme day moves no event that came before it
    filings, frames = book
    d = _index()
    a = F.family_earnings_breadth(d, move="up", min_abs=3.0, direction="long", filings=filings,
                                  reporters=frames, hold_bars=4)
    later = [r for r in filings if r["filed"] >= str(NEG_DAY.date())]
    frames2 = dict(frames)
    for r in later:                              # rewrite every reaction from NEG_DAY onward
        sym = F.ticker_cfd()[r["tickers"][0]]
        frames2[sym] = _reporter(pd.Timestamp(r["filed"]), 0.2)
    b = F.family_earnings_breadth(d, move="up", min_abs=3.0, direction="long", filings=filings,
                                  reporters=frames2, hold_bars=4)
    cut = _complete(NEG_DAY) - pd.Timedelta(days=1)
    assert [s.time for s in a if s.time < cut] == [s.time for s in b if s.time < cut]


# ----------------------------------------------------------------------- 4. min_reporters
def test_fewer_than_min_reporters_is_no_event(monkeypatch):
    k = FILE_DAYS.index(POS_DAY)
    filings, frames, tmap = _book(skip=frozenset((k, i) for i in range(11)))   # 9 that day
    monkeypatch.setattr(F, "ticker_cfd", lambda: tmap)
    d = _index()
    sig = F.family_earnings_breadth(d, move="up", min_abs=3.0, direction="long",
                                    filings=filings, reporters=frames, hold_bars=4)
    assert all(s.time != _complete(POS_DAY) for s in sig)
    assert F.family_earnings_breadth(d, move="up", min_abs=3.0, direction="long",
                                     filings=filings, reporters=frames, hold_bars=4,
                                     min_reporters=9)[0].time == _complete(POS_DAY)
    assert F.family_earnings_breadth(d, move="up", min_abs=0.0, direction="long",
                                     filings=filings, reporters=frames,
                                     min_reporters=PER_DAY + 1) == []


# --------------------------------------------------------------------- 5. the two lanes
def test_no_share_symbol_is_ever_traded_or_a_cell(book):
    filings, frames = book
    from research import universe_policy as up
    assert up.is_equity("Apple")
    assert F.family_earnings_breadth(_index(), symbol="Apple", min_abs=0.0, direction="long",
                                     filings=filings, reporters=frames) == []
    from research import earnings_breadth_proposer as P
    from research import proposer_common as pc
    syms = P.index_symbols(pc.universe_meta())
    assert syms and set(syms) <= set(F.INDEX_SYMBOLS)
    assert not any(up.is_equity(s) for s in syms)
    assert all(up.lane(s) == up.HYPOTHESIS for s in syms)
    from side_channels.run_external_backtest import route_by_lane
    kept, rep = route_by_lane([{"symbol": s, "family": "earnings_breadth"} for s in syms]
                              + [{"symbol": "Apple", "family": "earnings_breadth"}])
    assert [c["symbol"] for c in kept] == syms and rep["routed_event"] == 1


# ----------------------------------------------------------------------------- 6. wiring
def test_the_family_and_its_proposer_are_wired():
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    from research import axis_registry, hourly_cycle, orthogonal_sweep
    assert ORTHOGONAL_FAMILIES["earnings_breadth"] is F.family_earnings_breadth
    assert "earnings_breadth" in FAMILY_INPUTS
    assert "earnings_breadth" in orthogonal_sweep.NOT_SOURCED_HERE
    assert axis_registry.FAMILY_TABLE["earnings_breadth"][0] == "trend_persistence"
    assert "earnings_breadth_proposer" in hourly_cycle.LEG_BUDGET_SEC
    assert "earnings_breadth_proposer" in hourly_cycle.LEG_DEPARTMENT
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "research/earnings_breadth_proposer.py" in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["earnings_breadth_proposer"] == "prediction"
    assert "desks/mt5/mt5desk/family_earnings_breadth.py" in (
        ROOT / "ops" / "money_closure.txt").read_text("utf-8").split()
    from libs.ops import capability_graph as cg
    assert any(n.name == "earnings_breadth_proposer" for n in cg.NODES)


def test_the_proposer_writes_its_report_and_parks_by_name(book, tmp_path, monkeypatch):
    filings, frames = book
    from research import earnings_breadth_proposer as P
    from research import proposer_common as pc
    monkeypatch.setattr(P, "REPORT", tmp_path / "EARNINGS_BREADTH_PROPOSER.json")
    # absent cache: UNMEASURED by name, never zero
    monkeypatch.setattr(F, "CACHE", tmp_path / "none")
    F._cached_filings.cache_clear()
    rep = P.run(budget_s=30, donate=False)
    doc = json.loads(P.REPORT.read_text("utf-8"))
    assert doc["status"] == rep["status"] == "UNMEASURED"
    assert doc["parked_reason"] == F.ABSENT and doc["tests_run"] == "UNMEASURED"
    # a cache and bars: the grid runs and every row is charged for the whole pass
    monkeypatch.setattr(F, "cached_filings", lambda: filings)
    monkeypatch.setattr(F, "_is_share", lambda s: s in frames)
    idx = _index()
    monkeypatch.setattr(pc, "bars", lambda s: frames.get(s) if s in frames else
                        (idx if s == "US500" else None))
    monkeypatch.setattr(P, "MIN_BARS", 500)
    monkeypatch.setattr(pc, "cost_frac", lambda s, m, c: 0.0001)
    from mt5desk import family_inputs
    monkeypatch.setattr(family_inputs, "bars_named", lambda s, like: frames.get(s))
    monkeypatch.setattr(pc, "screen", lambda d, sig, cost, unf: (
        {"t_gross": 3.0 + len(sig) / 100, "clears_cost": True, "n_independent": len(sig)}
        if sig else None))
    rep = P.run(budget_s=120, donate=False)
    doc = json.loads(P.REPORT.read_text("utf-8"))
    assert doc["status"] == "OK" and doc["reach"]["filings_8k_202"] == len(filings)
    assert set(doc["reach"]["index_symbols"]) <= set(F.INDEX_SYMBOLS)
    assert isinstance(doc["tests_run"], int) and 1 <= doc["tests_run"] <= 8
    assert all(r["symbol"] == "US500" for r in doc["proposals"])
    assert all(r["n_tests_sweep"] == doc["tests_run"] for r in doc["proposals"])
