"""scripts/screen_unlock_supply_series.py -- R0385's second half: wiring real price bars.

The library-level parser bug (schedule rows silently dropped) is pinned in
tests/research/test_unlock_supply_series.py. This file pins the SCRIPT-level bug found while
fixing it: the caller passed bars=None unconditionally, so run_screen() reported the price panel
missing regardless of whether the schedule loaded -- the screen could never have produced a real
verdict even with 24,201 schedule rows recovered.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "screen_unlock_supply_series", _REPO / "scripts/screen_unlock_supply_series.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _seed_lake(root: Path, symbol: str, n: int = 40) -> None:
    from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
    from libs.data.lake import Layer, ParquetLake
    from libs.data.timeframe import Timeframe
    ticker = f"{symbol}USDT"
    register_instrument(InstrumentSpec(symbol=ticker, asset_class=AssetClass.CRYPTO,
                                       description=ticker))
    lake = ParquetLake(str(root / "data/lake"))
    idx = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    df = pd.DataFrame({"timestamp": idx, "open": 1.0, "high": 1.0, "low": 1.0,
                       "close": [1.0 + 0.01 * i for i in range(n)], "volume": 1.0})
    lake.write_bars(Layer.BRONZE, ticker, Timeframe.D1, df)


def test_load_bars_finds_a_symbol_present_in_the_lake(mod, tmp_path: Path) -> None:
    _seed_lake(tmp_path, "ARB")
    out = mod._load_bars({"ARB"})
    assert "ARB" in out
    instants, closes = out["ARB"]
    assert len(instants) == 40
    assert len(closes) == 40
    assert isinstance(instants[0], datetime) and instants[0].tzinfo is not None


def test_load_bars_skips_a_symbol_absent_from_the_lake_without_crashing(mod, tmp_path: Path
                                                                        ) -> None:
    out = mod._load_bars({"NOSUCHTOKEN"})
    assert out == {}


def test_load_bars_handles_a_mix_of_present_and_absent(mod, tmp_path: Path) -> None:
    _seed_lake(tmp_path, "ARB")
    out = mod._load_bars({"ARB", "NOSUCHTOKEN"})
    assert set(out) == {"ARB"}


def test_main_no_longer_passes_bars_none_unconditionally() -> None:
    """R0385's second defect, reproduced exactly: the caller passed bars=None regardless of
    what the schedule contained, so the screen could never report a real verdict even with rows
    recovered from the parser fix."""
    src = (_REPO / "scripts/screen_unlock_supply_series.py").read_text("utf-8")
    assert "bars=None,\n    )" not in src
    assert "_load_bars(" in src


def test_the_organ_still_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_unlock_supply_series.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr
    assert r.returncode == 0


def test_absent_schedule_still_reports_not_readable_not_a_crash() -> None:
    """On a box without data/unlock_events.json (this container, and any fresh clone), the
    organ must still refuse cleanly -- the bars-wiring fix must not have removed that guard."""
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_unlock_supply_series.py"),
                       "--json"], cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "NOT-READABLE-HERE" in r.stdout or "status" in r.stdout
