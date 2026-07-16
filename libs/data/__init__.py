"""``libs.data`` — MT5 ingestion, the Parquet medallion lake, DuckDB, and data quality."""

from __future__ import annotations

from libs.data.calendar import expected_index, is_open, session_of
from libs.data.duckdb_client import DuckDBClient
from libs.data.errors import DataError, MT5Error
from libs.data.instruments import (
    SUPPORTED_SYMBOLS,
    AssetClass,
    InstrumentSpec,
    get_spec,
    is_supported,
)
from libs.data.lake import Layer, ParquetLake
from libs.data.medallion import build_bronze, build_gold, build_silver
from libs.data.mt5_source import (
    BarSource,
    MT5BarSource,
    load_mt5_bars,
    normalize_timezone,
)
from libs.data.quality import (
    QualityReport,
    compute_quality_score,
    detect_duplicates,
    detect_gaps,
    detect_missing_bars,
    detect_spikes,
)
from libs.data.schema import BAR_COLUMNS, empty_bars, validate_bars
from libs.data.timeframe import Timeframe

__all__ = [  # noqa: RUF022  # grouped by concern
    # instruments / timeframe
    "AssetClass",
    "InstrumentSpec",
    "get_spec",
    "is_supported",
    "SUPPORTED_SYMBOLS",
    "Timeframe",
    # schema
    "BAR_COLUMNS",
    "empty_bars",
    "validate_bars",
    # ingestion
    "BarSource",
    "MT5BarSource",
    "load_mt5_bars",
    "normalize_timezone",
    # calendar
    "is_open",
    "expected_index",
    "session_of",
    # quality
    "QualityReport",
    "detect_duplicates",
    "detect_missing_bars",
    "detect_spikes",
    "detect_gaps",
    "compute_quality_score",
    # lake + duckdb + medallion
    "Layer",
    "ParquetLake",
    "DuckDBClient",
    "build_bronze",
    "build_silver",
    "build_gold",
    # errors
    "DataError",
    "MT5Error",
]
