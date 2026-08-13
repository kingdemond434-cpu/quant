"""scripts/screen_coinbase_premium.py -- a free substitute for the DATA-BLOCKED CME basis screen,
built entirely from already-collected data (collect_primary_market_flow.py's Coinbase leg + the
bronze crypto lake's Binance leg). Same testing shape as test_screen_stablecoin_flows.py.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "screen_coinbase_premium", _REPO / "scripts/screen_coinbase_premium.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_flow_ledger(root: Path, n: int, *, start: str = "2026-01-01",
                       source: str = "price_btc_coinbase") -> None:
    rng = np.random.default_rng(0)
    dates = pd.date_range(start, periods=n, freq="D", tz="UTC")
    close = 60_000.0 + np.cumsum(rng.normal(0, 400, n))
    lines = [json.dumps({"kind": "observation", "source": source,
                         "first_seen_utc": d.isoformat(), "backfilled": True,
                         "series": "price_btc", "stamp": d.date().isoformat(),
                         "value": float(c)})
            for d, c in zip(dates, close, strict=False)]
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/primary_market_flow.jsonl").write_text("\n".join(lines) + "\n", "utf-8")


def _write_btc_lake(root: Path, n: int, *, start: str = "2026-01-01") -> None:
    from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
    from libs.data.lake import Layer, ParquetLake
    from libs.data.timeframe import Timeframe
    register_instrument(InstrumentSpec(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO,
                                       description="BTCUSDT"))
    lake = ParquetLake(str(root / "data/lake"))
    rng = np.random.default_rng(1)
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
    close = 60_000.0 + np.cumsum(rng.normal(0, 500, n))
    df = pd.DataFrame({"timestamp": idx, "open": close, "high": close, "low": close,
                       "close": close, "volume": 1.0})
    lake.write_bars(Layer.BRONZE, "BTCUSDT", Timeframe.D1, df)


# --------------------------------------------------------------------------- _coinbase_closes
def test_coinbase_closes_empty_when_ledger_absent(mod) -> None:
    assert mod._coinbase_closes().empty


def test_coinbase_closes_ignores_other_sources_and_run_records(mod, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    lines = [
        json.dumps({"kind": "run", "source": "etf_btc_farside", "status": "OK"}),
        json.dumps({"kind": "observation", "source": "price_eth_coinbase",
                    "stamp": "2026-01-01", "value": 3000.0}),
        json.dumps({"kind": "observation", "source": "price_btc_coinbase",
                    "stamp": "2026-01-01", "value": 60000.0}),
    ]
    (tmp_path / "data/primary_market_flow.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    s = mod._coinbase_closes()
    assert len(s) == 1
    assert s.iloc[0] == 60000.0


def test_coinbase_closes_reads_real_rows(mod, tmp_path: Path) -> None:
    _write_flow_ledger(tmp_path, 90)
    s = mod._coinbase_closes()
    assert len(s) == 90


# --------------------------------------------------------------------------- _btc_closes
def test_btc_closes_empty_when_lake_absent(mod) -> None:
    assert mod._btc_closes().empty


def test_btc_closes_reads_seeded_lake(mod, tmp_path: Path) -> None:
    _write_btc_lake(tmp_path, 30)
    assert len(mod._btc_closes()) == 30


# --------------------------------------------------------------------------- main(): status paths
def test_main_data_blocked_when_ledger_absent(mod, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["screen_coinbase_premium.py"])
    rc = mod.main()
    assert rc == 0
    out = json.loads(Path("reports/axis_screens/coinbase_premium_20260813.json").read_text())
    assert out["status"] == "DATA-BLOCKED"


def test_main_insufficient_data_below_the_registered_floor(mod, tmp_path: Path, monkeypatch
                                                            ) -> None:
    monkeypatch.setattr(sys, "argv", ["screen_coinbase_premium.py"])
    _write_flow_ledger(tmp_path, 10)
    _write_btc_lake(tmp_path, 10)
    mod.main()
    out = json.loads(Path("reports/axis_screens/coinbase_premium_20260813.json").read_text())
    assert out["status"] == "INSUFFICIENT-DATA"


def test_main_runs_all_three_pre_registered_trials_end_to_end(mod, tmp_path: Path, monkeypatch
                                                               ) -> None:
    """250 days so T3's 5d-downsampled, zwin=12 trial clears stage_a_screen's own n>=30 floor."""
    monkeypatch.setattr(sys, "argv", ["screen_coinbase_premium.py"])
    _write_flow_ledger(tmp_path, 250)
    _write_btc_lake(tmp_path, 250)
    rc = mod.main()
    assert rc == 0
    out = json.loads(Path("reports/axis_screens/coinbase_premium_20260813.json").read_text())
    assert [t["name"] for t in out["trials"]] == [
        "premium_level->btc_1d", "premium_change_1d->btc_1d", "premium_level->btc_5d",
    ]
    for t in out["trials"]:
        assert "verdict" in t
    assert out["tempering_prior"]
    assert out["why_this_axis"]


# --------------------------------------------------------------------------- schema / cadence
def test_writes_the_declared_output_path(mod) -> None:
    assert Path("reports/axis_screens/coinbase_premium_20260813.json") == mod._OUT


def test_zero_new_network_dependency() -> None:
    """The whole point of reusing the collector: this screen must not open a second Coinbase
    connection -- it only reads the already-collected ledger."""
    src = (_REPO / "scripts/screen_coinbase_premium.py").read_text("utf-8")
    assert "urllib" not in src and "requests" not in src and "get_json" not in src


def test_the_organ_calls_the_lawful_guard() -> None:
    src = (_REPO / "scripts/screen_coinbase_premium.py").read_text("utf-8")
    assert "from libs.ops.lawful import guard as _law_guard" in src
    assert "_law_guard()" in src


def test_the_organ_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_coinbase_premium.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr
    assert r.returncode == 0


def test_the_organ_is_actually_scheduled() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    scheduled = any("screen_coinbase_premium.py" in ln and ln[:1] in "0123456789*"
                    for ln in man.splitlines())
    assert scheduled, "screen_coinbase_premium.py has no real cron line"
