"""Medallion builders: Bronze (raw) -> Silver (clean) -> Gold (analysis-ready).

* **Bronze** persists raw bars exactly as received (after epoch -> UTC).
* **Silver** deduplicates, sorts, drops broken rows, and tags the trading session.
* **Gold** adds analysis-ready derived columns (log returns). Feature engineering proper
  lives in Stage 6; Gold here is the minimal analysis-ready surface.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.data.calendar import session_of
from libs.data.lake import Layer, ParquetLake
from libs.data.quality import QualityReport, compute_quality_score
from libs.data.schema import OHLC, TIMESTAMP, validate_bars
from libs.data.timeframe import Timeframe


def build_bronze(
    lake: ParquetLake, symbol: str, timeframe: Timeframe, raw_bars: pd.DataFrame
) -> pd.DataFrame:
    """Persist canonical raw bars to the Bronze layer, unmodified."""
    validate_bars(raw_bars, require_sorted=True)
    lake.write_bars(Layer.BRONZE, symbol, timeframe, raw_bars)
    return raw_bars


def build_silver(
    lake: ParquetLake, symbol: str, timeframe: Timeframe
) -> tuple[pd.DataFrame, QualityReport]:
    """Clean Bronze into Silver and return ``(silver_bars, quality_report_on_bronze)``."""
    bronze = lake.read_bars(Layer.BRONZE, symbol, timeframe)
    report = compute_quality_score(bronze, symbol, timeframe)

    silver = (
        bronze.dropna(subset=list(OHLC))
        .drop_duplicates(subset=TIMESTAMP, keep="last")
        .sort_values(TIMESTAMP)
        .reset_index(drop=True)
    )
    silver["session"] = [session_of(ts) for ts in silver[TIMESTAMP]]
    lake.write_bars(Layer.SILVER, symbol, timeframe, silver)
    return silver, report


def build_gold(lake: ParquetLake, symbol: str, timeframe: Timeframe) -> pd.DataFrame:
    """Build the analysis-ready Gold layer from Silver (adds log returns)."""
    silver = lake.read_bars(Layer.SILVER, symbol, timeframe)
    gold = silver.copy()
    prev_close = gold["close"].shift(1)
    gold["log_return"] = np.log(gold["close"] / prev_close)
    gold["log_return"] = gold["log_return"].fillna(0.0)
    lake.write_bars(Layer.GOLD, symbol, timeframe, gold)
    return gold
