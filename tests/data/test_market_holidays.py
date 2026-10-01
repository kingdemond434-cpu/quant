"""RustQuant's national calendars, compiled into desk data: three-valued, and keyed per leg."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from libs.data import market_holidays as M


def test_known_days_and_the_unmeasured_edges():
    assert M.is_holiday("GB", dt.date(2025, 12, 25)) is True
    assert M.is_holiday("US", dt.date(2025, 7, 3)) is False
    assert M.is_holiday("EU", dt.date(2024, 4, 1)) is True            # TARGET2 Easter Monday
    assert M.is_holiday("JP", dt.date(2019, 5, 1)) is True            # the desk's Reiwa override
    assert M.is_holiday("CN", dt.date(2025, 1, 29)) is None           # past the lunar table
    assert M.is_holiday("TR", dt.date(2025, 3, 31)) is None           # bayrams never listed
    assert M.is_holiday("ZZ", dt.date(2025, 3, 31)) is None
    assert M.is_holiday("GB", dt.date(2025, 3, 29)) is None           # a Saturday is not asked
    assert len(M.countries()) == 31


def test_symbol_legs():
    assert M.instrument_countries("USDJPY") == ("US", "JP")
    assert M.instrument_countries("EURSEK") == ("EU", None)
    assert M.instrument_countries("XAUUSD") == ("US", "GB")
    assert M.instrument_countries("US500") == ("US",)
    assert M.instrument_countries("JP225.cash") == ("JP",)
    assert M.instrument_countries("WHEAT") == ()


def test_features_mark_today_tomorrow_and_yesterday():
    i = pd.date_range("2025-12-23", periods=96, freq="h", tz="UTC")
    f = M.features(i, "GBPUSD").resample("D").first()
    assert f["hol_next"].tolist() == [0.0, 1.0, 1.0, 0.0]
    assert f["hol_home"].tolist() == [0.0, 0.0, 1.0, 1.0]
    assert f["hol_second"].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert f["hol_prev"].tolist() == [0.0, 0.0, 0.0, 1.0]
    sek = M.features(i, "EURSEK")
    assert sek["hol_second"].isna().all() and np.isnan(sek["hol_next"].iloc[0])
    assert (sek["hol_next"].dropna() == 1.0).all()                     # a known shut leg still says 1
