"""DuckDB integration — embedded OLAP over the Parquet lake (no server)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe


class DuckDBClient:
    """A thin DuckDB wrapper for querying Parquet directly."""

    def __init__(self, database: str = ":memory:") -> None:
        self._con = duckdb.connect(database)

    def query(self, sql: str) -> pd.DataFrame:
        """Run ``sql`` and return the result as a pandas DataFrame."""
        return self._con.execute(sql).df()

    def read_parquet(self, glob: str | Path) -> pd.DataFrame:
        """Read a parquet glob (hive-partitioned) into a DataFrame."""
        sql = (
            f"SELECT * FROM read_parquet('{Path(glob).as_posix()}', hive_partitioning=true) "
            "ORDER BY timestamp"
        )
        return self.query(sql)

    def query_lake(
        self, lake: ParquetLake, layer: Layer, symbol: str, timeframe: Timeframe
    ) -> pd.DataFrame:
        """Query a single lake partition tree, returning bars ordered by timestamp."""
        path = lake.path(layer, symbol, timeframe)
        glob = path / "**" / "*.parquet"
        df = self.read_parquet(glob)
        return df.drop(columns=[c for c in ("year", "month") if c in df.columns])

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> DuckDBClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
