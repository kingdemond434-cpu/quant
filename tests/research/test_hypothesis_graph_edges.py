"""Typed edges on the hypothesis graph (Tier-1 A2).

Until 2026-09-08 the ledger's only edge was the scalar `parent` hash, so "which hypotheses use
the COT vintage on JPY crosses" could not be asked of it. Pinned here: every edge names a field
the candidate already carried (nothing inferred), the 30k legacy rows read as edge-less rather
than breaking, and `Graph.query` answers by type, target, symbol, family and fate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import hypothesis_graph as hg


def _legacy_row(sym: str, fam: str, params: dict, fate: str = "FAILED") -> dict:
    """A row exactly as the backfill wrote it before the `edges` field existed."""
    return {"id": hg.node_id(sym, fam, params), "region": hg.region_key(sym, fam, params),
            "symbol": sym, "family": fam, "params": params, "source": "external", "parent": "",
            "fate": fate, "why": "canonical verdict REJECTED", "gates": {},
            "at": "2026-09-01T22:01:33+00:00"}


# --------------------------------------------------------------------------- edges_for
def test_every_edge_names_a_field_the_candidate_carried() -> None:
    edges = hg.edges_for("usdjpy", {"input_source": "cot_point_in_time",
                                    "factor_symbols": ["US500", "DXY"], "lookback": 120},
                         parent="external.USDJPY.srb", operator="step_lookback_up",
                         source_url="https://example.test/a")
    by_type = {}
    for e in edges:
        by_type.setdefault(e["type"], []).append(e)
    assert by_type["applies_to_symbol"] == [{"type": "applies_to_symbol", "to": "symbol:USDJPY"}]
    assert [e["to"] for e in by_type["uses_data"]] == [
        "data:cot_point_in_time", "data:US500", "data:DXY"]
    assert by_type["uses_data"][0]["via"] == "input_source"
    assert by_type["mutated_from"] == [{"type": "mutated_from", "to": "external.USDJPY.srb",
                                        "operator": "step_lookback_up"}]
    assert by_type["sourced_from"] == [{"type": "sourced_from", "to": "url:https://example.test/a"}]
    assert {e["type"] for e in edges} <= set(hg.EDGE_TYPES)
    # a plain tunable is NOT data: `lookback` produces no edge
    assert not any(e.get("to") == "data:120" for e in edges)


def test_a_candidate_with_nothing_but_a_symbol_has_exactly_one_edge() -> None:
    assert hg.edges_for("XAUUSD", {"lookback": 20}) == [
        {"type": "applies_to_symbol", "to": "symbol:XAUUSD"}]
    assert hg.edges_for("", {}) == []


def test_duplicate_data_targets_collapse() -> None:
    edges = hg.edges_for("EURUSD", {"factor_symbols": ["DXY", "DXY"], "peer_symbol": "DXY"})
    assert [e["to"] for e in edges if e["type"] == "uses_data"] == ["data:DXY"]


# --------------------------------------------------------------------------- rows
def test_to_row_carries_edges_and_a_legacy_row_reads_as_edgeless() -> None:
    n = hg.Node("XAUUSD", "carry", {"input_source": "swap_terms"},
                edges=hg.edges_for("XAUUSD", {"input_source": "swap_terms"}))
    row = n.to_row()
    assert row["edges"] == [{"type": "applies_to_symbol", "to": "symbol:XAUUSD"},
                            {"type": "uses_data", "to": "data:swap_terms", "via": "input_source"}]
    assert hg.edges_of(_legacy_row("X", "f", {"k": 1})) == []
    assert hg.edges_of({"edges": "not a list"}) == []
    assert hg.Node("X", "f", {}).edges == []          # the default is [] , never shared state


# --------------------------------------------------------------------------- the graph
@pytest.fixture
def graph(tmp_path: Path) -> hg.Graph:
    p = tmp_path / "g.jsonl"
    legacy = [_legacy_row("CADCHF", "discovered", {"feature": "spread", "horizon": 1}),
              _legacy_row("EURCHF", "discovered", {"feature": "hour", "horizon": 3},
                          fate="CERTIFIED")]
    p.write_text("".join(json.dumps(r) + "\n" for r in legacy), "utf-8")
    return hg.Graph(p)


def test_record_candidates_emits_the_edges_and_query_finds_them(graph: hg.Graph) -> None:
    n = hg.record_candidates([
        {"symbol": "USDJPY", "family": "cot_positioning",
         "params": {"input_source": "cot_point_in_time", "lookback": 26},
         "source": "fund_playbook:X", "source_url": "https://cftc.test/cot"},
        {"symbol": "XAUUSD", "family": "cross_asset_residual",
         "params": {"factor_symbols": ["US500"], "lookback": 120},
         "source": "survivor_distiller",
         "evidence": {"parent": "external.XAUUSD.cross_asset_residual",
                      "operator": "step_lookback_down"}},
    ], source="miner_candidate_compiler", graph=graph)
    assert n == 2
    cot = graph.query(edge_type="uses_data", to="data:cot_point_in_time")
    assert [r["symbol"] for r in cot] == ["USDJPY"]
    assert graph.query(edge_type="uses_data", to="data:", symbol="xauusd")[0]["family"] == \
        "cross_asset_residual"
    mut = graph.query(edge_type="mutated_from")
    assert len(mut) == 1 and mut[0]["edges"][-1]["operator"] == "step_lookback_down"
    assert [r["symbol"] for r in graph.query(edge_type="sourced_from",
                                             to="url:https://cftc.test/cot")] == ["USDJPY"]
    # legacy rows are still queryable by the scalar filters, and carry no edges
    assert len(graph.query(family="discovered")) == 2
    assert graph.query(family="discovered", fate="CERTIFIED")[0]["symbol"] == "EURCHF"
    assert graph.query(edge_type="applies_to_symbol", family="discovered") == []


def test_query_refuses_an_unknown_edge_type(graph: hg.Graph) -> None:
    with pytest.raises(ValueError):
        graph.query(edge_type="correlated_with")


def test_the_census_says_how_much_of_the_graph_is_typed(graph: hg.Graph) -> None:
    before = graph.census()
    assert before["nodes"] == 2 and before["nodes_with_edges"] == 0
    assert before["by_edge_type"] == {}
    hg.record_verdicts([{"sym": "USDJPY", "family": "cot_positioning",
                         "params": {"input_source": "cot_point_in_time"},
                         "gates": {"pbo": {"passed": True}}}], graph=graph)
    after = graph.census()
    assert after["nodes"] == 3 and after["nodes_with_edges"] == 1
    assert after["by_edge_type"] == {"applies_to_symbol": 1, "uses_data": 1}
    assert after["by_fate"]["CERTIFIED"] == 2


def test_the_negative_knowledge_index_is_untouched_by_edges(graph: hg.Graph) -> None:
    pf = graph.prior_failures("CADCHF", "discovered", {"feature": "spread", "horizon": 1})
    assert pf["n_failed"] == 1 and pf["last_why"] == "canonical verdict REJECTED"
    assert graph.lineage(hg.node_id("CADCHF", "discovered", {"feature": "spread", "horizon": 1}))
