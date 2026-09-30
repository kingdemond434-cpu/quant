"""THE FOUR PROPERTIES THAT MAKE A REPRICED REGISTRY SAFE TO READ.

The desk has repriced `median_spread_pts` from bars before and the statistic it used was wrong in
a way no test could have caught, because no test asserted anything about WHICH BARS. Measured
2026-09-24 on the trading box: the non-zero H1 median reads exactly 50.0 on AUDUSD, EURUSD and
GBPUSD and exactly 160.0 on AUDCHF and EURCAD -- one fixed spread per symbol on every bar from
the start of history to a single cut-over (2020-12-11 for FX, 2020-12-31 for the CFDs), present
in H1/H4/D1 and in no other timeframe. It is the broker's own pre-2021 history, served at a fixed
spread because the server did not record one then. After the cut-over this account quotes 0 points
on 80-96% of FX bars, so "non-zero bars only" DELETES the modern era and leaves the fixed block as
the majority of what survives: the exclusion selects for the placeholder.

So these pin the four decisions that stop that recurring, each against the shape that caused it:

  1. a zero-spread bar that CARRIED TICKS is kept -- dropping it is what produced 50.0;
  2. a zero central value is never WRITTEN -- a registry spread of 0.0 prices an instrument at no
     cost at all and lets a non-edge certify (nine symbols carried exactly that);
  3. a cheapening no other source corroborates is refused and named -- cheap is as serious as
     dear, and this is the direction that mints claims;
  4. the dispersion travels with the scalar -- 2 for twenty-three hours and 158 at the rollover
     is not described by either number alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pd = pytest.importorskip("pandas")
fst = pytest.importorskip("fusion_spread_tape")


def _frame(spreads, *, start="2026-06-01 00:00", freq="1min", ticks=None):
    idx = pd.date_range(start, periods=len(spreads), freq=freq, tz="UTC")
    return pd.DataFrame({"spread": [float(s) for s in spreads],
                         "tick_volume": list(ticks) if ticks is not None else [1] * len(spreads)},
                        index=idx)


def _write(tmp_path, sym, frame, timeframe="M1"):
    frame.to_parquet(tmp_path / f"{sym}_{timeframe}.parquet")
    return tmp_path


# ------------------------------------------------------------------ 1. the zero is a reading

def test_a_zero_spread_bar_with_ticks_is_kept_not_dropped(tmp_path):
    """The exclusion that produced 50.0 on three unrelated majors must not come back.

    Nine hundred bars at 0 and a hundred at 40 is a book that quotes nothing 90% of the time and
    widens at the rollover. Keeping the zeros gives a median of 0 (which is then refused as a
    WRITE, property 2); dropping them gives 40 -- the rollover price charged all day.
    """
    _write(tmp_path, "ZEROY", _frame([0.0] * 900 + [40.0] * 100))
    out = fst.read_tape(tmp_path, "ZEROY")
    assert out["status"] == fst.MEASURED
    assert out["n"] == 1000, "every ticked bar counts; none may be filtered for being cheap"
    assert out["p50"] == 0.0
    assert out["zero_frac"] == 0.9
    assert out["p99"] == 40.0, "the tail is the number the rollover sleeves actually pay"


def test_a_bar_with_no_ticks_is_absence_and_is_dropped(tmp_path):
    """A minute in which nothing quoted prices nothing. That is the one exclusion."""
    _write(tmp_path, "GAPPY", _frame([0.0] * 500 + [7.0] * 500,
                                     ticks=[0] * 500 + [3] * 500))
    out = fst.read_tape(tmp_path, "GAPPY")
    assert out["n_no_quote_bars"] == 500
    assert out["n"] == 500 and out["p50"] == 7.0


# ------------------------------------------------------- 2. a zero is measured, never written

def test_a_zero_central_value_is_never_written_and_the_symbol_is_named(tmp_path):
    _write(tmp_path, "ZEROY", _frame([0.0] * 900 + [40.0] * 100))
    row = fst.judge("ZEROY", fst.read_tape(tmp_path, "ZEROY"), {}, {}, {}, old=6.0)
    assert row["status"] == fst.UNMEASURED and row["new"] is None
    value, why = fst.applicable(row)
    assert value is None
    assert "no cost at all" in why and "6.0" in why, "the kept old value must be named"
    assert row["dispersion"]["p99"] == 40.0, "the tail is published even when nothing is written"


def test_a_positive_central_value_is_written(tmp_path):
    _write(tmp_path, "REAL", _frame([5.0] * 600 + [9.0] * 400))
    row = fst.judge("REAL", fst.read_tape(tmp_path, "REAL"), {}, {}, {}, old=3.0)
    assert row["status"] == fst.MEASURED and row["new"] == 5.0
    assert row["direction"] == "dearer"
    assert fst.applicable(row)[0] == 5.0


# ------------------------------------------- 3. cheap is as serious as dear: corroborate or name

def test_a_cheapening_every_other_source_contradicts_is_refused(tmp_path):
    """The tape may not lower a charge alone when everything else says the old one was fair."""
    _write(tmp_path, "CHEAP", _frame([2.0] * 1000))
    row = fst.judge("CHEAP", fst.read_tape(tmp_path, "CHEAP"),
                    stability={"status": fst.MEASURED, "p50": 300.0},
                    live={"status": fst.MEASURED, "spread_pts": 250.0, "fresh": True},
                    fills={"status": fst.MEASURED, "p50": 280.0, "n_matched": 9},
                    old=100.0)
    assert row["direction"] == "cheaper"
    assert row["corroboration"] == "CONTRADICTED"
    value, why = fst.applicable(row)
    assert value is None and "may not lower it alone" in why


def test_a_cheapening_one_source_corroborates_is_taken(tmp_path):
    _write(tmp_path, "CHEAP", _frame([2.0] * 1000))
    row = fst.judge("CHEAP", fst.read_tape(tmp_path, "CHEAP"),
                    stability={"status": fst.MEASURED, "p50": 3.0},
                    live={"status": fst.MEASURED, "spread_pts": 250.0, "fresh": True},
                    fills={}, old=100.0)
    assert row["corroboration"] == "CORROBORATED"
    assert row["contradicted_by"], "the source that disagreed is still named"
    assert fst.applicable(row)[0] == 2.0


def test_a_stale_live_quote_cannot_corroborate_or_contradict(tmp_path):
    """A snapshot taken while the venue is shut is the widest number of the week.

    It was going to write zeros onto the majors in one direction and block every share CFD
    correction in the other, so freshness gates it rather than the reading being trusted.
    """
    _write(tmp_path, "CHEAP", _frame([2.0] * 1000))
    row = fst.judge("CHEAP", fst.read_tape(tmp_path, "CHEAP"),
                    stability={}, fills={},
                    live={"status": fst.MEASURED, "spread_pts": 250.0, "fresh": False},
                    old=100.0)
    assert row["corroboration"] == "TAPE_ONLY"
    assert fst.applicable(row)[0] == 2.0


def test_a_widening_needs_no_corroboration(tmp_path):
    """A wider charge can only retire claims. Only the minting direction gets a second opinion."""
    _write(tmp_path, "WIDE", _frame([50.0] * 1000))
    row = fst.judge("WIDE", fst.read_tape(tmp_path, "WIDE"),
                    stability={"status": fst.MEASURED, "p50": 1.0}, live={}, fills={}, old=2.0)
    assert row["direction"] == "dearer" and "corroboration" not in row
    assert fst.applicable(row)[0] == 50.0


# -------------------------------------------------- 4. dispersion and the instrument's own window

def test_the_dispersion_and_the_hours_ride_with_the_scalar(tmp_path):
    """2 for twenty-three hours and 158 at the rollover is not one number."""
    rows = []
    for day in range(40):
        for hour in range(24):
            rows += [(158.0 if hour == 0 else 2.0)] * 2
    _write(tmp_path, "ROLL", _frame(rows, freq="30min"))
    out = fst.read_tape(tmp_path, "ROLL")
    assert {"p25", "p50", "p75", "p90", "p99"} <= set(out)
    assert out["p50"] == 2.0 and out["p99"] == 158.0
    assert out["by_server_hour"]["0"]["p50"] == 158.0
    assert out["by_server_hour"]["12"]["p50"] == 2.0
    assert "server wall clock" in out["clock"], "the hours are the venue's, and must say so"


def test_a_twentyfour_seven_instrument_keeps_its_weekends(tmp_path):
    """The crypto CFDs trade when the majors do not, so one session filter cannot serve both.

    The filter is `cost_surface`'s per-symbol session measure, so this needs no asset-class list:
    a Saturday is a full session for this instrument and simply does not exist for EURUSD.
    """
    idx = pd.date_range("2026-06-01", periods=60 * 24 * 8, freq="1min", tz="UTC")
    frame = pd.DataFrame({"spread": [1700.0] * len(idx), "tick_volume": [5] * len(idx)},
                         index=idx)
    _write(tmp_path, "CRYPTO", frame)
    out = fst.read_tape(tmp_path, "CRYPTO")
    days = {ts.date() for ts in idx}
    weekend = {d for d in days if d.weekday() >= 5}
    assert weekend, "the fixture must actually span a weekend for this to mean anything"
    assert out["days_full"] == len(days), "no day of a 24/7 instrument is a partial session"
    assert out["session_bars"] >= 1440


def test_too_few_bars_is_unmeasured_and_emits_no_number(tmp_path):
    """Absence never resolves to a clean verdict (L1.28a / WS-005)."""
    _write(tmp_path, "THIN", _frame([3.0] * 20))
    out = fst.read_tape(tmp_path, "THIN")
    assert out["status"] == fst.UNMEASURED and "p50" not in out
    row = fst.judge("THIN", out, {}, {}, {}, old=11.0)
    assert fst.applicable(row)[0] is None
    assert "11.0" in row["why"]


def test_a_symbol_with_no_tape_keeps_its_old_value(tmp_path):
    out = fst.read_tape(tmp_path, "ABSENT")
    assert out["status"] == fst.UNMEASURED and "no local M1 bars" in out["why"]


# ------------------------------------------------------------------ the venue's clock, measured

def test_live_freshness_is_measured_against_the_book_not_a_hardcoded_offset():
    """`tick.time` is the SERVER's wall clock, so every open symbol reads hours in the future.

    A hardcoded +3 would need finding and changing the day the desk re-homes its server. The
    baseline is the median age over the whole registry, so the offset cancels and only a symbol
    the rest of the book disagrees with reads stale.
    """
    live = {"status": fst.MEASURED, "symbols": {
        "OPEN1": {"status": fst.MEASURED, "tick_age_s": -10798},
        "OPEN2": {"status": fst.MEASURED, "tick_age_s": -10799},
        "OPEN3": {"status": fst.MEASURED, "tick_age_s": -10790},
        "SHUT": {"status": fst.MEASURED, "tick_age_s": 39974}}}
    base = fst.mark_fresh(live)
    assert base["status"] == fst.MEASURED
    assert base["n_fresh"] == 3
    assert live["symbols"]["OPEN1"]["fresh"] is True
    assert live["symbols"]["SHUT"]["fresh"] is False
    assert live["symbols"]["SHUT"]["staleness_s"] > 50_000


# --------------------------------------------------------- the disagreement is published, not hid

def test_a_material_disagreement_is_published_and_does_not_block_the_value(tmp_path):
    _write(tmp_path, "ARGUE", _frame([100.0] * 1000))
    row = fst.judge("ARGUE", fst.read_tape(tmp_path, "ARGUE"),
                    stability={"status": fst.MEASURED, "p50": 5.0},
                    live={"status": fst.MEASURED, "spread_pts": 9000.0, "fresh": True},
                    fills={"status": fst.MEASURED, "p50": 4.0, "n_matched": 20},
                    old=50.0)
    assert len(row["disagreements"]) == 3, "every disagreeing source is named, none averaged in"
    assert row["new"] == 100.0, "the tape is the source of record; a disagreement is a finding"
