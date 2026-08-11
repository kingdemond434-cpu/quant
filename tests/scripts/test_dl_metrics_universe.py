"""The universe metrics ingester: aggregation arithmetic and S3 pagination, offline.

The kimchi-bug class this feeds (cross-sectional OOS) makes silent aggregation drift a
phantom-edge risk, so the mean is pinned to hand arithmetic, bad rows are proven skipped rather
than zero-filled, and a truncated listing is proven to keep paginating (a silently-single-page
listing would truncate every symbol's history at 1000 days and look exactly like short archives).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.dl_metrics_universe as U  # noqa: E402

HDR = ("create_time,symbol,sum_open_interest,sum_open_interest_value,"
       "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
       "count_long_short_ratio,sum_taker_long_short_vol_ratio")


def test_aggregate_is_the_mean_and_bad_rows_are_skipped_not_zeroed() -> None:
    lines = [HDR,
             "2021-06-01 00:00:00,BTCUSDT,1,100.0,1,2.0,1,3.0",
             "2021-06-01 00:05:00,BTCUSDT,1,300.0,1,4.0,1,5.0",
             "2021-06-01 00:10:00,BTCUSDT,1,not_a_number,1,9.0,1,9.0"]
    agg = U.aggregate_day(lines)
    assert agg == {"oi_value": 200.0, "ls_ratio": 3.0, "taker_ratio": 4.0}


def test_a_day_with_no_parseable_rows_is_none_not_zero() -> None:
    assert U.aggregate_day([HDR]) is None
    assert U.aggregate_day(["some,other,header", "1,2,3"]) is None


def test_listing_paginates_until_not_truncated(monkeypatch) -> None:
    pages = [
        "<r><IsTruncated>true</IsTruncated>"
        "<Key>data/futures/um/daily/metrics/X/X-metrics-2021-06-01.zip</Key>"
        "<Key>data/futures/um/daily/metrics/X/X-metrics-2021-06-01.zip.CHECKSUM</Key></r>",
        "<r><IsTruncated>false</IsTruncated>"
        "<Key>data/futures/um/daily/metrics/X/X-metrics-2021-06-02.zip</Key></r>",
    ]
    calls: list[str] = []

    def fake_http(url: str, timeout: int = 20) -> bytes:
        calls.append(url)
        return pages[len(calls) - 1].encode()

    monkeypatch.setattr(U, "_http", fake_http)
    keys = U.list_symbol_zips("X")
    assert len(calls) == 2, "IsTruncated=true must fetch the next page"
    assert keys == ["data/futures/um/daily/metrics/X/X-metrics-2021-06-01.zip",
                    "data/futures/um/daily/metrics/X/X-metrics-2021-06-02.zip"]
    assert "marker=data%2Ffutures" in calls[1], "page 2 must resume from the last key"
