"""The research counterfactual: what reached a survivor's region first, and how long before.

Measured 2026-09-08 (inventory A5): four counterfactual modules priced TRADING decisions and
none reconstructed the discovery path of an existing survivor. `check_dig_roi --survivor` now
walks `hypothesis_graph.lineage` back from the certified node and prices the delay -- and when
the graph's earliest reach IS the certifying pass, it says the delay is BOUNDED by the graph's
memory rather than reporting a zero it never measured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.hypothesis_graph import BORN, CERTIFIED, Graph, Node, node_id  # noqa: E402
from scripts import check_dig_roi as cdr  # noqa: E402

D0, D5, D10 = ("2026-08-01T00:00:00+00:00", "2026-08-06T00:00:00+00:00",
               "2026-08-11T00:00:00+00:00")
KEY = "external.XAUUSD.carry.p=deadbeef"


def _graph(tmp_path: Path) -> Graph:
    g = Graph(tmp_path / "hypothesis_graph.jsonl")
    root = Node(symbol="XAUUSD", family="carry", params={"lookback": 20}, source="miner:cot",
                fate=BORN, at=D0)
    g.append(root)
    child = Node(symbol="XAUUSD", family="carry", params={"lookback": 25}, source="deepening",
                 parent=root.id, fate=BORN, at=D5)
    g.append(child)                                   # same region: lookback bucket [0,100)
    g.append(Node(symbol="XAUUSD", family="carry", params={"lookback": 25}, source="gauntlet",
                  parent=root.id, fate=CERTIFIED, at=D10))
    return g


def _survivors(**over) -> dict:
    base = {"hunt": "external_discoveries", "sym": "XAUUSD", "gated_at": D10,
            "shadow_spec": {"symbol": "XAUUSD", "family": "carry", "params": {"lookback": 25}}}
    base.update(over)
    return {KEY: base}


def test_the_lineage_is_walked_and_the_earliest_reach_is_priced_in_days(tmp_path) -> None:
    doc = cdr.survivor_counterfactual(KEY, survivors=_survivors(), graph=_graph(tmp_path))
    assert doc["status"] == "MEASURED"
    assert doc["node_id"] == node_id("XAUUSD", "carry", {"lookback": 25})
    assert doc["lineage_depth"] == 2
    assert [r["source"] for r in doc["lineage"]] == ["gauntlet", "miner:cot"]
    assert doc["certified_at"] == D10 and doc["certified_at_basis"] == "the node's CERTIFIED row"
    assert doc["first_reachable"]["node"]["at"] == D5                    # the cell itself
    assert doc["first_reachable"]["region"]["at"] == D0                  # its region, via the root
    assert doc["first_reachable"]["region"]["source"] == "miner:cot"
    assert doc["first_reachable"]["lineage_root"]["id"] == doc["lineage"][-1]["id"]
    assert doc["delay_days"] == 10.0
    assert "miner:cot" in doc["counterfactual"] and "10.0 day(s) before" in doc["counterfactual"]
    assert doc["unresolved_parent"] == ""


def test_a_reach_in_the_same_pass_is_bounded_by_the_graphs_memory_not_zero(tmp_path) -> None:
    """Today's state for every certificate: the verdict row is the first row, and its parent
    hash names a miner row that was never registered."""
    g = Graph(tmp_path / "graph.jsonl")
    g.append(Node(symbol="XAUUSD", family="carry", params={"lookback": 25}, source="external",
                  parent="bc6bb828ceb20716", fate=CERTIFIED, at=D10))
    doc = cdr.survivor_counterfactual(KEY, survivors=_survivors(), graph=g)
    assert doc["status"] == "BOUNDED" and doc["delay_days"] == 0.0
    assert doc["lineage_depth"] == 1
    assert doc["unresolved_parent"] == "bc6bb828ceb20716"
    assert "not measured as zero" in doc["counterfactual"]
    assert "bc6bb828ceb20716" in doc["counterfactual"]
    assert "unrecorded" in doc["counterfactual"]


def test_an_unknown_certificate_is_unmeasured_and_names_the_key(tmp_path) -> None:
    doc = cdr.survivor_counterfactual("no.such.cert", survivors=_survivors(),
                                      graph=_graph(tmp_path))
    assert doc["status"] == "UNMEASURED"
    assert "'no.such.cert'" in doc["missing_input"]
    assert "1 certificate(s) held" in doc["missing_input"]


def test_a_certificate_never_registered_in_the_graph_names_its_hunt(tmp_path) -> None:
    surv = _survivors(hunt="hunt16.json",
                      shadow_spec={"symbol": "AUDNZD", "family": "dav_range_filter_adx",
                                   "params": {"adx": 20}})
    doc = cdr.survivor_counterfactual(KEY, survivors=surv, graph=_graph(tmp_path))
    assert doc["status"] == "UNMEASURED"
    assert "no hypothesis_graph node for (AUDNZD, dav_range_filter_adx" in doc["missing_input"]
    assert "'hunt16.json'" in doc["missing_input"]


def test_the_family_horizon_reaches_further_back_than_the_region(tmp_path) -> None:
    g = _graph(tmp_path)
    g.append(Node(symbol="XAUUSD", family="carry", params={"lookback": 900}, source="fund_playbook",
                  fate=BORN, at="2026-07-01T00:00:00+00:00"))   # same family, other region
    doc = cdr.survivor_counterfactual(KEY, survivors=_survivors(), graph=g)
    assert doc["first_reachable"]["family"]["source"] == "fund_playbook"
    assert doc["earliest_horizon"] == "family"
    assert doc["delay_days"] == 41.0
    assert "fund_playbook" in doc["counterfactual"]


def test_main_survivor_mode_writes_the_counterfactual_artifact(tmp_path, monkeypatch,
                                                                capsys) -> None:
    g = _graph(tmp_path)
    monkeypatch.setattr(cdr, "GRAPH_PATH", g.path)
    monkeypatch.setattr(cdr, "UNI", tmp_path / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(cdr, "CANON", tmp_path / "canon.json")
    monkeypatch.setattr(cdr, "CF_OUT", tmp_path / "research_counterfactual.json")
    (tmp_path / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"survivors": _survivors()}), "utf-8")
    assert cdr.main(["--survivor", KEY]) == 0
    out = capsys.readouterr().out
    assert "MEASURED" in out and "10.0 day(s)" in out
    written = json.loads((tmp_path / "research_counterfactual.json").read_text("utf-8"))
    assert written[KEY]["status"] == "MEASURED"
    # A second key merges rather than overwrites.
    assert cdr.main(["--survivor", "no.such.cert"]) == 2
    written = json.loads((tmp_path / "research_counterfactual.json").read_text("utf-8"))
    assert set(written) == {KEY, "no.such.cert"}
    assert written["no.such.cert"]["status"] == "UNMEASURED"
