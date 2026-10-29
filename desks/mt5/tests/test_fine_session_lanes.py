"""The fine sessions the coverage tensor declares are real filters on both clocks and on every
producer's axis (2026-10-06): before, an unknown name filtered nothing and ran as `all`."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

from libs.regime import session_clock  # noqa: E402
from libs.research import coverage, family_firing  # noqa: E402
from mt5desk import family_call  # noqa: E402

FINE = ("tokyo_fix", "london_fix", "overlap")


def test_every_fine_session_has_a_window_on_both_clocks() -> None:
    for s in FINE:
        assert s in coverage.SESSIONS
        assert family_call.session_window(s) is not None
        assert s in session_clock.MARKET_SESSIONS
        assert s in family_firing.SESSION_NAMES


def test_the_server_window_contains_the_fix_in_both_seasons() -> None:
    """Server stamps are New York + 7h: the market-clock instant must fall inside the server
    window in summer and in winter."""
    cases = {"tokyo_fix": ("Asia/Tokyo", "09:55"), "london_fix": ("Europe/London", "16:00"),
             "overlap": ("America/New_York", "09:30")}
    for s, (tz, hhmm) in cases.items():
        lo, hi = family_call.WINDOWS[s] or (0, 0)
        for day in ("2026-07-15", "2026-01-15"):
            t = pd.Timestamp(f"{day} {hhmm}", tz=tz).tz_convert("America/New_York")
            server_hour = (t.tz_localize(None) + pd.Timedelta(hours=7)).hour
            assert lo <= server_hour < hi, (s, day, server_hour)
            stamp = pd.DatetimeIndex([t.tz_localize(None) + pd.Timedelta(hours=7)])
            assert bool(session_clock.in_session(stamp, s)[0]), (s, day)


def test_every_producer_axis_carries_them() -> None:
    from research import (axis_registry, breadth_sweep, miner_candidate_compiler, producer_breadth,
                          qd_frontier)
    for axis in (miner_candidate_compiler.SESSION_AXIS, breadth_sweep.SESSION_AXIS,
                 axis_registry.PROPOSABLE_SESSIONS, qd_frontier.PROPOSABLE_SESSIONS,
                 producer_breadth.SESSIONS):
        assert set(FINE) <= set(axis), axis


def test_the_broad_table_stays_the_partition_of_the_day() -> None:
    """A fine session sits inside a broad one; the organs that place a bar in ONE session read
    `SESSIONS` as the partition, so the fine windows live beside it, never in it."""
    assert set(family_call.SESSIONS) == {"asia", "london", "ny", "all"}
    for s in FINE:
        assert s not in family_call.SESSIONS
        assert family_call.WINDOWS[s] == family_call.FINE_SESSIONS[s]
