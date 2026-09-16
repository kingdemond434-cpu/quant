"""Point-in-time frame stamps: a row is available at event_time + lag, never at event_time."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from libs.data import pit_stamp as pit


def test_lag_prefers_the_registry_then_cadence_then_fallback() -> None:
    assert pit.lag_for({"pit": {"publication_lag_days": 20}, "cadence": "daily"})[0] == 20
    assert pit.lag_for({"cadence": "weekly"})[0] == 3
    assert pit.lag_for({"cadence": "monthly"})[0] == 20
    assert pit.lag_for({"cadence": "never heard of it"})[0] == pit.FALLBACK_LAG_DAYS
    assert pit.lag_for(None)[0] == pit.FALLBACK_LAG_DAYS


def test_available_at_adds_the_lag_in_utc() -> None:
    a = pit.available_at(date(2026, 7, 31), 20)
    assert a == datetime(2026, 8, 20, tzinfo=UTC)
    b = pit.available_at(datetime(2026, 7, 31, 12, tzinfo=UTC), 1)
    assert b == datetime(2026, 8, 1, 12, tzinfo=UTC)


def test_stamp_frame_adds_three_columns_and_never_backdates() -> None:
    df = pd.DataFrame({"Date": ["2026-06-30", "2026-07-31"], "value": [1.0, 2.0]})
    out, meta = pit.stamp_frame(df, lag_days=20, observed_at="2026-09-16T00:00:00+00:00")
    assert meta["status"] == "STAMPED" and meta["period_column"] == "Date"
    assert (out["available_time"] > out["event_time"]).all()
    assert str(out["available_time"].iloc[1])[:10] == "2026-08-20"
    assert set(out["ingested_time"]) == {"2026-09-16T00:00:00+00:00"}


def test_no_period_column_is_unstamped_not_guessed() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    out, meta = pit.stamp_frame(df, lag_days=5, observed_at=None)
    assert meta["status"] == "UNSTAMPED" and "available_time" not in out.columns


def test_stamp_carries_the_full_point_in_time_envelope() -> None:
    import pandas as pd

    from libs.data.pit_stamp import PIT_FIELDS, stamp_frame, vintage_id_for

    df = pd.DataFrame({"period_end": ["2026-01-31", "2026-02-28"], "value": [1.0, 2.0]})
    out, meta = stamp_frame(df, lag_days=2, observed_at="2026-03-05T00:00:00+00:00",
                            source_id="fred:CPIAUCSL")
    assert meta["status"] == "STAMPED" and meta["fields"] == list(PIT_FIELDS)
    for col in PIT_FIELDS:
        assert col in out.columns
    assert (out["published_time"] == out["available_time"]).all()
    assert (out["retrieval_time"] == "2026-03-05T00:00:00+00:00").all()
    assert (out["source_id"] == "fred:CPIAUCSL").all()
    assert meta["vintage_id"] == vintage_id_for("fred:CPIAUCSL", "2026-03-05T00:00:00+00:00", df)
    assert meta["undeclared"] == ["revision_time"]
    # nothing is invented: no fetch instant -> no vintage, and it says so
    out2, meta2 = stamp_frame(df, lag_days=2, observed_at=None)
    assert meta2["vintage_id"] is None and "vintage_id" in meta2["undeclared"]
    assert out2["source_id"].isna().all()
