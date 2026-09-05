"""The world causal graph: the estimator finds a planted lag, a planted chain appears as a
second-order path, a null pair is recorded and not admitted, and the multiplicity charge
raises the bar with the number of cells searched -- never the other way.

Both directions are tested because a module that only ever refuses has only been shown to be
quiet: the planted positive control must be ADMITTED at the lag it was planted at, with an
interval that excludes zero; and the SAME edge, at the SAME n, must NOT be admitted once three
hundred noise pairs have been charged to the ledger.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from libs.research import causal_graph as cg

N = 4_000


def _planted(rng: np.random.Generator, *, coef: float, lag: int, n: int = N
             ) -> tuple[np.ndarray, np.ndarray]:
    x = rng.standard_normal(n)
    y = rng.standard_normal(n)
    y[lag:] += coef * x[:-lag]
    return x, y


# --------------------------------------------------------------------- the estimator
def test_the_estimator_finds_a_planted_lag_two_link_and_admits_it() -> None:
    rng = np.random.default_rng(11)
    x, y = _planted(rng, coef=0.25, lag=2)
    e = cg.measure_edge(x, y, src="A", dst="B", clock="H1", decay_cls="bar_H1", n_tests=18)
    assert e.lag == 2
    assert e.status == cg.ADMITTED, e.reason
    lo, hi = e.evidence["xcorr"]["best"]["ci_deflated"]
    assert lo > 0.0 and hi > lo
    assert e.direction == "same" and e.strength > 0.15
    assert e.incremental_info > 0.0
    assert e.evidence["incremental"]["p_value"] <= cg.ALPHA
    assert e.stability == 1.0
    assert e.n >= N - 10
    # the wrong lags are recorded beside the right one, each with its own interval
    assert {row["lag"] for row in e.evidence["xcorr"]["lags"]} == set(range(1, cg.MAX_LAG + 1))


def test_a_null_pair_is_recorded_not_admitted_with_the_reason() -> None:
    rng = np.random.default_rng(5)
    x = rng.standard_normal(N)
    z = rng.standard_normal(N)
    e = cg.measure_edge(x, z, src="A", dst="C", clock="H1", decay_cls="bar_H1", n_tests=18)
    assert e.status == cg.RECORDED_NOT_ADMITTED
    assert "includes zero" in e.reason
    assert e.measured and e.measured_at


def test_multiplicity_deflation_raises_the_bar_with_more_pairs_at_the_same_n() -> None:
    """PIN: the same edge admitted with 3 pairs is not admitted with 300 noise pairs."""
    rng = np.random.default_rng(3)
    x, y = _planted(rng, coef=0.055, lag=2)
    few = cg.measure_edge(x, y, src="A", dst="B", clock="H1", decay_cls="bar_H1",
                          n_tests=3 * cg.MAX_LAG, seed=1)
    many = cg.measure_edge(x, y, src="A", dst="B", clock="H1", decay_cls="bar_H1",
                           n_tests=300 * cg.MAX_LAG, seed=1)
    assert few.status == cg.ADMITTED, few.reason
    assert many.status == cg.RECORDED_NOT_ADMITTED
    assert many.n == few.n and many.lag == few.lag == 2
    assert "300" in many.reason or "1800" in many.reason
    # the bar is monotone in the charge and never drops
    assert cg.deflated_z(cg.ALPHA, 1800) > cg.deflated_z(cg.ALPHA, 18) > cg.deflated_z(cg.ALPHA, 1)
    assert cg.deflated_z(cg.ALPHA, 1) == pytest.approx(1.959964, abs=1e-5)


def test_lag_zero_is_refused_as_a_lead() -> None:
    x = np.arange(100, dtype=float)
    with pytest.raises(ValueError):
        cg.lagged_xcorr(x, x, lags=[0])
    with pytest.raises(ValueError):
        cg.incremental_information(x, x, 0)


def test_state_dependence_nonlinearity_and_stability_see_what_they_are_for() -> None:
    rng = np.random.default_rng(9)
    n = 6_000
    x = rng.standard_normal(n)
    labels = np.where(np.arange(n) % 2 == 0, "ON", "OFF")
    y = rng.standard_normal(n) * 0.5
    on = labels[1:] == "ON"
    y[1:][on] += 0.8 * x[:-1][on]                         # the edge lives in one state only
    sd = cg.state_dependence(x, y, 1, labels)
    assert sd["by_state"]["ON"]["corr"] > 0.5 > sd["by_state"]["OFF"]["corr"]
    assert sd["spread"] > 0.4 and sd["basis"] == "caller labels"
    # without labels the trailing-vol split stands in, and says so
    assert cg.state_dependence(x, y, 1)["basis"] == "trailing-vol median split"
    # a monotone but not linear link: the ranks see more than the line does
    xm = rng.standard_normal(n)
    ym = np.zeros(n)
    ym[1:] = np.sign(xm[:-1]) * np.abs(xm[:-1]) ** 3 + 0.3 * rng.standard_normal(n - 1)
    nl = cg.nonlinearity(xm, ym, 1)
    assert nl["spearman"] > nl["pearson"] and nl["score"] > 0.0
    # a link that flips sign halfway is not stable
    xs = rng.standard_normal(n)
    ys = np.zeros(n)
    ys[1:n // 2] = 0.5 * xs[:n // 2 - 1]
    ys[n // 2:] = -0.5 * xs[n // 2 - 1:-1]
    ys += 0.3 * rng.standard_normal(n)
    assert cg.stability(xs, ys, 1) <= 0.5
    assert cg.stability(x, y, 1) == 1.0


# ------------------------------------------------------------------------ the graph
def _chain_graph(rng: np.random.Generator) -> tuple[cg.CausalGraph, np.ndarray, np.ndarray,
                                                     np.ndarray]:
    n = 5_000
    a = rng.standard_normal(n)
    b = rng.standard_normal(n)
    b[1:] += 0.6 * a[:-1]
    c = rng.standard_normal(n)
    c[1:] += 0.6 * b[:-1]
    g = cg.CausalGraph(instrument_ids={"CCC"})
    g.add_node(cg.Node("A", "event"))
    g.add_node(cg.Node("B", "commodity"))
    g.add_node(cg.Node("CCC", cg.MT5))
    return g, a, b, c


def test_a_planted_second_order_chain_appears_in_paths_and_upstream() -> None:
    rng = np.random.default_rng(21)
    g, a, b, c = _chain_graph(rng)
    # seeded as plausible-unmeasured first, at a lag hint that the data will overrule
    g.add_edge(cg.Edge("A", "B", 3, plausibility=0.7, decay_cls="macro_monthly", clock="H1",
                       evidence={"prior_why": "A prints, B reprices"}))
    g.add_edge(cg.Edge("B", "CCC", 3, plausibility=0.6, decay_cls="bar_H1", clock="H1"))
    before = g.paths("A", "CCC", max_order=3)
    assert [x.src for x in before[0]] == ["A", "B"]
    assert not g.paths("A", "CCC", max_order=3, admitted_only=True)

    n_tests = g.charge("A", "B", range(1, 7))
    n_tests = g.charge("B", "CCC", range(1, 7))
    ab = g.add_edge(cg.measure_edge(a, b, src="A", dst="B", clock="H1",
                                    decay_cls="macro_monthly", n_tests=n_tests))
    bc = g.add_edge(cg.measure_edge(b, c, src="B", dst="CCC", clock="H1", decay_cls="bar_H1",
                                    n_tests=n_tests))
    assert ab.status == bc.status == cg.ADMITTED
    assert ab.lag == bc.lag == 1
    # the measurement absorbed the prior: plausibility and reason survive, the lag-3 prior is gone
    assert ab.plausibility == 0.7 and ab.evidence["prior_why"] == "A prints, B reprices"
    assert ab.evidence["prior_lag"] == 3
    assert g.edge("A", "B", 3) is None and g.measured_edge("A", "B") is ab
    assert g.counts()["plausible_unmeasured"] == 0

    paths = g.paths("A", "CCC", max_order=3, admitted_only=True)
    assert len(paths) == 1 and [x.src for x in paths[0]] == ["A", "B"]
    assert cg.path_order(paths[0]) == 2
    up = g.upstream("CCC", max_order=3, admitted_only=True)
    chain = next(p for p in up if p["order"] == 2)
    assert chain["nodes"] == ["A", "B", "CCC"] and chain["lag_total"] == 2
    assert chain["decay_cls"] == "macro_monthly"           # the slowest link on the chain
    assert chain["admitted"] and chain["measured"]
    assert g.multiplicity == 12


def test_merge_is_idempotent_and_never_loosens() -> None:
    g = cg.CausalGraph()
    g.add_node(cg.Node("A", "event"))
    g.add_node(cg.Node("B", "currency"))
    p1 = g.add_edge(cg.Edge("A", "B", 1, plausibility=0.5, evidence={"prior_why": "w"}))
    p2 = g.add_edge(cg.Edge("A", "B", 1, plausibility=0.9))
    assert p1 is p2 and p2.plausibility == 0.5 and len(g.edges) == 1
    s = g.add_edge(cg.Edge("A", "B", 0, status=cg.STRUCTURAL, direction="same"))
    assert g.add_edge(cg.Edge("A", "B", 0, status=cg.ADMITTED, strength=0.9,
                              measured_at="x")) is s
    with pytest.raises(KeyError):
        g.add_edge(cg.Edge("A", "Z", 1))
    with pytest.raises(ValueError):
        cg.Node("A", "not_a_kind")
    # a measured edge is replaced by a newer measurement, and the older one is remembered
    m1 = cg.Edge("A", "B", 2, strength=0.1, n=100, status=cg.RECORDED_NOT_ADMITTED,
                 measured_at="2026-01-01T00:00:00+00:00")
    m2 = cg.Edge("A", "B", 2, strength=0.2, n=200, status=cg.ADMITTED,
                 measured_at="2026-02-01T00:00:00+00:00")
    g.add_edge(m1)
    got = g.add_edge(m2)
    assert got.evidence["previous"]["n"] == 100 and got.plausibility == 0.5
    assert got.evidence["prior_why"] == "w"


def test_instrument_nodes_come_from_the_universe_only(tmp_path) -> None:
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({"XAUUSD": {"asset_class": "Metals", "currency_profit": "USD"},
                               "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
                               "_meta": "not a row"}), "utf-8")
    nodes = cg.instrument_nodes(uni)
    assert set(nodes) == {"XAUUSD", "EURUSD"}
    assert nodes["XAUUSD"].kind == cg.MT5 and nodes["XAUUSD"].source == "fusion:Metals"
    assert cg.instrument_nodes(tmp_path / "absent.json") == {}
    g = cg.CausalGraph(instrument_ids=nodes)
    with pytest.raises(ValueError):
        g.add_node(cg.Node("COPPER", cg.MT5))
    g.add_node(nodes["XAUUSD"])
    assert [n.id for n in g.instrument_nodes()] == ["XAUUSD"]


def test_json_round_trip_keeps_edges_cells_and_notes(tmp_path) -> None:
    rng = np.random.default_rng(2)
    g, _a, b, c = _chain_graph(rng)
    g.add_edge(cg.Edge("A", "B", 1, plausibility=0.4, decay_cls="news", clock="H1"))
    g.charge("A", "B", [1, 2])
    g.seed_notes.append("note")
    g.add_edge(cg.measure_edge(b, c, src="B", dst="CCC", clock="H1", decay_cls="bar_H1",
                               n_tests=g.charge("B", "CCC", range(1, 7))))
    path = tmp_path / "g.json"
    g.save(path)
    back = cg.CausalGraph.load(path, instrument_ids={"CCC"})
    assert back.counts() == g.counts()
    assert back.cells == g.cells and back.seed_notes == ["note"]
    assert back.measured_edge("B", "CCC").status == cg.ADMITTED
    assert back.edge("A", "B", 1).decay_cls == "news"
    doc = json.loads(path.read_text("utf-8"))
    assert doc["counts"]["multiplicity_charged"] == 8


def test_the_prior_table_seeds_every_named_chain_before_data_proves_it() -> None:
    inst = {s: cg.Node(s, cg.MT5, source="fusion:test") for s in
            ("XAUUSD", "XAGUSD", "AUDJPY", "AUDUSD", "USDJPY", "EURUSD", "USDCAD", "JPN225")}
    g = cg.seed_priors(cg.CausalGraph(), inst)
    status = g.chain_status()
    assert set(status) == set(cg.PRIOR_CHAINS)
    for name in ("china_physical_gold", "us_cpi_2y_usd_gold", "australia_commodities_to_audjpy",
                 "metals_complex", "risk_off_yen", "cot_gold_reversal"):
        assert status[name]["seeded"] and not status[name]["measured"], name
    # a proxy the universe does not quote is noted, never invented
    assert any("USDNOK" in n for n in g.seed_notes)
    assert "USDNOK" not in g.nodes and "XCUUSD" not in g.nodes
    # the three example chains are third-order paths into their instruments
    cpi = g.paths("event:US_CPI", "XAUUSD", max_order=3)
    assert any([e.src for e in p] == ["event:US_CPI", "yield:US2Y", "currency:USD",
                                      "commodity:gold"] for p in cpi)
    au = g.paths("event:AU_trade_balance", "AUDJPY", max_order=3)
    assert au and cg.path_order(au[0]) == 3
    cn = g.paths("physical:CN_gold_demand", "XAUUSD", max_order=3)
    assert cn and [e.src for e in cn[0]] == ["physical:CN_gold_demand", "physical:SGE_premium",
                                             "commodity:gold"]
    # seeding twice changes nothing
    before = g.counts()
    cg.seed_priors(g, inst)
    assert g.counts() == before
    # every seeded edge carries its reason and its prior direction
    for e in g.edges.values():
        if e.status == cg.PLAUSIBLE_UNMEASURED:
            assert e.evidence["prior_why"] and e.evidence["prior_direction"] in ("same",
                                                                                 "opposite")
            assert 0.0 < e.plausibility <= 1.0
    # and every node kind is one the order names
    assert {n.kind for n in g.nodes.values()} <= set(cg.KINDS)
