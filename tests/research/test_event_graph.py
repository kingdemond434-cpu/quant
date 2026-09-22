"""The cross-market event graph: a planted chain is found end to end, edges carry evidence
states that only ever rise, readings are computed, and every edge yields a hypothesis with a
falsifier and competing explanations."""
from __future__ import annotations

from libs.research import event_graph as eg


def _planted() -> eg.EventGraph:
    """port closure -> copper shipment delay -> copper -> Chile -> CLP -> USDCLP proxy."""
    g = eg.EventGraph()
    ev = g.add_node("event", "supply_disruption", "a port closes")
    flow = g.add_node("shipping", "copper shipment delay", "copper shipment delay")
    cu = g.add_node("commodity", "copper", "copper")
    cl = g.add_node("country", "CL", "CL", currency="CLP")
    clp = g.add_node("currency", "CLP", "CLP")
    px = g.add_node("asset", "USDCLP", "USDCLP", symbol="USDCLP", selector="sym:USDCLP")
    xcu = g.add_node("asset", "XCUUSD", "XCUUSD", symbol="XCUUSD", selector="sym:XCUUSD")
    g.add_edge(ev.id, flow.id, "closes the loading berths", sign="+", horizon="days")
    g.add_edge(flow.id, cu.id, "inventory expectations tighten", sign="+", horizon="days")
    g.add_edge(cu.id, xcu.id, "price of", sign="+", horizon="minutes",
               evidence=eg.MEASURED_ELSEWHERE)
    g.add_edge(cu.id, cl.id, "export revenue", sign="+", horizon="days")
    g.add_edge(cl.id, clp.id, "terms of trade", sign="+", horizon="days")
    g.add_edge(clp.id, px.id, "currency leg", sign="-", horizon="minutes",
               evidence=eg.DESK_MEASURED, strength=0.4)
    return g


def test_a_planted_chain_is_found_end_to_end() -> None:
    g = _planted()
    chain = g.find_chain("event:supply_disruption", "asset:usdclp")
    assert chain is not None
    assert [e.dst for e in chain] == ["shipping:copper_shipment_delay", "commodity:copper",
                                      "country:cl", "currency:clp", "asset:usdclp"]
    paths = g.propagation_paths("event:supply_disruption")
    sigs = {eg.summarise_path(p, g)["signature"] for p in paths}
    assert any(s.endswith("asset:usdclp") for s in sigs)
    assert any(s.endswith("asset:xcuusd") for s in sigs)
    longest = max(paths, key=len)
    assert eg.ladder_score(longest, g) == 1.0          # the textbook chain descends the ladder


def test_edges_carry_evidence_states_that_only_rise() -> None:
    g = _planted()
    e = g.add_edge("commodity:copper", "country:cl", "export revenue")
    assert e.evidence == eg.HYPOTHESIS
    g.add_edge("commodity:copper", "country:cl", "export revenue",
               evidence=eg.MEASURED_ELSEWHERE, strength=0.2)
    assert e.evidence == eg.MEASURED_ELSEWHERE and e.strength == 0.2
    g.add_edge("commodity:copper", "country:cl", "export revenue", evidence=eg.HYPOTHESIS)
    assert e.evidence == eg.MEASURED_ELSEWHERE                 # never downgraded
    g.set_measurement(e.id, strength=-0.3, sign="-")
    assert e.evidence == eg.DESK_MEASURED and e.weight == 0.3 and e.measured_at
    by_ev = g.readings()["edges_by_evidence"]
    assert by_ev[eg.DESK_MEASURED] == 2 and by_ev[eg.HYPOTHESIS] == 3


def test_readings_and_persistence_round_trip() -> None:
    g = _planted()
    cent = g.centrality()
    assert cent["commodity:copper"]["betweenness"] == 1.0          # the hub of the chain
    reach = g.contagion({"event:supply_disruption": 1.0})
    assert reach["asset:usdclp"] > 0 and reach["asset:usdclp"] < reach["commodity:copper"]
    labels = g.communities()
    assert set(labels) == set(g.nodes)
    assert g.community_change(None)["status"] == eg.UNMEASURED
    assert g.community_change(labels)["n_moved"] == 0
    again = eg.EventGraph.from_doc(g.to_doc())
    assert set(again.edges) == set(g.edges) and set(again.nodes) == set(g.nodes)
    assert again.edges[next(iter(g.edges))].evidence == g.edges[next(iter(g.edges))].evidence


def test_every_edge_yields_a_hypothesis_with_a_falsifier_and_competing_explanations() -> None:
    g = _planted()
    hyps = g.hypotheses()
    assert len(hyps) == len(g.edges)
    for h in hyps:
        assert h["falsifier"] and len(h["competing"]) >= 3
    testable = [h for h in hyps if h["testable"]]
    assert {h["symbol"] for h in testable} == {"USDCLP", "XCUUSD"}
    assert hyps[0]["testable"]                                   # asset-terminal edges first


def test_the_ontology_seeds_without_redeclaring_and_respects_the_universe() -> None:
    g = eg.EventGraph()
    n = eg.seed_from_ontology(g, universe={"XAUUSD": "Commodities", "EURUSD": "Forex",
                                           "US500": "Indices"})
    assert n > 0
    assets = {x.attrs.get("symbol") for x in g.nodes_of_kind("asset") if x.attrs.get("symbol")}
    assert assets <= {"XAUUSD", "EURUSD", "US500"}           # never a symbol Fusion does not list
    assert "event:war_escalation" in g.nodes and "commodity:crude" in g.nodes
    rows = [{"from_country": "cn", "actor": "Chinese industrial buyers", "flow": "metal imports",
             "to_country": "au", "asset": "XCUUSD", "target": "sym:XCUUSD",
             "source": "series:cn_imports", "lag_days": 1.0, "measured": True, "strength": 0.3,
             "evidence": {"admitted": True, "why": "planted"}, "origin": "pack:cn"}]
    assert eg.seed_from_transmission(g, rows, universe={"XCUUSD": "Commodities"}) >= 3
    chain = g.find_chain("country:cn", "asset:xcuusd")
    assert chain is not None and chain[-1].evidence == eg.DESK_MEASURED
    causal = [{"src": "AUDUSD", "dst": "US500", "lag": 4, "direction": "opposite",
               "strength": -0.1, "status": "ADMITTED", "decay_cls": "bar_W1"}]
    assert eg.seed_from_causal_edges(g, causal, universe={"AUDUSD": "Forex", "US500": "Indices"})
    assert eg.seed_from_events(g, [{"kind": "sanctions", "entities": ["RU"],
                                    "at": "2026-09-22T00:00:00+00:00"}]) >= 1
