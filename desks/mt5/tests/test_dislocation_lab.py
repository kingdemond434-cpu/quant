"""The dislocation lab on a temporary desk: six engines named, an absent surface reads
UNMEASURED by name, a dry run writes nothing, and a real pass writes its report, its state and
(when a cell fires) exact-recipe donations into a temporary registry."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import probability_engines as PE  # noqa: E402
from research import dislocation_lab as DL  # noqa: E402

N_BARS = 3000
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield R
    R.set_path(None)


def _bars(seed: int, start: float, digits: int, *, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=NOW - pd.Timedelta(hours=1), periods=N_BARS, freq="h", tz="UTC")
    r = rng.normal(drift, 0.002, N_BARS)
    close = start * np.exp(np.cumsum(r))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": np.round(close, digits), "tick_volume": 100,
                         "spread": rng.integers(10, 30, N_BARS), "real_volume": 0},
                        index=pd.DatetimeIndex(idx, name="time"))


@pytest.fixture
def desk(tmp_path: Path) -> Path:
    d = tmp_path / "desk"
    (d / "data" / "universe").mkdir(parents=True)
    (d / "data" / "axes").mkdir(parents=True)
    (d / "reports").mkdir()
    _bars(1, 4300.0, 2, drift=0.0004).to_parquet(d / "data" / "universe" / "XAUUSD_H1.parquet")
    _bars(2, 98.0, 3).to_parquet(d / "data" / "universe" / "USDX_H1.parquet")
    _bars(3, 111.0, 3).to_parquet(d / "data" / "universe" / "UST10Y_H1.parquet")
    (d / "data" / "universe" / "universe.json").write_text(json.dumps({
        "XAUUSD": {"asset_class": "Commodities", "digits": 2},
        "USDX": {"asset_class": "Indices", "digits": 3},
        "UST10Y": {"asset_class": "Bonds", "digits": 3}}), encoding="utf-8")
    # a knowable_at-stamped positioning series for gold: P6 replayable on history
    rows = []
    stamp = NOW - pd.Timedelta(days=7 * 120)
    rng = np.random.default_rng(9)
    for i in range(120):
        rows.append({"symbol": "XAUUSD", "knowable_at": (stamp + pd.Timedelta(days=7 * i))
                     .strftime("%Y-%m-%d"), "net_pct_oi": float(rng.normal(0.3, 0.1))})
    (d / "data" / "axes" / "cot.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return d


def test_six_engines_named_and_an_absent_surface_reads_unmeasured(desk: Path) -> None:
    rep = DL.run_pass(budget_s=120, dry_run=True, desk=desk, now=NOW)
    assert list(rep["engines"]) == list(PE.ENGINES) and len(PE.ENGINES) == 6
    assert set(rep["targets"]) == {"XAUUSD", "USDX", "UST10Y"}
    gold = rep["targets"]["XAUUSD"]["horizons"]["1d"]["engines"]
    p2 = gold["P2_options_implied"]
    assert p2["status"] == PE.UNMEASURED
    assert "no options surface for XAUUSD" in p2["why"]
    assert "deribit_atm_iv" in p2["why"] and "cboe_delayed_surface" in p2["why"]
    for name in ("P2_options_implied", "P3_prediction_market", "P5_llm_news"):
        assert name in rep["unmeasured_engines"], name
        assert rep["engines"][name]["targets_unmeasured"]["XAUUSD"]
    # the replayable engines are measured with a curve that has an n
    for name in ("P1_macro_statistical", "P4_cross_asset", "P6_physical_fundamental"):
        e = gold[name]
        assert e["status"] == PE.MEASURED, (name, e["why"])
        assert e["record"]["n"] >= PE.MIN_N_TABLE
        assert e["calibration_overall"]["status"] == PE.MEASURED
        assert e["record"]["withheld_lookahead"] == 0
    assert "cot.json" in gold["P6_physical_fundamental"]["source"]
    hd = rep["targets"]["XAUUSD"]["horizons"]["1d"]
    assert hd["market_implied"]["status"] == PE.MEASURED
    assert hd["dislocation"]["status"] in (PE.MEASURED, PE.UNMEASURED)
    assert isinstance(hd["fired"], bool) and hd["why"]
    fams = rep["cell_families"]
    assert set(fams) == set(DL.CELL_FAMILIES) and len(fams) == 11
    weather = fams["weather_vs_energy_agriculture"]
    assert weather["n_measured"] == 0 and "weather data plane" in weather["why_sample"]
    assert rep["allocates_capital"] is False


def test_dry_run_writes_nothing(desk: Path, registry) -> None:
    before = registry.counts()
    DL.run_pass(budget_s=120, dry_run=True, desk=desk, now=NOW)
    paths = DL.Paths(desk)
    assert not paths.report.exists() and not paths.state.exists()
    assert not paths.ledger.exists() and not paths.intel.exists()
    assert registry.counts() == before


def test_a_real_pass_writes_report_state_ledger_and_exact_recipe_donations(
        desk: Path, registry, monkeypatch) -> None:
    # force one fired cell so the donation path is exercised: no costs, no buffer, no doubt
    monkeypatch.setattr(PE, "REGIME_BUFFER_BASE", 0.0)
    monkeypatch.setattr(PE, "UNMEASURED_REGIME_PENALTY", 0.0)
    real = PE.dislocation

    def loud(ens, market, **kw):
        d = real(ens, market, **kw)
        if d.status == PE.MEASURED and d.edge is not None:
            return PE.Dislocation(d.edge, 0.0, True, 1 if d.edge >= 0 else -1, 0.0, 0.0, 0.0,
                                  PE.MEASURED, "forced by the test")
        return d
    monkeypatch.setattr(PE, "dislocation", loud)
    rep = DL.run_pass(budget_s=120, dry_run=False, desk=desk, now=NOW)
    paths = DL.Paths(desk)
    assert paths.report.exists() and paths.state.exists() and paths.ledger.exists()
    state = json.loads(paths.state.read_text("utf-8"))
    assert "XAUUSD" in state["last_readings"] and "1d" in state["last_readings"]["XAUUSD"]
    assert rep["donated"]["n"] >= 1 and rep["donated"]["path"]
    doc = json.loads(Path(rep["donated"]["path"]).read_text("utf-8"))
    assert doc["source"] == "dislocation_lab" and doc["discoveries"]
    for row in doc["discoveries"]:
        assert row["kind"] == "dislocation_cell" and row["symbols"] == [row["symbol"]]
        assert row["family"] in ("momentum_volgate", "mean_reversion_bollinger",
                                 "cot_positioning", "event_reaction")
        assert isinstance(row["params"], dict) and row["params"]
        assert row["exact_rule"] and row["falsifier"] and row["cell_family"] in DL.CELL_FAMILIES
    assert rep["discoveries"] == rep["donated"]["n"] and rep["discovery_errors"] == []
    discs = registry.discoveries(limit=100)
    assert discs and all(d["source_type"] == "dislocation_cell" for d in discs)
    # the second pass sees the state: the shock family now has a previous reading to compare
    rep2 = DL.run_pass(budget_s=120, dry_run=True, desk=desk, now=NOW)
    shock = [c for c in rep2["cells"]
             if c["family"] == "under_over_reaction_after_probability_shock"]
    assert shock and all("first pass" not in c["why"] for c in shock)
