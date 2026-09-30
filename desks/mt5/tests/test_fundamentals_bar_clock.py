"""Fundamentals are known at a TRUE UTC instant; bar stamps are the broker's clock (2026-09-30).

`fundamentals_pit.asof` compared SEC acceptance times (true UTC) with bar stamps (the venue's
New York + 7 h clock under a UTC label, 2-3 h ahead), so a filing accepted after the US close read
as known at a bar that closed before it existed. The conversion is `libs.regime.session_clock`
(PR #134). Every expected offset here is DERIVED from that helper, never from a box offset file."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import fundamentals_pit as fp  # noqa: E402

from libs.regime import session_clock  # noqa: E402


def _ns(*stamps: str) -> np.ndarray:
    return pd.DatetimeIndex(list(stamps), tz="UTC").as_unit("ns").asi8


def _broker_offset_h(day: str) -> int:
    """The venue's UTC offset on `day`, derived from the helper: a noon stamp minus its UTC."""
    stamp = pd.DatetimeIndex([f"{day} 12:00"], tz="UTC")
    return int((stamp[0] - session_clock.server_to_utc(stamp)[0]) / pd.Timedelta(hours=1))


@pytest.mark.parametrize("day,expected_broker_hour", [
    ("2026-01-15", 10),      # winter both sides: UTC+2
    ("2026-07-15", 11),      # summer both sides: UTC+3
    ("2026-03-16", None),    # US on daylight time, EU not yet: NY+7 differs from EET here
    ("2026-10-28", None),    # EU back on winter time, US not yet
])
def test_a_london_0800_utc_bar_is_the_broker_hour_the_helper_derives(day, expected_broker_hour):
    offset = _broker_offset_h(day)
    hour = 8 + offset
    if expected_broker_hour is not None:
        assert hour == expected_broker_hour
    else:
        # the DST-mismatch weeks: New York is on daylight time, so the venue is UTC+3 -- where an
        # EET/EEST clock would have said UTC+2
        assert offset == 3
    stamp = f"{day} {hour:02d}:00"
    assert session_clock.server_to_utc(pd.DatetimeIndex([stamp], tz="UTC")).hour[0] == 8
    got = fp.bar_stamps_to_utc_ns(_ns(stamp))
    assert list(pd.DatetimeIndex(got, tz="UTC").hour) == [8]
    london = session_clock.in_session(pd.DatetimeIndex([stamp], tz="UTC"), "london")
    assert london is not None and london.tolist() == [True]


@pytest.fixture
def one_filing(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "PIT_PATH", tmp_path / "sec_pit.parquet")
    monkeypatch.setattr(fp, "_CACHE", {"key": None, "by_symbol": {}})
    row = dict.fromkeys(fp.FIELDS, np.nan)
    row.update(eps_ttm=4.0, available=pd.Timestamp("2026-07-15 20:05", tz="UTC"),
               period_end=pd.Timestamp("2026-06-30", tz="UTC"))
    fp.write_table([("NVDA", pd.DataFrame([row]))])


def test_a_filing_accepted_after_the_us_close_is_not_known_at_an_earlier_bar(one_filing) -> None:
    # Summer: bar 22:00 = 19:00 UTC and bar 23:00 = 20:00 UTC, both before the 20:05 UTC
    # acceptance. Read raw as UTC, the 22:00 bar "knew" it -- the lookahead this pins.
    got = fp.asof("NVDA", _ns("2026-07-15 22:00", "2026-07-15 23:00", "2026-07-16 00:00"),
                  "eps_ttm")
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert got[2] == 4.0


def test_freshness_is_measured_on_the_same_true_utc_clock(one_filing) -> None:
    ok = fp.fresh("NVDA", _ns("2026-07-15 22:00", "2026-07-16 00:00"), 200.0)
    assert ok.tolist() == [False, True]


def test_an_empty_stamp_array_is_empty() -> None:
    assert fp.bar_stamps_to_utc_ns(np.asarray([], dtype="int64")).size == 0
