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
from libs.research import lead_schema as ls


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


# --------------------------------------------------------------- lineage (defect, 2026-09-17)
#
# THE GRAPH RECORDED THE SEED, NOT THE CELL IT MUTATED. Measured on the live ledger: 0 of 35,199
# `parent` references resolved to any of the 23,972 node ids, because `record_candidates` stamped
# the miner-row hash it computed itself over whatever ancestor the donor named. `descendants`
# writes `parent = root_id` (a real node id) and `operator = descendant:<axis>` on every row it
# donates; both were dropped one function later, so `alpha_lineage_search.untried_mutations`
# found no mutation edge under any family and `Graph.lineage` never walked past the first row.

def test_an_explicit_parent_that_the_graph_holds_is_recorded_as_the_parent(graph: hg.Graph
                                                                          ) -> None:
    root = hg.node_id("CADCHF", "discovered", {"feature": "spread", "horizon": 1})
    assert root in graph.current(), "the fixture's own row is the ancestor under test"
    hg.record_candidates([
        {"symbol": "CADCHF", "family": "discovered", "params": {"feature": "spread",
                                                                "horizon": 2},
         "source": "descendants:chart", "source_title": "a chart descendant", "source_url": "u",
         "parent": root, "operator": "descendant:chart",
         "lineage": {"root": root, "axis": "chart"}},
    ], source="miner_candidate_compiler", graph=graph)
    child = graph.current()[hg.node_id("CADCHF", "discovered", {"feature": "spread",
                                                               "horizon": 2})]
    assert child["parent"] == root, "the parent field must RESOLVE to a node of this graph"
    assert child["parent"] in graph.current()
    assert child["operator"] == "descendant:chart"
    # the seed is never dropped: the BECAME join in knowledge_graph reads exactly this
    assert child["seed_key"] == hg.seed_key_of({"source": "descendants:chart",
                                                "source_title": "a chart descendant",
                                                "source_url": "u"})
    assert child["seed_key"] != child["parent"]
    # and the lineage walk now has two rows rather than one
    assert [r["id"] for r in graph.lineage(child["id"])] == [child["id"], root]


def test_a_candidate_with_no_parent_keeps_the_seed_in_both_fields(graph: hg.Graph) -> None:
    hg.record_candidates([
        {"symbol": "USDJPY", "family": "cot_positioning", "params": {"lookback": 26},
         "source": "miner:cot", "source_title": "COT extremes", "source_url": "https://c.test"},
    ], source="miner_candidate_compiler", graph=graph)
    row = graph.current()[hg.node_id("USDJPY", "cot_positioning", {"lookback": 26})]
    seed = hg.seed_key_of({"source": "miner:cot", "source_title": "COT extremes",
                           "source_url": "https://c.test"})
    assert row["parent"] == seed == row["seed_key"], "unchanged for every reader of `parent`"
    assert ls.compiler_parent_key("cot", "COT extremes", "https://c.test") == seed
    assert "operator" not in row, "never invented; only passed through"


def test_a_parent_the_graph_does_not_hold_stays_a_claim_on_the_edge(graph: hg.Graph) -> None:
    """An unresolvable claim must not go into `parent` -- that is how the field filled with
    prose ("Renaissance|stock book approximately balanced...") in the first place."""
    hg.record_candidates([
        {"symbol": "XAUUSD", "family": "carry", "params": {"input_symbol": "XAUUSD"},
         "source": "survivor_distiller", "source_title": "t", "source_url": "u",
         "evidence": {"parent": "external.XAUUSD.carry", "operator": "step_rr_up"}},
    ], source="miner_candidate_compiler", graph=graph)
    row = graph.current()[hg.node_id("XAUUSD", "carry", {"input_symbol": "XAUUSD"})]
    assert row["parent"] == row["seed_key"] != "external.XAUUSD.carry"
    assert {"type": "mutated_from", "to": "external.XAUUSD.carry",
            "operator": "step_rr_up"} in row["edges"]


def test_every_field_a_donor_may_name_a_parent_in_is_read() -> None:
    root = hg.node_id("EURUSD", "carry", {"k": 1})
    for row in ({"parent": root}, {"parent_id": root}, {"mutated_from": root},
                {"parent_ids": ["nope", root]}, {"lineage": {"root": root}},
                {"lineage": {"parents": [root]}}, {"evidence": {"parent": root}},
                {"parent": {"symbol": "EURUSD", "family": "carry", "params": {"k": 1}}}):
        assert root in hg.parent_claims(row), row
        assert hg.resolve_parent(row, {root}) == root, row
    assert hg.parent_claims({"symbol": "EURUSD"}) == [], "nothing is inferred from the spec"
    assert hg.resolve_parent({"parent": root}, set()) == "", "unknown ids do not resolve"


def test_a_batch_can_be_its_own_ancestry(graph: hg.Graph) -> None:
    """The parent and the child are donated in one call; the child must still resolve."""
    parent_spec = {"symbol": "EURUSD", "family": "carry", "params": {"k": 1}}
    root = hg.node_id_for_spec(parent_spec)
    hg.record_candidates([
        {**parent_spec, "source": "s", "source_title": "t", "source_url": "u"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 2}, "source": "s",
         "source_title": "t2", "source_url": "u2", "parent": root, "operator": "step_k_up"},
    ], source="miner_candidate_compiler", graph=graph)
    child = graph.current()[hg.node_id("EURUSD", "carry", {"k": 2})]
    assert child["parent"] == root and root in graph.current()


def test_the_judges_terminal_gate_rides_onto_the_verdict_row(graph: hg.Graph) -> None:
    """24,027 of 26,843 dead cells carry no terminal gate because `gates` holds
    `canonical_report` alone -- while the judging code had the answer and dropped it."""
    hg.record_verdicts([{"sym": "XAGUSD", "family": "carry", "params": {"k": 3},
                         "terminal_gate": "deflated_sharpe",
                         "gates": {"canonical_report": {"passed": False}}}], graph=graph)
    row = graph.current()[hg.node_id("XAGUSD", "carry", {"k": 3})]
    assert row["fate"] == hg.FAILED and row["terminal_gate"] == "deflated_sharpe"
    hg.record_verdicts([{"sym": "XAGUSD", "family": "carry", "params": {"k": 4},
                         "gates": {"pbo": {"passed": True}}}], graph=graph)
    unjudged = graph.current()[hg.node_id("XAGUSD", "carry", {"k": 4})]
    assert "terminal_gate" not in unjudged, "never invented when the judge did not say"


def test_one_identity_function_serves_both_writers_and_the_verdict_ledger() -> None:
    """`node_id_for_spec` is the join `external_gauntlet` stamps as `graph_id`: a candidate
    (`symbol`) and the judged cell (`sym`) must land on ONE id or trials join nothing."""
    cand = {"symbol": "EURAUD", "family": "overnight_gap_decay", "params": {"hold_bars": 4}}
    verdict = {"sym": "EURAUD", "family": "overnight_gap_decay", "params": {"hold_bars": 4}}
    assert hg.node_id_for_spec(cand) == hg.node_id_for_spec(verdict)
    assert hg.node_id_for_spec(verdict) == hg.node_id("EURAUD", "overnight_gap_decay",
                                                      {"hold_bars": 4})
    assert hg.spec_identity({"sym": "eurusd"}) == ("eurusd", "", {})
