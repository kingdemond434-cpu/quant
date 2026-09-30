"""Fundamentals are known at a TRUE UTC instant; bar stamps are the broker's clock (2026-09-30).

`fundamentals_pit.asof` compared SEC acceptance times (true UTC) with bar stamps (EET/EEST under
a UTC label, 2-3 h ahead), so a filing accepted after the US close read as known at a bar that
closed before it existed. The conversion is `libs.regime.session_clock` (PR #134)."""
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


def test_a_london_0800_utc_bar_is_broker_1000_in_winter_and_1100_in_summer() -> None:
    winter = session_clock.server_to_utc(pd.DatetimeIndex(["2026-01-15 10:00"], tz="UTC"))
    summer = session_clock.server_to_utc(pd.DatetimeIndex(["2026-07-15 11:00"], tz="UTC"))
    assert (winter.hour[0], summer.hour[0]) == (8, 8)
    got = fp.bar_stamps_to_utc_ns(_ns("2026-01-15 10:00", "2026-07-15 11:00"))
    assert list(pd.DatetimeIndex(got, tz="UTC").hour) == [8, 8]
    london = session_clock.in_session(pd.DatetimeIndex(["2026-01-15 10:00", "2026-07-15 11:00"],
                                                       tz="UTC"), "london")
    assert london is not None and london.tolist() == [True, True]


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
