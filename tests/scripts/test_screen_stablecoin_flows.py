"""scripts/screen_stablecoin_flows.py -- pins the trial-construction wiring for the on-chain
stablecoin exchange-flow / supply-growth axis (pre-registered 2026-08-13, see the module
docstring for the mechanism and the tempering prior against a related, already-negative CoinMetrics
finding). This is the counterpart to tests/scripts/test_screen_oi_ls_axes.py and
tests/scripts/test_screen_unlock_supply_series.py -- same class of organ, same testing shape.
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
        "screen_stablecoin_flows", _REPO / "scripts/screen_stablecoin_flows.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_archive(root: Path, n: int, *, start: str = "2026-01-01") -> None:
    """n days of a synthetic archive with genuine day-to-day variation (never a flat series --
    stage_a_screen correctly refuses a zero-variance signal, and a flat fixture would silently
    test nothing)."""
    rng = np.random.default_rng(0)
    dates = pd.date_range(start, periods=n, freq="D", tz="UTC")
    total = 900_000_000.0 + np.cumsum(rng.normal(0, 5_000_000, n))
    supply = 140_000_000_000.0 + np.cumsum(rng.normal(0, 80_000_000, n))
    rows = [{"date": d.date().isoformat(), "ts": d.isoformat(), "total": float(t),
             "per_token": {"USDT": float(t) * 0.9, "USDC": float(t) * 0.1},
             "per_exchange": {"binance": float(t)}, "supply_total": float(s),
             "supply_per_token": {"USDT": float(s) * 0.6, "USDC": float(s) * 0.4}}
            for d, t, s in zip(dates, total, supply, strict=False)]
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/stablecoin_flows_archive.json").write_text(json.dumps(rows), "utf-8")


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


# --------------------------------------------------------------------------- _load_archive
def test_load_archive_absent_file_is_empty_not_a_crash(mod) -> None:
    assert mod._load_archive().empty


def test_load_archive_unparseable_file_is_empty_not_a_crash(mod, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/stablecoin_flows_archive.json").write_text("not json", "utf-8")
    assert mod._load_archive().empty


def test_load_archive_reads_real_rows(mod, tmp_path: Path) -> None:
    _write_archive(tmp_path, 45)
    df = mod._load_archive()
    assert len(df) == 45
    assert {"total", "supply_total"} <= set(df.columns)


# --------------------------------------------------------------------------- _downsample
def test_downsample_matches_screen_cme_basis_construction(mod) -> None:
    sig = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    ret = np.array([0.01, 0.02, -0.01, 0.03, 0.0, 0.01])
    s, r = mod._downsample(sig, ret, 2)
    assert list(s) == [1.0, 3.0, 5.0]
    assert len(r) == 3
    assert r[0] == pytest.approx((1.01 * 1.02) - 1.0)


# --------------------------------------------------------------------------- _btc_returns
def test_btc_returns_empty_when_lake_absent(mod) -> None:
    assert mod._btc_returns().empty


def test_btc_returns_reads_seeded_lake(mod, tmp_path: Path) -> None:
    _write_btc_lake(tmp_path, 30)
    r = mod._btc_returns()
    assert len(r) == 30
    assert r.notna().sum() == 29  # first row has no prior close to diff against


# --------------------------------------------------------------------------- main(): status paths
def test_main_data_blocked_when_archive_absent(mod, capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["screen_stablecoin_flows.py"])
    rc = mod.main()
    assert rc == 0
    out = json.loads(Path("reports/axis_screens/stablecoin_flows_20260813.json").read_text())
    assert out["status"] == "DATA-BLOCKED"
    assert "ModuleNotFoundError" not in capsys.readouterr().err


def test_main_insufficient_data_below_the_registered_floor(mod, tmp_path: Path, monkeypatch
                                                            ) -> None:
    monkeypatch.setattr(sys, "argv", ["screen_stablecoin_flows.py"])
    _write_archive(tmp_path, 10)
    _write_btc_lake(tmp_path, 10)
    mod.main()
    out = json.loads(Path("reports/axis_screens/stablecoin_flows_20260813.json").read_text())
    assert out["status"] == "INSUFFICIENT-DATA"
    assert out["rows_archived"] == 10


def test_main_runs_all_five_pre_registered_trials_end_to_end(mod, tmp_path: Path, monkeypatch
                                                              ) -> None:
    """250 days so T5's 5d-downsampled, zwin=12 trial clears stage_a_screen's own n>=30 floor
    (n//5 - 12 - 1 >= 30 needs n >= 215) -- the realistic near-term archive (currently 41 real
    days on the live desk) will legitimately read INSUFFICIENT-DATA on T5 for a while yet; this
    test only pins that the WIRING is correct once enough days exist, not today's live verdict."""
    monkeypatch.setattr(sys, "argv", ["screen_stablecoin_flows.py"])
    _write_archive(tmp_path, 250)
    _write_btc_lake(tmp_path, 250)
    rc = mod.main()
    assert rc == 0
    out = json.loads(Path("reports/axis_screens/stablecoin_flows_20260813.json").read_text())
    assert [t["name"] for t in out["trials"]] == [
        "netflow_1d->btc_1d", "netflow_7d->btc_1d", "supply_1d->btc_1d",
        "supply_7d->btc_1d", "netflow_7d->btc_5d",
    ]
    for t in out["trials"]:
        assert "verdict" in t
    assert out["tempering_prior"]  # the R0024 context travels with every real result


# --------------------------------------------------------------------------- schema / cadence
def test_writes_the_declared_output_path(mod) -> None:
    assert Path("reports/axis_screens/stablecoin_flows_20260813.json") == mod._OUT


def test_the_organ_calls_the_lawful_guard() -> None:
    src = (_REPO / "scripts/screen_stablecoin_flows.py").read_text("utf-8")
    assert "from libs.ops.lawful import guard as _law_guard" in src
    assert "_law_guard()" in src


def test_the_organ_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/screen_stablecoin_flows.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr
    assert r.returncode == 0


def test_the_organ_is_actually_scheduled() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    scheduled = any("screen_stablecoin_flows.py" in ln and ln[:1] in "0123456789*"
                    for ln in man.splitlines())
    assert scheduled, "screen_stablecoin_flows.py has no real cron line"
