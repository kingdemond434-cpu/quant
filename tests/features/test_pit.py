"""Tests for point-in-time joins and feature-table construction."""

from __future__ import annotations

import pandas as pd
from tests.features.conftest import make_bars

from libs.features.pit import build_feature_table, compute_online_vector, pit_join
from libs.features.registry import get_feature


def test_pit_join_is_backward_asof() -> None:
    base = pd.DataFrame(
        {"timestamp": pd.to_datetime(
            ["2026-01-05 00:00", "2026-01-05 12:00", "2026-01-06 06:00"], utc=True
        )}
    )
    other = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-01-05 00:00", "2026-01-06 00:00"], utc=True),
            "macro": [1.0, 2.0],
        }
    )
    joined = pit_join(base, other, value_columns=["macro"])
    # each base row sees only the latest macro at-or-before its timestamp
    assert list(joined["macro"]) == [1.0, 1.0, 2.0]


def test_build_feature_table_columns() -> None:
    bars = make_bars(40)
    features = [get_feature("ret_1"), get_feature("sma_10")]
    table = build_feature_table(bars, features)
    assert list(table.columns) == ["timestamp", "ret_1@v1", "sma_10@v1"]
    assert len(table) == 40


def test_online_vector_matches_offline_last_value() -> None:
    bars = make_bars(40)
    features = [get_feature("sma_10"), get_feature("atr_14")]
    table = build_feature_table(bars, features)
    online = compute_online_vector(bars, features)
    for definition in features:
        assert online[definition.key] == table[definition.key].iloc[-1]
