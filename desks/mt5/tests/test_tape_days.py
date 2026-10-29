"""Two tape writers, one tape: every reader must see the newest DAYS, whichever writer wrote them.

THE REGRESSION (2026-10-29). `data/tape/ticks/<SYM>/` holds `2026-10-29.parquet` (mt5desk/tape:
`ts` + `time_msc`) and `20261029.parquet` (moat/moat_silver: `time_msc`, no `ts`). Readers took
the last 30 NAMES; compact names sort after dashed ones, so they read only ts-less files, every
read threw, and `_tape_series` was None for every symbol while the recorder was live.
"""
from __future__ import annotations

import sys
from datetime import UTC
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
    files = tape_days.day_paths(d, last=2)
    assert [f.name for f in files] == ["2026-10-28.parquet", "2026-10-29.parquet"]
    t = tape_days.recent_quotes(d, 2)
    assert t is not None and t.index.min().date().isoformat() == "2026-10-28"


def test_recent_quotes_reads_compact_files_with_no_ts(tmp_path):
    d = tmp_path / "EURUSD"
    _compact(d, "2026-10-28")
    _compact(d, "2026-10-29")
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 10
    assert str(t.index.tz) == "UTC"
    assert t.index.max() == pd.Timestamp(_ms("2026-10-29", 5)[-1], unit="ms", tz="UTC")


def _frame_at(ms: list[int], bid: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({"time_msc": ms, "bid": [bid] * len(ms), "ask": [bid + 0.1] * len(ms)})


def _write(d: Path, name: str, df: pd.DataFrame, with_ts: bool) -> None:
    d.mkdir(parents=True, exist_ok=True)
    if with_ts:
        df = df.assign(ts=pd.to_datetime(df["time_msc"], unit="ms", utc=True))
    df.to_parquet(d / name, index=False)


def test_a_restart_split_across_both_writers_keeps_every_tick(tmp_path):
    """Auditor probe MF1: dashed holds 00-12h, compact holds 10-24h. Union, never pick one."""
    d = tmp_path / "XAUUSD"
    t0 = int(pd.Timestamp("2026-10-29", tz="UTC").value // 1_000_000)
    sec = 1_000
    _write(d, "2026-10-29.parquet", _frame_at([t0 + i * sec for i in range(0, 43_200)]), True)
    _write(d, "20261029.parquet", _frame_at([t0 + i * sec for i in range(36_000, 86_400)]), False)
    t = tape_days.recent_quotes(d, 30)
    assert t is not None
    assert len(t) == 86_400                       # every unique tick, the overlap counted once
    assert t["time_msc"].is_unique


def test_a_receive_day_file_spilling_into_the_next_day_loses_nothing(tmp_path):
    """Compact keys by RECEIVE day: 20261029 can hold 00:00-01:00 of the 30th. The 29th's dashed
    morning must survive and the 30th must not double-count the spill."""
    d = tmp_path / "EURUSD"
    day29 = int(pd.Timestamp("2026-10-29", tz="UTC").value // 1_000_000)
    day30 = day29 + DAY_MS
    _write(d, "2026-10-29.parquet", _frame_at([day29 + i * 60_000 for i in range(600)]), True)
    spill = [day29 + 23 * 3_600_000 + i * 60_000 for i in range(120)]   # 23:00 -> 01:00
    _write(d, "20261029.parquet", _frame_at(spill), False)
    _write(d, "2026-10-30.parquet", _frame_at([day30 + i * 60_000 for i in range(60)]), True)
    t = tape_days.recent_quotes(d, 30)
    assert t is not None
    assert len(t) == 600 + 120                    # 60 of the spill ARE the 30th's first hour
    assert t["time_msc"].is_unique
    one = tape_days.recent_quotes(d, 1)
    assert one is not None and one.index.min() == pd.Timestamp(day30, unit="ms", tz="UTC")
    assert len(one) == 60


def test_duplicate_ticks_from_overlapping_repulls_are_dropped(tmp_path):
    """The recorder re-pulls its last window after a crash; its contract is that readers dedupe."""
    d = tmp_path / "BTCUSD"
    t0 = int(pd.Timestamp("2026-10-29", tz="UTC").value // 1_000_000)
    ms = [t0 + i for i in range(500)]
    _write(d, "20261029.parquet", pd.concat([_frame_at(ms), _frame_at(ms)]), False)
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 500


def test_a_ts_only_millisecond_file_derives_the_right_time_msc(tmp_path):
    """Auditor S2: ts stored at ms resolution must give 1793282642940, not 1793282."""
    d = tmp_path / "USDJPY"
    d.mkdir()
    ts = pd.Series(pd.to_datetime([1793282642940], unit="ms", utc=True)).dt.as_unit("ms")
    pd.DataFrame({"ts": ts, "bid": [1.0], "ask": [1.1]}).to_parquet(d / "2026-10-29.parquet")
    got = tape_days.read_quotes(d / "2026-10-29.parquet")
    assert got is not None and int(got["time_msc"].iloc[0]) == 1793282642940


def test_a_torn_file_is_skipped_and_the_other_writer_still_reads(tmp_path):
    d = tmp_path / "USDJPY"
    _compact(d, "2026-10-29", n=4)
    (d / "2026-10-29.parquet").write_bytes(b"PAR1 not really parquet PAR1")
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 4


def test_triangle_latest_reads_the_newest_day_not_the_newest_name(tmp_path, monkeypatch):
    """Auditor MF2: sorted(glob)[-1] opened yesterday's ts-less compact file."""
    from mt5desk import triangle_tape
    _compact(tmp_path / "EURGBP", "2026-10-28")
    _dashed(tmp_path / "EURGBP", "2026-10-29")
    monkeypatch.setattr(triangle_tape, "TICKS", tmp_path)
    got = triangle_tape._latest("EURGBP")
    assert got is not None and set(got.columns) >= triangle_tape.QUOTE_COLUMNS
    assert pd.to_datetime(got["ts"]).max().date().isoformat() == "2026-10-29"


def test_shadow_execution_reads_a_day_only_the_silver_holds(tmp_path, monkeypatch):
    from datetime import datetime as _dt

    from mt5desk import shadow_execution
    _compact(tmp_path / "XAUUSD", "2026-10-29")
    monkeypatch.setattr(shadow_execution, "TAPE", tmp_path)
    got = shadow_execution.load_ticks("XAUUSD", _dt(2026, 10, 29, 5, tzinfo=UTC))
    assert got is not None and len(got) == 5 and list(got.columns) == ["ts", "bid", "ask"]


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


def test_dedupe_survives_a_writer_with_float32_quotes_and_string_stamps(tmp_path):
    """Auditor S4: dtypes are normalised before the dedupe, so duplicates cannot hide in them."""
    d = tmp_path / "GBPUSD"
    t0 = int(pd.Timestamp("2026-10-29", tz="UTC").value // 1_000_000)
    ms = [t0 + i for i in range(50)]
    _write(d, "2026-10-29.parquet", _frame_at(ms, bid=1.25), True)
    odd = _frame_at(ms, bid=1.25).astype({"bid": "float32", "ask": "float32"})
    odd["time_msc"] = odd["time_msc"].astype(str)
    _write(d, "20261029.parquet", odd, False)
    t = tape_days.recent_quotes(d, 30)
    assert t is not None and len(t) == 50

