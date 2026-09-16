"""The forced-flow lane: does the calendar say the right dates, and does the family stay causal?

TWO LOAD-BEARING TESTS, and the rest is arithmetic around them.

`test_a_signal_never_reads_a_bar_after_itself` rewrites every bar strictly after a signal and
asserts the signal does not move. A forced-flow family is the easiest place on this desk to
smuggle in a look-ahead, because the window is genuinely knowable in advance and it is one small
step from "the window is knowable" to "so is what happened in it". If that test ever passes
vacuously the family is worthless.

`test_the_signature_is_the_one_the_forward_clock_calls` pins the call shape against a family that
already runs. `mt5desk.family_call.signals` passes `side=-1` for a short cell and OMITS `side`
for a long one; a family whose `side` is keyword-only, or has no default, works in exactly one of
those two branches and silently produces nothing in the other.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from inspect import Parameter, signature
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Signal  # noqa: E402
from mt5desk.families_orthogonal import family_turn_of_month  # noqa: E402
from mt5desk.family_call import accepts_side  # noqa: E402
from mt5desk.family_call import signals as call_signals  # noqa: E402
from mt5desk.family_forced_flow import (  # noqa: E402
    CLOCKS,
    FORCED_FLOW_DEFAULTS,
    MODES,
    calendar_windows,
    describe,
    family_forced_flow,
)

from research import forced_flow_calendar as C  # noqa: E402

FRIDAY = 4


# =============================================================================================
# CALENDAR -- the rules
# =============================================================================================

def test_third_friday_is_the_third_friday() -> None:
    """S&P/FTSE/STOXX reviews, quad witching and the CME roll all hang off this one rule."""
    assert [C.nth_weekday(2026, m, FRIDAY, 3) for m in (3, 6, 9, 12)] == [
        date(2026, 3, 20), date(2026, 6, 19), date(2026, 9, 18), date(2026, 12, 18)]
    # A month whose 1st IS a Friday must not be off by a week.
    assert C.nth_weekday(2026, 5, FRIDAY, 3) == date(2026, 5, 15)
    assert C.nth_weekday(2027, 1, FRIDAY, 3) == date(2027, 1, 15)


def test_the_cme_roll_is_the_thursday_before_the_third_friday() -> None:
    rows = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
            if e.kind == "futures_roll" and e.name.startswith("cme_equity_index")]
    assert [e.date for e in rows] == [
        date(2026, 3, 19), date(2026, 6, 18), date(2026, 9, 17), date(2026, 12, 17)]
    assert all(e.date.weekday() == 3 for e in rows)


def test_russell_reconstitution_is_the_last_friday_of_june() -> None:
    assert C.last_weekday(2026, 6, FRIDAY) == date(2026, 6, 26)
    (row,) = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
              if e.name.startswith("russell_reconstitution")]
    assert row.date == date(2026, 6, 26) and row.kind == "index_rebalance"


def test_last_business_day_skips_the_weekend() -> None:
    """31 May 2026 is a Sunday and 31 October is a Saturday: both must walk back to Friday."""
    assert C.last_business_day(2026, 5) == date(2026, 5, 29)
    assert C.last_business_day(2026, 10) == date(2026, 10, 30)
    assert C.last_business_day(2026, 3) == date(2026, 3, 31)     # a Tuesday, unchanged
    every = [C.last_business_day(2026, m) for m in range(1, 13)]
    assert all(d.weekday() < 5 for d in every)


def test_business_day_arithmetic_walks_both_ways() -> None:
    assert C.add_business_days(date(2026, 3, 20), 1) == date(2026, 3, 23)   # Fri -> Mon
    assert C.add_business_days(date(2026, 3, 23), -1) == date(2026, 3, 20)  # Mon -> Fri
    assert C.add_business_days(date(2026, 3, 20), 0) == date(2026, 3, 20)
    assert C.add_business_days(date(2026, 1, 30), -5) == date(2026, 1, 23)


def test_wti_expiry_is_three_business_days_before_the_25th() -> None:
    """25 Jan 2026 is a Sunday, so the rule falls back to Friday the 23rd first."""
    rows = {e.date for e in C.events(date(2026, 1, 1), date(2026, 3, 31))
            if e.name.startswith("wti_expiry")}
    assert date(2026, 1, 20) in rows       # Fri 23 Jan - 3 business days
    assert date(2026, 3, 20) in rows       # Wed 25 Mar - 3 business days


def test_comex_gold_rolls_into_first_notice_of_the_even_months() -> None:
    rows = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
            if e.name.startswith("comex_gold_roll")]
    assert len(rows) == 6                                     # Feb Apr Jun Aug Oct Dec delivery
    feb = next(e for e in rows if e.name.endswith("202602"))
    # First notice is the last business day of January (30th); the roll ends the day before.
    assert feb.date == date(2026, 1, 29)
    assert feb.window_start_utc.date() == date(2026, 1, 23)   # five business days earlier


# ---------------------------------------------------------------------------- DST, the one risk

def test_dst_a_march_and_an_october_month_end_fix_differ_by_an_hour() -> None:
    """THE WHOLE POINT OF USING zoneinfo. The WMR window is 15:00-16:30 LONDON all year.

    UK summer time in 2026 runs 29 March to 25 October, so the 31 March month end is in BST and
    the 30 October one is in GMT -- and the blueprint's quoted "15:00-16:30 UTC" is the GMT
    reading. A hard-coded UTC constant is an hour wrong for one of these two dates whichever
    constant is chosen.
    """
    rows = {e.date: e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
            if e.kind == "month_end"}
    march, october = rows[date(2026, 3, 31)], rows[date(2026, 10, 30)]
    assert march.window_start_utc == datetime(2026, 3, 31, 14, 0, tzinfo=ZoneInfo("UTC"))
    assert march.window_end_utc == datetime(2026, 3, 31, 15, 30, tzinfo=ZoneInfo("UTC"))
    assert october.window_start_utc == datetime(2026, 10, 30, 15, 0, tzinfo=ZoneInfo("UTC"))
    assert october.window_end_utc == datetime(2026, 10, 30, 16, 30, tzinfo=ZoneInfo("UTC"))
    # Both are 16:00 in London -- the local wall clock is what does not move.
    for row in (march, october):
        fix = row.window_end_utc - timedelta(minutes=30)
        assert fix.astimezone(ZoneInfo("Europe/London")).hour == 16


def test_dst_new_york_anchors_move_with_us_summer_time() -> None:
    """The FOMC statement is 14:00 ET: 18:00 UTC in EDT (the blueprint's figure) and 19:00 in
    EST. US summer time in 2026 runs 8 March to 1 November, so June and December disagree."""
    assert C.local_utc(date(2026, 6, 17), 14, 0, "America/New_York").hour == 18
    assert C.local_utc(date(2026, 12, 9), 14, 0, "America/New_York").hour == 19
    assert C.local_utc(date(2026, 3, 7), 14, 0, "America/New_York").hour == 19    # day before
    assert C.local_utc(date(2026, 3, 9), 14, 0, "America/New_York").hour == 18    # day after


def test_the_tokyo_fix_never_moves_because_japan_has_no_summer_time() -> None:
    hours = {C.local_utc(date(2026, m, 10), 9, 55, "Asia/Tokyo").hour for m in range(1, 13)}
    assert hours == {0}


# ------------------------------------------------------------------------------- central banks

def test_the_central_bank_table_is_sane() -> None:
    rows = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31)) if e.kind == "central_bank"]
    by_bank: dict[str, list] = {}
    for row in rows:
        by_bank.setdefault(row.name.split("_")[0], []).append(row)
    assert sorted(by_bank) == ["boe", "boj", "ecb", "fomc"]
    assert {k: len(v) for k, v in by_bank.items()} == {"boe": 8, "boj": 8, "ecb": 8, "fomc": 8}
    for row in rows:
        assert row.date.weekday() < 5, f"{row.name} lands at a weekend"
        assert C.VERIFY_BANK in row.source_rule, "a hard-coded date list must say so"
        assert row.window_end_utc > row.window_start_utc
        assert row.instruments and row.forced_actor and row.mechanism


def test_a_multi_day_meeting_is_dated_on_its_decision_day() -> None:
    """FOMC 27-28 January is one event on the 28th -- the statement day -- not two."""
    fomc = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
            if e.name.startswith("fomc")]
    assert [e.date for e in fomc] == [
        date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
        date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9)]
    assert "2026-01-27..28" in fomc[0].source_rule
    # 14:00 New York; the -30/+90 window therefore straddles 18:00 UTC in June.
    june = next(e for e in fomc if e.date == date(2026, 6, 17))
    assert june.window_start_utc.hour == 17 and june.window_end_utc.hour == 19


def test_a_year_with_no_published_table_is_reported_not_silently_empty() -> None:
    """L1.28a: absence of measurement must never read as a clean 'no meetings' verdict."""
    assert [e for e in C.events(date(2027, 1, 1), date(2027, 12, 31))
            if e.kind == "central_bank"] == []
    missing = C.unmeasured_years(date(2027, 1, 1), date(2027, 12, 31))
    assert set(missing) == {"FOMC", "ECB", "BOE", "BOJ"}
    assert all(v == [2027] for v in missing.values())


# ------------------------------------------------------------------------------------ holidays

def test_us_market_holidays_2026() -> None:
    assert sorted(C.us_market_holidays(2026)) == [
        date(2026, 1, 1),    # New Year's Day (Thu)
        date(2026, 1, 19),   # MLK, third Monday
        date(2026, 2, 16),   # Presidents', third Monday
        date(2026, 4, 3),    # Good Friday (Easter 5 April)
        date(2026, 5, 25),   # Memorial, last Monday
        date(2026, 6, 19),   # Juneteenth (Fri)
        date(2026, 7, 3),    # Independence Day observed -- the 4th is a Saturday
        date(2026, 9, 7),    # Labor, first Monday
        date(2026, 11, 26),  # Thanksgiving, fourth Thursday
        date(2026, 12, 25),  # Christmas (Fri)
    ]
    assert C.easter(2026) == date(2026, 4, 5)
    assert C.easter(2027) == date(2027, 3, 28)


def test_uk_bank_holidays_use_the_substitute_day_rule() -> None:
    table = C.uk_bank_holidays(2026)
    assert sorted(table) == [
        date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4),
        date(2026, 5, 25), date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28)]
    # Boxing Day 2026 is a Saturday, so it is observed on the Monday.
    assert "substitute" in table[date(2026, 12, 28)]
    assert all(d.weekday() < 5 for d in table)


def test_japan_golden_week_substitutes_a_sunday_holiday() -> None:
    table = C.japan_golden_week(2026)
    assert sorted(table) == [date(2026, 4, 29), date(2026, 5, 3), date(2026, 5, 4),
                             date(2026, 5, 5), date(2026, 5, 6)]
    # 3 May is a Sunday; 4 and 5 May are already holidays, so the substitute is the 6th.
    assert "substitute" in table[date(2026, 5, 6)]


def test_holidays_reach_the_calendar_as_events() -> None:
    rows = [e for e in C.events(date(2026, 1, 1), date(2026, 12, 31))
            if e.kind == "holiday_liquidity"]
    days = {e.date for e in rows}
    assert {date(2026, 7, 3), date(2026, 12, 28), date(2026, 5, 6)} <= days
    assert all(e.window_end_utc > e.window_start_utc for e in rows)


# ---------------------------------------------------------------------------- shape and mandate

def test_every_event_is_complete_and_inside_the_requested_range() -> None:
    start, end = date(2026, 2, 1), date(2026, 5, 31)
    rows = C.events(start, end)
    assert rows, "the rules produce events for any ordinary quarter"
    assert all(start <= e.date <= end for e in rows)
    assert all(e.kind in C.KINDS for e in rows)
    assert rows == sorted(rows, key=lambda e: (e.window_start_utc, e.kind, e.name))
    for e in rows:
        assert e.window_start_utc.tzinfo is not None and e.window_end_utc.tzinfo is not None
        assert e.window_end_utc > e.window_start_utc
        assert e.name and e.forced_actor and e.mechanism and e.source_rule
        assert isinstance(e.instruments, tuple)
    assert C.events(date(2026, 5, 1), date(2026, 2, 1)) == []


def test_no_event_names_an_instrument_outside_the_hypothesis_lane() -> None:
    """MT5 UNIVERSE MANDATE + the 2026-09-06 lane order: forced flow is a DISCOVERY source, so a
    single-name equity may never appear in it, and neither may a symbol Fusion does not list."""
    policy = pytest.importorskip("research.universe_policy")
    named = {s for e in C.events(date(2026, 1, 1), date(2026, 12, 31)) for s in e.instruments}
    assert named, "the bundles resolved to nothing -- the registry did not load"
    offenders = [s for s in named if not policy.may_hypothesise(s)]
    assert offenders == [], f"event-lane or unclassified symbols leaked in: {offenders}"


def test_pattern_rows_say_they_are_a_pattern() -> None:
    rows = C.events(date(2026, 1, 1), date(2026, 12, 31))
    for kind in ("bond_auction", "usda"):
        chosen = [e for e in rows if e.kind == kind]
        assert chosen
        assert all(C.VERIFY_SCHEDULE in e.source_rule for e in chosen)


# --------------------------------------------------------------------------------------- write

def test_write_produces_the_declared_artifact(tmp_path: Path) -> None:
    out = tmp_path / "forced_flow_calendar.json"
    payload = C.write(out, days_ahead=120, days_back=400, today=date(2026, 6, 30))
    assert out.exists()
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(payload, default=str))
    assert set(on_disk) >= {"generated_at", "rules_version", "n_events", "by_kind", "events"}
    assert on_disk["rules_version"] == C.RULES_VERSION
    assert on_disk["n_events"] == len(on_disk["events"]) > 0
    assert sum(on_disk["by_kind"].values()) == on_disk["n_events"]
    assert set(on_disk["by_kind"]) == set(C.KINDS)
    assert on_disk["range"] == {"start": "2025-05-26", "end": "2026-10-28",
                                "days_back": 400, "days_ahead": 120}
    row = on_disk["events"][0]
    assert set(row) == {"date", "kind", "name", "window_start_utc", "window_end_utc",
                        "instruments", "forced_actor", "mechanism", "source_rule"}


def test_the_cli_reports_counts_by_kind(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert C.main(["--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "n_events=" in dry and "month_end" in dry and "nothing written" in dry
    out = tmp_path / "cal.json"
    assert C.main(["--path", str(out)]) == 0
    assert out.exists() and f"wrote {out}" in capsys.readouterr().out


# =============================================================================================
# FAMILY
# =============================================================================================

#: A March month end: the WMR window is 14:00-15:30 UTC on Tuesday 31 March 2026 (BST).
MARCH_FIX_START = pd.Timestamp("2026-03-31 14:00", tz="UTC")
MARCH_FIX_END = pd.Timestamp("2026-03-31 15:30", tz="UTC")


def _bars(n: int = 24 * 12, seed: int = 11, start: str = "2026-03-25") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o,
                         "high": np.maximum(o, close) * 1.002,
                         "low": np.minimum(o, close) * 0.998,
                         "close": close}, index=idx)


def _ramp(direction: int, n: int = 24 * 12, start: str = "2026-03-25") -> pd.DataFrame:
    """A deterministic monotone path, so the direction a mode picks is not a coin flip."""
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    close = 100 + direction * 0.05 * np.arange(n, dtype=float)
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) + 0.02,
                         "low": np.minimum(o, close) - 0.02, "close": close}, index=idx)


def test_signals_fall_only_inside_the_pre_flow_window() -> None:
    sigs = family_forced_flow(_bars(), 1, event_kind="month_end", mode="pre_flow",
                              window_before_min=60)
    assert sigs, "a March month end is inside the sample and must produce signals"
    for s in sigs:
        assert MARCH_FIX_START - pd.Timedelta(minutes=60) <= s.time < MARCH_FIX_START


def test_signals_fall_only_inside_the_post_flow_window() -> None:
    sigs = family_forced_flow(_bars(), 1, event_kind="month_end", mode="post_flow_fade",
                              window_after_min=90)
    assert sigs
    for s in sigs:
        assert MARCH_FIX_END < s.time <= MARCH_FIX_END + pd.Timedelta(minutes=90)


def test_a_wider_window_admits_strictly_more_bars_and_a_zero_one_admits_none() -> None:
    narrow = family_forced_flow(_bars(), 1, window_before_min=60)
    wide = family_forced_flow(_bars(), 1, window_before_min=300)
    assert {s.time for s in narrow} < {s.time for s in wide}
    assert family_forced_flow(_bars(), 1, window_before_min=0) == []


def test_pre_flow_follows_the_prior_three_bar_drift() -> None:
    assert {s.side for s in family_forced_flow(_ramp(+1), 1, mode="pre_flow")} == {1}
    assert {s.side for s in family_forced_flow(_ramp(-1), 1, mode="pre_flow")} == {-1}


def test_post_flow_fade_trades_against_the_window_move() -> None:
    assert {s.side for s in family_forced_flow(_ramp(+1), 1, mode="post_flow_fade")} == {-1}
    assert {s.side for s in family_forced_flow(_ramp(-1), 1, mode="post_flow_fade")} == {1}


def test_side_minus_one_is_the_mirror_hypothesis() -> None:
    """`side` is a polarity, not a direction: -1 tests the opposite claim on the same bars."""
    base = family_forced_flow(_bars(), 1, mode="pre_flow")
    mirror = family_forced_flow(_bars(), -1, mode="pre_flow")
    assert [s.time for s in base] == [s.time for s in mirror]
    assert [s.side for s in base] == [-s.side for s in mirror]


def test_stops_and_targets_sit_on_the_right_sides_of_the_entry() -> None:
    for mode in MODES:
        for s in family_forced_flow(_bars(), 1, mode=mode, stop_atr=1.0, target_atr=1.5):
            assert s.side in (1, -1)
            assert (s.target - s.stop) * s.side > 0
            assert s.tag.startswith("forced_flow.month_end.")
            assert s.ttl_bars > 0


def test_entry_is_at_the_next_open_like_every_other_family() -> None:
    for s in family_forced_flow(_bars(), 1):
        assert s.trigger is None and s.wait_bars == 1


def test_a_kind_with_no_event_in_the_sample_produces_nothing() -> None:
    """March 2026 holds no Russell reconstitution and no quad witching."""
    assert family_forced_flow(_bars(), 1, event_kind="index_rebalance") == []


def test_bad_parameters_refuse_rather_than_guess() -> None:
    assert family_forced_flow(_bars(), 1, mode="whatever") == []
    assert family_forced_flow(_bars(), 1, clock="gmt") == []
    assert family_forced_flow(_bars(), 0) == []
    assert family_forced_flow(pd.DataFrame(), 1) == []
    assert family_forced_flow(_bars().head(4), 1) == []
    assert family_forced_flow(_bars(), 1, event_kind="not_a_kind") == []


def test_the_symbol_filter_uses_the_events_own_instrument_list() -> None:
    assert family_forced_flow(_bars(), 1, symbol="EURUSD")
    assert family_forced_flow(_bars(), 1, symbol="NOT_A_SYMBOL") == []


def test_the_utc_clock_shifts_the_window_into_the_bars_frame() -> None:
    """The bar index is broker time wearing a UTC tzinfo. `clock="utc"` moves the window by the
    measured offset; `clock="bars"` leaves it alone, and the two must not agree."""
    bar_clock = pytest.importorskip("libs.research.bar_clock")
    if not bar_clock.offsets():
        pytest.skip("no measured bar clock on this tree: the conversion is UNMEASURED")
    plain = family_forced_flow(_bars(), 1, clock="bars")
    moved = family_forced_flow(_bars(), 1, clock="utc")
    assert plain
    assert {s.time for s in plain} != {s.time for s in moved}


# ------------------------------------------------------------------------------- THE LEAK GUARD

def test_a_signal_never_reads_a_bar_after_itself() -> None:
    """Rewrite every bar strictly after a signal; the signal must not move by a tick.

    This is the property the whole lane lives or dies on. Using a RULE-DERIVED window is legal
    because it was computable years ahead -- using anything the window's bars did, before they
    exist, is not.
    """
    for mode in MODES:
        bars = _bars()
        sigs = family_forced_flow(bars, 1, mode=mode)
        assert sigs, mode
        cut = sigs[0].time
        tampered = bars.copy()
        after = tampered.index > cut
        for col in ("open", "high", "low", "close"):
            tampered.loc[after, col] = tampered.loc[after, col] * 3.0
        again = family_forced_flow(tampered, 1, mode=mode)
        before = [(s.time, s.side, s.stop, s.target) for s in sigs if s.time <= cut]
        still = [(s.time, s.side, s.stop, s.target) for s in again if s.time <= cut]
        assert before == still, f"{mode} moved when bars after the signal were rewritten"


def test_truncating_the_sample_at_the_signal_keeps_the_signal() -> None:
    """The live counterpart of the test above: at decision time no later bar exists at all."""
    bars = _bars()
    for mode in MODES:
        sigs = family_forced_flow(bars, 1, mode=mode)
        assert sigs, mode
        first = sigs[0]
        pos = int(bars.index.get_loc(first.time))
        # +2 keeps the NEXT-OPEN bar the entry needs, and nothing beyond it.
        short = family_forced_flow(bars.iloc[:pos + 2], 1, mode=mode)
        assert [(s.time, s.side, s.stop, s.target) for s in short][:1] == [
            (first.time, first.side, first.stop, first.target)]


# ------------------------------------------------------------------------------ THE CALL SHAPE

def test_the_signature_is_the_one_the_forward_clock_calls() -> None:
    params = list(signature(family_forced_flow).parameters.values())
    assert [p.name for p in params[:2]] == ["bars", "side"]
    assert all(p.kind is Parameter.POSITIONAL_OR_KEYWORD for p in params[:2])
    assert params[1].default == 1, "family_call omits `side` for a long cell"
    assert all(p.kind is Parameter.KEYWORD_ONLY for p in params[2:])
    assert accepts_side(family_forced_flow) is True
    # Both branches of the clock's own call shape must work.
    bars = _bars()
    assert call_signals(family_forced_flow, bars, side=1, params={"mode": "pre_flow"})
    assert call_signals(family_forced_flow, bars, side=-1, params={"mode": "pre_flow"})


def test_it_returns_exactly_what_an_existing_family_returns() -> None:
    """Called on the same bars as `family_turn_of_month` -- the calendar family this one mirrors
    -- the two must be indistinguishable to the engine."""
    bars = _bars()
    mine = family_forced_flow(bars, 1)
    theirs = family_turn_of_month(bars)
    assert isinstance(mine, list) and isinstance(theirs, list)
    assert mine and theirs
    assert {type(s) for s in mine} == {type(s) for s in theirs} == {Signal}
    fields = ("time", "side", "stop", "target", "ttl_bars", "tag", "trigger", "wait_bars")
    for a, b in zip(mine, theirs, strict=False):
        for f in fields:
            assert type(getattr(a, f)) is type(getattr(b, f)), f
    assert all(isinstance(s.time, pd.Timestamp) and s.time.tzinfo is not None for s in mine)


def test_the_defaults_table_matches_the_signature() -> None:
    declared = {p.name: p.default for p in signature(family_forced_flow).parameters.values()
                if p.default is not Parameter.empty and p.name != "side"}
    assert declared == FORCED_FLOW_DEFAULTS


def test_describe_states_all_three_parts_of_the_claim() -> None:
    text = describe()
    for part in ("FORCED PARTICIPANT", "TIME WINDOW", "OBSERVABLE CONSTRAINT"):
        assert part in text
    assert "pre_flow" in text and "post_flow_fade" in text
    assert set(MODES) == {"pre_flow", "post_flow_fade"}
    assert set(CLOCKS) == {"bars", "utc"}


def test_the_family_reads_the_written_artifact(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """The artifact is preferred over recomputation, so a scheduled leg's output is what trades."""
    import mt5desk.family_forced_flow as fam
    out = tmp_path / "forced_flow_calendar.json"
    C.write(out, days_ahead=30, days_back=30, today=date(2026, 3, 31))
    monkeypatch.setattr(fam, "CALENDAR_PATH", out)
    windows = calendar_windows("month_end", date(2026, 3, 1), date(2026, 3, 31))
    assert [w[0] for w in windows] == [MARCH_FIX_START]
    assert fam.family_forced_flow(_bars(), 1, mode="pre_flow")
    # An artifact that holds nothing for the kind falls back to the rules rather than going dark.
    monkeypatch.setattr(fam, "CALENDAR_PATH", tmp_path / "absent.json")
    assert fam.family_forced_flow(_bars(), 1, mode="pre_flow")
