"""The drift monitor, factor x model co-evolution and the anomaly factory.

What is pinned: a verdict ladder that puts the book's structure above any one instrument's
hazard, degradation that leaves a reason on the report rather than a clean-looking blank, a
trial count that includes every pairing and every miner cell an anomaly was selected from, and
tasks that leave for the deepening queue only in the shape its worker reads.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research.multiplicity import deflate_t  # noqa: E402

from libs.models import zoo  # noqa: E402
from research import anomaly_factory as af  # noqa: E402
from research import drift_monitor as dm  # noqa: E402
from research import factor_model_coevolution as fmc  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import regime_coverage  # noqa: E402

BANNED = ("binance", "bybit", "okx", "hyperliquid", "funding rate", "perp")


def _bars(days: int = 300, seed: int = 0, vol: np.ndarray | None = None) -> pd.DataFrame:
    """Hourly bars with spread and tick_volume, tz-aware UTC; `vol` scales each bar's return."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=days * 24, freq="h", tz="UTC")
    scale = np.full(idx.size, 0.0008) if vol is None else vol
    c = np.exp(np.cumsum(rng.normal(scale=scale))) * 100
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) * (1 + 0.0004 * (1 + rng.random(idx.size)))
    lo = np.minimum(o, c) * (1 - 0.0004 * (1 + rng.random(idx.size)))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c,
                         "spread": rng.integers(5, 25, size=idx.size).astype(float),
                         "tick_volume": rng.integers(100, 1000, size=idx.size).astype(float)},
                        index=pd.Index(idx, name="time"))


@pytest.fixture
def universe(tmp_path, monkeypatch):
    """A tmp universe dir on `proposer_common.UNI`; returns a writer for named frames."""
    uni = tmp_path / "universe"
    uni.mkdir()
    monkeypatch.setattr(pc, "UNI", uni)

    def write(sym: str, d: pd.DataFrame) -> Path:
        path = uni / f"{sym}_H1.parquet"
        d.to_parquet(path)
        return path
    return write


@pytest.fixture
def queue(tmp_path, monkeypatch) -> Path:
    q = tmp_path / "hypotheses" / "miner_deepening_queue.json"
    monkeypatch.setattr(regime_coverage, "QUEUE", q)
    return q


def _queue_rows(q: Path, source: str) -> list[dict]:
    doc = json.loads(q.read_text("utf-8"))
    return [t for t in doc["tasks"] if t.get("source") == source]


# ------------------------------------------------------------------------------------------
# Drift monitor
# ------------------------------------------------------------------------------------------

def test_verdict_ladder_puts_the_books_structure_above_any_one_instrument():
    calm = {"A": {"hazard_max": 0.4}, "B": {"hazard_max": 0.9}}
    assert dm.verdict(calm, {"verdict": "STABLE"}) == "STABLE"
    assert dm.verdict({**calm, "C": {"hazard_max": 1.5}}, {"verdict": "STABLE"}) == "WATCH"
    assert dm.verdict({**calm, "C": {"hazard_max": 2.5}}, {"verdict": "STABLE"}) == "DRIFT_AHEAD"
    assert dm.verdict({**calm, "C": {"hazard_max": 2.5}},
                      {"verdict": "STRUCTURE_SHIFTED"}) == "STRUCTURE_SHIFTED"
    assert dm.verdict({}, {"verdict": "UNMEASURED"}) == "STABLE"
    assert dm.verdict({"A": {"hazard_max": None}}, {"verdict": "UNMEASURED"}) == "STABLE"


def test_a_persistent_vol_regime_that_just_jumped_is_drift_ahead(universe, tmp_path,
                                                                 monkeypatch):
    # Window vol follows a persistent AR(1) in log space -- so the lag weights are real -- and
    # the last eight days sit at five times the baseline: the NEXT window is forecast far away.
    rng = np.random.default_rng(7)
    n_days = 400
    lv = np.zeros(n_days)
    for i in range(1, n_days):
        lv[i] = 0.9 * lv[i - 1] + rng.normal(scale=0.25)
    day_vol = 0.0008 * np.exp(lv)
    day_vol[-8:] = 0.0008 * 5.0
    d = _bars(days=n_days, seed=7, vol=np.repeat(day_vol, 24))
    universe("JUMPY", d)
    universe("CALM", _bars(days=n_days, seed=8))
    monkeypatch.setattr(dm, "_book_symbols", lambda: [])
    monkeypatch.setattr(dm, "_load_trades", list)
    monkeypatch.setattr(dm, "REPORT", tmp_path / "DRIFT.json")
    doc = dm.run(budget_s=60)
    assert doc["per_symbol"]["JUMPY"]["hazard_max"] > 2.0
    assert doc["per_symbol"]["JUMPY"]["verdict"] == "DRIFT_AHEAD"
    assert doc["verdict"] == "DRIFT_AHEAD" and doc["symbol_verdict"] == "DRIFT_AHEAD"
    assert doc["what_changed"][0]["symbol"] == "JUMPY"
    assert doc["what_changed"][0]["stat"] in ("vol", "abs_ret", "range")
    # Off-box degradation is written, never silent.
    assert doc["structure_verdict"] == "UNMEASURED"
    assert doc["structure"]["why"] and any("structure" in w for w in doc["degraded"])
    assert doc["symbols"]["source"] == "fallback" and doc["symbols"]["why"]
    written = json.loads((tmp_path / "DRIFT.json").read_text("utf-8"))
    assert written["verdict"] == "DRIFT_AHEAD" and "generated_utc" in written


def _trades(n_days: int = 400, sleeves: int = 4, shifted: int = 30, seed: int = 5):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 1, n_days)
    days = pd.date_range("2025-01-01", periods=n_days, freq="D", tz="UTC")
    out = []
    for j in range(sleeves):
        r = rng.normal(0, 1, n_days)
        if shifted:
            r[-shifted:] = 0.95 * f[-shifted:] + 0.3 * rng.normal(0, 1, shifted)
        out.extend(SimpleNamespace(sleeve=f"s{j}", when=days[i].isoformat(), r=float(r[i]))
                   for i in range(n_days))
    return out


def test_structure_drift_hears_sleeves_collapsing_onto_one_factor():
    m, sleeves, why = dm.daily_pnl_matrix(_trades())
    assert m is not None and m.shape == (400, 4) and sleeves == ["s0", "s1", "s2", "s3"]
    assert why == ""
    s = dm.structure_drift(m, sleeves)
    assert s["verdict"] == "STRUCTURE_SHIFTED" and s["z"] > 2.0
    assert s["tail_dependence"]["recent_mean"] > s["tail_dependence"]["prior_mean"]
    assert s["factor_explained"]["recent"] > s["factor_explained"]["prior"]
    assert s["heats_equal_weight"]["n_eff"]["covariance"] > 1.0
    calm_m, calm_sl, _ = dm.daily_pnl_matrix(_trades(shifted=0))
    assert dm.structure_drift(calm_m, calm_sl)["verdict"] == "STABLE"
    none = dm.structure_drift(*dm.daily_pnl_matrix([]))
    assert none["verdict"] == "UNMEASURED" and "no shadow trades" in none["why"]


def test_structure_shift_is_the_verdict_even_when_every_instrument_is_calm(universe, tmp_path,
                                                                            monkeypatch):
    universe("CALM", _bars(days=200, seed=3))
    monkeypatch.setattr(dm, "_book_symbols", lambda: ["CALM"])
    monkeypatch.setattr(dm, "_load_trades", lambda: _trades())
    monkeypatch.setattr(dm, "REPORT", tmp_path / "DRIFT.json")
    doc = dm.run(budget_s=60)
    assert doc["symbols"]["source"] == "book"
    assert doc["verdict"] == "STRUCTURE_SHIFTED"
    assert any(r["symbol"] == "BOOK" and r["stat"] == "correlation_structure"
               for r in doc["what_changed"])


# ------------------------------------------------------------------------------------------
# Factor x model co-evolution
# ------------------------------------------------------------------------------------------

def test_the_positive_verdict_is_the_zoos_own():
    src = inspect.getsource(zoo)
    assert f'"{fmc.POSITIVE}"' in src, "the zoo renamed its positive verdict; follow it"


def _coevo_env(tmp_path, monkeypatch):
    monkeypatch.setattr(fmc, "REPORT", tmp_path / "COEVOLUTION.json")
    monkeypatch.setattr(fmc, "TRIALS", tmp_path / "coevolution_trials.jsonl")
    monkeypatch.setattr(fmc, "FEATURE_ROOT", tmp_path / "features")
    monkeypatch.setattr(fmc, "_book_symbols", lambda: [])


def test_coevolution_counts_every_pairing_and_tasks_only_what_earns(universe, queue, tmp_path,
                                                                     monkeypatch):
    universe("SYNA", _bars(days=200, seed=1))
    _coevo_env(tmp_path, monkeypatch)
    earning = {"features": ['log_return:{"h": 6}', "hour:{}"], "model": "hist_gb",
               "net_gain": 0.0021, "gain": 0.0036, "tax": 0.0015, "verdict": fmc.POSITIVE,
               "n": 950, "brier": 0.249}
    taxed = {**earning, "model": "mlp", "net_gain": -0.001, "verdict": "TAXED_OUT"}
    calls = []

    def fake_evolve(df, **kw):
        calls.append(kw)
        return {"pairings_evaluated": 7, "best": [earning, taxed], "n_earning": 1, "trials": 7}
    monkeypatch.setattr(fmc, "evolve", fake_evolve)
    doc = fmc.run(budget_s=10)
    assert doc["symbols"]["source"] == "fallback" and doc["symbols"]["why"]
    assert doc["tests_run"] == 7 and doc["per_symbol"]["SYNA"]["pairings_evaluated"] == 7
    assert len(calls) == 1 and calls[0]["pop"] == fmc.POP and calls[0]["gens"] == fmc.GENS
    assert doc["n_tasks"] == 1
    rows = _queue_rows(queue, fmc.SOURCE)
    assert len(rows) == 1
    t = rows[0]
    assert t["kind"] == "model_pairing" and t["symbols"] == ["SYNA"] and t["status"] is None
    for needle in ("hist_gb", 'log_return:{"h": 6}', "+0.00210", "n=950"):
        assert needle in t["description"], needle
    assert "state-conditioned family recipe" in t["consumer"]
    ledger_path = tmp_path / "coevolution_trials.jsonl"
    ledger = [json.loads(ln) for ln in ledger_path.read_text("utf-8").splitlines()]
    assert ledger == [{**ledger[0], "symbol": "SYNA", "pairings": 7}]
    # A rerun REPLACES this source's rows rather than accumulating them.
    fmc.run(budget_s=10)
    assert len(_queue_rows(queue, fmc.SOURCE)) == 1
    assert len((tmp_path / "coevolution_trials.jsonl").read_text().splitlines()) == 2


def test_coevolution_really_breeds_on_synthetic_bars_and_stores_features(universe, queue,
                                                                          tmp_path, monkeypatch):
    universe("SYNB", _bars(days=180, seed=2))
    _coevo_env(tmp_path, monkeypatch)
    doc = fmc.run(symbols=["SYNB"], budget_s=60, pop=3, gens=1, models=("ridge_sign",))
    r = doc["per_symbol"]["SYNB"]
    assert r["pairings_evaluated"] >= 1 and doc["tests_run"] == r["pairings_evaluated"]
    assert r["bars"] == 180 * 24
    for b in r["best"]:
        assert b["model"] == "ridge_sign"
        assert b["verdict"] in (fmc.POSITIVE, "TAXED_OUT", "UNMEASURED", "FAILED")
    assert list((tmp_path / "features").glob("*.npy")), "the feature store must be shared"
    assert doc["feature_store"]["misses"] >= 1


def test_the_symbol_cap_defers_rather_than_excludes(universe, monkeypatch):
    names = [f"S{i}" for i in range(8)]
    tiny = _bars(days=2)
    for n in names:
        universe(n, tiny)
    monkeypatch.setattr(fmc, "_book_symbols", lambda: names)
    pool, chosen = fmc._symbols(None)
    assert len(pool) == fmc.MAX_SYMBOLS and chosen["source"] == "book"
    assert sorted(pool + chosen["deferred"]) == names


# ------------------------------------------------------------------------------------------
# Anomaly factory
# ------------------------------------------------------------------------------------------

def test_condition_strings_parse_only_in_the_executors_shape():
    assert af.parse_condition("kurt_96_q0.9-1") == ("kurt_96", (0.9, 1.0))
    assert af.parse_condition("x_ret_24__dd_12_q0.25-0.4") == ("x_ret_24__dd_12", (0.25, 0.4))
    assert af.parse_condition("ext_series_z_q0-0.05") == ("ext_series_z", (0.0, 0.05))
    assert af.parse_condition("lead_lag_XAUUSD_lag1") is None
    assert af.parse_condition("resid_rich_vs_EURUSD") is None
    assert af.parse_condition("dd_12_q0.9-0.5") is None


def test_deflation_charges_the_miners_selection_trials_on_top_of_the_sweep(monkeypatch):
    monkeypatch.setattr(af, "_family_trials", lambda: 0)
    base = {"t_gross": 4.0, "clears_cost": True, "n_independent": 80}
    narrow, wide = af.deflate([{**base, "selection_trials": 0},
                               {**base, "selection_trials": 100_000}])
    assert narrow["n_tests_sweep"] == 2 and wide["n_tests_sweep"] == 100_002
    assert narrow["t_deflated_sweep"] == round(deflate_t(4.0, 2), 3)
    assert wide["t_deflated_sweep"] == round(deflate_t(4.0, 100_002), 3)
    assert narrow["proposed"] and not wide["proposed"]
    monkeypatch.setattr(af, "_family_trials", lambda: 5000)
    (row,) = af.deflate([{**base, "selection_trials": 10}])
    assert row["n_tests_lifetime"] == 5011 and row["t_deflated_lifetime"] < row["t_deflated_sweep"]


def _scan(rows: list[dict]) -> dict:
    return {"anomalies": rows, "trials": 12_000, "symbols_scanned": 1,
            "cross_sectional_trials": 5}


def _anomaly(**kw) -> dict:
    row = {"kind": "anomaly", "symbol": "SYNA", "condition": "ret_24_q0.9-1", "horizon": 6,
           "n": 500, "mean_bp": 4.0, "t_stat": 4.2, "hit_rate": 0.55, "baseline_bp": 0.1,
           "question": "SYNA returns over 6h are 4.0bp when ret_24_q0.9-1. WHAT MECHANISM?",
           "mechanism_status": "UNNAMED", "selection_trials": 9000}
    row.update(kw)
    return row


def _factory_env(tmp_path, monkeypatch, rows: list[dict], buried: dict | None = None):
    monkeypatch.setattr(af, "REPORT", tmp_path / "ANOMALY_FACTORY.json")
    monkeypatch.setattr(af.am, "scan", lambda symbols=None, limit=None: _scan(rows))
    monkeypatch.setattr(af, "_buried_index", lambda: (buried or {}, ""))
    monkeypatch.setattr(af, "_family_trials", lambda: 0)
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 1e-5)
    donated: list[tuple] = []
    monkeypatch.setattr(pc, "donate", lambda src, cands, n: donated.append((src, cands, n))
                        or tmp_path / "discoveries.json")
    return donated


def test_the_factory_executes_what_resolves_and_queues_what_must_be_named(universe, queue,
                                                                          tmp_path, monkeypatch):
    universe("SYNA", _bars(days=300, seed=4))
    rows = [
        _anomaly(),                                                    # executable
        _anomaly(condition="ret_24_q0.75-0.9", t_stat=3.3),            # same finding, weaker
        _anomaly(condition="no_such_primitive_q0.9-1", t_stat=3.5, mean_bp=-3.0, n=100),
        {"kind": "anomaly", "family_hint": "lead_lag", "symbol": "SYNA", "against": "SYNB",
         "condition": "lead_lag_SYNB_lag1", "horizon": 1, "n": 5000, "corr": 0.2,
         "t_stat": 10.0, "mechanism_status": "UNNAMED", "question": "SYNB leads SYNA?"},
        _anomaly(condition="dd_12_q0-0.1", t_stat=1.0),               # below the floor
        _anomaly(condition="dd_24_q0-0.1", t_stat=5.0, n=30),          # below the floor
    ]
    donated = _factory_env(tmp_path, monkeypatch, rows)
    rep = af.run(budget_s=120)
    assert rep["anomalies_in"] == 6 and rep["eligible"] == 4
    assert rep["collapsed_near_duplicates"] == 1
    assert rep["tests_run"] == 1 and rep["executable"]["n"] == 1
    row = rep["executable"]["top"][0]
    assert row["params"] == {"feature": "ret_24", "band": [0.9, 1.0], "horizon": 6, "side": 1}
    assert row["n_independent"] >= pc.MIN_TRADES, row
    assert row["selection_trials"] == 9000 and row["n_tests_sweep"] == 9001
    assert row["t_deflated_sweep"] == round(deflate_t(row["t_gross"], 9001), 3)
    assert rep["unexecutable"]["n"] == 2 and rep["unexecutable"]["tasks"] == 2
    assert rep["skipped"]["reasons"][f"below the |t| >= {af.MIN_T:g}, n >= {af.MIN_N} floor"] == 2
    tasks = _queue_rows(queue, af.SOURCE)
    assert [t["kind"] for t in tasks] == ["anomaly", "anomaly"]
    assert tasks[0]["params"]["condition"] == "lead_lag_SYNB_lag1"          # strongest first
    assert tasks[0]["symbols"] == ["SYNA", "SYNB"] and tasks[0]["family"] is None
    assert tasks[1]["params"]["condition"] == "no_such_primitive_q0.9-1"
    for t in tasks:
        assert t["status"] is None and "MECHANISM MUST BE NAMED" in t["description"]
        assert t["params"]["horizon"] == t["params"]["horizon"] and "t=" in t["description"]
    assert "anomaly" in tasks[0]["consumer"]
    # Proposal is decided by the charged deflation, and donation follows it exactly.
    assert rep["cells_proposed"] == int(row["proposed"])
    assert len(donated) == int(row["proposed"])
    if donated:
        c = donated[0][1][0]
        assert c["family"] == "discovered" and c["evidence"]["mechanism_status"] in (
            "UNNAMED", "ADAPTER_NAMED")
        assert donated[0][2] == 1
    written = json.loads((tmp_path / "ANOMALY_FACTORY.json").read_text("utf-8"))
    for key in ("tests_run", "cells_proposed", "executable", "unexecutable", "skipped"):
        assert key in written


def test_buried_regions_are_not_re_proposed(universe, queue, tmp_path, monkeypatch):
    universe("SYNA", _bars(days=120, seed=4))
    _factory_env(tmp_path, monkeypatch, [_anomaly()], buried={("SYNA", "ret_24", 1): 3})
    rep = af.run(budget_s=60)
    assert rep["tests_run"] == 0 and rep["buried"] == 1
    assert rep["skipped"]["reasons"]["region already buried in the hypothesis graph"] == 1
    assert rep["skipped"]["detail"][0]["n_failed"] == 3


def test_a_failed_scan_is_a_recorded_reason_and_leaves_the_queue_alone(universe, queue, tmp_path,
                                                                        monkeypatch):
    queue.parent.mkdir(parents=True)
    queue.write_text(json.dumps({"tasks": [{"source": af.SOURCE, "kind": "anomaly"}]}), "utf-8")
    _factory_env(tmp_path, monkeypatch, [])

    def boom(symbols=None, limit=None):
        raise RuntimeError("no bars")
    monkeypatch.setattr(af.am, "scan", boom)
    rep = af.run(budget_s=5)
    assert rep["tests_run"] == 0 and "RuntimeError" in rep["scan"]["error"]
    assert len(_queue_rows(queue, af.SOURCE)) == 1, "a failed scan must not erase real tasks"


def test_no_module_names_a_crypto_exchange_universe():
    for mod in (af, dm, fmc):
        text = inspect.getsource(mod).lower()
        for banned in BANNED:
            assert banned not in text, f"{mod.__name__} touches a forbidden venue: {banned}"
