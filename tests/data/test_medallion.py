"""Tests for the Bronze -> Silver -> Gold medallion builders."""

from __future__ import annotations

import pandas as pd
from tests.data.conftest import MONDAY, make_bars

from libs.data.lake import Layer, ParquetLake
from libs.data.medallion import build_bronze, build_gold, build_silver
from libs.data.timeframe import Timeframe


def test_bronze_persists_raw(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 20)
    build_bronze(lake, "XAUUSD", Timeframe.H1, df)
    read = lake.read_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1)
    assert len(read) == 20


def test_silver_dedupes_and_tags_session(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 20)
    with_dupe = pd.concat([df, df.iloc[[5]]]).sort_values("timestamp").reset_index(drop=True)
    build_bronze(lake, "XAUUSD", Timeframe.H1, with_dupe)
    silver, report = build_silver(lake, "XAUUSD", Timeframe.H1)
    assert len(silver) == 20  # duplicate removed
    assert "session" in silver.columns
    assert report.n_duplicates == 2


def test_gold_adds_log_return(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 20)
    build_bronze(lake, "XAUUSD", Timeframe.H1, df)
    build_silver(lake, "XAUUSD", Timeframe.H1)
    gold = build_gold(lake, "XAUUSD", Timeframe.H1)
    assert "log_return" in gold.columns
    assert gold["log_return"].iloc[0] == 0.0
    assert len(gold) == 20
    read = lake.read_bars(Layer.GOLD, "XAUUSD", Timeframe.H1)
    assert "log_return" in read.columns


def test_full_pipeline_crypto_includes_weekend(lake: ParquetLake) -> None:
    df = make_bars("BTCUSD", Timeframe.D1, MONDAY, 14)
    build_bronze(lake, "BTCUSD", Timeframe.D1, df)
    silver, report = build_silver(lake, "BTCUSD", Timeframe.D1)
    # crypto trades weekends, so a 14-day span has no missing bars
    assert report.n_missing == 0
    assert len(silver) == 14
