"""A roster descriptor cannot masquerade as a verified, frozen execution identity."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK / "scripts", DESK / "research", DESK, DESK.parents[1]):
    sys.path.insert(0, str(path))

import heal_identity_broken_clocks as heal  # noqa: E402
import shadow_forward as engine  # noqa: E402
from mt5desk.engine import Costs  # noqa: E402
from research import h1_source  # noqa: E402

FIELDS = {"spread_per_lot": 647.0, "commission_per_lot": 2.0,
          "contract_oz": 100000.0, "quote_per_account": 20.48969}
SPEC = {"symbol": "GBPMXN", "family": "clock_transition", "selector": "asia",
        "side": "LONG", "params": {"label": "tokyo_open", "side": 1, "stamp_hour": 0}}


def test_exact_gbpmxn_malformed_freeze_cannot_be_declared_restored():
    old = {**SPEC, "code_hash": "425a56cfd425ccf4", "behaviour_hash": "f0046e0220e835c8"}
    assert heal.current_identity({"identity": old}) is None
    assert "direction" not in old  # detection does not silently backfill/bless the old record


@pytest.fixture
def resolved(monkeypatch):
    def family(df, **kwargs):
        return df

    monkeypatch.setattr(engine, "_family_fn", lambda _: family)
    monkeypatch.setattr(h1_source, "from_cache",
                        lambda *args: SimpleNamespace(evidence_venue="MT5:FusionMarkets-Live"))
    return family


@pytest.mark.parametrize("timeframe,side", [("H1", "LONG"), ("M5", "SHORT"), ("M30", "LONG")])
def test_freeze_constructor_matches_the_real_engine(resolved, timeframe, side):
    spec = {**SPEC, "side": side, "params": {**SPEC["params"], "timeframe": timeframe}}
    got = heal.execution_identity(spec, FIELDS)
    expected = heal.reg.identity(
        family=spec["family"], symbol=spec["symbol"], direction=side, timeframe=timeframe,
        selector=spec["selector"], condition=None, params=spec["params"],
        code=heal.reg.code_hash(resolved), behaviour=heal.reg.behaviour_hash(resolved),
        cost=heal.reg.cost_hash(Costs(**FIELDS)), data_venue="MT5:FusionMarkets-Live")
    assert got == expected
    assert all(field in got for field in heal.reg.IDENTITY_FIELDS)
    assert len(got["sleeve_id"]) == 20


def test_missing_costs_or_unknown_venue_do_not_create_a_clock(resolved, monkeypatch):
    assert heal.execution_identity(SPEC, None) is None
    monkeypatch.setattr(h1_source, "from_cache",
                        lambda *args: SimpleNamespace(evidence_venue="UNKNOWN-VENUE"))
    assert heal.execution_identity(SPEC, FIELDS) is None
    monkeypatch.setattr(h1_source, "from_cache", lambda *args: None)
    assert heal.execution_identity(SPEC, FIELDS) is None


def test_unloadable_family_does_not_create_a_clock(resolved, monkeypatch):
    monkeypatch.setattr(engine, "_family_fn", lambda _: None)
    assert heal.execution_identity(SPEC, FIELDS) is None


def test_existing_malformed_identity_is_not_rewritten_or_credited(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "DESK", tmp_path)
    state_path = tmp_path / "reports" / "shadow" / "shadow_state.json"
    state_path.parent.mkdir(parents=True)
    key = "GBPMXN.clock_transition.asia#label=tokyo_open_side=1_stamp_hour=0"
    state = {key: {"status": "ACTIVE", "forward_start": "2026-09-30", "n": 2}}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    old = {"sleeves": {key: {"identity": dict(SPEC)}}}
    monkeypatch.setattr(heal.reg, "freeze",
                        lambda *a, **k: pytest.fail("an old malformed clock must be archived first"))
    assert heal.freeze_unfrozen(old, apply=True, identities={key: SPEC}) == 0
    assert json.loads(state_path.read_text()) == state
    assert old["sleeves"][key]["identity"] == SPEC


def test_behaviour_backfill_publishes_atomically_not_via_a_shadowed_dict(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"sleeves": {"USDJPY.asia": {
        "identity": {"code_hash": "same"}}}}), encoding="utf-8")
    monkeypatch.setattr(heal, "current_identity",
                        lambda row: {"code_hash": "same", "behaviour_hash": "bytecode"})
    assert heal.backfill_behaviour(path, apply=True) == 1
    doc = json.loads(path.read_text())
    assert doc["sleeves"]["USDJPY.asia"]["identity"]["behaviour_hash"] == "bytecode"
    assert doc["updated_at"]
    assert not path.with_suffix(".json.tmp").exists()
