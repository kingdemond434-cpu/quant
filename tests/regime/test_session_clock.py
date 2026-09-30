"""Broker stamps are EET/EEST under a UTC label; sessions are judged in real time (2026-09-30)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.regime import session_clock as sc


def _idx(*stamps: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(list(stamps), tz="UTC")


def test_a_stamp_is_three_hours_ahead_in_summer_and_two_in_winter() -> None:
    got = sc.server_to_utc(_idx("2026-07-15 10:00", "2026-01-15 10:00"))
    assert list(got.hour) == [7, 8]
    assert list(sc.utc_hours(_idx("2026-07-15 10:00", "2026-01-15 10:00"))) == [7, 8]


def test_naive_stamps_read_the_same_as_utc_labelled_ones() -> None:
    naive = pd.DatetimeIndex(["2026-07-15 10:00"])
    assert sc.server_to_utc(naive)[0] == sc.server_to_utc(_idx("2026-07-15 10:00"))[0]


def test_the_dst_edges_never_raise() -> None:
    # 09:30 stamp on the US spring-forward day is 02:30 New York, which does not exist; 08:30
    # stamp on the autumn day is 01:30 New York, which happens twice.
    got = sc.server_to_utc(_idx("2026-03-08 09:30", "2026-11-01 08:30"))
    assert len(got) == 2 and got.tz is not None


def test_the_clock_follows_us_daylight_dates_not_the_eus() -> None:
    # 2026-03-16: New York is on daylight time, Europe is not yet. The venue is UTC+3 (the week
    # opened Monday 00:00 stamp = 17:00 New York Sunday = 21:00 UTC), where EET would say UTC+2.
    assert int(sc.utc_hours(_idx("2026-03-16 00:00"))[0]) == 21
    # 2026-10-28: Europe is back on winter time, New York is not yet: still UTC+3.
    assert int(sc.utc_hours(_idx("2026-10-28 10:00"))[0]) == 7


def test_london_is_the_london_open_in_both_seasons() -> None:
    # 10:00 server is 07:00 UTC = 08:00 London in summer; 10:00 server in winter is 08:00 UTC
    # = 08:00 London. 09:00 server in summer is 07:00 London: before the open.
    mask = sc.in_session(_idx("2026-07-15 10:00", "2026-01-15 10:00", "2026-07-15 09:00"),
                         "london")
    assert mask is not None and mask.tolist() == [True, True, False]


def test_the_old_utc_reading_was_the_frankfurt_pre_open() -> None:
    # A stamp-hour 07:00 read as UTC is "london" in the old tables; in real time it is 04:00 UTC.
    stamp = _idx("2026-07-15 07:00")
    assert int(sc.utc_hours(stamp)[0]) == 4
    assert sc.in_session(stamp, "london").tolist() == [False]  # type: ignore[union-attr]


def test_aliases_and_unknown_sessions() -> None:
    idx = _idx("2026-07-15 16:00")                     # 13:00 UTC = 09:00 New York (EDT)
    assert sc.in_session(idx, "newyork").tolist() == [True]  # type: ignore[union-attr]
    assert sc.in_session(idx, "tokyo").tolist() == [False]  # type: ignore[union-attr]
    assert sc.in_session(idx, "overlap") is None
    assert isinstance(sc.in_session(idx, "ny"), np.ndarray)
