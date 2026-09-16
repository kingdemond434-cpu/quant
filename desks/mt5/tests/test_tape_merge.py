"""The tick tape's day merge: two writers' schemas unite, ts is derived, the file is an explicit
Arrow table with ts as timestamp[ms, UTC] (the ArrowInvalid of 2026-09-16 cannot recur)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import tape  # noqa: E402


def _recorder_frame() -> pd.DataFrame:
    return pd.DataFrame({"time": [1, 2], "bid": [1.0, 1.1], "ask": [1.1, 1.2], "last": [0.0, 0.0],
                         "volume": [1, 1], "time_msc": [1000, 2000], "flags": [0, 0],
                         "volume_real": [0.0, 0.0], "recv_utc": ["a", "b"],
                         "recv_mono": [0.1, 0.2]})


def _hourly_chunk() -> pd.DataFrame:
    df = pd.DataFrame({"time": [2, 3], "bid": [1.1, 1.2], "ask": [1.2, 1.3], "last": [0.0, 0.0],
                       "volume": [1, 1], "time_msc": [2000, 3000], "flags": [0, 0],
                       "volume_real": [0.0, 0.0]})
    df["ts"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
    return df


def test_merge_unites_the_two_writers_and_derives_ts():
    merged = tape.merge_day(_recorder_frame(), _hourly_chunk())
    assert list(merged["time_msc"]) == [1000, 2000, 3000]          # deduplicated on the union
    assert "recv_utc" in merged.columns and "ts" in merged.columns
    assert str(merged["ts"].dtype).startswith("datetime64") and merged["ts"].iloc[-1].year == 1970
    assert merged["recv_utc"].isna().iloc[-1]                        # the hourly row has none


def test_write_day_round_trips_with_ts_as_arrow_timestamp(tmp_path: Path):
    out = tmp_path / "XAUUSD" / "2026-09-16.parquet"
    out.parent.mkdir(parents=True)
    _recorder_frame().to_parquet(out, index=False)                   # the recorder's file first
    n = tape.write_day(_hourly_chunk(), out)
    assert n == 3
    t = pq.read_table(out)
    assert t.num_rows == 3
    assert str(t.schema.field("ts").type).startswith("timestamp[ms")
    assert t.column("time_msc").to_pylist() == [1000, 2000, 3000]
    # a second merge of the same chunk changes nothing
    assert tape.write_day(_hourly_chunk(), out) == 3


def test_empty_frames_do_not_crash():
    empty = _hourly_chunk().iloc[0:0]
    assert len(tape.merge_day(None, empty)) == 0
    assert len(tape.merge_day(empty, _hourly_chunk())) == 2
