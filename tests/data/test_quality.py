"""Tests for the data quality framework."""

from __future__ import annotations

import pandas as pd
from tests.data.conftest import MONDAY, make_bars

from libs.data.quality import (
    compute_quality_score,
    detect_duplicates,
    detect_gaps,
    detect_missing_bars,
    detect_spikes,
)
from libs.data.timeframe import Timeframe


def test_complete_series_scores_100() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 48)
    report = compute_quality_score(df, "XAUUSD", Timeframe.H1)
    assert report.n_missing == 0
    assert report.n_duplicates == 0
    assert report.completeness == 1.0
    assert report.score == 100.0


def test_detect_missing_bars() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 48)
    dropped = df.drop(index=[10, 11, 12]).reset_index(drop=True)
    missing = detect_missing_bars(dropped, Timeframe.H1, "XAUUSD")
    assert len(missing) == 3
    assert set(missing) == set(df["timestamp"].iloc[[10, 11, 12]])


def test_detect_duplicates() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 20)
    with_dupe = pd.concat([df, df.iloc[[5]]]).sort_values("timestamp").reset_index(drop=True)
    dupes = detect_duplicates(with_dupe)
    assert len(dupes) == 2


def test_detect_spikes() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 30).copy()
    df.loc[15, "close"] = df.loc[14, "close"] * 1.5  # +50% single-bar jump
    spikes = detect_spikes(df, threshold=0.2)
    assert len(spikes) >= 1


def test_detect_gaps_flags_weekend() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-09 00:00", "2026-01-12 00:00"], utc=True  # Friday -> Monday
            ),
            "open": [100.0, 110.0],   # Monday gaps +10%
            "high": [101.0, 111.0],
            "low": [99.0, 109.0],
            "close": [100.0, 110.5],
            "volume": [500.0, 500.0],
        }
    )
    gaps = detect_gaps(df, Timeframe.D1, threshold=0.005)
    assert len(gaps) == 1
    assert bool(gaps["crosses_nontrading"].iloc[0]) is True


def test_quality_score_penalises_duplicates() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 48)
    with_dupe = pd.concat([df, df.iloc[[5]]]).sort_values("timestamp").reset_index(drop=True)
    report = compute_quality_score(with_dupe, "XAUUSD", Timeframe.H1)
    assert report.n_duplicates == 2
    assert report.score < 100.0


def test_quality_score_drops_with_missing() -> None:
    df = make_bars("XAUUSD", Timeframe.H1, MONDAY, 48)
    dropped = df.drop(index=range(10, 20)).reset_index(drop=True)
    report = compute_quality_score(dropped, "XAUUSD", Timeframe.H1)
    assert report.n_missing == 10
    assert report.completeness < 1.0
    assert report.score < 100.0
