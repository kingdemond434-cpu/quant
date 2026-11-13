"""Decay-aware refit trigger: decayed / regime-broken live and forward cells of a learned family are
re-proposed on their event-driven refit schedule, once per window, through the intake door; other
families are counted as a named gap; absent inputs are UNMEASURED."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import decay_refit_trigger as drt  # noqa: E402

NOW = datetime(2026, 11, 14, 2, tzinfo=UTC)
GNN_KEY = "EURUSD.gnn_propagation.daily#adjacency=lead_lag_layers=1"
SPECS = {
    GNN_KEY: {"symbol": "EURUSD", "family": "gnn_propagation", "side": "LONG",
              "params": {"adjacency": "lead_lag", "layers": 1, "peer_symbols": ["EURUSD", "GBPUSD"],
                         "entry_z": 1.0}},
    "USDJPY.carry.daily": {"symbol": "USDJPY", "family": "carry", "side": "LONG", "params": {}},
    "XAUUSD.attention_ts.daily": {"symbol": "XAUUSD", "family": "attention_ts", "side": "LONG",
                                  "params": {"heads": 1, "lookback": 20, "refit": "decay"}},
}


def _shadow(**cells: dict) -> dict:
    return {"updated_at": NOW.isoformat(), **cells}


def test_forward_kill_on_a_learned_family_proposes_its_decay_refit() -> None:
    doc = drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=[],
                   shadow=_shadow(**{GNN_KEY: {"n": 40, "status": "KILL", "forward_t": -1.2},
                                     "USDJPY.carry.daily": {"n": 30, "status": "ACTIVE",
                                                            "forward_t": -0.4}}))
    assert [(p["cell"], p["mode"]) for p in doc["proposals"]] == [(GNN_KEY, "decay")]
    p = doc["proposals"][0]
    assert p["params"]["refit"] == "decay" and p["params"]["adjacency"] == "lead_lag"
    assert doc["no_refit_schedule"] == {"carry": 1}         # counted, never silently dropped
    assert doc["status"] == "MEASURED"


def test_a_cell_already_on_that_schedule_is_not_reproposed() -> None:
    doc = drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=[],
                   shadow=_shadow(**{"XAUUSD.attention_ts.daily": {"n": 25, "status": "KILL",
                                                                    "forward_t": -2}}))
    assert doc["proposals"] == [] and doc["already_on_that_schedule"]


def test_one_proposal_per_cell_and_mode_per_window() -> None:
    sh = _shadow(**{GNN_KEY: {"n": 40, "status": "KILL", "forward_t": -1.2}})
    led = [{"at": (NOW - timedelta(days=3)).isoformat(), "cell": GNN_KEY, "mode": "decay"}]
    assert drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=led,
                    shadow=sh)["proposals"] == []
    old = [{"at": (NOW - timedelta(days=drt.REPROPOSE_DAYS + 1)).isoformat(),
            "cell": GNN_KEY, "mode": "decay"}]
    assert drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=old,
                    shadow=sh)["proposals"]


def test_live_fade_and_regime_class_trigger_decay() -> None:
    live = {"checked_at": NOW.isoformat(), "verdicts": {
        GNN_KEY: {"verdict": "HEALTHY", "regime_class": "STRUCTURAL_BREAK", "regime_why": "bocpd"},
        "USDJPY.carry.daily": {"verdict": "FADE", "why": "t<=0"}}}
    doc = drt.plan(NOW, decay_live=live, shadow=None, drift=None, specs=SPECS, ledger=[])
    assert [(p["cell"], p["mode"]) for p in doc["proposals"]] == [(GNN_KEY, "decay")]
    assert doc["no_refit_schedule"] == {"carry": 1}


def test_regime_shift_proposes_the_regime_schedule() -> None:
    drift = {"generated_utc": NOW.isoformat(), "structure_verdict": "STABLE",
             "per_symbol": {"EURUSD": {"hazard_max": 2.6}, "XAUUSD": {"hazard_max": 0.4}},
             "hazard_by_sleeve": {}}
    doc = drt.plan(NOW, decay_live=None, shadow=None, drift=drift, specs=SPECS, ledger=[])
    assert [(p["cell"], p["mode"]) for p in doc["proposals"]] == [(GNN_KEY, "regime")]
    book = {**drift, "structure_verdict": "STRUCTURE_SHIFTED", "per_symbol": {}}
    doc = drt.plan(NOW, decay_live=None, shadow=None, drift=book, specs=SPECS, ledger=[])
    assert {(p["cell"], p["mode"]) for p in doc["proposals"]} == {
        (GNN_KEY, "regime"), ("XAUUSD.attention_ts.daily", "regime")}


def test_stale_or_absent_inputs_are_unmeasured_and_trigger_nothing() -> None:
    stale = {"updated_at": (NOW - timedelta(days=5)).isoformat(),
             GNN_KEY: {"n": 40, "status": "KILL", "forward_t": -1.2}}
    doc = drt.plan(NOW, decay_live=None, shadow=stale, drift=None, specs=SPECS, ledger=[])
    assert doc["status"] == "UNMEASURED" and doc["proposals"] == []


def test_unresolved_learned_spec_is_reported_not_guessed() -> None:
    key = "GBPUSD.rocket_ts.daily"
    doc = drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=[],
                   shadow=_shadow(**{key: {"n": 40, "status": "KILL", "forward_t": -1},
                                     "AUDUSD.carry.daily": {"n": 40, "status": "KILL",
                                                            "forward_t": -1}}))
    assert doc["unresolved_spec"] == [key] and doc["no_refit_schedule"] == {"carry": 1}


def test_family_from_key() -> None:
    assert drt.family_from_key("XAUUSD.asia#rr=1.5") == "session_range_breakout"
    assert drt.family_from_key("EURNOK.overnight_gap_decay.asia") == "overnight_gap_decay"
    assert drt.family_from_key("X.carry.daily@M5#a=1") == "carry"


def test_candidate_is_an_exact_recipe_with_the_schedule(tmp_path: Path) -> None:
    doc = drt.plan(NOW, decay_live=None, drift=None, specs=SPECS, ledger=[],
                   shadow=_shadow(**{GNN_KEY: {"n": 40, "status": "KILL", "forward_t": -1.2}}))
    c = drt.to_candidate(doc["proposals"][0])
    assert c["family"] == "gnn_propagation" and c["symbol"] == "EURUSD"
    assert c["params"]["refit"] == "decay" and c["lineage"]["parent_cell"] == GNN_KEY
    assert json.dumps(c)                                    # serialisable for the intake
