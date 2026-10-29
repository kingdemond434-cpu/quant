"""Two tape writers, one tape: every reader must see the newest DAYS, whichever writer wrote them.

THE REGRESSION (2026-10-29). `data/tape/ticks/<SYM>/` holds `2026-10-29.parquet` (mt5desk/tape:
`ts` + `time_msc`) and `20261029.parquet` (moat/moat_silver: `time_msc`, no `ts`). Readers took
the last 30 NAMES; compact names sort after dashed ones, so they read only ts-less files, every
read threw, and `_tape_series` was None for every symbol while the recorder was live.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import tape_days  # noqa: E402

DAY_MS = 86_400_000


def _ms(day: str, n: int) -> list[int]:
    t0 = int(pd.Timestamp(day, tz="UTC").value // 1_000_000)
    return [t0 + 3_600_000 + i * 1_000 for i in range(n)]


def _dashed(d: Path, day: str, n: int = 5) -> Path:
    """mt5desk/tape.record_ticks: `ts` derived from `time_msc`."""
    ms = _ms(day, n)
    df = pd.DataFrame({"time_msc": ms, "bid": [1.0] * n, "ask": [1.1] * n})
    df["ts"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{day}.parquet"
    df.to_parquet(p, index=False)
    return p


def _compact(d: Path, day: str, n: int = 5) -> Path:
    """moat/moat_silver: the recorder's raw rows, no `ts`, string receive stamps."""
    ms = _ms(day, n)
    df = pd.DataFrame({"time": [m // 1000 for m in ms], "time_msc": ms, "bid": [2.0] * n,
                       "ask": [2.2] * n, "recv_utc": ["2026-10-29T00:00:00.000+00:00"] * n})
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{day.replace('-', '')}.parquet"
    df.to_parquet(p, index=False)
    return p


def test_day_key_normalises_both_writers_and_refuses_the_rest():
    assert tape_days.day_key("2026-10-29") == "2026-10-29"
    assert tape_days.day_key("20261029") == "2026-10-29"
    assert tape_days.day_key("20261329") is None
    assert tape_days.day_key("tape_state") is None


def test_newest_days_are_dates_not_names(tmp_path):
    """The exact shape on the box: old compact silver days, fresh dashed days. Names put the
    stale compact files last; dates must put the fresh dashed ones last."""
    d = tmp_path / "XAUUSD"
    for day in ("2026-09-14", "2026-09-15", "2026-09-16"):
        _compact(d, day)
    for day in ("2026-10-27", "2026-10-28", "2026-10-29"):
        _dashed(d, day)
    files = tape_days.day_files(d, last=2)
    assert [f.name for f in files] == ["2026-10-28.parquet", "2026-10-29.parquet"]


def test_recent_quotes_reads_compact_files_with_no_ts(tmp_path):
    d = tmp_path / "EURUSD"
    _compact(d, "2026-10-28")
    _compact(d, "2026-10-29")
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 10
    assert str(t.index.tz) == "UTC"
    assert t.index.max() == pd.Timestamp(_ms("2026-10-29", 5)[-1], unit="ms", tz="UTC")


def test_same_day_from_both_writers_reads_once_and_the_fuller_one_wins(tmp_path):
    d = tmp_path / "BTCUSD"
    _dashed(d, "2026-10-29", n=50)
    _compact(d, "2026-10-29", n=3)       # heavier columns, fewer ticks
    files = tape_days.day_files(d)
    assert [f.name for f in files] == ["2026-10-29.parquet"]
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 50


def test_a_torn_best_file_falls_back_to_the_other_writer(tmp_path):
    d = tmp_path / "USDJPY"
    _compact(d, "2026-10-29", n=4)
    (d / "2026-10-29.parquet").write_bytes(b"PAR1 not really parquet PAR1")
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 4


def test_orthogonal_sweep_reader_sees_the_fresh_tape(tmp_path, monkeypatch):
    """End to end through the real research reader the tape families are judged on."""
    from research import orthogonal_sweep as osw
    _compact(tmp_path / "XAUUSD", "2026-09-16")
    _dashed(tmp_path / "XAUUSD", "2026-10-29")
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    osw._ticks.cache_clear()
    try:
        t = osw._ticks("XAUUSD")
    finally:
        osw._ticks.cache_clear()
    assert t is not None
    assert t.index.max().date().isoformat() == "2026-10-29"
    assert {"bid", "ask"} <= set(t.columns)
