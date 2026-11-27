"""The tick-tape reader takes the whole window, folds each day, and names why it has no tape.

MEASURED on 013f0b3f76: `_ticks` took `sorted(glob)[-30:]` -- thirty daily observations where the
judge needs sixty -- so liquidity_regime and orderflow_imbalance came back UNKNOWN never_fires
(3,772 and 3,721 cells), and a missing tape was a silent `None`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research import fire_inputs, orthogonal_sweep as osw  # noqa: E402


def _day(day: str, n: int = 120, start: float = 1.1000) -> pd.DataFrame:
    ts = pd.date_range(f"{day} 00:00", periods=n, freq="30s", tz="UTC")
    mid = start + np.cumsum(np.where(np.arange(n) % 3 == 0, 1e-5, -5e-6))
    return pd.DataFrame({"ts": ts, "bid": mid - 1e-5, "ask": mid + 1e-5})


def _tree(tmp_path: Path, monkeypatch, days: int, sym: str = "EURUSD") -> dict:
    d = tmp_path / sym
    d.mkdir(parents=True)
    frames = {}
    base = pd.Timestamp("2026-01-01")
    for i in range(days):
        day = (base + pd.Timedelta(days=i)).date().isoformat()
        (d / f"{day}.parquet").write_bytes(b"x")
        frames[f"{day}.parquet"] = _day(day, start=1.1 + i * 1e-4)
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    monkeypatch.setattr(osw, "_read_tape_file", lambda f: frames.get(Path(f).name))
    osw._tape_minutes.cache_clear()
    return frames


def test_window_is_a_named_constant_well_over_thirty() -> None:
    assert osw.TAPE_MAX_FILES >= 365 and osw.TAPE_MIN_DAYS == 60


def test_more_than_thirty_days_are_read(tmp_path, monkeypatch) -> None:
    _tree(tmp_path, monkeypatch, 75)
    st = osw.tape_status("EURUSD")
    assert st["days_read"] == 75 and st["reason"] == osw.TAPE_OK
    idx = pd.date_range("2026-01-01", periods=75 * 24, freq="1h", tz="UTC")
    spread, flow = osw._tape_series("EURUSD", idx, "H1")
    assert spread is not None and flow is not None
    assert spread.notna().sum() >= 74 * 24 // 2  # not just the last thirty days


def test_the_bound_applies(tmp_path, monkeypatch) -> None:
    _tree(tmp_path, monkeypatch, 12)
    monkeypatch.setattr(osw, "TAPE_MAX_FILES", 5)
    osw._tape_minutes.cache_clear()
    assert osw.tape_status("EURUSD")["days_read"] == 5


def test_folded_partials_equal_the_raw_tick_resample(tmp_path, monkeypatch) -> None:
    frames = _tree(tmp_path, monkeypatch, 3)
    t = pd.concat(frames.values(), ignore_index=True).set_index("ts")
    spread_raw = (t["ask"] - t["bid"]).resample("15min").mean()
    mid = (t["ask"] + t["bid"]) / 2.0
    step = mid.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    flow_raw = step.resample("15min").sum()
    idx = spread_raw.index
    spread, flow = osw._tape_series("EURUSD", idx, "M15")
    live = spread_raw.dropna().index
    assert len(live) > 10
    assert np.allclose(spread.reindex(live).to_numpy(), spread_raw.reindex(live).to_numpy(),
                       atol=1e-12)
    # raw flow treats each day's first tick as diff vs the previous day's last: so does the fold
    assert np.allclose(flow.to_numpy(), flow_raw.reindex(idx).ffill().to_numpy())


def test_short_tape_is_served_and_named(tmp_path, monkeypatch) -> None:
    _tree(tmp_path, monkeypatch, 20)
    idx = pd.date_range("2026-01-01", periods=240, freq="1h", tz="UTC")
    spread, _flow = osw._tape_series("EURUSD", idx, "H1")
    assert spread is not None
    st = osw.tape_status("EURUSD")
    assert st["reason"] == osw.TAPE_SHORT and st["days_read"] == 20 and st["min_days"] == 60


def test_missing_dir_and_unreadable_files_are_named_not_silent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    osw._tape_minutes.cache_clear()
    assert osw._tape_series("NOPE", pd.DatetimeIndex([]), "H1") == (None, None)
    assert osw.tape_status("NOPE")["reason"] == osw.TAPE_NO_DIR
    (tmp_path / "BAD").mkdir()
    (tmp_path / "BAD" / "2026-01-01.parquet").write_bytes(b"x")
    monkeypatch.setattr(osw, "_read_tape_file", lambda f: None)
    osw._tape_minutes.cache_clear()
    assert osw.tape_status("BAD")["reason"] == osw.TAPE_NO_READABLE


def test_both_writers_one_day_dashed_wins_and_order_is_by_date(tmp_path) -> None:
    d = tmp_path / "S"
    d.mkdir()
    for n in ("2026-10-29", "20261029", "20261001", "2026-10-02", "junk"):
        (d / f"{n}.parquet").write_bytes(b"x")
    got = [f.name for f in osw._tape_files(d)]
    assert got == ["20261001.parquet", "2026-10-02.parquet", "2026-10-29.parquet"]


def test_fire_probe_names_a_missing_tape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    osw._tape_minutes.cache_clear()
    out = fire_inputs.probe("EURUSD", "liquidity_regime")
    assert out["status"] == "NEEDS_DATA" and out["missing_input"] == "tape_series:EURUSD"
    monkeypatch.setattr(osw, "TAPE", tmp_path / "does_not_exist")
    osw._tape_minutes.cache_clear()
    assert fire_inputs.probe("EURUSD", "orderflow_imbalance")["status"] == "UNMEASURED"


def test_fire_probe_short_tape_is_present_with_a_warning(tmp_path, monkeypatch) -> None:
    _tree(tmp_path, monkeypatch, 10)
    out = fire_inputs.probe("EURUSD", "orderflow_imbalance")
    assert out["status"] == "PRESENT" and out["warning"].startswith("short_tape")
