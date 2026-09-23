"""The digital-twin organ on a synthetic desk: the rotation cursor walks the hypothesis-lane
universe and never reaches an equity, a dry run writes nothing, and every sleeve and candidate
judged across a twin reaches the registry -- with UNMEASURED kept as a value, not a zero.

EVERY INPUT IS SYNTHETIC. The universe registry, the bars (simulated from a known world by the
twin's own simulator), the sleeves file and the canonical registry all live in `tmp_path`; the
lane fence and the family engine are stubbed so the test judges the organ, not the broker book.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import digital_twin as organ  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from libs.research import digital_twin as dt  # noqa: E402

UNIVERSE: dict[str, dict[str, Any]] = {
    "EURUSD": {"asset_class": "Forex", "digits": 5, "contract_size": 100000.0,
               "tick_size": 1e-5, "tick_value": 1.0, "median_spread_pts": 2.0},
    "USDJPY": {"asset_class": "Forex", "digits": 3, "contract_size": 100000.0,
               "tick_size": 1e-3, "tick_value": 0.68, "median_spread_pts": 3.0},
    "XAUUSD": {"asset_class": "Commodities", "digits": 2, "contract_size": 100.0,
               "tick_size": 0.01, "tick_value": 1.0, "median_spread_pts": 15.0},
    "APPLE": {"asset_class": "Equities", "digits": 2},
}
HUNT = ("EURUSD", "USDJPY", "XAUUSD")
LEVELS = {"EURUSD": 1.1, "USDJPY": 150.0, "XAUUSD": 4300.0, "APPLE": 230.0}
N_BARS = 260


def _world() -> np.ndarray:
    d = {p.name: (p.lo + p.hi) / 2 for p in dt.PARAMS}
    d.update(fundamental_vol=3e-4, base_intensity=30.0, hawkes_alpha=0.3, hawkes_decay=0.3,
             cancel_rate=0.3, latency_mean=1.0, impact_coef=1.0, impact_exponent=0.6,
             mm_spread_base=2e-5, mm_depth=50.0, mm_inventory_aversion=0.5, trend_strength=0.2,
             revert_strength=1.0, hedger_gamma=0.0, liquidator_strength=0.3,
             liquidation_threshold=3.0, retail_noise=1.0, passive_amp=0.2, season_amp=0.3,
             season_phase=0.6, jump_rate=0.003, jump_scale=4.0)
    return np.array([[d[n] for n in dt.PARAM_NAMES]])


def _bars(symbol: str, seed: int) -> pd.DataFrame:
    idx = pd.date_range("2026-08-01", periods=N_BARS, freq="h", tz="UTC")
    tod = ((idx.hour + idx.minute / 60.0) / 24.0).to_numpy()
    sim = dt.simulate(_world(), N_BARS, 2, tod, np.random.default_rng(seed))
    lvl = LEVELS[symbol]
    return pd.DataFrame({"open": sim.open[0] * lvl, "high": sim.high[0] * lvl,
                         "low": sim.low[0] * lvl, "close": sim.close[0] * lvl,
                         "tick_volume": sim.volume[0].astype("uint64"),
                         "spread": np.zeros(N_BARS, dtype="int32"),
                         "real_volume": np.zeros(N_BARS, dtype="uint64")}, index=idx)


SLEEVES = {"sleeves": [
    {"name": "eurusd_fade", "symbol": "EURUSD", "family": "anti_range_fade", "status": "LIVE",
     "session": "london"},
    {"name": "xau_follow", "symbol": "XAUUSD", "family": "session_momentum", "status": "STANDBY"},
    {"name": "retired_one", "symbol": "EURUSD", "family": "anti_old", "status": "RETIRED"},
    {"name": "gold_window", "symbol": "XAUUSD", "family": None, "status": "LIVE"},
]}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "desk"
    uni = root / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps(UNIVERSE), encoding="utf-8")
    for i, sym in enumerate(UNIVERSE):
        _bars(sym, 100 + i).to_parquet(uni / f"{sym}_H1.parquet")
    (root / "data" / "sleeves.json").write_text(json.dumps(SLEEVES), encoding="utf-8")
    (root / "data" / "tape" / "ticks").mkdir(parents=True)
    monkeypatch.setattr(organ, "UNIVERSE_DIR", uni)
    monkeypatch.setattr(organ, "UNIVERSE_JSON", uni / "universe.json")
    monkeypatch.setattr(organ, "TICKS", root / "data" / "tape" / "ticks")
    monkeypatch.setattr(organ, "SLEEVES", root / "data" / "sleeves.json")
    monkeypatch.setattr(organ, "STORE", root / "data" / "digital_twin")
    monkeypatch.setattr(organ, "CURSOR", root / "data" / "digital_twin_cursor.json")
    monkeypatch.setattr(organ, "REPORT", root / "reports" / "DIGITAL_TWIN.json")
    # THE STUBBED FENCE AND ENGINE: the lane fence reads the stub registry's classes, and the
    # family engine is absent so every family goes through its vocabulary proxy
    monkeypatch.setattr(organ, "_may_hypothesise",
                        lambda s: UNIVERSE.get(s, {}).get("asset_class") not in (None, "Equities"))
    monkeypatch.setattr(organ, "_family_engine", lambda: None)
    monkeypatch.setattr(organ, "_free_phys_bytes", lambda: None)   # the floor: 64 worlds
    monkeypatch.setattr(organ, "WINDOW_BARS", {"H1": 240, "M5": 240})
    monkeypatch.setattr(organ, "STEPS_PER_BAR", {"H1": 2, "M5": 2})
    monkeypatch.setattr(organ, "N_ROUNDS", 1)
    monkeypatch.setattr(organ, "PPC_DRAWS", 12)
    monkeypatch.setattr(organ, "ROBUST_WORLDS", 8)
    monkeypatch.setattr(organ, "MECHANISM_WORLDS", 8)
    monkeypatch.setattr(organ, "MAX_TWINS_PER_PASS", 2)
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    R.enqueue_candidate(family="liquidity_gamma_reversal", symbol="EURUSD",
                        params={"conditioner": "none"}, origin="TEST", chart="H1")
    R.enqueue_candidate(family="nonsense_family", symbol="USDJPY", params={}, origin="TEST",
                        chart="H1")
    R.enqueue_candidate(family="liquidity_gamma_reversal", symbol="APPLE", params={},
                        origin="TEST", chart="H1")
    yield root
    R.set_path(None)


def _memories() -> list[dict[str, Any]]:
    return R.memories(category="digital_twin", kind="twin_robustness")


def test_dry_run_calibrates_and_writes_nothing(desk: Path) -> None:
    report = organ.run(budget_s=120.0, dry_run=True)
    assert [c["symbol"] for c in report["calibrated"]] == ["EURUSD", "USDJPY"]
    assert report["universe"]["hunt"] == 3 and "APPLE" not in report["twins"]
    assert report["memory"]["worlds_per_batch"] == 64
    assert "floor" in report["memory"]["derived_from"]
    for c in report["calibrated"]:
        assert c["verdict"] and c["calibration_score"] is not None
        assert set(c["preregistrations"]) == {m.name for m in organ.MECHANISMS}
        assert "spread" in c["unmeasured_statistics"][0] or c["unmeasured_statistics"]
    # judged in memory against the twins it just built, and nothing on disk or in the registry
    assert any(e["kind"] == "sleeve" and e["name"] == "eurusd_fade" for e in report["evaluations"])
    assert report["registry_rows"] == 0 and _memories() == []
    assert not organ.STORE.exists() and not organ.CURSOR.exists() and not organ.REPORT.exists()


def test_rotation_cursor_advances_wraps_and_never_reaches_an_equity(desk: Path) -> None:
    first = organ.run(budget_s=120.0, dry_run=False)
    assert [c["symbol"] for c in first["calibrated"]] == ["EURUSD", "USDJPY"]
    cursor = json.loads(organ.CURSOR.read_text(encoding="utf-8"))
    assert cursor["next_index"] == 2 and cursor["last_calibrated"] == ["EURUSD", "USDJPY"]
    assert sorted(p.stem for p in organ.STORE.glob("*.json")) == ["EURUSD", "USDJPY"]
    second = organ.run(budget_s=120.0, dry_run=False)
    assert [c["symbol"] for c in second["calibrated"]] == ["XAUUSD", "EURUSD"]   # wrapped
    assert json.loads(organ.CURSOR.read_text(encoding="utf-8"))["next_index"] == 1
    assert sorted(p.stem for p in organ.STORE.glob("*.json")) == list(HUNT)
    assert not (organ.STORE / "APPLE.json").exists()
    doc = json.loads((organ.STORE / "XAUUSD.json").read_text(encoding="utf-8"))
    for key in ("posterior", "ppc", "calibration", "calibration_score", "preregistrations",
                "participant_mix", "verdict", "unmeasured_statistics"):
        assert key in doc, key
    assert dt.Posterior.from_dict(doc["posterior"]).n >= 8
    report = json.loads(organ.REPORT.read_text(encoding="utf-8"))
    assert report["universe"]["with_twin"] == 3 and set(report["twins"]) == set(HUNT)
    cal = report["calibration"]
    assert cal["n_twins"] == 3 and cal["n_scored"] == 3 and 0.0 <= cal["score_mean"] <= 1.0
    assert cal["score_min"] <= cal["score_median"] <= 1.0


def test_sleeves_and_candidates_reach_the_registry_with_unmeasured_kept(desk: Path) -> None:
    organ.run(budget_s=120.0, dry_run=False)
    report = organ.run(budget_s=120.0, dry_run=False)
    rows = {(e["kind"], e["name"]): e for e in report["evaluations"]}
    names = {n for k, n in rows}
    assert "eurusd_fade" in names and "xau_follow" in names
    assert "retired_one" not in names and "gold_window" not in names
    fade = rows[("sleeve", "eurusd_fade")]
    assert fade["basis"] == "proxy:mean_reversion" and fade["robustness"]["verdict"] != "UNMEASURED"
    assert "execution_cost" in fade and fade["execution_cost"]["n_worlds"] == 8
    assert fade["expected_outcome"] is not None and "q05" in fade["expected_outcome"]
    cands = {e["symbol"]: e for e in report["evaluations"] if e["kind"] == "candidate"}
    assert set(cands) == {"EURUSD", "USDJPY"}                      # the equity has no twin
    nonsense = cands["USDJPY"]
    assert nonsense["basis"].startswith("UNMEASURED")
    assert nonsense["posterior_world_robustness"] is None
    assert nonsense["robustness"]["verdict"] == "UNMEASURED"
    conn = R.connect()
    try:
        by_id = {r["id"]: r for r in conn.execute(
            "SELECT id, symbol, posterior_world_robustness, simulator_family "
            "FROM research_candidates")}
    finally:
        conn.close()
    for sym, e in cands.items():
        row = by_id[e["name"]]
        assert row["symbol"] == sym
        twin_ok = str(e["twin_verdict"]).startswith("REALISTIC")
        if twin_ok and e["robustness"]["verdict"] != "UNMEASURED":
            carried = e["posterior_world_robustness"]
            assert row["posterior_world_robustness"] == pytest.approx(carried)
            assert 0.0 <= row["posterior_world_robustness"] <= 1.0
        else:
            assert row["posterior_world_robustness"] is None
            assert e["posterior_world_robustness"] is None
        assert row["simulator_family"] == f"digital_twin:{e['twin_verdict']}"
    apple = next(r for r in by_id.values() if r["symbol"] == "APPLE")
    assert apple["posterior_world_robustness"] is None and apple["simulator_family"] is None
    mem = _memories()
    assert len(mem) == len(report["evaluations"]) == report["registry_rows"]
    keys = {m["memory_key"] for m in mem}
    assert "twin_robustness:sleeve:eurusd_fade" in keys
    assert all(m["result"] in {"ROBUST", "MIXED", "FRAGILE", "UNMEASURED"} for m in mem)
