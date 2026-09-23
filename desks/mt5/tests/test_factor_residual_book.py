"""The book as a factor (Tier-1 audit G5): one sweep searches the residual of the LIVE BOOK.

The engine searched the residual against a peer-instrument panel only; the book's own daily P&L
-- the one factor the desk is unavoidably long -- was priced at SCORING time by
`alpha_fitness.delta_elog_term` and was never the search target. What is pinned: the book is read
from the allocator's artifact, then the shadow ledgers, then UNMEASURED with a reason; the book
return is joined ONE DAY LATE so a bar cannot see its own day; a planted book-orthogonal edge is
found; and a book row is charged as a trial but never donated, because nothing can rebuild it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import factor_residual_engine as eng  # noqa: E402

DAYS = 400


def _daily(n: int = DAYS, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(rng.normal(0.01, 0.05, n), index=idx)


def _isolate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(eng, "ALLOCATION", tmp_path / "pf_allocation.json")
    monkeypatch.setattr(eng, "SLEEVE_DAILY", tmp_path / "daily_r.parquet")
    monkeypatch.setattr(eng, "SHADOW_LEDGERS", tmp_path / "shadow")


# ------------------------------------------------------------------- where the book comes from
def test_the_allocators_artifact_is_the_book_when_it_exists(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    idx = pd.date_range("2024-01-01", periods=DAYS, freq="D", tz="UTC")
    rng = np.random.default_rng(2)
    mat = pd.DataFrame({"A": rng.normal(0, 0.05, DAYS), "B": rng.normal(0, 0.05, DAYS),
                        "UNFUNDED": rng.normal(0, 9.0, DAYS)}, index=idx)
    mat.to_parquet(eng.SLEEVE_DAILY)
    eng.ALLOCATION.write_text(json.dumps({"book": {"A": 0.2, "B": 0.1}}), "utf-8")
    book, why = eng.book_daily()
    assert book is not None and "pf_allocation.json" in why and "2 funded" in why
    expect = mat["A"] * 0.2 + mat["B"] * 0.1
    assert float((book - expect).abs().max()) == pytest.approx(0.0, abs=1e-12), (
        "a sleeve the allocator did not fund must not enter the book")


def test_the_shadow_ledgers_are_the_fallback_and_absence_is_named(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    book, why = eng.book_daily()
    assert book is None and "no book to residualise against" in why and "under 40 days" in why

    led = tmp_path / "shadow"
    led.mkdir()
    rows = [{"entry_time": str(pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=i)),
             "r_multiple": 0.1 * (i % 5 - 2)} for i in range(60)]
    (led / "ledger_XAUUSD_session_range_breakout_asia.json").write_text(json.dumps(rows), "utf-8")
    book, why = eng.book_daily()
    assert book is not None and "shadow ledger" in why and book.size == 60
    assert str(book.index.tz) == "UTC"


# --------------------------------------------------------------------------- the causal join
def test_a_bar_never_sees_its_own_days_book_return() -> None:
    daily = _daily(30)
    idx = pd.date_range("2024-01-01", periods=30 * 24, freq="1h", tz="UTC")
    on = eng.book_on(idx, daily)
    # Every bar of day D carries day D-1's value.
    for day in range(1, 30):
        stamp = idx[day * 24 + 7]
        assert on.loc[stamp] == pytest.approx(float(daily.iloc[day - 1])), stamp
    # The first day has nothing before it: NaN, dropped by the panel, never a zero.
    assert on.iloc[:24].isna().all()
    # And rewriting a later day cannot move an earlier bar.
    moved = daily.copy()
    moved.iloc[20:] += 99.0
    assert on.iloc[:20 * 24].equals(eng.book_on(idx, moved).iloc[:20 * 24])


def test_the_book_column_joins_the_panel_and_a_missing_book_refuses(tmp_path, monkeypatch
                                                                    ) -> None:
    n = eng.MIN_PANEL_BARS + 500
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(3)
    close = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))}, index=idx)
    cache = {"EURUSD": close}
    ds = eng.book_driver_sets(["EURUSD"])[0]
    assert ds.drivers == (eng.BOOK_DRIVER,) and ds.name == eng.BOOK_SET_NAME
    assert eng.panel(ds, cache, None) is None, "no book is no panel, never a zero column"
    ret = eng.panel(ds, cache, _daily(n // 24 + 2))
    assert ret is not None and eng.BOOK_DRIVER in ret.columns
    assert not ret[eng.BOOK_DRIVER].isna().any()
    # The peer path is untouched: a set with no BOOK driver never consults the book.
    from mt5desk.economic_drivers import DriverSet
    peer = DriverSet(target="EURUSD", name="x", drivers=("EURUSD",), why="w")
    assert eng.panel(peer, cache, None) is not None


# --------------------------------------------------------------------------- what it finds
def test_a_book_orthogonal_edge_is_measured_against_the_book() -> None:
    """The residual is taken against the book, so a symbol that IS the book has none left."""
    n = eng.MIN_PANEL_BARS + 2000
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(4)
    daily = _daily(n // 24 + 2, seed=7)
    hourly_book = eng.book_on(idx, daily)
    # A symbol whose return IS the (lagged) book plus noise: the causal beta explains it, so its
    # residual is noise -- the measurement the engine exists to make.
    r = 0.4 * hourly_book.fillna(0.0).to_numpy() + rng.normal(0, 0.001, n)
    close = pd.DataFrame({"close": 100 * np.exp(np.cumsum(r))}, index=idx)
    ds = eng.book_driver_sets(["EURUSD"])[0]
    ret = eng.panel(ds, {"EURUSD": close}, daily)
    assert ret is not None
    z = eng.residual_z(ret, ds)
    assert z.notna().sum() > 500
    rows = eng.measure(ds, ret, cost_frac=1e-5)
    assert rows, "the book set must produce measured rows"
    assert all(r["driver_set"] == eng.BOOK_SET_NAME for r in rows)
    assert all(r["drivers"] == [eng.BOOK_DRIVER] for r in rows)


def test_a_book_row_is_charged_as_a_trial_and_never_donated(tmp_path, monkeypatch) -> None:
    """A candidate naming BOOK could not be rebuilt by family_inputs.resolve, so it must not be
    donated -- but it WAS tested, so it stays in the deflation that every other row faces."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(eng, "REPORT", tmp_path / "factor_residual.json")
    monkeypatch.setattr(eng, "INTEL", tmp_path / "intel")

    from mt5desk import family_inputs
    got, why = family_inputs.resolve("EURUSD", "cross_asset_residual",
                                     {"factor_symbols": [eng.BOOK_DRIVER]}, None)
    assert got is None and "no factor bars" in why, (
        "if this ever resolves, a book row could be donated and this rule can be revisited")

    rows = [{"cell": "EURUSD.book_residual", "drivers": [eng.BOOK_DRIVER], "clears_cost": True,
             "t_gross": 9.0, "n_independent": 500, "side_mode": "revert", "horizon_bars": 24,
             "entry_z": 2.0, "net_per_trade": 0.01},
            {"cell": "EURUSD.triangle", "drivers": ["GBPUSD", "EURGBP"], "clears_cost": True,
             "t_gross": 9.0, "n_independent": 500, "side_mode": "revert", "horizon_bars": 24,
             "entry_z": 2.0, "net_per_trade": 0.01}]
    from research.multiplicity import deflate_t
    for r in rows:
        r["t_deflated_sweep"] = round(deflate_t(r["t_gross"], len(rows)), 3)
        r["proposed"] = bool(r["clears_cost"] and r["t_deflated_sweep"] > eng.PROPOSE_T
                             and r["n_independent"] >= eng.MIN_INDEPENDENT)
        if eng.BOOK_DRIVER in r["drivers"]:
            r["not_proposed_why"] = "x"
            r["proposed"] = False
    assert rows[1]["proposed"] is True and rows[0]["proposed"] is False
    rep = eng._book_report(rows, _daily(), "synthetic")
    assert rep["status"] == "MEASURED" and rep["tests_run"] == 1
    assert rep["clearing_the_bar"][0]["cell"] == "EURUSD.book_residual", (
        "a book row that clears the bar is PUBLISHED even though it is not donated")
    absent = eng._book_report([], None, "no book here")
    assert absent["status"] == "UNMEASURED" and absent["why"] == "no book here"
