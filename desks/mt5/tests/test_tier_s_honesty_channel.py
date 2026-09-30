"""THE HONESTY CHANNEL, end to end inside tier_s: organ_predictions scores each research factory's
backtest claims against forward/live reality (`prediction_accounting.honesty`) and saves the
multipliers with the certificate -> factory map it scored them by; the opportunity exchange's
posterior (`_posterior_bids`) and the researcher market read the same state.

Pinned defects (2026-09-30): the exchange looked the factory up by the raw `hunt` string, which
is not the name the writer scored, and `or 1.0` turned a measured honesty of 0 into 1.

Every test runs in tmp_path; none reads or writes the desk's live data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import prediction_accounting  # noqa: E402

SURV = {
    # born by the deep-forest miner (hypothesis graph), its hunt string says something else
    "h1.cellA": {"cell": "cellA", "hunt": "hunt_alpha:batch7",
                 "shadow_spec": {"symbol": "EURUSD", "selector": "asia", "family": "f"},
                 "gates": {"expected_value": {"ev": 0.4}}},
    # no graph producer: the factory is the hunt's producer
    "h2.cellB": {"cell": "cellB", "hunt": "moat_factory:gen3",
                 "shadow_spec": {"symbol": "GBPUSD", "selector": "ny", "family": "f"},
                 "gates": {"expected_value": {"ev": 0.3}}},
}
SHADOW = {"EURUSD.asia": {"n": 270, "exp_r": -0.4},       # the claim is refuted forward
          "GBPUSD.ny": {"n": 60, "exp_r": 0.3}}           # the claim holds


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: Any) -> Path:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "survivors", lambda: SURV)
    monkeypatch.setattr(ts, "shadow_rows", lambda: SHADOW)
    monkeypatch.setattr(ts, "registry", dict)
    monkeypatch.setattr(ts, "live_rows", list)
    monkeypatch.setattr(ts, "_producer_of_cell", lambda: {"cellA": "deep_forest"})
    monkeypatch.setattr(ts, "_quantity_accounting", lambda *a: {
        "prequential": {q: {} for q in prediction_accounting.QUANTITIES}})
    monkeypatch.setattr(ts.authority, "suspended", lambda k: False)
    return tmp_path


def test_organ_predictions_scores_factories_and_saves_the_key_map(desk: Path) -> None:
    out = ts.organ_predictions()
    fac = out["honesty"]["factories"]
    assert set(fac) == {"deep_forest", "moat_factory"}
    # 270 forward trades at -0.4R against a +0.4R claim: floored at zero
    assert fac["deep_forest"]["honesty"] == 0.0
    assert fac["moat_factory"]["honesty"] == 1.0
    assert out["honesty"]["most_exaggerating"][0] == "deep_forest"
    saved = json.loads((desk / "honesty.json").read_text("utf-8"))
    assert saved["factory_of_key"] == {"h1.cellA": "deep_forest", "h2.cellB": "moat_factory"}
    assert saved["factories"] == fac


def test_the_exchange_reads_the_factory_the_writer_scored(desk: Path) -> None:
    ts.organ_predictions()
    hon = ts._state("honesty")
    # the certificate born by deep_forest carries deep_forest's honesty, not its hunt's (1.0)
    assert ts._factory_honesty(hon, "h1.cellA", SURV["h1.cellA"]) == 0.0
    assert ts._factory_honesty(hon, "h2.cellB", SURV["h2.cellB"]) == 1.0
    # an unmapped certificate falls back to its hunt's producer; an unknown factory is 1.0
    assert ts._factory_honesty({"factories": {"moat_factory": {"honesty": 0.6}}}, "zz",
                               {"hunt": "moat_factory:gen9"}) == 0.6
    assert ts._factory_honesty({}, "zz", {"hunt": "nobody"}) == 1.0
    assert ts._factory_honesty({"factories": {"x": {"honesty": "bad"}}}, "k",
                               {"hunt": "x"}) == 1.0


def _bids(monkeypatch: Any) -> dict[str, Any]:
    monkeypatch.setattr(ts, "_first", lambda paths: None)
    monkeypatch.setattr(ts, "_jsonl", lambda *a, **k: [])
    monkeypatch.setattr(ts, "_read", lambda p: None)
    monkeypatch.setattr(ts, "names", lambda: SimpleNamespace(group=lambda k: str(k)))
    monkeypatch.setattr(ts, "shadow_rows", dict)           # no forward yet: mu is the prior
    bids, _live = ts._posterior_bids()
    return {b.key: b for b in bids}


def test_the_exchange_prices_a_refuted_factory_at_its_honesty(desk: Path,
                                                              monkeypatch: Any) -> None:
    ts.organ_predictions()
    by = _bids(monkeypatch)
    # prior mu = claimed ev x factory honesty (x 0.01, the exchange's unit)
    assert by["h1.cellA"].mu == pytest.approx(0.0), "a refuted factory's claim is worth nothing"
    assert by["h2.cellB"].mu == pytest.approx(0.3 * 1.0 * 0.01)


def test_a_suspended_prediction_organ_leaves_every_factory_honest(desk: Path,
                                                                 monkeypatch: Any) -> None:
    ts.organ_predictions()
    monkeypatch.setattr(ts.authority, "suspended", lambda k: k == "predictions")
    by = _bids(monkeypatch)
    assert by["h1.cellA"].mu == pytest.approx(0.4 * 0.01)

