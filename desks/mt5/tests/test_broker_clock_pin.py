"""THE PIN `broker_clock`'s docstring promises: one broker-stamp conversion on the desk.

`mt5desk.broker_clock.broker_to_utc` (the scalar form the gateway's stale-tick guard and time
exits use) must equal `libs.regime.session_clock.server_to_utc` (the vector form the research
tables use) at EVERY 15-minute broker stamp across 2026-2027 -- both US daylight-time changes of
each year, both repeat hours and both gap hours included. If someone forks the scalar form into
its own arithmetic, this goes red on the first stamp they get wrong.

It also checks both against an INDEPENDENT reading of the rule, built from `zoneinfo` alone (New
York wall time + 7 h), outside the two hours a year where the rule needs a tie-break, so the pin
cannot pass by both sides being wrong together. Nothing here reads the host's timezone.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime.session_clock import server_to_utc  # noqa: E402
from mt5desk.broker_clock import broker_epoch_to_utc, broker_to_utc  # noqa: E402

_NY = ZoneInfo("America/New_York")
_GRID = pd.date_range("2026-01-01 00:00", "2027-12-31 23:45", freq="15min")


def _independent(stamp: datetime) -> datetime | None:
    """The true UTC instant of a naive broker stamp by the venue rule alone, or None where New
    York's wall clock showed that time twice or never (the rule's tie-break hours)."""
    wall = stamp - timedelta(hours=7)
    first = wall.replace(tzinfo=_NY, fold=0)
    second = wall.replace(tzinfo=_NY, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None   # repeat hour (autumn) or gap hour (spring)
    return first.astimezone(UTC)


def test_the_grid_spans_two_full_years_of_quarter_hours() -> None:
    assert len(_GRID) == 730 * 96
    assert _GRID[0] == pd.Timestamp("2026-01-01") and _GRID[-1] == pd.Timestamp("2027-12-31 23:45")


def test_broker_to_utc_is_server_to_utc_at_every_quarter_hour_of_2026_and_2027() -> None:
    vector = server_to_utc(_GRID)
    mismatches = [(s, broker_to_utc(s), v) for s, v in zip(_GRID, vector, strict=True)
                  if broker_to_utc(s) != v]
    assert not mismatches, f"{len(mismatches)} stamps disagree, first: {mismatches[:3]}"


def test_a_utc_labelled_stamp_and_epoch_seconds_read_the_same_instant() -> None:
    vector = server_to_utc(_GRID)
    epochs = (_GRID - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    bad = [(s, v) for s, e, v in zip(_GRID, epochs, vector, strict=True)
           if broker_epoch_to_utc(int(e)) != v or broker_to_utc(s.tz_localize("UTC")) != v]
    assert not bad, f"{len(bad)} stamps disagree, first: {bad[:3]}"


def test_both_match_the_venue_rule_read_independently() -> None:
    vector = server_to_utc(_GRID)
    checked = tie_break = 0
    for s, v in zip(_GRID, vector, strict=True):
        want = _independent(s.to_pydatetime())
        if want is None:
            tie_break += 1
            continue
        checked += 1
        assert v.to_pydatetime() == want, (s, v, want)
    # two US changes a year, four 15-minute stamps in each tie-break hour, over two years
    assert tie_break == 2 * 2 * 4
    assert checked == len(_GRID) - tie_break


def test_the_offset_is_three_in_ny_daylight_time_and_two_in_standard_time() -> None:
    assert broker_to_utc(pd.Timestamp("2026-07-15 15:00")) == pd.Timestamp("2026-07-15 12:00Z")
    assert broker_to_utc(pd.Timestamp("2026-01-15 14:00")) == pd.Timestamp("2026-01-15 12:00Z")
    assert broker_to_utc(pd.Timestamp("2027-07-15 15:00")) == pd.Timestamp("2027-07-15 12:00Z")
    assert broker_to_utc(pd.Timestamp("2027-12-15 14:00")) == pd.Timestamp("2027-12-15 12:00Z")
