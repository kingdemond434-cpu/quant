"""Parquet medallion lake (Bronze / Silver / Gold).

Hive-partitioned by ``year``/``month`` under ``{base}/{layer}/{asset_class}/{symbol}/{tf}`` for
DuckDB partition pruning. Writes replace matching month partitions (corrections create new
partition contents); dataset-level immutability is enforced via the store's snapshot catalog.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from libs.data.instruments import get_spec
from libs.data.schema import BAR_COLUMNS, TIMESTAMP, empty_bars, validate_bars
from libs.data.timeframe import Timeframe

_PARTITION_COLS = ["year", "month"]


class Layer(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class ParquetLake:
    """Read/write bars to the partitioned Parquet lake."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def path(self, layer: Layer, symbol: str, timeframe: Timeframe) -> Path:
        spec = get_spec(symbol)
        return self.base_dir / layer.value / spec.asset_class.value / symbol / timeframe.value

    def write_bars(
        self, layer: Layer, symbol: str, timeframe: Timeframe, df: pd.DataFrame
    ) -> Path:
        """Write a bar frame to the lake, partitioned by year/month. Returns its path."""
        validate_bars(df)
        path = self.path(layer, symbol, timeframe)
        if df.empty:
            path.mkdir(parents=True, exist_ok=True)
            return path
        out = df.copy()
        out["year"] = out[TIMESTAMP].dt.year.astype("int32")
        out["month"] = out[TIMESTAMP].dt.month.astype("int32")
        table = pa.Table.from_pandas(out, preserve_index=False)
        # pyarrow>=24 ships partial type info, so these become `no-untyped-call` rather than
        # resolving to Any as they did when pyarrow was fully untyped. The module is already
        # declared untyped-third-party in pyproject's ignore_missing_imports list; this keeps
        # that same decision at the two call sites the new stubs reach.
        ds.write_dataset(  # type: ignore[no-untyped-call]
            table,
            base_dir=str(path),
            format="parquet",
            partitioning=_PARTITION_COLS,
            partitioning_flavor="hive",
            existing_data_behavior="delete_matching",
            basename_template="part-{i}.parquet",
        )
        return path

    def read_bars(
        self,
        layer: Layer,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Read bars back from the lake, sorted ascending, in the canonical schema (+ extras)."""
        path = self.path(layer, symbol, timeframe)
        if not path.exists() or not any(path.rglob("*.parquet")):
            return empty_bars()
        table = ds.dataset(  # type: ignore[no-untyped-call]
            str(path), format="parquet", partitioning="hive"
        ).to_table()
        df = table.to_pandas()
        df = df.drop(columns=[c for c in _PARTITION_COLS if c in df.columns])
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP], utc=True)
        df = df.sort_values(TIMESTAMP).reset_index(drop=True)
        if start is not None:
            df = df[df[TIMESTAMP] >= start]
        if end is not None:
            df = df[df[TIMESTAMP] <= end]
        df = df.reset_index(drop=True)
        ordered = [*BAR_COLUMNS, *[c for c in df.columns if c not in BAR_COLUMNS]]
        return validate_bars(df[ordered], require_sorted=True)
