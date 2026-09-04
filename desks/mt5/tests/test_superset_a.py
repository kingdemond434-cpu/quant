"""The first superset batch: typed units, the DataHub, the feature store, netting, the fill
surface and execution policy, strategy artifacts, the release, the immutable evaluator, the
graveyard model and pre-registration.

What is pinned:

  * a number without a declared unit cannot be built, unlike units cannot be added, and two
    sources disagreeing by more than the tolerance is a finding with a number;
  * the hub tries providers in order, stamps rows point-in-time, and records mined provenance;
  * a feature block is identified by (name, code, params, bars) -- same inputs, same id, cache
    hit; different bars, different id -- and a non-causal compute is refused;
  * netting collapses opposing theoretical positions and attribution survives it;
  * the fill surface falls back to the spread prior below the sample floor and fits above it;
  * execution policy never chooses a resting order the surface says will not fill, and SKIP wins
    when no action has positive utility;
  * an artifact without a certificate, symbol or cost basis is refused;
  * the release id changes when a money-path file changes; the immutable manifest catches a
    changed judge; a pre-registered card's hash is stable and a verdict without one is flagged;
  * the graveyard model names the failure class the gates imply and yields a pre-mortem.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import execution_policy, fill_surface, netting  # noqa: E402

from libs.data import datahub, feature_store, units  # noqa: E402
from libs.ops import release  # noqa: E402
from libs.research import graveyard_model, preregistration, strategy_artifact  # noqa: E402


def _bars(n: int = 1200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(scale=0.1, size=n))
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.1,
                       "low": close - 0.1, "close": close,
                       "spread": rng.integers(10, 20, n).astype(float),
                       "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)
    return df


# --------------------------------------------------------------------------- units
def test_units_refuse_the_untyped_and_the_mismatched() -> None:
    with pytest.raises(units.UnitError):
        units.Quantity(1.0, "furlongs")
    a = units.Quantity(0.18, "price", currency="USD", source="mt5")
    b = units.Quantity(0.00008, "price", currency="USD", source="mt5")
    assert (a + b).value == pytest.approx(0.18008)
    with pytest.raises(units.UnitError):
        _ = a + units.Quantity(1.0, "points")
    with pytest.raises(units.UnitError):
        _ = a + units.Quantity(1.0, "price", currency="EUR")
    assert units.Quantity(25.0, "bp").convert("fraction").value == pytest.approx(0.0025)
    assert units.to_price(units.Quantity(15.0, "points"), 0.01).value == pytest.approx(0.15)
    r = units.reconcile(units.Quantity(1.000, "price", source="A"),
                        units.Quantity(1.002, "price", source="B"), rel_tol=1e-3)
    assert r["agree"] is False and r["rel_diff"] == pytest.approx(0.002, rel=1e-2)


# --------------------------------------------------------------------------- datahub
def test_hub_tries_providers_in_order_and_stamps_rows(tmp_path) -> None:
    hub = datahub.DataHub()
    calls: list[str] = []

    def dead(**kw):
        calls.append("dead")
        raise OSError("vendor down")

    def alive(**kw):
        calls.append("alive")
        return [{"title": "cpi", "found_at": "2026-01-02T00:00:00+00:00"}]
    hub.register(datahub.Contract("calendar.events", "rows", providers=[
        datahub.Provider("vendor_a", dead, "primary"),
        datahub.Provider("vendor_b", alive, "backup")]))
    out = hub.get("calendar.events")
    assert out["provider"] == "vendor_b" and calls == ["dead", "alive"]
    assert out["payload"][0]["available_time"] == "2026-01-02T00:00:00+00:00"
    assert out["payload"][0]["payload_hash"]
    hub.register(datahub.Contract("terms.spread", "quantity", unit="price", providers=[
        datahub.Provider("a", lambda **kw: 0.18), datahub.Provider("b", lambda **kw: 0.30)]))
    assert hub.reconcile("terms.spread")["agree"] is False
    row = datahub.record_mined_source(repo="x/y", url="https://example/x", commit="abc",
                                      license_="AGPL-3.0", file="f.py", mechanism="m",
                                      path=tmp_path / "mined.jsonl")
    assert row["code_copied"] is False and "reimplemented" in row["policy"]
    assert datahub.copy_allowed("MIT") and not datahub.copy_allowed("AGPL-3.0")


# --------------------------------------------------------------------------- feature store
def test_feature_ids_are_content_addressed_and_cached(tmp_path) -> None:
    fs = feature_store.FeatureStore(tmp_path)
    df = _bars()
    a = fs.get("realised_vol", df, {"w": 24}, check_causal=True)
    b = fs.get("realised_vol", df, {"w": 24})
    assert fs.hits == 1 and fs.misses == 1 and np.array_equal(np.nan_to_num(a), np.nan_to_num(b))
    c = fs.get("realised_vol", df.iloc[:-10], {"w": 24})
    assert fs.misses == 2 and c.shape[0] == len(df) - 10
    assert fs.get("realised_vol", df, {"w": 48}).shape[0] == len(df)
    m = fs.matrix(df, [("log_return", {"h": 1}), ("zscore", {"of": "range_frac", "w": 48}),
                       ("hour", {}), ("column", {"col": "spread"})])
    assert m.shape == (len(df), 4)
    assert fs.census()["blocks"] >= 5


def test_a_non_causal_feature_is_refused(tmp_path) -> None:
    @feature_store.register("_leaky_test", "count")
    def _leaky(df: pd.DataFrame, p: dict) -> np.ndarray:
        return np.full(len(df), float(df["close"].iloc[-1]))         # looks at the last bar
    fs = feature_store.FeatureStore(tmp_path)
    with pytest.raises(ValueError, match="NOT CAUSAL"):
        fs.get("_leaky_test", _bars(300), {}, check_causal=True)
    feature_store.REGISTRY.pop("_leaky_test", None)


# --------------------------------------------------------------------------- netting
def test_netting_collapses_opposing_positions_and_keeps_attribution() -> None:
    T = netting.Theoretical
    pos = [T("A", "XAUUSD", 0.20), T("B", "XAUUSD", -0.08), T("C", "XAUUSD", 0.05),
           T("D", "EURUSD", 0.10)]
    n = netting.net_targets(pos)
    assert n["XAUUSD"]["net_lots"] == pytest.approx(0.17)
    assert n["XAUUSD"]["saved_lots"] == pytest.approx(0.16) and n["XAUUSD"]["opposing"]
    assert n["EURUSD"]["saved_lots"] == 0.0 and not n["EURUSD"]["opposing"]
    pnl = netting.virtual_pnl({p.sleeve: p for p in pos}, {"XAUUSD": 3010.0, "EURUSD": 1.1},
                              {"XAUUSD": 3000.0, "EURUSD": 1.1}, {"XAUUSD": 100.0})
    assert pnl["A"] == pytest.approx(200.0) and pnl["B"] == pytest.approx(-80.0)
    intents = [{"time": "2026-09-01T10:00:00+00:00", "symbol": "XAUUSD", "side": "buy",
                "lot": 0.2},
               {"time": "2026-09-01T11:00:00+00:00", "symbol": "XAUUSD", "side": "sell",
                "lot": 0.1},
               {"time": "2026-09-03T11:00:00+00:00", "symbol": "XAUUSD", "side": "sell",
                "lot": 0.1}]
    rep = netting.savings_report(intents, write=False)
    assert rep["per_symbol"]["XAUUSD"]["opposing_lots"] == pytest.approx(0.2)
    assert rep["verdict"] == "NETTING_WORTH_ROUTING"


# --------------------------------------------------------------------------- fill surface
def _intent_rows(n: int, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        spread = float(rng.uniform(0.1, 0.4))
        rows.append({"time": f"2026-08-{1 + i % 28:02d}T{int(rng.integers(0, 24)):02d}:00:00+00:00",
                     "intended": 3000.0, "fill": 3000.0 + spread * 0.6 + rng.normal(0, 0.02),
                     "spread_at_decision": spread, "atr_frac": 0.003, "lot": 0.1,
                     "side": "buy", "order_type": "limit",
                     "distance_frac": float(rng.uniform(0, 0.002)),
                     "filled": bool(rng.uniform() < 0.6)})
    return rows


def test_fill_surface_prior_then_fit() -> None:
    fs = fill_surface.FillSurface().fit(_intent_rows(5))
    assert fs.slip_w is None and "prior" in fs.note
    mu, sd = fs.expected_slip({"intended": 3000.0, "spread_at_decision": 0.3, "time":
                               "2026-08-01T10:00:00+00:00", "lot": 0.1, "side": "buy",
                               "atr_frac": 0.003}, spread_frac_prior=1e-4)
    assert mu == pytest.approx(5e-5) and sd == pytest.approx(1e-4)
    fitted = fill_surface.FillSurface().fit(_intent_rows(200))
    assert fitted.slip_w is not None and fitted.n_fills == 200 and fitted.fill_w is not None
    mu2, _ = fitted.expected_slip({"intended": 3000.0, "spread_at_decision": 0.3, "time":
                                   "2026-08-01T10:00:00+00:00", "lot": 0.1, "side": "buy",
                                   "atr_frac": 0.003}, spread_frac_prior=1e-4)
    assert 0 < mu2 < 3e-4                                            # ~0.6 x spread / price
    p_near = fitted.p_fill({**_intent_rows(1)[0], "distance_frac": 0.0})
    p_far = fitted.p_fill({**_intent_rows(1)[0], "distance_frac": 0.01})
    assert 0.0 <= p_far <= 1.0 and 0.0 <= p_near <= 1.0


def test_execution_policy_chooses_by_utility_and_skips_a_dead_signal() -> None:
    C = execution_policy.Context
    live = C("XAUUSD", "buy", 3000.0, spread_frac=1e-4, atr_frac=0.003, stop_frac=0.004,
             edge_r=0.3, hour=10, lot=0.1)
    d = execution_policy.choose(live)
    assert d["would_have_traded"] and d["policy"] in execution_policy.POLICIES
    assert set(d["alternatives"]) >= {"MARKET", "PULLBACK", "SKIP", "SPLIT"}
    dead = C("XAUUSD", "buy", 3000.0, spread_frac=1e-3, atr_frac=0.003, stop_frac=0.004,
             edge_r=0.0, hour=10, lot=0.1)
    assert execution_policy.choose(dead)["policy"] == "SKIP"
    wide = C("XAUUSD", "buy", 3000.0, spread_frac=5e-4, atr_frac=0.003, stop_frac=0.004,
             edge_r=0.3, hour=10, lot=0.1, spread_rank=0.95)
    assert "SPREAD_CONDITIONED" in execution_policy.choose(wide)["alternatives"]


# --------------------------------------------------------------------------- artifacts
def test_strategy_artifact_refuses_what_the_allocator_cannot_size() -> None:
    cert = {"sym": "XAUUSD", "shadow_spec": {"family": "session_range_breakout",
                                            "selector": "asia", "params": {"rr": 1.5}},
            "hunt": "external_discoveries", "status": "PASS", "cost_hash": "abc"}
    a = strategy_artifact.from_certificate("external.XAUUSD.srb", cert)
    v = strategy_artifact.validate(a, known_families={"session_range_breakout"},
                                   known_symbols={"XAUUSD"})
    assert v["ok"] and a.to_dict()["version_hash"] == a.compute_hash()
    bad = strategy_artifact.from_certificate("k", {"shadow_spec": {"family": "nope"}})
    vb = strategy_artifact.validate(bad, known_families={"session_range_breakout"})
    assert not vb["ok"] and len(vb["problems"]) >= 3


# --------------------------------------------------------------------------- release
def test_release_id_tracks_the_money_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(release, "RELEASE", tmp_path / "RELEASE.json")
    d1 = release.build(write=True)
    assert release.release_id() == d1["release_id"]
    assert release.verify()["ok"]
    monkeypatch.setattr(release, "MONEY_PATH", (*release.MONEY_PATH, "CLAUDE.md"))
    d2 = release.build(write=False)
    assert d2["money_path_hash"] != d1["money_path_hash"] and d2["release_id"] != d1["release_id"]
    assert not release.verify()["ok"]


def test_immutable_manifest_catches_a_changed_judge(tmp_path, monkeypatch) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cie", _ROOT / "scripts" / "check_immutable_evaluator.py")
    cie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cie)                                        # type: ignore[union-attr]
    monkeypatch.setattr(cie, "MANIFEST", tmp_path / "m.json")
    (tmp_path / "judge.py").write_text("x = 1\n")
    monkeypatch.setattr(cie, "ROOT", tmp_path)
    monkeypatch.setattr(cie, "IMMUTABLE", ("judge.py",))
    assert cie.check()[0]["why"].startswith("no IMMUTABLE_MANIFEST")
    cie.sign("test")
    assert cie.check() == []
    (tmp_path / "judge.py").write_text("x = 2\n")
    assert "changed since signing" in cie.check()[0]["why"]


# --------------------------------------------------------------------------- graveyard
def test_graveyard_model_names_the_class_and_gives_a_premortem() -> None:
    rows = []
    for i in range(60):
        rows.append({"id": f"c{i}", "symbol": "EURUSD", "family": "carry", "source": "x",
                     "fate": "FAILED", "gates": {"stress_costs": {"passed": False}},
                     "params": {"a": 1}})
    for i in range(40):
        rows.append({"id": f"b{i}", "symbol": "XAUUSD", "family": "session_range_breakout",
                     "source": "y", "fate": "FAILED",
                     "gates": {"deflated_sharpe": {"passed": False}}, "params": {}})
    for i in range(10):
        rows.append({"id": f"s{i}", "symbol": "XAUUSD", "family": "session_range_breakout",
                     "source": "y", "fate": "CERTIFIED", "gates": {}, "params": {}})
    m = graveyard_model.GraveyardModel().fit(rows)
    assert m.summary()["failure_classes"]["COST_DEATH"] == 60
    pm = m.premortem({"symbol": "EURUSD", "family": "carry", "source": "x", "params": {"a": 2}})
    assert pm["failure_class"] == "COST_DEATH" and "cost" in pm["first_test"]
    pm2 = m.premortem({"symbol": "XAUUSD", "family": "session_range_breakout", "source": "y"})
    assert pm2["p_survivor"] > pm["p_survivor"]
    assert graveyard_model.failure_class({"placebo_entry_shift": {"passed": False}}) == "LEAKAGE"


# --------------------------------------------------------------------------- preregistration
def test_preregistration_hash_is_stable_and_unregistered_verdicts_are_flagged(tmp_path) -> None:
    cand = {"title": "t", "mechanism": "m", "family": "formula", "symbol": "XAUUSD",
            "params": {"expr": ["delta", "close", 24], "hold_bars": 8, "side_mode": "follow"},
            "evidence": {"screen": "s"}}
    card = preregistration.from_candidate(cand)
    assert preregistration.validate(card) == []
    h = preregistration.register(card, source="alpha_evolution", path=tmp_path / "p.jsonl")
    assert preregistration.register(card, source="alpha_evolution", path=tmp_path / "p.jsonl") == h
    with pytest.raises(ValueError):
        preregistration.register({"hypothesis": "only this"}, source="x", path=tmp_path / "p.jsonl")
    chk = preregistration.check([{"id": "v1", "prereg_hash": h}, {"id": "v2"}],
                                path=tmp_path / "p.jsonl")
    assert chk["registered"] == 1 and chk["unregistered"] == ["v2"] and not chk["ok"]
