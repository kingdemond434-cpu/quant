"""The whole certified book inside survival (principal 2026-10-06: "the max growth n promising
sleeve book"). `kelly_survival.solve_book` keeps banned families out, funds no negative-edge
sleeve, never exceeds the gateway's per-trade ceiling, and publishes only a book whose P(death)
holds on an independent sample, as estimated and with edges halved."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ks = pytest.importorskip("kelly_survival")


def _cert(sym: str, fam: str) -> dict:
    return {"sym": sym, "cell": f"{sym}.{fam}", "gates": {"stress_costs": {"exp_x3": 0.2}},
            "shadow_spec": {"family": fam, "selector": "asia", "symbol": sym}}


@pytest.fixture()
def desk(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    names = ["gold_asia", "AAA_carry_asia", "BBB_carry_asia", "CCC_discovered_asia"]
    r = rng.normal(0.0, 1.0, (32, 128, 4))
    r[:, :, 0] += 0.10
    r[:, :, 1] = r[:, :, 1] * 0.3 + 0.10            # strong, low vol: wants more than the cap
    r[:, :, 2] -= 0.10                               # negative edge: must get nothing
    r[:, :, 3] = r[:, :, 3] * 0.3 + 0.30             # banned family: must get nothing
    worlds = tmp_path / "worlds.npz"
    np.savez(worlds, r=r, names=np.array(names), crisis=np.zeros(32), mu=np.zeros((32, 4)))
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps({"gate_policy": {"version": "v2"}, "survivors": {
        "a": _cert("AAA", "carry"), "b": _cert("BBB", "carry"),
        "c": _cert("CCC", "discovered")}}), encoding="utf-8")
    monkeypatch.setattr(ks, "WORLDS", worlds)
    monkeypatch.setattr(ks, "CERT_CANON", canon)
    monkeypatch.setattr(ks, "CERT_STORE", tmp_path / "absent_store.json")
    monkeypatch.setattr(ks, "_replayed_certificates", lambda: ({}, "no replay in tests"))
    monkeypatch.setattr(ks, "LEDGER", tmp_path / "absent.jsonl")
    monkeypatch.setattr(ks, "BOOK_PATHS", 400)
    monkeypatch.setattr(ks, "BOOK_STARTS", 2)
    monkeypatch.setattr(ks, "BOOK_STEPS", (0.02, 0.005))
    monkeypatch.setattr(ks, "TERMS_FENCED_CELLS", tmp_path / "absent_fence.json")
    monkeypatch.setattr(ks, "RESEARCH_QUEUE", tmp_path / "absent_queue.json")
    return ks


def test_book_screens_caps_and_survives(desk):
    from mt5desk.sizing import MAX_RISK_FRAC
    doc = desk.solve_book()
    assert doc["status"] == "OK"
    assert "CCC_discovered_asia" not in doc["columns"]
    assert {r["certificate"]: r.get("excluded") for r in doc["screen"]}["c"] == "banned family"
    assert all(r["v4"] is False for r in doc["screen"])
    fus = doc["fusion"]
    assert fus["status"] == "OK"
    assert "BBB_carry_asia" not in fus["heat"]
    assert fus["heat"]["AAA_carry_asia"] <= MAX_RISK_FRAC + 1e-9
    assert fus["as_estimated"]["p_death"] <= ks.EPS_DEATH
    assert fus["edges_halved"]["p_death"] <= ks.EPS_DEATH
    assert doc["e8"]["status"].startswith("UNMEASURED")


def test_unpriced_certificates_are_replayed_and_join(desk, tmp_path, monkeypatch):
    """A certificate the allocator never priced is priced by replay and can win heat; the store
    is read before the canon, and a store row without a family field takes it from its key."""
    import pandas as pd
    store = tmp_path / "store.json"
    store.write_text(json.dumps({"survivors": {
        "external.DDD.carry.p=1": {"sym": "DDD", "cell": "DDD.carry",
                                   "shadow_spec": {"selector": "asia", "symbol": "DDD"}},
        "external.EEE.carry.p=2": {"sym": "EEE", "cell": "EEE.carry",
                                   "shadow_spec": {"selector": "asia", "symbol": "EEE"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(desk, "CERT_STORE", store)
    rng = np.random.default_rng(3)
    idx = pd.date_range("2024-01-01", periods=400).date
    series = {"DDD_carry_asia": pd.Series(rng.normal(0.08, 0.3, 400), index=idx),
              "EEE_carry_asia": pd.Series(rng.normal(-0.05, 0.3, 400), index=idx)}
    monkeypatch.setattr(desk, "_replayed_certificates", lambda: (series, "test replay"))
    doc = desk.solve_book()
    assert doc["status"] == "OK"
    assert "DDD_carry_asia" in doc["columns"]
    assert "EEE_carry_asia" not in doc["columns"]          # negative mean never joins
    assert doc["fusion"]["heat"].get("DDD_carry_asia", 0) > 0
    rows = {r["certificate"]: r for r in doc["screen"]}
    assert rows["external.DDD.carry.p=1"]["family"] == "carry"
    assert rows["external.DDD.carry.p=1"]["store"] == "store.json"
    assert "1 joined" in doc["unpriced"]


def test_a_certificate_judged_on_a_reddit_card_never_enters_the_book(desk, tmp_path, monkeypatch):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps([
        {"geneology_id": "external:ext_reddit_AAA_carry"},
        {"geneology_id": "external:ext_reddit_BBB_carry"},
        {"geneology_id": "external:ext_forexfactory_BBB_carry"}]), encoding="utf-8")
    monkeypatch.setattr(desk, "RESEARCH_QUEUE", queue)
    doc = desk.solve_book()
    why = {r["certificate"]: r.get("excluded") for r in doc["screen"]}
    assert why["a"].startswith("TERMS_QUARANTINE")
    assert why["b"] is None                           # a lawful card also carried it
    assert "AAA_carry_asia" not in doc["fusion"]["heat"]
    fence = tmp_path / "fence.json"                   # the published index wins over genealogy
    fence.write_text(json.dumps({"cells": ["BBB.carry"]}), encoding="utf-8")
    monkeypatch.setattr(desk, "TERMS_FENCED_CELLS", fence)
    assert desk.terms_fenced_cells()[0] == {"BBB.carry"}


def test_the_fence_decides_per_certificate_when_it_is_importable(desk, monkeypatch):
    import sys
    import types
    fence = types.ModuleType("libs.data.terms_fence")
    fence.quarantined_certificate = lambda key="", **kw: "held" if key == "a" else None
    pkg = types.ModuleType("libs.data")
    pkg.terms_fence = fence
    monkeypatch.setitem(sys.modules, "libs.data", pkg)
    monkeypatch.setitem(sys.modules, "libs.data.terms_fence", fence)
    why = {r["certificate"]: r.get("excluded") for r in desk.solve_book()["screen"]}
    assert why["a"].startswith("TERMS_QUARANTINE") and why["b"] is None
