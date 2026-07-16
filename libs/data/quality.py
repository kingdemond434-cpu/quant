"""Data quality framework: duplicates, missing bars, spikes, gaps, and a score.

These detectors operate on the canonical bar schema and are the gate between Bronze (raw)
and trustworthy Silver. Weekend handling is delegated to the trading calendar so that
missing-bar detection does not flag legitimately-closed sessions.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict

from libs.data.calendar import expected_index
from libs.data.instruments import get_spec
from libs.data.schema import TIMESTAMP, validate_bars
from libs.data.timeframe import Timeframe


class QualityReport(BaseModel):
    """A summary of a bar frame's data quality, with a 0-100 score."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    n_bars: int
    n_expected: int
    n_duplicates: int
    n_missing: int
    n_spikes: int
    n_gaps: int
    completeness: float
    score: float
    first_timestamp: str | None
    last_timestamp: str | None


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Return all rows that share a timestamp with another row."""
    mask = df[TIMESTAMP].duplicated(keep=False)
    return df.loc[mask].sort_values(TIMESTAMP).reset_index(drop=True)


def detect_missing_bars(df: pd.DataFrame, timeframe: Timeframe, symbol: str) -> pd.DatetimeIndex:
    """Return expected (calendar-aware) timestamps that are absent from ``df``."""
    if df.empty:
        return pd.DatetimeIndex([], tz="UTC")
    spec = get_spec(symbol)
    expected = expected_index(
        df[TIMESTAMP].min(), df[TIMESTAMP].max(), timeframe, spec.asset_class
    )
    present = pd.DatetimeIndex(df[TIMESTAMP])
    return expected.difference(present)


def detect_spikes(df: pd.DataFrame, *, threshold: float = 0.2) -> pd.DataFrame:
    """Return bars whose single-bar close-to-close return exceeds ``threshold`` (fraction)."""
    returns = df["close"].pct_change(fill_method=None)
    mask = returns.abs() > threshold
    flagged = df.loc[mask].copy()
    flagged["return"] = returns.loc[mask]
    return flagged.reset_index(drop=True)


def detect_gaps(
    df: pd.DataFrame, timeframe: Timeframe, *, threshold: float = 0.005
) -> pd.DataFrame:
    """Return bars that open beyond ``threshold`` from the prior close (price gaps).

    Flags whether each gap also spans a non-trading interval (e.g. a weekend), so expected
    weekend gaps can be distinguished from intrabar dislocations.
    """
    prev_close = df["close"].shift(1)
    gap_pct = (df["open"] - prev_close) / prev_close
    time_delta = df[TIMESTAMP].diff()
    crosses = time_delta > (pd.Timedelta(timeframe.timedelta) * 1.5)
    mask = gap_pct.abs() > threshold
    flagged = df.loc[mask].copy()
    flagged["gap_pct"] = gap_pct.loc[mask]
    flagged["crosses_nontrading"] = crosses.loc[mask].fillna(False)
    return flagged.reset_index(drop=True)


def compute_quality_score(df: pd.DataFrame, symbol: str, timeframe: Timeframe) -> QualityReport:
    """Compute a full quality report (completeness-led, penalised for dupes and spikes)."""
    validate_bars(df)
    n_bars = len(df)
    duplicates = detect_duplicates(df)
    missing = detect_missing_bars(df, timeframe, symbol)
    spikes = detect_spikes(df)
    gaps = detect_gaps(df, timeframe)

    n_duplicates = len(duplicates)
    n_missing = len(missing)
    n_spikes = len(spikes)
    n_gaps = len(gaps)
    n_expected = n_bars + n_missing

    completeness = (n_expected - n_missing) / n_expected if n_expected > 0 else 1.0
    dup_ratio = n_duplicates / n_bars if n_bars else 0.0
    spike_ratio = n_spikes / n_bars if n_bars else 0.0
    score = max(0.0, min(100.0, 100.0 * completeness - 50.0 * dup_ratio - 20.0 * spike_ratio))

    first_ts = df[TIMESTAMP].min().isoformat() if n_bars else None
    last_ts = df[TIMESTAMP].max().isoformat() if n_bars else None

    return QualityReport(
        symbol=symbol,
        timeframe=str(timeframe),
        n_bars=n_bars,
        n_expected=n_expected,
        n_duplicates=n_duplicates,
        n_missing=n_missing,
        n_spikes=n_spikes,
        n_gaps=n_gaps,
        completeness=round(completeness, 6),
        score=round(score, 4),
        first_timestamp=first_ts,
        last_timestamp=last_ts,
    )
