"""The causal lab: it finds a planted lag-1 cause at the RIGHT lag and charges every test it ran
for multiplicity, it recovers a planted contemporaneous DAG where the data can orient one, it
REFUSES the edges the economics forbid before testing them, it stamps each survivor with the class
its evidence earns (and hands the top class only to an edge a natural experiment supports), it
chains classed edges at their weakest link, and on absent data it says UNMEASURED instead of zero.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import causal_lab as cl  # noqa: E402

MOCK_ONTOLOGY = {
    ("macro", "fx"): "MACRO_SURPRISE_REPRICING",
    ("energy", "index"): "INPUT_COST_PASSTHROUGH",
    ("fx", "metal"): "DOLLAR_NUMERAIRE",
}


def _dates(n: int) -> list[str]:
    d0 = datetime(2024, 1, 1, tzinfo=UTC)
    return [(d0 + timedelta(days=i)).date().isoformat() for i in range(n)]


def _panel(names: list[str], x: np.ndarray, releases: dict[str, np.ndarray] | None = None):
    return cl.Panel(names=names, kinds={n: cl.kind_of(n) for n in names}, x=x,
                    dates=_dates(len(x)), releases=releases or {})


# --------------------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def lagged_fixture():
    """X -> Y at lag 1, a CONTEMPORANEOUS confounder behind C1 and C2 (no lagged link at all),
    and two pure-noise columns that nothing should ever point at."""
    rng = np.random.default_rng(11)
    n = 400
    e = rng.normal(0, 1, (n, 6))
    conf = rng.normal(0, 1, n)
    x = np.zeros((n, 6))
    x[:, 0] = e[:, 0]                                  # XAUUSD  (the cause)
    x[1:, 1] = 0.7 * x[:-1, 0] + 0.5 * e[1:, 1]        # XAGUSD  (the effect, at lag 1)
    x[:, 2] = 0.8 * conf + 0.4 * e[:, 2]               # NAS100  \ same-day confounder,
    x[:, 3] = 0.8 * conf + 0.4 * e[:, 3]               # GER40   / no lagged relation
    x[:, 4] = e[:, 4]                                  # EURUSD  noise
    x[:, 5] = e[:, 5]                                  # GBPUSD  noise
    names = ["XAUUSD", "XAGUSD", "NAS100", "GER40", "EURUSD", "GBPUSD"]
    return _panel(names, x)


@pytest.fixture(scope="module")
def dag_fixture():
    """Two colliders: V0 -> V2 <- V1, V2 -> V4 <- V3, then V4 -> V5. Colliders are the ONLY thing
    observational data can orient, so they are what the test is allowed to demand."""
    rng = np.random.default_rng(23)
    n = 600
    u = rng.normal(0, 1, (n, 6))
    v = np.zeros((n, 6))
    v[:, 0], v[:, 1], v[:, 3] = u[:, 0], u[:, 1], u[:, 3]
    v[:, 2] = 0.8 * v[:, 0] + 0.8 * v[:, 1] + 0.4 * u[:, 2]
    v[:, 4] = 0.8 * v[:, 2] + 0.8 * v[:, 3] + 0.4 * u[:, 4]
    v[:, 5] = 0.9 * v[:, 4] + 0.4 * u[:, 5]
    return _panel([f"V{i}" for i in range(6)], v)


@pytest.fixture(scope="module")
def class_fixture():
    """A release axis with a planted DiD effect, and a chain out of it.

    fred.macro1 prints every 14th day (+/- 0.25, alternating) and EURUSD reacts the NEXT day;
    EURUSD -> GBPUSD -> XAUUSD carries it on, and XTIUSD -> NAS100 is a separate mapped pair.
    """
    rng = np.random.default_rng(5)
    n = 420
    names = ["EURUSD", "GBPUSD", "XAUUSD", "XTIUSD", "NAS100", "fred.macro1"]
    x = np.zeros((n, 6))
    noise = rng.normal(0, 0.005, (n, 6))
    axis = np.zeros(n)
    for k, t in enumerate(range(20, n - 6, 14)):
        axis[t] = 0.25 * (1.0 if k % 2 == 0 else -1.0)
    x[:, 5] = axis
    x[:, 3] = noise[:, 3]
    for t in range(1, n):
        x[t, 0] = 0.04 * axis[t - 1] + noise[t, 0]
        x[t, 1] = 0.5 * x[t - 1, 0] + noise[t, 1]
        x[t, 2] = 0.5 * x[t - 1, 1] + noise[t, 2]
        x[t, 4] = 0.5 * x[t - 1, 3] + noise[t, 4]
    return _panel(names, x, {"fred.macro1": axis != 0.0})


@pytest.fixture(scope="module")
def classed(class_fixture):
    doc = cl.build(panel=class_fixture, pair_map=MOCK_ONTOLOGY)
    return doc


def _edge(doc, src, dst, lag=None):
    for e in doc["edges"]:
        if e["from"] == src and e["to"] == dst and (lag is None or e["lag"] == lag):
            return e
    return None


# --------------------------------------------------------------------------- (1) lagged discovery

def test_planted_lag1_cause_is_found_at_the_right_lag(lagged_fixture):
    res = cl.discover_lagged(lagged_fixture)
    assert res["n_tests"] == 6 * 5 * 3, "every ordered pair at every lag must be charged"
    hit = [e for e in res["edges"] if e["from"] == "XAUUSD" and e["to"] == "XAGUSD"]
    assert hit, "the planted lag-1 cause was not recovered"
    assert [e["lag"] for e in hit] == [1], "the edge must be found at lag 1 and only lag 1"
    assert hit[0]["r"] > 0.5 and hit[0]["q"] < 1e-6
    assert hit[0]["coef"] > 0.4, "the partial-regression slope carries the planted sign and size"


def test_fdr_does_not_reject_the_null_pairs(lagged_fixture):
    res = cl.discover_lagged(lagged_fixture)
    false_pos = [e for e in res["edges"]
                 if not (e["from"] == "XAUUSD" and e["to"] == "XAGUSD")]
    assert len(false_pos) <= 2, f"BH at q=0.05 let through {len(false_pos)} null edges: {false_pos}"
    # The contemporaneous confounder is a LAG-0 story. A lagged test must not mistake it for one.
    assert _edge(res, "NAS100", "GER40") is None and _edge(res, "GER40", "NAS100") is None


def test_bh_fdr_is_benjamini_hochberg():
    p = np.array([0.001, 0.008, 0.04, 0.4, 0.9])
    rej, q = cl.bh_fdr(p, 0.05)
    assert list(rej) == [True, True, False, False, False]
    assert q[0] == pytest.approx(0.005) and q[1] == pytest.approx(0.02)
    assert np.all(np.diff(q[np.argsort(p)]) >= -1e-12), "q-values must be monotone in p"
    empty_rej, empty_q = cl.bh_fdr(np.zeros(0), 0.05)
    assert empty_rej.size == 0 and empty_q.size == 0


# --------------------------------------------------------------------------- (2) NOTEARS-lite

def test_notears_lite_recovers_the_planted_dag(dag_fixture):
    dag = cl.notears_lite(dag_fixture)
    got = {(e["from"], e["to"]) for e in dag["edges"]}
    planted = {("V0", "V2"), ("V1", "V2"), ("V2", "V4"), ("V3", "V4"), ("V4", "V5")}
    skeleton = {frozenset(p) for p in got}
    assert {frozenset(p) for p in planted} <= skeleton, "a planted pair is missing from the DAG"
    # The four collider arrows are the identifiable part, and they must point the planted way.
    colliders = {("V0", "V2"), ("V1", "V2"), ("V2", "V4"), ("V3", "V4")}
    assert colliders <= got, f"collider orientation lost: {sorted(colliders - got)}"
    assert not {(j, i) for i, j in colliders} & got, "a collider arrow was also claimed reversed"
    assert len(got - planted) <= 6, "the DAG is denser than the structure that generated it"
    assert dag["acyclicity_h"] < 1e-3 and dag["n_vars"] == 6
    assert dag["threshold"] == 0.05 and dag["noise_floor"] > 0


def test_expm_matches_a_known_exponential():
    a = np.diag([0.0, np.log(2.0), np.log(3.0)])
    assert np.allclose(cl._expm(a), np.diag([1.0, 2.0, 3.0]))
    big = np.array([[0.0, 4.0], [4.0, 0.0]])  # forces the scaling-and-squaring branch
    assert np.allclose(cl._expm(big), np.array([[np.cosh(4), np.sinh(4)],
                                                [np.sinh(4), np.cosh(4)]]), rtol=1e-6)


# --------------------------------------------------------------------------- (3) restrictions

def test_restrictions_refuse_the_forbidden_edges():
    assert cl.forbidden("fx", "macro", 0) == "NO_EDGE_INTO_RELEASE_AT_LAG0"
    assert cl.forbidden("index", "positioning", 0) == "NO_EDGE_INTO_RELEASE_AT_LAG0"
    assert cl.forbidden("positioning", "fx", 0) == "POSITIONING_LAG_GE_1"
    assert cl.forbidden("fx", "metal", -1) == "NO_FUTURE_LAGS"
    # What is allowed: the release into the tape at any lag, positioning from lag 1, markets on
    # each other at lag 0.
    assert cl.forbidden("macro", "fx", 0) is None
    assert cl.forbidden("positioning", "fx", 1) is None
    assert cl.forbidden("fx", "macro", 1) is None
    assert cl.forbidden("fx", "index", 0) is None


def test_a_forbidden_lag0_edge_is_never_fitted():
    """A market series that PERFECTLY explains the axis at lag 0 still gets no arrow into it."""
    rng = np.random.default_rng(3)
    n = 300
    mkt = rng.normal(0, 1, n)
    x = np.column_stack([mkt, rng.normal(0, 1, n), rng.normal(0, 1, n),
                         2.0 * mkt + rng.normal(0, 0.05, n),          # the axis IS the market
                         rng.normal(0, 1, n)])
    names = ["EURUSD", "GBPUSD", "XAUUSD", "cot.EURUSD", "fred.macro1"]
    dag = cl.notears_lite(_panel(names, x))
    got = {(e["from"], e["to"]) for e in dag["edges"]}
    assert ("EURUSD", "cot.EURUSD") not in got, "a market series was allowed into a release series"
    assert ("EURUSD", "fred.macro1") not in got
    assert not any(e["from"] == "cot.EURUSD" for e in dag["edges"]), "COT entered at lag 0"
    assert dag["blocked"]["NO_EDGE_INTO_RELEASE_AT_LAG0"] > 0
    assert dag["blocked"]["POSITIONING_LAG_GE_1"] > 0


def test_restrictions_are_counted_in_the_artifact(classed):
    counts = classed["restrictions_applied"]["counts"]
    assert counts.get("NO_EDGE_INTO_RELEASE_AT_LAG0", 0) > 0
    rules = classed["restrictions_applied"]["rules"]
    assert all(k in cl.RESTRICTION_TEXT for k in rules)
    assert "exogenous" in rules["NO_EDGE_INTO_RELEASE_AT_LAG0"]


# --------------------------------------------------------------------------- edge classes

def test_release_edge_with_a_planted_experiment_is_intervention_supported(classed):
    e = _edge(classed, "fred.macro1", "EURUSD", 1)
    assert e is not None, "the planted release -> responder edge was not found"
    assert e["klass"] == "INTERVENTION_SUPPORTED"
    assert e["mechanism"] == "MACRO_SURPRISE_REPRICING"
    did = e["intervention"]
    assert did["status"] == "OK" and did["engine"] == "natural_experiment"
    assert did["identified"] is True, did["verdict"]
    assert did["t"] > cl.DID_T_BAR and did["effect"] > 0
    assert did["n_units"] >= cl.MIN_RELEASES


def test_mapped_kinds_earn_plausible_mechanism_and_unmapped_ones_do_not(classed):
    mapped = _edge(classed, "XTIUSD", "NAS100", 1)
    assert mapped is not None and mapped["klass"] == "PLAUSIBLE_MECHANISM"
    assert mapped["mechanism"] == "INPUT_COST_PASSTHROUGH"
    bare = _edge(classed, "EURUSD", "GBPUSD", 1)
    assert bare is not None and bare["klass"] == "OBSERVATIONAL" and bare["mechanism"] == ""
    assert classed["class_counts"]["INTERVENTION_SUPPORTED"] >= 1
    assert sum(classed["class_counts"].values()) == len(classed["edges"])


def test_every_edge_carries_its_regime_table(classed):
    for e in classed["edges"]:
        reg = e["by_regime"]
        assert reg["status"] == "OK"
        assert {"low", "mid", "high"} <= set(reg)
        assert sum(reg[b]["n"] for b in ("low", "mid", "high")) > 3 * cl.MIN_REGIME_N
        assert isinstance(reg["sign_stable"], bool)


def test_an_intervention_needs_a_release_and_a_price():
    """No release calendar, no top class -- and one calendar moving another is not a price."""
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1, (300, 4))
    names = ["EURUSD", "GBPUSD", "XAUUSD", "fred.macro1"]
    bare = _panel(names, x)
    assert cl.intervention_test(bare, "fred.macro1", "EURUSD", 1, 1.0)["status"] == "UNMEASURED"
    daily = _panel(names, x, {"fred.macro1": np.ones(300, dtype=bool)})
    out = cl.intervention_test(daily, "fred.macro1", "EURUSD", 1, 1.0)
    assert out["status"] == "UNMEASURED" and "STATE variable" in out["why"]
    rel = np.zeros(300, dtype=bool)
    rel[::14] = True
    axis_resp = _panel(names, x, {"fred.macro1": rel})
    out2 = cl.intervention_test(axis_resp, "fred.macro1", "fred.macro1", 1, 1.0)
    assert out2["status"] == "UNMEASURED" and "not a market series" in out2["why"]


# --------------------------------------------------------------------------- chains

def test_chains_are_enumerated_and_reported_at_their_weakest_link(classed):
    chains = classed["chains"]
    assert chains, "no chain was enumerated from the classed edges"
    paths = {"->".join(c["nodes"]) for c in chains}
    assert "fred.macro1->EURUSD->GBPUSD" in paths
    assert any(len(c["nodes"]) == 4 for c in chains), "no 3-edge chain was enumerated"
    two = next(c for c in chains if c["nodes"] == ["fred.macro1", "EURUSD", "GBPUSD"])
    assert two["klass"] == "OBSERVATIONAL", "a chain must take the class of its weakest arrow"
    assert two["weakest_link"] == "EURUSD->GBPUSD"
    assert two["kinds"] == ["macro", "fx", "fx"] and two["total_lag"] == 2
    assert all(len(c["nodes"]) <= 4 for c in chains) and len(chains) <= cl.MAX_CHAINS


def test_find_chains_does_not_revisit_a_node():
    edges = [{"from": "A", "to": "B", "from_kind": "fx", "to_kind": "fx", "lag": 1, "r": 0.5,
              "klass": "OBSERVATIONAL", "mechanism": ""},
             {"from": "B", "to": "A", "from_kind": "fx", "to_kind": "fx", "lag": 1, "r": 0.5,
              "klass": "OBSERVATIONAL", "mechanism": ""}]
    assert cl.find_chains(edges) == []


# --------------------------------------------------------------------------- UNMEASURED and CLI

def test_absent_data_is_unmeasured_not_empty(tmp_path):
    panel, unmeasured = cl.load_panel(["NOSUCH1", "NOSUCH2", "NOSUCH3"], 200, uni=tmp_path,
                                      axes_dir=tmp_path)
    assert panel is None
    assert len(unmeasured) == 4, unmeasured
    assert all("never substituted" in u["why"] for u in unmeasured[:3])
    doc = cl.build(symbols=["NOSUCH1", "NOSUCH2"], days=200)
    assert doc["status"] == "UNMEASURED"
    assert doc["edges"] == [] and doc["chains"] == [] and doc["n_nodes"] == 0
    assert doc["n_unmeasured"] >= 2 and doc["rule"] == cl.RULE
    assert len(cl.summary_lines(doc)) <= 10


def test_a_short_panel_refuses_rather_than_reporting_noise(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "MIN_DAYS", 10_000)
    doc = cl.build(symbols=["EURUSD", "GBPUSD", "XAUUSD"], days=50)
    assert doc["status"] == "UNMEASURED" and "degrees of freedom" in doc["why"]


def test_cli_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    out = tmp_path / "CAUSAL_LAB.json"
    monkeypatch.setattr(cl, "OUT", out)
    assert cl.main(["--dry-run", "--symbols", "NOSUCHSYM", "--days", "50"]) == 0
    assert not out.exists(), "--dry-run wrote the artifact"
    printed = capsys.readouterr().out
    assert "UNMEASURED" in printed and "nothing written" in printed


def test_cli_writes_the_artifact_atomically(tmp_path, monkeypatch, capsys):
    out = tmp_path / "reports" / "CAUSAL_LAB.json"
    monkeypatch.setattr(cl, "OUT", out)
    assert cl.main(["--symbols", "NOSUCHSYM", "--days", "50"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["status"] == "UNMEASURED" and doc["rule"] == cl.RULE
    assert not list(out.parent.glob("*.tmp")), "the temp file survived the write"
    assert str(out) in capsys.readouterr().out


# --------------------------------------------------------------------------- the artifact itself

def test_artifact_carries_every_field_the_order_named(classed):
    for key in ("at", "n_nodes", "n_tests", "fdr_q", "edges", "dag", "chains",
                "restrictions_applied", "unmeasured", "rule"):
        assert key in classed, f"the artifact is missing {key}"
    assert classed["fdr_q"] == 0.05 and classed["n_nodes"] == 6
    assert classed["rule"].startswith("an LLM never invents an edge")
    for e in classed["edges"]:
        assert {"from", "to", "lag", "coef", "p", "q", "klass", "mechanism", "by_regime"} <= set(e)
        assert e["klass"] in cl.CLASS_RANK and 1 <= e["lag"] <= cl.MAX_LAG
        assert "i" not in e and "j" not in e, "internal column indices leaked into the artifact"
    assert json.loads(json.dumps(classed, default=str))["n_tests"] == classed["n_tests"]
    lines = cl.summary_lines(classed)
    assert len(lines) == 10 and lines[-1].strip().startswith("rule:")


def test_node_kinds_route_by_class_not_by_symbol_list():
    assert cl.kind_of("EURUSD") == "fx" and cl.kind_of("XAUUSD") == "metal"
    assert cl.kind_of("XTIUSD") == "energy" and cl.kind_of("NAS100") == "index"
    assert cl.kind_of("cot.EURUSD") == "positioning" and cl.kind_of("bis.EURUSD") == "rate"
    assert cl.kind_of("ecb.eur_aaa_10y") == "rate" and cl.kind_of("fred.macro1") == "macro"


def test_the_desk_ontology_registers_and_maps_the_mt5_kinds():
    ont, pair_map = cl.build_ontology()
    if not ont:  # pragma: no cover - the library is a hard dependency of the desk
        pytest.skip("mechanism_ontology unavailable")
    for mid, pairs, _, _ in cl._MECHANISMS:
        assert mid in ont and ont[mid].falsifiers, f"{mid} registered without a falsifier"
        for p in pairs:
            assert pair_map[p] == mid
    assert ("fx", "fx") not in pair_map, "a cross-pair identity must not count as a mechanism"
