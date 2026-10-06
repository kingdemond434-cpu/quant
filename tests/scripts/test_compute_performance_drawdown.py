"""Pins the 2026-08-19 wiring of libs.validation.drawdown_metrics into compute_performance.

The module shipped 2026-08-01 with zero production callers (orphan-modules census) while
compute_performance computed a weaker inline max-drawdown one line above the natural call site.
This pins that the dashboard stats now carry the path-severity trio, finite and JSON-safe.
"""

from __future__ import annotations

import numpy as np
import scripts.compute_performance as cp


def test_stats_carry_drawdown_trio() -> None:
    close = np.array([100.0, 101.0, 99.0, 102.0, 101.0, 104.0, 103.0, 106.0])
    pos = np.array([0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0])
    ext = cp._extract_trades(close, pos, cost_side=0.0005)
    stats = cp._metrics(ext["net"], ext["equity"], ext["trades"])
    for key in ("ulcer_index", "martin_ratio", "return_over_max_drawdown"):
        assert key in stats
        # _safe() guarantees JSON-safe finite numbers even where the statistic is undefined
        assert np.isfinite(stats[key])


def test_flat_series_is_json_safe_not_nan() -> None:
    # A position series that never trades: every drawdown statistic is undefined (nan upstream)
    # and must land as 0.0, never as a NaN that breaks the dashboard's JSON.
    close = np.array([100.0, 100.0, 100.0, 100.0])
    pos = np.zeros(4)
    ext = cp._extract_trades(close, pos, cost_side=0.0005)
    stats = cp._metrics(ext["net"], ext["equity"], ext["trades"])
    for key in ("ulcer_index", "martin_ratio", "return_over_max_drawdown"):
        assert stats[key] == 0.0
