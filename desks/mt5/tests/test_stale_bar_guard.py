"""Frozen bars are withheld from minting; a slow leg or an outage never empties the universe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from research import bar_freshness as bf

END = datetime(2026, 11, 4, 12, tzinfo=UTC)


def _bars(root: Path, sym: str, last: datetime, n: int = 48) -> None:
    idx = pd.date_range(end=last.replace(tzinfo=None), periods=n, freq="h", name="time")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx).to_parquet(
        root / f"{sym}_H1.parquet"
    )


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "REPORT", tmp_path / "STALE_BARS.json")
    monkeypatch.setattr(bf, "SWITCH_OFF", tmp_path / "STALE_BAR_GUARD_OFF")


def test_a_series_that_stopped_while_the_rest_moved_is_withheld(tmp_path):
    for s in ("EURUSD", "USDJPY", "XAUUSD", "US500"):
        _bars(tmp_path, s, END)
    _bars(tmp_path, "UST10Y", datetime(2025, 12, 31, 22, tzinfo=UTC))
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "XAUUSD", "US500", "UST10Y"}, tmp_path)
    assert "UST10Y" not in kept and len(kept) == 4
    assert doc["withheld_from_minting"] == ["UST10Y"]
    assert doc["frozen"]["UST10Y"] > 300
    assert bf.REPORT.exists()
    assert doc["missed_growth"]["withheld_symbols"] == 1


def test_a_slow_refresh_leg_holding_most_symbols_is_never_frozen(tmp_path):
    # FX refreshed hourly, the equity leg three weeks behind: the median follows the majority.
    for s in ("EURUSD", "USDJPY"):
        _bars(tmp_path, s, END)
    for s in ("AAPL", "MSFT", "NVDA"):
        _bars(tmp_path, s, END - timedelta(days=21))
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "AAPL", "MSFT", "NVDA"}, tmp_path)
    assert len(kept) == 5 and doc["verdict"] == "ALL_FRESH"


def test_an_outage_that_ages_everything_freezes_nothing(tmp_path):
    for s in ("EURUSD", "USDJPY", "XAUUSD"):
        _bars(tmp_path, s, END - timedelta(days=60))
    kept, _ = bf.live_symbols({"EURUSD", "USDJPY", "XAUUSD"}, tmp_path)
    assert kept == {"EURUSD", "USDJPY", "XAUUSD"}


def test_unreadable_file_is_unmeasured_never_frozen(tmp_path):
    for s in ("EURUSD", "USDJPY"):
        _bars(tmp_path, s, END)
    (tmp_path / "BROKEN_H1.parquet").write_bytes(b"not a parquet")
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "BROKEN"}, tmp_path)
    assert "BROKEN" in kept and doc["unmeasured"] == ["BROKEN"]


def test_switch_off_keeps_every_symbol(tmp_path):
    _bars(tmp_path, "EURUSD", END)
    _bars(tmp_path, "USDJPY", END)
    _bars(tmp_path, "UST10Y", datetime(2025, 12, 31, tzinfo=UTC))
    bf.SWITCH_OFF.write_text("")
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "UST10Y"}, tmp_path)
    assert "UST10Y" in kept and doc["verdict"] == "SWITCHED_OFF"


def test_compiler_universe_withholds_the_frozen_series(tmp_path, monkeypatch):
    import research.miner_candidate_compiler as mcc

    for s in ("EURUSD", "USDJPY", "XAUUSD"):
        _bars(tmp_path, s, END)
    _bars(tmp_path, "UST05Y", datetime(2025, 12, 31, tzinfo=UTC))
    monkeypatch.setattr(mcc, "UNIVERSE", tmp_path)
    universe, note = mcc.live_known_symbols()
    assert universe == {"EURUSD", "USDJPY", "XAUUSD"}
    assert note["withheld_from_minting"] == ["UST05Y"]
