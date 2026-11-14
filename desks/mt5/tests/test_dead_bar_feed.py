"""A dead bar feed raises an alarm and blocks its clocks; it is never rewritten as if it lived.

Measured 2026-11-13: Fusion put UST10Y/UST05Y into close-only. The terminal kept serving cached
history ending 2025-12-31, `refresh_tail` rewrote every file each pass (fresh mtime, no new bar),
and 25 cross_asset_residual clocks on ['USDX', 'UST10Y'] read ACTIVE with zero observations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "scripts"))
sys.path.insert(0, str(DESK))

import refresh_tail as rt  # noqa: E402
from mt5desk import family_inputs as fi  # noqa: E402


def _frame(end: str, n: int = 50) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=n, freq="5min")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": np.linspace(1, 2, n),
                         "tick_volume": 1, "spread": 1, "real_volume": 0}, index=idx)


def _rates(frame: pd.DataFrame) -> np.ndarray:
    out = frame.reset_index(names="time")
    out["time"] = out["time"].astype("int64") // 10**9
    return out.to_records(index=False)


class _FakeMT5:
    TIMEFRAME_M5 = 5

    def __init__(self, served: pd.DataFrame, mode: int | None) -> None:
        self.served, self.mode = served, mode

    def symbol_select(self, *_a: object) -> bool:
        return True

    def copy_rates_from_pos(self, *_a: object) -> np.ndarray:
        return _rates(self.served)

    def symbol_info(self, _sym: str) -> object:
        return None if self.mode is None else SimpleNamespace(trade_mode=self.mode)

    def last_error(self) -> tuple[int, str]:
        return (0, "")


def _setup(tmp_path: Path, monkeypatch, served: pd.DataFrame, mode: int | None) -> Path:
    monkeypatch.setattr(rt, "OUT", tmp_path)
    monkeypatch.setattr(rt, "DERIVED_MANIFEST", tmp_path / "derived_series.json")
    monkeypatch.setattr(rt, "mt5", _FakeMT5(served, mode))
    monkeypatch.setattr(rt, "_ALARMS", {})
    return tmp_path


def test_a_dead_feed_is_not_rewritten_and_raises_an_alarm(tmp_path: Path, monkeypatch) -> None:
    held = _frame("2025-12-31 09:10")
    out = _setup(tmp_path, monkeypatch, held, mode=3)
    pq = out / "UST10Y_M5.parquet"
    held.to_parquet(pq)
    before = pq.stat().st_mtime_ns
    import os
    os.utime(pq, ns=(1, 1))
    status = rt.refresh_symbol("UST10Y", "M5")
    assert status.startswith("STALE_FEED")
    assert pq.stat().st_mtime_ns == 1, "a dead feed must not be rewritten"
    assert before != 1
    row = rt._ALARMS[("UST10Y", "M5")]
    assert row["venue_trade_mode"] == "CLOSE_ONLY" and row["bars_added"] == 0


def test_a_live_feed_with_nothing_new_is_left_alone(tmp_path: Path, monkeypatch) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    held = _frame(str(now.tz_localize(None) - pd.Timedelta("5min")))
    out = _setup(tmp_path, monkeypatch, held, mode=4)
    pq = out / "EURUSD_M5.parquet"
    held.iloc[:-1].to_parquet(pq)   # the served frame's own last bar is dropped as still-forming
    import os
    os.utime(pq, ns=(1, 1))
    status = rt.refresh_symbol("EURUSD", "M5")
    assert status.startswith("unchanged")
    assert pq.stat().st_mtime_ns == 1
    assert not rt._ALARMS


def test_new_bars_are_still_written(tmp_path: Path, monkeypatch) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    served = _frame(str(now.tz_localize(None)))
    out = _setup(tmp_path, monkeypatch, served, mode=4)
    pq = out / "EURUSD_M5.parquet"
    served.iloc[:-10].to_parquet(pq)
    assert rt.refresh_symbol("EURUSD", "M5").startswith("+9 bars")
    assert len(pd.read_parquet(pq)) == len(served) - 1


def test_alarm_report_names_the_starved_clocks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    (tmp_path / "reports" / "shadow" / "shadow_state.json").write_text(json.dumps({
        "BTCUSD.cross_asset_residual.asia@M15#factor_symbols=['USDX', 'UST10Y']_x=1": {},
        "UST10Y.trend.asia@H1": {},
        "EURUSD.trend.asia@H1": {},
        "retired_clocks": {"X.y.asia#factor_symbols=['UST10Y']": {}},
    }), encoding="utf-8")
    monkeypatch.setattr(rt, "desk_root", lambda: tmp_path)
    monkeypatch.setattr(rt, "ALARMS", tmp_path / "reports" / "BAR_FEED_ALARMS.json")
    monkeypatch.setattr(rt, "_ALARMS", {("UST10Y", "M5"): {
        "symbol": "UST10Y", "timeframe": "M5", "last_bar_utc": "2025-12-31 09:10:00+00:00",
        "age_days": 317.0, "bars_added": 0, "venue_trade_mode": "CLOSE_ONLY"}})
    doc = rt.write_alarms("FusionMarkets-Live")
    on_disk = json.loads((tmp_path / "reports" / "BAR_FEED_ALARMS.json").read_text("utf-8"))
    assert on_disk == doc and doc["n_dead_symbols"] == 1
    row = doc["dead_feeds"][0]
    assert row["dependent_clocks"] == 2
    assert row["missed_growth"]["mechanism"] == "dead_bar_feed"


def test_a_dead_factor_blocks_the_cell_by_name(monkeypatch) -> None:
    primary = _frame("2026-11-13 21:00")
    frames = {"USDX": _frame("2026-11-13 21:00"), "UST10Y": _frame("2025-12-31 09:10")}
    monkeypatch.setattr(fi, "_runtime_bars_raw", lambda _i, s, _tf, _p: frames.get(s))
    monkeypatch.setattr(fi, "_STALE", {})
    import mt5desk.legacy_family_inputs as lfi
    monkeypatch.setattr(lfi, "input_preflight", lambda *_a: None)
    extra, why = fi.resolve("BTCUSD", "cross_asset_residual",
                            {"factor_symbols": ["USDX", "UST10Y"], "timeframe": "M5"}, primary)
    assert extra is None
    assert "UST10Y" in why and "dead at the venue" in why


def test_a_weekend_gap_is_not_stale() -> None:
    assert fi.stale_reason("EURUSD", _frame("2026-11-13 21:00"),
                           _frame("2026-11-16 09:00")) is None


def test_a_dead_feed_is_refreshed_last_not_first(tmp_path: Path, monkeypatch) -> None:
    """Its file is never rewritten, so by mtime it is the oldest forever (Auditor SF1)."""
    import importlib
    import os
    import types
    monkeypatch.setitem(sys.modules, "MetaTrader5", types.ModuleType("MetaTrader5"))
    had = "research.fetch_universe" in sys.modules
    fu = importlib.import_module("research.fetch_universe")
    try:
        _check_order(fu, tmp_path, monkeypatch)
    finally:
        if not had:     # never leave a module bound to the stub terminal for later tests
            sys.modules.pop("research.fetch_universe", None)


def _check_order(fu, tmp_path: Path, monkeypatch) -> None:
    import os
    lake = tmp_path / "data" / "universe"
    lake.mkdir(parents=True)
    for sym, mtime in (("UST10Y", 1), ("EURUSD", 2), ("GBPUSD", 3)):
        (lake / f"{sym}_H1.parquet").write_bytes(b"x")
        os.utime(lake / f"{sym}_H1.parquet", (mtime, mtime))
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "BAR_FEED_ALARMS.json").write_text(
        json.dumps({"dead_feeds": [{"symbol": "UST10Y"}]}), encoding="utf-8")
    monkeypatch.setattr(fu, "OUT", lake)
    monkeypatch.setattr(fu, "_clocked_symbols", lambda: set())
    assert fu._refresh_order(["UST10Y", "GBPUSD", "EURUSD"]) == ["EURUSD", "GBPUSD", "UST10Y"]
