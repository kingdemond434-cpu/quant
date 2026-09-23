"""Feature genealogy (Tier-1 A9): breadth measured at the VARIABLE level.

Measured 2026-09-08: both StrategyArtifact constructors set feature_ids=[] on every artifact, so
"these twelve alphas are all the 20-day range" was not a question any module could answer.
Pinned: `from_certificate` stamps variable-level ids from the certificate's params (value-bearing
names carry their value, tunables their name), the alpha genome carries the same ids and rolls
them up as `feature_genealogy`, and a certificate with no params says so in the denominator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import strategy_artifact as sa  # noqa: E402
from research import alpha_genome as ag  # noqa: E402


def test_feature_ids_carry_the_variable_not_only_the_knob() -> None:
    ids = sa.feature_ids_of({"feature": "hour", "band": [0.9, 1.0], "horizon": 3, "side": -1,
                             "factor_symbols": ["US500", "DXY"], "input_source": "cot_pit"})
    assert ids == ["band", "factor_symbols:DXY", "factor_symbols:US500", "feature:hour",
                   "horizon", "input_source:cot_pit", "side"]
    assert sa.feature_ids_of({}) == [] and sa.feature_ids_of(None) == []
    assert sa.feature_ids_of({"feature": None, "peer_symbol": ""}) == []


def test_from_certificate_populates_feature_ids_and_hashes_them() -> None:
    cert = {"sym": "EURCHF", "shadow_spec": {"family": "discovered", "selector": "asia",
                                            "params": {"feature": "hour", "band": [0.9, 1.0],
                                                       "horizon": 3, "side": -1}},
            "hunt": "external", "status": "PASS", "cost_hash": "abc"}
    a = sa.from_certificate("external.EURCHF.discovered", cert)
    assert a.feature_ids == ["band", "feature:hour", "horizon", "side"]
    other = sa.from_certificate("k", {**cert, "shadow_spec": {**cert["shadow_spec"],
                                                             "params": {"feature": "spread",
                                                                        "band": [0.9, 1.0],
                                                                        "horizon": 3,
                                                                        "side": -1}}})
    assert other.feature_ids != a.feature_ids and other.compute_hash() != a.compute_hash()
    assert sa.validate(a, known_families={"discovered"}, known_symbols={"EURCHF"})["ok"]


def _genome() -> dict[str, dict]:
    row = {"symbol": "X", "legs": ["USD"], "mechanism": "reversion", "direction_bias": "against",
           "clock": "asia", "factor_roles": [], "family": "discovered", "status": "PASS"}
    return {"a": {**row, "feature_ids": ["feature:hour", "horizon", "band"]},
            "b": {**row, "feature_ids": ["feature:hour", "horizon", "band"]},
            "c": {**row, "feature_ids": ["feature:spread", "horizon", "band"]},
            "d": {**row, "feature_ids": []}}


def test_the_genealogy_counts_sleeves_per_variable_largest_first() -> None:
    fg = ag.feature_genealogy(_genome())
    assert list(fg)[:2] == ["band", "horizon"]                 # fan-out 3, then alphabetical
    assert fg["feature:hour"] == {"n": 2, "share": 0.5, "members": ["a", "b"]}
    assert fg["feature:spread"]["n"] == 1                       # unique is a reading too
    assert ag.feature_genealogy({}) == {}


def test_run_publishes_the_variable_view_beside_the_cluster_view(tmp_path, monkeypatch) -> None:
    canon = tmp_path / "canon.json"
    spec = {"family": "discovered", "selector": "asia"}
    canon.write_text(json.dumps({"survivors": {
        "external.EURCHF.discovered": {
            "sym": "EURCHF", "status": "PASS",
            "shadow_spec": {**spec, "symbol": "EURCHF",
                            "params": {"feature": "hour", "band": [0.9, 1.0], "horizon": 3}}},
        "external.CADCHF.discovered": {
            "sym": "CADCHF", "status": "PASS",
            "shadow_spec": {**spec, "symbol": "CADCHF",
                            "params": {"feature": "hour", "band": [0.5, 0.6], "horizon": 1}}},
        "qquant.legacy": {"sym": "AUDNZD", "status": "PASS",
                          "shadow_spec": {**spec, "symbol": "AUDNZD"}},
    }}), "utf-8")
    monkeypatch.setattr(ag, "CANON", canon)
    monkeypatch.setattr(ag, "OUT", tmp_path / "ALPHA_GENOME.json")
    monkeypatch.setattr(ag, "_factor_roles", lambda sym, meta: ())
    import research.proposer_common as pc
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    doc = ag.run()
    assert doc["n_sleeves"] == 3
    assert doc["genome"]["external.EURCHF.discovered"]["feature_ids"] == \
        ["band", "feature:hour", "horizon"]
    assert doc["feature_genealogy"]["feature:hour"]["n"] == 2
    assert doc["max_feature_fanout"] == 2 and doc["n_shared_feature_ids"] == 3
    assert doc["sleeves_without_feature_ids"] == ["qquant.legacy"]
    assert doc["largest_feature_lineages"][0]["n"] == 2
    written = json.loads((tmp_path / "ALPHA_GENOME.json").read_text("utf-8"))
    assert written["feature_genealogy"] == doc["feature_genealogy"]
    # the cluster view is untouched by the new field
    assert doc["n_clusters"] >= 1 and set(doc["clusters"]) and doc["structural_breadth"] > 0
