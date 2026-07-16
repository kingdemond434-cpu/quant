"""Trading-calendar helpers driving missing-bar and weekend-gap detection.

Simplified but explicit: crypto is open 24/7; FX, metals, and indices are closed on
Saturday and Sunday (UTC). Intraday session sub-structure is layered on later; the
weekend boundary is the load-bearing rule for completeness checks.
"""

from __future__ import annotations

import pandas as pd

from libs.data.instruments import AssetClass
from libs.data.timeframe import Timeframe


def is_open(timestamp: pd.Timestamp, asset_class: AssetClass) -> bool:
    """Return whether the market is open at ``timestamp`` (UTC) for ``asset_class``."""
    if asset_class is AssetClass.CRYPTO:
        return True
    return bool(timestamp.weekday() < 5)


def expected_index(
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeframe: Timeframe,
    asset_class: AssetClass,
) -> pd.DatetimeIndex:
    """Return the expected UTC timestamps between ``start`` and ``end`` for an instrument."""
    grid = pd.date_range(start=start, end=end, freq=timeframe.pandas_freq, tz="UTC")
    if asset_class is AssetClass.CRYPTO:
        return grid
    return grid[grid.weekday < 5]


def session_of(timestamp: pd.Timestamp) -> str:
    """Tag a UTC timestamp with a coarse trading session."""
    hour = timestamp.hour
    if hour < 7:
        return "asia"
    if hour < 12:
        return "london"
    if hour < 16:
        return "overlap"
    if hour < 21:
        return "newyork"
    return "off"
