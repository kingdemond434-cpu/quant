"""Tests for the Parquet lake and DuckDB integration."""

from __future__ import annotations

import numpy as np
from tests.data.conftest import MONDAY, make_bars

from libs.data.duckdb_client import DuckDBClient
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe


def test_write_read_roundtrip(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 30)
    lake.write_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1, df)
    read = lake.read_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1)
    assert len(read) == 30
    assert list(read["timestamp"]) == list(df["timestamp"])
    assert np.allclose(read["close"].to_numpy(), df["close"].to_numpy())


def test_partitioning_creates_hive_dirs(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 30)
    path = lake.write_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1, df)
    dirs = {p.name for p in path.glob("year=*")}
    assert dirs == {"year=2026"}
    assert any(path.rglob("month=1/*.parquet"))


def test_read_with_time_filter(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 30)
    lake.write_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1, df)
    start = df["timestamp"].iloc[5]
    end = df["timestamp"].iloc[10]
    read = lake.read_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1, start=start, end=end)
    assert len(read) == 6


def test_read_missing_returns_empty(lake: ParquetLake) -> None:
    read = lake.read_bars(Layer.BRONZE, "EURUSD", Timeframe.M5)
    assert read.empty


def test_duckdb_query_lake(lake: ParquetLake) -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 30)
    lake.write_bars(Layer.BRONZE, "XAUUSD", Timeframe.H1, df)
    with DuckDBClient() as client:
        result = client.query_lake(lake, Layer.BRONZE, "XAUUSD", Timeframe.H1)
    assert len(result) == 30


def test_duckdb_arbitrary_query() -> None:
    with DuckDBClient() as client:
        out = client.query("SELECT 1 AS one, 2 AS two")
    assert out["one"].iloc[0] == 1
    assert out["two"].iloc[0] == 2
