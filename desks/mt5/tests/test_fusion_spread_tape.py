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
  2. a zero central value is WRITTEN only as an OBSERVED zero (2026-10-21) -- ticked bars, a
     family-wise Wilson day vote above 1/2, no contradicting M5 window -- and stamped as one;
     any other zero prices the spread leg at no cost on no evidence and keeps its old value;
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


# ---------------------------------------- 2. a zero is written only as an observed zero

def test_a_zero_central_value_short_of_an_observed_zero_is_not_written_and_is_named(tmp_path):
    """One day of zeros is one observation: it is not what the spread ALWAYS is."""
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


# ------------------------------------------------- 2b. the observed zero (2026-10-21)

def _days(n_days, *, zero_days=None, start="2026-06-01 00:00"):
    """`n_days` full 24h days of minute bars: the first `zero_days` quote 0 on 95% of their
    minutes (the rollover hour wide), the rest quote 3 points."""
    zero_days = n_days if zero_days is None else zero_days
    spreads: list[float] = []
    for d in range(n_days):
        day = [0.0] * 1368 + [40.0] * 72 if d < zero_days else [3.0] * 1440
        spreads.extend(day)
    return _frame(spreads, start=start)


def _live(n_days=20, zero_days=None, hours=(2, 9, 15, 22), start_day=1):
    """`n_days` UTC days of fresh hourly live samples, one per hour in `hours` (all four
    sessions by default); every sample of the first `zero_days` days quotes bid == ask."""
    zero_days = n_days if zero_days is None else zero_days
    out = {}
    for d in range(n_days):
        for h in hours:
            out[f"2026-07-{start_day + d:02d}T{h:02d}"] = 1 if d < zero_days else 0
    return out


LIVE = _live()


def test_the_day_floor_is_derived_from_the_family_wise_z_not_chosen():
    z = fst.zero_z(251)
    assert 3.5 < z < 3.6, "Bonferroni over this registry's 251 symbols at 5%"
    # every day voting zero still needs more than z^2 days for the Wilson bound to clear 1/2
    assert fst.wilson_lower(12, 12, z) < 0.5 < fst.wilson_lower(13, 13, z)


def test_an_observed_zero_is_measured_written_and_stamped(tmp_path):
    _write(tmp_path, "EURUSD", _days(20))
    row = fst.judge("EURUSD", fst.read_tape(tmp_path, "EURUSD"), {}, {}, {}, old=0.0,
                    n_tests=251, live_samples=LIVE)
    assert row["status"] == fst.MEASURED and row["new"] == 0.0 and row["zero_spread"] is True
    ev = row["zero_evidence"]
    assert ev["stamp"] == fst.ZERO_STAMP and ev["ticks_measured"] is True
    assert ev["days_full"] == 20 and ev["days_zero_median"] == 20
    assert ev["day_share_wilson_lower"] > 0.5 and ev["min_days_implied"] == 13
    assert ev["live_unit"] == "day" and ev["live_n"] == 20 and ev["live_zero"] == 20
    assert ev["live_hours"] == 80 and ev["live_hours_zero"] == 80
    assert ev["live_wilson_lower"] > 0.5
    assert ev["live_sessions"] == ["asia", "late", "london", "new_york"]
    assert row["direction"] == "unchanged", "an unstamped registry zero is stamped, not moved"
    assert fst.applicable(row)[0] == 0.0
    assert "commission" in row["why"] and "p99 40.0" in row["why"], "the tail is still published"


def test_twelve_zero_days_at_this_registrys_z_are_not_enough(tmp_path):
    _write(tmp_path, "SHORT", _days(12))
    row = fst.judge("SHORT", fst.read_tape(tmp_path, "SHORT"), {}, {}, {}, old=5.0,
                    n_tests=251)
    assert row["status"] == fst.UNMEASURED and row["new"] is None
    assert "Wilson lower bound" in row["why"] and "5.0" in row["why"]
    _write(tmp_path, "ENOUGH", _days(13))
    ok = fst.judge("ENOUGH", fst.read_tape(tmp_path, "ENOUGH"), {}, {}, {}, old=5.0,
                   n_tests=251, live_samples=LIVE)
    assert ok["status"] == fst.MEASURED and ok["new"] == 0.0


def test_a_median_of_zero_carried_by_a_minority_of_days_is_not_an_observed_zero(tmp_path):
    # 14 of 20 days zero: the bar median is 0, but the day vote's lower bound does not clear 1/2
    _write(tmp_path, "MIXED", _days(20, zero_days=14))
    tape = fst.read_tape(tmp_path, "MIXED")
    assert tape["p50"] == 0.0 and tape["days_zero_median"] == 14
    row = fst.judge("MIXED", tape, {}, {}, {}, old=3.0, n_tests=251)
    assert row["status"] == fst.UNMEASURED


def test_a_zero_with_no_tick_column_is_never_an_observed_zero(tmp_path):
    frame = _days(20).drop(columns=["tick_volume"])
    _write(tmp_path, "NOTICK", frame)
    tape = fst.read_tape(tmp_path, "NOTICK")
    assert tape["ticks_measured"] is False
    row = fst.judge("NOTICK", tape, {}, {}, {}, old=2.0, n_tests=251)
    assert row["status"] == fst.UNMEASURED and "tick_volume" in row["why"]


def test_a_longer_window_that_reads_a_positive_median_refutes_the_zero(tmp_path):
    _write(tmp_path, "UNSTABLE", _days(20))
    row = fst.judge("UNSTABLE", fst.read_tape(tmp_path, "UNSTABLE"),
                    {"status": fst.MEASURED, "p50": 4.0}, {}, {}, old=4.0, n_tests=251)
    assert row["status"] == fst.UNMEASURED and "M5 long window" in row["why"]


def test_an_observed_zero_below_a_positive_registry_value_is_a_cheapening_and_corroborated(
        tmp_path):
    _write(tmp_path, "GBPUSD", _days(20))
    row = fst.judge("GBPUSD", fst.read_tape(tmp_path, "GBPUSD"), {},
                    {"status": fst.MEASURED, "spread_pts": 0.0, "fresh": True}, {}, old=50.0,
                    n_tests=251, live_samples=LIVE)
    assert row["new"] == 0.0 and row["direction"] == "cheaper"
    assert row["corroboration"] == "CORROBORATED"
    contradicted = fst.judge("GBPUSD", fst.read_tape(tmp_path, "GBPUSD"), {},
                             {"status": fst.MEASURED, "spread_pts": 60.0, "fresh": True}, {},
                             old=50.0, n_tests=251, live_samples=LIVE)
    assert fst.applicable(contradicted)[0] is None, "a contradicted cheapening is still refused"


def test_a_zero_without_its_evidence_is_never_writable():
    row = {"status": fst.MEASURED, "new": 0.0, "why": "hand-made"}
    assert fst.applicable(row)[0] is None
    assert fst.applicable({**row, "zero_spread": True})[0] is None
    assert fst.applicable({**row, "zero_spread": True, "zero_evidence": {}})[0] == 0.0


# ------------------------------------------- 2c. the live confirmation and the family (v2.1)

def test_a_bar_zero_with_no_live_tick_is_unmeasured_never_a_pass(tmp_path):
    _write(tmp_path, "NOLIVE", _days(20))
    tape = fst.read_tape(tmp_path, "NOLIVE")
    row = fst.judge("NOLIVE", tape, {}, {}, {}, old=0.0, n_tests=251, live_samples={})
    assert row["status"] == fst.UNMEASURED and row["new"] is None
    assert "UNMEASURED live confirmation" in row["why"]
    assert row["zero_evidence"]["live_n"] == 0
    assert row["zero_evidence"]["live_status"] == fst.UNMEASURED
    # None is an UNREADABLE ledger: no counts at all, never a count of zero
    torn = fst.judge("NOLIVE", tape, {}, {}, {}, old=0.0, n_tests=251, live_samples=None,
                     live_ledger="UNMEASURED: the live ledger is unreadable (JSONDecodeError)")
    assert torn["status"] == fst.UNMEASURED and "unreadable" in torn["why"]
    ev = torn["zero_evidence"]
    assert ev["live_status"] == fst.UNMEASURED and ev["live_n"] is None
    assert ev["live_zero"] is None and ev["live_wilson_lower"] is None


def test_a_live_book_that_quotes_a_spread_most_of_the_time_refutes_the_bar_zero(tmp_path):
    _write(tmp_path, "LIVEMIN", _days(20))
    tape = fst.read_tape(tmp_path, "LIVEMIN")
    row = fst.judge("LIVEMIN", tape, {}, {}, {}, old=0.0, n_tests=251,
                    live_samples=_live(20, zero_days=8))
    assert row["status"] == fst.UNMEASURED and "live days" in row["why"]
    ev = row["zero_evidence"]
    assert (ev["live_n"], ev["live_zero"]) == (20, 8) and ev["live_wilson_lower"] < 0.5
    # even a unanimous live book is not enough at this z on 12 days (z^2 is 12.5); 13 is
    thin = fst.judge("LIVEMIN", tape, {}, {}, {}, old=0.0, n_tests=251,
                     live_samples=_live(12))
    assert thin["status"] == fst.UNMEASURED and "Wilson" in thin["why"]
    enough = fst.judge("LIVEMIN", tape, {}, {}, {}, old=0.0, n_tests=251,
                       live_samples=_live(13))
    assert enough["zero_spread"] is True


def test_the_live_unit_is_the_day_so_hours_of_one_day_are_one_vote(tmp_path):
    """THE AUDIT RULING (v2.1.1): twenty-four unanimous hours of ONE day, across every session,
    are one live day -- they confirm nothing at this z, where the hourly unit once read 24 votes."""
    _write(tmp_path, "ONEDAY", _days(20))
    tape = fst.read_tape(tmp_path, "ONEDAY")
    row = fst.judge("ONEDAY", tape, {}, {}, {}, old=0.0, n_tests=251,
                    live_samples=_live(1, hours=tuple(range(24))))
    ev = row["zero_evidence"]
    assert row["status"] == fst.UNMEASURED and ev["live_n"] == 1 and ev["live_hours"] == 24
    # forty hours over two days: still two votes
    two = fst.judge("ONEDAY", tape, {}, {}, {}, old=0.0, n_tests=251,
                    live_samples=_live(2, hours=tuple(range(20))))
    assert two["zero_evidence"]["live_n"] == 2 and two["status"] == fst.UNMEASURED


def test_a_day_votes_zero_only_on_a_strict_majority_of_its_hours():
    z = fst.zero_z(251)
    half = {"2026-07-01T02": 1, "2026-07-01T09": 1, "2026-07-01T15": 0, "2026-07-01T22": 0}
    assert fst.live_vote(half, z)["live_zero"] == 0, "a tie is not a zero day"
    more = {**half, "2026-07-01T15": 1}
    assert fst.live_vote(more, z)["live_zero"] == 1


def test_live_ticks_from_too_few_sessions_do_not_confirm(tmp_path):
    _write(tmp_path, "ONESESS", _days(20))
    row = fst.judge("ONESESS", fst.read_tape(tmp_path, "ONESESS"), {}, {}, {}, old=0.0,
                    n_tests=251, live_samples=_live(20, hours=(1, 3, 5, 6)))
    assert row["status"] == fst.UNMEASURED and "session" in row["why"]


def test_only_a_fresh_measured_book_is_a_live_sample():
    assert fst.live_sample({"status": fst.MEASURED, "fresh": True, "bid_eq_ask": True}) == 1
    assert fst.live_sample({"status": fst.MEASURED, "fresh": True, "bid_eq_ask": False}) == 0
    assert fst.live_sample({"status": fst.MEASURED, "fresh": True, "book_pts": 0.0}) == 1
    assert fst.live_sample({"status": fst.MEASURED, "fresh": False, "bid_eq_ask": True}) is None
    assert fst.live_sample({"status": fst.UNMEASURED, "fresh": True}) is None
    assert fst.live_sample({"status": fst.MEASURED, "fresh": True}) is None


def test_live_samples_are_one_per_hour_and_bounded():
    live = {"status": fst.MEASURED, "at": "2026-07-01T09:30:00+00:00",
            "symbols": {"A": {"status": fst.MEASURED, "fresh": True, "bid_eq_ask": True},
                        "B": {"status": fst.MEASURED, "fresh": False, "bid_eq_ask": True}}}
    one = fst.merge_live_samples({}, live, ["A", "B"])
    assert one == {"A": {"2026-07-01T09": 1}}, "a stale book is no sample"
    again = fst.merge_live_samples(one, {**live, "symbols": {"A": {
        "status": fst.MEASURED, "fresh": True, "bid_eq_ask": False}}}, ["A"])
    assert again == one, "the first reading of the hour stands"
    full = {"A": {f"2025-01-01T{i:05d}": 1 for i in range(fst.LIVE_KEEP_PER_SYMBOL)}}
    pruned = fst.merge_live_samples(full, live, ["A"])
    assert len(pruned["A"]) == fst.LIVE_KEEP_PER_SYMBOL and "2026-07-01T09" in pruned["A"]
    assert full["A"].get("2026-07-01T09") is None, "the input map is never mutated"


def _desk(root, n_registry=251):
    uni = root / "desks" / "mt5" / "data" / "universe"
    uni.mkdir(parents=True)
    reg = {f"S{i:03d}": {"median_spread_pts": 3.0} for i in range(n_registry - 1)}
    reg["EURUSD"] = {"median_spread_pts": 0.0}
    (uni / "universe.json").write_text(__import__("json").dumps(reg), "utf-8")
    return uni


def _ledger(root, samples):
    p = root / "desks" / "mt5" / "data" / fst.LIVE_SAMPLES_NAME
    p.write_text(__import__("json").dumps({"schema": fst.LIVE_SAMPLES_SCHEMA,
                                           "symbols": samples}), "utf-8")
    return p


def test_the_auditors_five_day_eurusd_probe_is_judged_against_the_whole_registry(tmp_path):
    """THE AUDIT REPRO (v2.1 must-fix 1). `--symbols EURUSD` once made the family one symbol:
    z = 1.645, and five zero days clear the Wilson bound (0.649 > 1/2). The family is the
    registry, so the same probe is judged at 251 and refused -- with live ticks in hand, so the
    day vote is the clause that refuses."""
    uni = _desk(tmp_path)
    _write(uni, "EURUSD", _days(5))
    _ledger(tmp_path, {"EURUSD": LIVE})
    assert fst.wilson_lower(5, 5, fst.zero_z(1)) > 0.5, "the hole the probe found"
    doc = fst.measure(tmp_path, ["EURUSD"], with_terminal=False)
    row = doc["by_symbol"]["EURUSD"]
    assert doc["n_tests"] == 251 and row["zero_evidence"]["n_tests"] == 251
    assert row["status"] == fst.UNMEASURED and row["new"] is None
    assert "Wilson lower bound" in row["why"] and "5 of 5" in row["why"]
    assert doc["observed_zero"] == []
    # the positive control: twenty zero days and the live book, at the same family, is stamped
    _write(uni, "EURUSD", _days(20))
    ok = fst.measure(tmp_path, ["EURUSD"], with_terminal=False)["by_symbol"]["EURUSD"]
    assert ok["zero_spread"] is True and ok["zero_evidence"]["n_tests"] == 251
    assert ok["zero_evidence"]["live_n"] == 20


def test_a_check_never_writes_the_live_ledger_and_the_hourly_pass_does(tmp_path, monkeypatch):
    uni = _desk(tmp_path, n_registry=3)
    _write(uni, "EURUSD", _days(20))
    _write(uni, "S000", _days(20, zero_days=0))
    snap = {"status": fst.MEASURED, "at": "2026-07-20T15:05:00+00:00", "symbols": {
        s: {"status": fst.MEASURED, "spread_pts": 0.0, "book_pts": 0.0, "bid_eq_ask": s != "S000",
            "tick_age_s": -10800} for s in ("EURUSD", "S000", "S001")}}
    monkeypatch.setattr(fst, "live_snapshot", lambda syms: __import__("copy").deepcopy(snap))
    monkeypatch.setattr(fst, "deals_from_terminal", lambda: [])
    ledger = tmp_path / "desks" / "mt5" / "data" / fst.LIVE_SAMPLES_NAME
    doc = fst.measure(tmp_path)
    assert not ledger.exists() and doc["live_samples"]["recorded"] is False
    doc = fst.measure(tmp_path, record_live=True)
    assert doc["live_samples"]["recorded"] is True
    kept = fst.load_live_samples(ledger)
    assert kept == {"EURUSD": {"2026-07-20T15": 1}}, "only the zero candidates are recorded"
    # one sample from one session is no confirmation, so the zero is not written yet
    assert doc["by_symbol"]["EURUSD"]["status"] == fst.UNMEASURED


# ------------------------------------------------ the live ledger on disk (v2.1.1 audit)

@pytest.mark.parametrize("body", [
    '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": {"2026-07-01T0',   # torn write
    "not json at all",
    '{"symbols": {"EURUSD": {"2026-07-01T02": 1}}}',                           # no schema
    '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": {"2026-07-01T02": 2}}}',
    '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": {"yesterday": 1}}}',
    '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": [1, 1, 1]}}',
    '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": {"2026-07-01T02": true}}}',
])
def test_a_torn_or_malformed_ledger_reads_unmeasured_never_as_no_evidence(tmp_path, body):
    p = tmp_path / fst.LIVE_SAMPLES_NAME
    p.write_text(body, "utf-8")
    samples, status = fst.read_live_ledger(p)
    assert samples is None and status.startswith("UNMEASURED")


def test_an_absent_ledger_is_absent_and_a_whole_one_measured(tmp_path):
    p = tmp_path / fst.LIVE_SAMPLES_NAME
    assert fst.read_live_ledger(p) == ({}, "ABSENT")
    fst.write_live_ledger(p, {"EURUSD": {"2026-07-01T02": 1}}, "2026-07-01T02:05:00+00:00")
    assert fst.read_live_ledger(p) == ({"EURUSD": {"2026-07-01T02": 1}}, "MEASURED")


def test_a_torn_ledger_judges_nothing_and_is_kept_beside_the_fresh_one(tmp_path, monkeypatch):
    """The ledger's bytes are torn: the pass's zero is UNMEASURED -- even though the bars and
    this pass's own fresh tick read zero -- and the torn bytes are kept, not overwritten."""
    uni = _desk(tmp_path, n_registry=3)
    _write(uni, "EURUSD", _days(20))
    torn = '{"schema": "live_quote_samples/1", "symbols": {"EURUSD": {"2026-07-0'
    ledger = _ledger(tmp_path, {})
    ledger.write_text(torn, "utf-8")
    snap = {"status": fst.MEASURED, "at": "2026-07-20T15:05:00+00:00", "symbols": {
        s: {"status": fst.MEASURED, "spread_pts": 0.0, "book_pts": 0.0, "bid_eq_ask": True,
            "tick_age_s": -10800} for s in ("EURUSD", "S000", "S001")}}
    monkeypatch.setattr(fst, "live_snapshot", lambda syms: __import__("copy").deepcopy(snap))
    monkeypatch.setattr(fst, "deals_from_terminal", lambda: [])
    doc = fst.measure(tmp_path, record_live=True)
    row = doc["by_symbol"]["EURUSD"]
    assert row["status"] == fst.UNMEASURED and "unreadable" in row["why"]
    assert row["zero_evidence"]["live_n"] is None
    assert doc["live_samples"]["status"].startswith("UNMEASURED")
    assert (ledger.parent / f"{ledger.name}.unreadable").read_text("utf-8") == torn
    assert fst.read_live_ledger(ledger) == ({"EURUSD": {"2026-07-20T15": 1}}, "MEASURED")


def test_the_ledger_write_is_atomic_and_retried_on_windows(tmp_path, monkeypatch):
    import os

    p = tmp_path / fst.LIVE_SAMPLES_NAME
    fst.write_live_ledger(p, {"A": {"2026-07-01T02": 1}}, None)
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError(13, "WinError 5: Access is denied")
        return real(src, dst)

    monkeypatch.setattr(fst.time, "sleep", lambda s: None)
    monkeypatch.setattr(fst.os, "replace", flaky)
    fst.write_live_ledger(p, {"A": {"2026-07-01T09": 0}}, None)
    assert len(calls) == 3 and fst.load_live_samples(p) == {"A": {"2026-07-01T09": 0}}
    monkeypatch.setattr(fst.os, "replace",
                        lambda s, d: (_ for _ in ()).throw(PermissionError(13, "held")))
    with pytest.raises(PermissionError):
        fst.write_live_ledger(p, {"A": {"2026-07-02T09": 1}}, None)
    assert fst.load_live_samples(p) == {"A": {"2026-07-01T09": 0}}, "the old ledger stands"
    assert sorted(x.name for x in tmp_path.iterdir()) == [fst.LIVE_SAMPLES_NAME], "no tmp left"


def test_the_ledger_holds_no_login_path_or_host_and_is_never_published(tmp_path):
    import json
    import socket

    p = tmp_path / fst.LIVE_SAMPLES_NAME
    fst.write_live_ledger(p, {"EURUSD": {"2026-07-01T02": 1}}, "2026-07-01T02:05:00+00:00")
    text = p.read_text("utf-8")
    assert set(json.loads(text)) == {"schema", "at", "symbols"}
    assert socket.gethostname() not in text and str(tmp_path) not in text
    assert "login" not in text and "/" not in text.replace("live_quote_samples/1", "")
    ignore = (_DESK.parents[1] / ".gitignore").read_text("utf-8").splitlines()
    assert "desks/mt5/data/live_quote_samples.json" in ignore
    assert "desks/mt5/data/live_quote_samples.json.*" in ignore
