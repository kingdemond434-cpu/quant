"""The paradigm router: every lead meets every paradigm, and the argument is kept.

WHAT THESE PIN. (1) COVERAGE -- one lead is fed to all nine paradigms on one pass, which is the
whole claim of M14 and the one thing a refactor can quietly halve. (2) The agreement rule, and
in particular that it CAN return a disagreement: an instrument pool taken as a union rather than
a plurality would report unanimity forever, which is a metric that cannot take the value it
exists to detect. (3) That a disagreement reaches `research_memory` as kind
`method_disagreement`, keyed by the lead, so it outlives the pass. (4) That an unavailable or
un-seedable paradigm is NAMED as a gap rather than counted as a clean zero (L1.28a). (5) The LLM
intake row, in the shape both compilers already glob. (6) That --dry-run writes nothing.

Every paradigm module is stubbed through `_load`, which is the router's ONE import door. The
real modules have their own suites; what is measured here is what the ROUTER did with them.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paradigm_router as pr  # noqa: E402

from libs.moat import registry as reg  # noqa: E402

LEAD_SYMS = ["XAUUSD", "XAGUSD"]


# --------------------------------------------------------------------------- the stub desk
def _stub_mcts(instruments: list[str]):
    """`project_tree` + `run`, with just enough of the real contract: leaf specs carry `symbol`."""
    def project_tree(roots, kinds):
        nodes = {"root": {"id": "root", "kind": kinds[0], "spec": None}}
        for s in instruments:
            nodes[f"leaf:{s}"] = {"id": f"leaf:{s}", "kind": kinds[-1], "parent": "root",
                                  "spec": {"symbol": s}}
        return nodes

    def run(nodes, root_id, generator, screen, **kw):
        frontier = [{"id": f"leaf:{s}", "value": 0.0, "measured": False} for s in instruments]
        return types.SimpleNamespace(to_dict=lambda: {
            "status": "UNMEASURED", "frontier": frontier, "evaluations": 0,
            "unmeasured": len(instruments), "concentration": 0.0})

    return types.SimpleNamespace(project_tree=project_tree, run=run,
                                 node_id=lambda kind, parent, label: "root")


def _stub_axis():
    return types.SimpleNamespace(
        asset_class_of=lambda s: "metal" if str(s).startswith("X") else "fx",
        may_hypothesise=lambda s: True,
        classify_family=lambda f: ("session_handover", "price_only", "market"),
        MECHANISM_ACTOR={"session_handover": "overnight_desk"})


def _stub_qd(row: dict | None):
    ax = _stub_axis()
    return types.SimpleNamespace(
        ar=ax, UNKNOWN="UNKNOWN", HORIZON_CHART={"sub_4h": "H1", "sub_1d": "H4"},
        niche_of=lambda cell: dict(cell), niche_key=lambda niche: "|".join(sorted(niche)),
        proposal=lambda *a, **k: (dict(row) if row is not None else None))


def _stub_populations(per_population: int):
    class _Ctx:
        def __init__(self, **kw):
            self.kw = kw

    def run(ctx, *, n_per_population, budget_s, names):
        proposals = [(f"expr{i}", n) for n in names for i in range(per_population)]
        yields = {n: types.SimpleNamespace(note=f"{n} drew {per_population}",
                                           proposed=per_population, unique=per_population)
                  for n in names}
        return types.SimpleNamespace(proposals=proposals, yields=yields)

    return types.SimpleNamespace(SearchContext=_Ctx, run=run)


def _stub_program(library: tuple[str, ...]):
    return types.SimpleNamespace(templates=lambda sym: dict.fromkeys(library, object()))


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A tmp registry with one discovery lead, tmp artifacts, and every paradigm stubbed."""
    reg.set_path(tmp_path / "registry.sqlite")
    monkeypatch.setattr(pr, "OUT", tmp_path / "PARADIGM_ROUTER.json")
    monkeypatch.setattr(pr, "INTAKE", tmp_path / "intelligence" / "paradigm_router")
    causal = tmp_path / "CAUSAL_LAB.json"
    causal.write_text(json.dumps({
        "edges": [{"from": "XAUUSD", "to": "ecb.eur_aaa_1y", "lag": 1, "klass": "OBSERVATIONAL"}],
        "dag": {"edges": [{"from": "XAUUSD", "to": "XAGUSD", "weight": 0.76}]}}), encoding="utf-8")
    monkeypatch.setattr(pr, "CAUSAL_LAB", causal)
    monkeypatch.setattr(pr, "_LOADED", {})
    did, _created = reg.record_discovery(
        source_id="probe", source_type="test", mechanism="session_handover", origin="MOAT",
        generator="probe", assets=LEAD_SYMS, sessions=["asia"], horizons=["sub_4h"],
        regimes=["unconditional"], economic_rationale="the asia book must transfer risk",
        exact_rule=json.dumps({"family": "session_range_breakout",
                               "params": {"direction": "long"}}))
    reg.set_discovery_state(did, "INTERPRETED")
    stubs = {
        "mcts": (_stub_mcts(LEAD_SYMS), ""),
        "axis": (_stub_axis(), ""),
        "map_elites": (_stub_qd({"kind": "hypothesis", "family": "session_range_breakout",
                                 "symbols": LEAD_SYMS, "axis_cell": {"instrument": "XAUUSD"},
                                 "timeframe": "H1", "session": "asia"}), ""),
        "populations": (_stub_populations(3), ""),
        "program_evolution": (_stub_program(("session_range_breakout", "adaptive_reversion")), ""),
    }
    monkeypatch.setattr(pr, "_load", lambda key: stubs.get(key, (None, f"{key} stubbed absent")))
    try:
        yield {"tmp": tmp_path, "discovery_id": did, "stubs": stubs}
    finally:
        reg.set_path(None)


# --------------------------------------------------------------------------- coverage
def test_every_paradigm_is_fed_the_lead(desk):
    """Nine paradigms, one lead, one pass -- the claim M14 exists to make."""
    report, rows = pr.route(max_leads=5, budget_s=30.0, dry_run=True)
    assert report["n_leads"] == 1
    assert set(report["paradigms"]) == set(pr.PARADIGMS) and len(pr.PARADIGMS) == 9
    for name in pr.PARADIGMS:
        assert report["paradigms"][name]["fed"] == 1, name
        assert report["paradigms"][name]["available"] is True, name
        assert report["paradigms"][name]["produced"] > 0, name
        assert report["paradigms"][name]["why"], name
    assert report["rule"] == pr.RULE
    assert len(rows) == 1 and rows[0]["kind"] == "hypothesis"
    # the four populations are one call, credited separately
    assert {report["paradigms"][p]["produced"] for p in pr.POPULATIONS} == {3}
    # and the causal lab speaks only about edges it has tested
    assert report["paradigms"]["causal_discovery"]["produced"] == 2


def test_a_queued_candidate_is_a_lead_too(desk):
    """Leads are interpreted discoveries AND the best-scored queued candidates, deduped."""
    reg.enqueue_candidate(family="carry_basis", symbol="EURUSD", params={}, origin="MOAT",
                          mechanism="carry_rollover", generator="probe")
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=True)
    assert report["n_leads"] == 2
    assert {a["mechanism"] for a in report["agreement"]} == {"session_handover", "carry_rollover"}


# --------------------------------------------------------------------------- agreement
def test_agreement_is_a_plurality_so_a_disagreement_can_exist():
    """A union pool could never disagree with itself; a plurality pool can, and must."""
    def out(name, produced, instruments, direction=None):
        return pr._outcome(name, "PRODUCED", "", produced=produced, instruments=instruments,
                           direction=direction)

    verdict = pr.agreement([out("llm_seats", 1, ["XAUUSD"], "long"),
                            out("map_elites", 1, ["XAUUSD"]),
                            out("gp", 1, ["XAUUSD"], "short"),
                            out("mcts", 1, ["USDJPY"]),
                            out("causal_discovery", 0, [])])
    assert verdict["instruments"] == ["XAUUSD"]           # 3 votes against USDJPY's 1
    assert verdict["direction"] == "long"
    assert verdict["agree"] == ["llm_seats", "map_elites"]
    assert set(verdict["disagree"]) == {"gp", "mcts"}     # wrong sign, and a disjoint instrument
    assert "causal_discovery" not in verdict["agree"] + verdict["disagree"]


def test_a_paradigm_that_named_no_instrument_never_disagrees_about_one():
    """A mechanism-level result is not a vote about instruments, and is not scored as one."""
    verdict = pr.agreement([
        pr._outcome("llm_seats", "PRODUCED", "", produced=1, instruments=["XAUUSD"]),
        pr._outcome("symreg", "PRODUCED", "", produced=4, instruments=[])])
    assert verdict["disagree"] == []
    assert verdict["agree"] == ["llm_seats", "symreg"]


def test_one_producer_is_neither_agreement_nor_disagreement():
    verdict = pr.agreement([pr._outcome("llm_seats", "PRODUCED", "", produced=1,
                                        instruments=["XAUUSD"]),
                            pr._outcome("mcts", "GAP", "no instrument")])
    assert verdict["disagree"] == [] and verdict["agree"] == ["llm_seats"]
    assert "nothing to agree or disagree about" in verdict["why"]


def test_disagreement_is_remembered_as_value(desk, monkeypatch):
    """METHOD DISAGREEMENT IS THE OUTPUT NOTHING ELSE PRODUCES, so it goes to the registry."""
    # MCTS lands on an instrument nobody else names: one lead, one recorded argument.
    desk["stubs"]["mcts"] = (_stub_mcts(["USDJPY"]), "")
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=False)
    assert report["n_disagreements"] == 1
    row = report["agreement"][0]
    assert row["disagree"] == ["mcts"] and "llm_seats" in row["agree"]
    mem = reg.memories(kind="method_disagreement")
    assert len(mem) == 1
    assert mem[0]["memory_key"] == f"paradigm:{desk['discovery_id']}"
    payload = json.loads(mem[0]["payload_json"])
    assert payload["disagree"] == ["mcts"]
    assert payload["mechanism"] == "session_handover"
    assert set(payload["by_paradigm"]) == set(pr.PARADIGMS)
    # the SAME lead argued again refreshes one row rather than growing a second
    pr.route(max_leads=5, budget_s=30.0, dry_run=False)
    assert len(reg.memories(kind="method_disagreement")) == 1


def test_agreement_is_not_remembered_as_a_disagreement(desk):
    """When every paradigm lands in the same place there is no argument to keep."""
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=False)
    assert report["n_disagreements"] == 0
    assert reg.memories(kind="method_disagreement") == []


# --------------------------------------------------------------------------- gaps
def test_gaps_are_named_for_unavailable_and_unseedable_paradigms(desk):
    """UNAVAILABLE and GAP are different facts from zero, and both are named with their reason."""
    desk["stubs"].pop("mcts")                                 # the module cannot be imported
    desk["stubs"]["map_elites"] = (_stub_qd(None), "")        # the niche cannot be built
    desk["stubs"]["program_evolution"] = (_stub_program(("cross_asset_residual",)), "")
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=True)
    assert report["paradigms"]["mcts"]["available"] is False
    assert report["paradigms"]["map_elites"]["available"] is True     # loaded, but refused
    assert report["paradigms"]["map_elites"]["produced"] == 0
    assert report["paradigms"]["program_evolution"]["produced"] == 0
    gaps = {g["paradigm"]: g for g in report["gaps"]}
    assert gaps["mcts"]["status"] == "UNAVAILABLE" and "stubbed absent" in gaps["mcts"]["why"]
    assert gaps["map_elites"]["status"] == "GAP"
    assert "no seed inbox" in gaps["program_evolution"]["why"]
    assert all(int(g["n_leads"]) >= 1 for g in report["gaps"])


def test_a_causal_lab_with_no_edge_on_the_lead_is_none_not_a_refutation(desk):
    """An untested pair is not a refuted one, and the report says which it is."""
    (desk["tmp"] / "CAUSAL_LAB.json").write_text(
        json.dumps({"edges": [{"from": "US500", "to": "NAS100", "klass": "OBSERVATIONAL"}],
                    "dag": {"edges": []}}), encoding="utf-8")
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=True)
    assert report["paradigms"]["causal_discovery"]["produced"] == 0
    assert "not a refuted one" in report["paradigms"]["causal_discovery"]["why"]
    assert not any(g["paradigm"] == "causal_discovery" for g in report["gaps"])


# --------------------------------------------------------------------------- the intake
def test_llm_intake_row_is_written_in_the_shape_the_compilers_glob(desk):
    """`data/intelligence/paradigm_router/leads_<stamp>.json`, a STRUCTURED_HYPOTHESIS row."""
    report, _rows = pr.route(max_leads=5, budget_s=30.0, dry_run=False)
    files = sorted((desk["tmp"] / "intelligence" / "paradigm_router").glob("leads_*.json"))
    assert len(files) == 1 and str(files[0]) == report["llm_intake"]
    rows = json.loads(files[0].read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["kind"] == "hypothesis"
    assert rows[0]["family"] == "session_range_breakout"
    assert rows[0]["symbols"] == LEAD_SYMS
    assert rows[0]["source"] == "paradigm_router"
    assert rows[0]["discovery_id"] == desk["discovery_id"]
    assert "falsifier" in rows[0]["prompt"]


def test_a_lead_with_no_family_reaches_the_seats_as_a_question(desk):
    """A compiler cannot execute a guess; a seat can answer a question. Both are produced."""
    lead = {"lead_id": "L1", "discovery_id": "D1", "state": "INTERPRETED", "kind": "discovery",
            "mechanism": "gamma_hedging_state", "family": "", "symbols": [], "params": {},
            "session": "ny", "horizon": "", "regime": "", "direction": None, "why": "", "score": 0}
    outcome, row = pr.p_llm_seats(lead)
    assert outcome["produced"] == 1 and row["kind"] == "question"
    assert "NO instrument declared" in row["prompt"]


def test_dry_run_writes_nothing_and_remembers_nothing(desk):
    assert pr.main(["--dry-run", "--max-leads", "5", "--budget-s", "30"]) == 0
    assert not (desk["tmp"] / "PARADIGM_ROUTER.json").exists()
    assert not (desk["tmp"] / "intelligence").exists()
    assert reg.memories(kind="method_disagreement") == []


def test_main_writes_the_report_and_an_empty_pass_is_a_verdict(desk, monkeypatch):
    """A routed pass writes its artifact; a pass with no lead exits 2 -- news, not a crash."""
    assert pr.main(["--max-leads", "5", "--budget-s", "30"]) == 0
    doc = json.loads((desk["tmp"] / "PARADIGM_ROUTER.json").read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "n_leads", "paradigms", "agreement", "gaps", "unmeasured", "rule"}
    assert doc["n_leads"] == 1 and doc["n_intake_rows"] == 1
    monkeypatch.setattr(pr, "leads", lambda max_leads=50: ([], []))
    assert pr.main(["--max-leads", "5", "--budget-s", "30"]) == 2
