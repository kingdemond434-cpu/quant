"""Time exits are compared with the wall clock, so a broker bar stamp (New York + 7h, labelled
UTC by the frame builders) must become true UTC first -- 3h earlier in New York summer, 2h in
winter, and the right hour on either side of both US daylight-time changes."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import session_clock  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import scalp_exec as sx  # noqa: E402
from mt5desk.broker_clock import broker_to_utc  # noqa: E402

STAMPS = ["2026-01-14 10:00", "2026-07-14 10:00",
          # US spring-forward (2026-03-08) and fall-back (2026-11-01), both sides
          "2026-03-08 08:00", "2026-03-09 10:00", "2026-11-01 07:00", "2026-11-02 10:00",
          # EU changes, which the broker clock does NOT follow
          "2026-03-29 10:00", "2026-10-25 10:00"]


@pytest.mark.parametrize("stamp", STAMPS)
def test_it_matches_the_session_clock(stamp: str) -> None:
    ts = pd.Timestamp(stamp, tz="UTC")
    assert broker_to_utc(ts) == session_clock.server_to_utc([ts])[0]
    assert broker_to_utc(pd.Timestamp(stamp)) == broker_to_utc(ts)        # naive reads the same


def test_offset_is_three_hours_in_ny_summer_and_two_in_winter() -> None:
    assert broker_to_utc(pd.Timestamp("2026-07-14 10:00", tz="UTC")) == pd.Timestamp(
        "2026-07-14 07:00", tz="UTC")
    assert broker_to_utc(pd.Timestamp("2026-01-14 10:00", tz="UTC")) == pd.Timestamp(
        "2026-01-14 08:00", tz="UTC")
    # Between the EU and US autumn changes (2026-10-25 .. 11-01) the broker is still +3.
    assert broker_to_utc(pd.Timestamp("2026-10-28 10:00", tz="UTC")) == pd.Timestamp(
        "2026-10-28 07:00", tz="UTC")


def test_a_family_deadline_spans_its_bars_in_real_hours_across_the_fall_back() -> None:
    """A 12-bar H1 hold whose bars straddle the US fall-back: the deadline is the entry bar's
    true UTC plus 13 real hours, not the broker stamp plus 13 (which is 2-3h late)."""
    bar = pd.Timestamp("2026-10-31 20:00", tz="UTC")          # broker stamp, NY daylight time
    ttl = pd.Timestamp(dc.family_ttl_until(broker_to_utc(bar), 12))
    assert ttl == pd.Timestamp("2026-10-31 17:00", tz="UTC") + pd.Timedelta(hours=13)
    assert pd.Timestamp(dc.family_ttl_until(bar, 12)) - ttl == pd.Timedelta(hours=3)


def test_a_scalp_deadline_converts_the_forming_bar_then_adds() -> None:
    ft = pd.Timestamp("2026-03-08 08:45", tz="UTC")           # broker stamp after spring-forward
    got = pd.Timestamp(sx.ttl_deadline(broker_to_utc(ft), "M15", 6))
    assert got == broker_to_utc(ft) + pd.Timedelta(minutes=15 * 7)
    assert got == pd.Timestamp("2026-03-08 05:45", tz="UTC") + pd.Timedelta(minutes=105)
