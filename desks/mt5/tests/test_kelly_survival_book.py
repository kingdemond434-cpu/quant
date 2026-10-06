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
    monkeypatch.setattr(ks, "LEDGER", tmp_path / "absent.jsonl")
    monkeypatch.setattr(ks, "BOOK_PATHS", 400)
    monkeypatch.setattr(ks, "BOOK_STARTS", 2)
    monkeypatch.setattr(ks, "BOOK_STEPS", (0.02, 0.005))
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
