"""Trajectory evolution: the genome carries the step that killed the run, the mutation happens
THERE and nowhere else, a segment crosses only when the causal contract admits it, nothing leaves
for a family this tree cannot call or an instrument the two-lane order does not hunt, the factor
memory survives a run and fertility moves when a child cashes, the budget stops the generation,
and `--dry-run` writes nothing.

Every path is monkeypatched onto a tmp desk: the graph, the verdict ledger, the shadow state, the
universe registry, the ban list, the trajectory store and the donation seam. Nothing here reads or
writes the real desk.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import research_state as store  # noqa: E402
from libs.research import trajectory as tj  # noqa: E402
from research import axis_registry as ar  # noqa: E402
from research import family_policy as fp  # noqa: E402
from research import trajectory_evolution as te  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: Families the fake tree can call. Real names, so `axis_registry.FAMILY_TABLE` classifies them:
#: carry -> carry_rollover/carry, lead_lag -> cross_market_lead/cross_asset, liquidity_regime ->
#: execution_microstructure/microstructure, overnight_gap_decay -> session_handover/price_only,
#: range_reversion and trend_ma_cross -> range_reversion / trend_persistence, both price_only.
FAMILIES = frozenset({"carry", "lead_lag", "liquidity_regime", "overnight_gap_decay",
                      "range_reversion", "trend_ma_cross", "vol_transition", "turn_of_month"})

REGISTRY = {
    "EURUSD": {"asset_class": "forex", "bars": 40000},
    "GBPUSD": {"asset_class": "forex", "bars": 39000},
    "USDJPY": {"asset_class": "forex", "bars": 38000},
    "XAUUSD": {"asset_class": "metals", "bars": 37000},
    "Apple": {"asset_class": "equities", "bars": 9000},
}


def _row(node: str, symbol: str, family: str, params: dict[str, Any],
         fate: str = "FAILED") -> dict[str, Any]:
    return {"id": node, "symbol": symbol, "family": family, "params": params,
            "source": "miner:test", "fate": fate, "gates": {"canonical_report": {}},
            "at": "2026-09-16T00:00:00+00:00"}


def _append(path: Path, *rows: dict[str, Any]) -> None:
    """Append JSONL rows to one of the fake desk's ledgers."""
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _verdict(row: dict[str, Any], gate: str, passed: bool = False) -> dict[str, Any]:
    return {"at": "2026-09-16T04:00:00+00:00",
            "cell": te._cell_id(row["symbol"], row["family"], row["params"]),
            "sym": row["symbol"], "family": row["family"], "terminal_gate": gate,
            "passed": passed}


#: (node, symbol, family, params, terminal gate) -- one judged cell per failure stage the map
#: knows, plus an unmapped gate and a pass.
CELLS: tuple[tuple[str, str, str, dict[str, Any], str], ...] = (
    ("n1", "EURUSD", "carry", {"ttl_bars": 2, "entry_z": 1.5, "rr": 2.0}, "stress_costs"),
    ("n2", "EURUSD", "lead_lag", {"lookback": 100, "entry_z": 2.0, "ttl_bars": 4},
     "deflated_sharpe"),
    ("n3", "GBPUSD", "trend_ma_cross", {"fast": 12, "slow": 96, "ttl_bars": 24},
     "economic_prior"),
    ("n4", "XAUUSD", "overnight_gap_decay", {"ttl_bars": 6, "rr": 1.5, "session": "asia"},
     "in_sample_screen"),
    ("n5", "USDJPY", "liquidity_regime", {"lookback": 96, "widen_z": 2.0, "ttl_bars": 12},
     "UNKNOWN"),
    ("n6", "Apple", "turn_of_month", {"ttl_bars": 48}, "stress_costs"),
    ("n7", "GBPUSD", "vol_transition", {"ratio_in": 1.4, "ttl_bars": 24}, "PASSED"),
)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole fake desk: graph, ledger, shadow state, registry, ban list and trajectory store."""
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    graph, ledger = tmp_path / "graph.jsonl", tmp_path / "data" / "hypotheses" / "verdicts.jsonl"
    rows = [_row(n, s, f, p) for n, s, f, p, _g in CELLS]
    graph.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    verdicts = [_verdict(r, c[-1], passed=c[-1] == "PASSED")
                for r, c in zip(rows, CELLS, strict=True)]
    ledger.write_text("\n".join(json.dumps(v) for v in verdicts) + "\n", encoding="utf-8")
    (tmp_path / "reports" / "shadow" / "shadow_state.json").write_text(
        json.dumps({"EURUSD.carry.all": {"n": 12, "exp_r": 0.08}}), encoding="utf-8")
    (tmp_path / "universe.json").write_text(json.dumps(REGISTRY), encoding="utf-8")
    (tmp_path / "banned.json").write_text(
        json.dumps({"banned": {"discovered": {"why": "the principal banned it"}}}),
        encoding="utf-8")

    monkeypatch.setattr(te, "GRAPH", graph)
    monkeypatch.setattr(te, "VERDICTS", ledger)
    monkeypatch.setattr(te, "SHADOW", tmp_path / "reports" / "shadow")
    monkeypatch.setattr(te, "AXIS_REPORT", tmp_path / "AXIS_REGISTRY.json")
    monkeypatch.setattr(te, "MEMORY", tmp_path / "data" / "trajectory_memory.json")
    monkeypatch.setattr(te, "OUT", tmp_path / "reports" / "TRAJECTORY_EVOLUTION.json")
    monkeypatch.setattr(te, "registered_families", lambda: FAMILIES)
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", tmp_path / "banned.json")
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(ar, "UNIVERSE", tmp_path / "universe.json")
    up._registry.cache_clear()
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "research_state.db")
    yield tmp_path
    up._registry.cache_clear()


@pytest.fixture
def donations(monkeypatch: pytest.MonkeyPatch) -> list[list[dict[str, Any]]]:
    """Capture what would leave for the intake, without a live donation door."""
    seen: list[list[dict[str, Any]]] = []

    def capture(rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        seen.append([dict(r) for r in rows])
        return "intake/discoveries_test.json", {"donated": len(rows)}

    monkeypatch.setattr(te, "donate_children", capture)
    return seen


def _genome(node: str) -> te.Genome:
    """One genome, assembled the way the organ assembles it, for a unit-level assertion."""
    spec = next(c for c in CELLS if c[0] == node)
    row = _row(spec[0], spec[1], spec[2], spec[3])
    verdict = _verdict(row, spec[4], passed=spec[4] == "PASSED")
    g = te.genome_of(row, verdict, {})
    assert g is not None
    return g


# --------------------------------------------------------------------------- the genome
def test_every_genome_carries_the_step_its_own_verdict_indicts(desk: Path) -> None:
    genomes, inputs, unmeasured, census = te.assemble()
    by_node = {g.node_id: g for g in genomes}
    assert len(genomes) == len(CELLS)
    assert by_node["n1"].failure_stage == "horizon"        # stress_costs: the holding cost
    assert by_node["n2"].failure_stage == "condition"      # deflated_sharpe: the width
    assert by_node["n3"].failure_stage == "mechanism"      # economic_prior: no named cause
    assert by_node["n4"].failure_stage == "condition"      # in_sample_screen
    assert by_node["n7"].failure_stage == "PASSED"
    # AN UNMAPPED GATE INDICTS NOTHING. `mutation_target` would answer "mechanism" for it; a census
    # that accepted that answer would blame a step the verdict never named.
    assert by_node["n5"].failure_stage == te.UNATTRIBUTED
    assert te.tj.mutation_target("UNKNOWN") == "mechanism"
    # The CENSUS counts every judged cell, held or not, so the report's stage table is the whole
    # graveyard rather than the head of a file.
    assert dict(census) == {"horizon": 2, "condition": 2, "mechanism": 1,
                            te.UNATTRIBUTED: 1, "PASSED": 1}
    assert any("no attributable failure" in u["what"] for u in unmeasured)
    assert "7 row(s)" in inputs["hypothesis_graph"] and "7 cell(s)" in inputs["gate_verdict_ledger"]


def test_a_row_still_marked_born_is_assembled_once_the_ledger_has_judged_it(desk: Path) -> None:
    """The graph is appended hourly and the ledger more often, so the newest verdicts land against
    rows whose fate was never rewritten. Reading the fate alone lost every one of them."""
    judged = _row("n8", "GBPUSD", "range_reversion", {"entry_z": 2.0, "ttl_bars": 8}, fate="BORN")
    judged["gates"] = {}
    fresh = _row("n9", "GBPUSD", "range_reversion", {"entry_z": 3.0, "ttl_bars": 9}, fate="BORN")
    fresh["gates"] = {}
    _append(te.GRAPH, judged, fresh)
    _append(te.VERDICTS, _verdict(judged, "deflated_sharpe"))
    nodes = {g.node_id: g for g in te.assemble()[0]}
    assert nodes["n8"].failure_stage == "condition"
    assert "n9" not in nodes          # born, unjudged, and nothing is claimed about it


def test_the_genome_carries_the_whole_path_not_just_the_formula(desk: Path) -> None:
    g = _genome("n1")
    assert g.source_ground == "miner:test"
    assert g.causal_hypothesis == "carry_rollover"
    assert g.economic_actor == "negative_carry_holder"
    assert g.information_axes["information_source"] == "carry"
    assert g.feature_construction == {"family": "carry",
                                      "param_keys": ["entry_z", "rr", "ttl_bars"]}
    assert g.timing_logic["session"] == "all" and g.timing_logic["chart"] == "H1"
    assert g.risk_transform == {"rr": 2.0} and g.exit_logic == {"ttl_bars": 2}
    assert "stress_costs" in g.falsifier
    assert g.validation_history["terminal_gate"] == "stress_costs"
    assert g.validation_history["gates_passed"][:2] == ["symbol_eligibility", "economic_prior"]


def test_forward_evidence_joins_the_genome_when_a_clock_exists(desk: Path) -> None:
    genomes, _inputs, _unmeasured, _census = te.assemble()
    carry = next(g for g in genomes if g.node_id == "n1")
    other = next(g for g in genomes if g.node_id == "n3")
    assert carry.validation_history["forward_n"] == 12
    assert carry.validation_history["forward_exp_r"] == pytest.approx(0.08)
    assert other.validation_history["forward_n"] is None     # UNMEASURED, never zero


def test_every_gate_class_agrees_with_the_desks_own_gate_spec() -> None:
    """The lineage posterior must move only where the gate spec says the gate tests VALIDITY."""
    from research.gate_classification import GATE_CLASSIFICATION

    from libs.research.artifacts import POWER_FAILURES, VALIDITY_FAILURES

    for gate, klass in GATE_CLASSIFICATION.items():
        cls = te.GATE_FAILURE_CLASS[gate]
        expected = POWER_FAILURES if klass == "power" else VALIDITY_FAILURES
        assert cls in expected, f"{gate} is {klass} in the spec but {cls} here"


# --------------------------------------------------------------------------- mutation
def test_a_cost_failed_genome_mutates_its_exit_and_never_its_mechanism(desk: Path) -> None:
    g = _genome("n1")
    refusals: Counter = Counter()
    child = te.mutate_child(g, refusals, set())
    assert child is not None and not refusals
    assert child["lineage"]["step_mutated"] == "horizon"
    assert child["family"] == "carry"                       # the mechanism is untouched
    assert child["mechanism"] == "carry_rollover"
    assert child["params"]["ttl_bars"] == 4                 # hold it longer, amortise the cost
    assert child["params"]["entry_z"] == 1.5                # the condition was never indicted
    assert child["source"] == "trajectory_evolution:mutate"
    assert child["lineage"]["parents"] == [g.cell]
    assert child["lineage"]["mutation_op"] == "trajectory_evolution:horizon"


def test_a_mechanism_failure_leaves_the_branch_instead_of_re_parameterising_it(desk: Path) -> None:
    g = _genome("n3")
    child = te.mutate_child(g, Counter(), set())
    assert child is not None and child["lineage"]["step_mutated"] == "mechanism"
    assert child["family"] != g.family
    assert child["family"] in FAMILIES
    assert ar.classify_family(child["family"])[0] != g.causal_hypothesis
    assert set(child["params"]) <= set(te.CARRIER_KEYS)     # the new family keeps its own defaults


def test_a_condition_failure_tightens_the_condition_and_leaves_the_exit_alone(desk: Path) -> None:
    g = _genome("n2")
    child = te.mutate_child(g, Counter(), set())
    assert child is not None and child["lineage"]["step_mutated"] == "condition"
    assert child["params"]["entry_z"] == 2.5
    assert child["params"]["ttl_bars"] == 4 and child["params"]["lookback"] == 100


def test_an_unattributed_or_passed_genome_is_never_mutated(desk: Path) -> None:
    refusals: Counter = Counter()
    assert te.mutate_child(_genome("n5"), refusals, set()) is None
    assert te.mutate_child(_genome("n7"), refusals, set()) is None
    assert refusals["no_mutable_step"] == 2


# --------------------------------------------------------------------------- crossover
def test_crossover_is_refused_when_the_left_contract_does_not_admit_the_right(desk: Path) -> None:
    """`liquidity_regime` is ORDER_FLOW_IMBALANCE in the ontology; `basis` does not measure it."""
    left, right = _genome("n5"), _genome("n1")
    left.failure_stage = "condition"                        # give it an attributed step
    ok, code, why = te.compatible(left, right)
    assert not ok and code == "ontology_refuses" and "does not MEASURE" in why
    refusals: Counter = Counter()
    assert te.crossover_child(left, right, refusals, set()) is None
    assert refusals["ontology_refuses"] == 1


def test_crossover_is_admitted_when_the_left_contract_lists_the_right_observable(desk: Path
                                                                                ) -> None:
    """`lead_lag` is CROSS_VENUE_PRICE_DISCOVERY, whose observables include `basis` -- the carry
    genome's observable -- so the two cross even though they read different information sources."""
    left, right = _genome("n2"), _genome("n1")
    ok, code, _why = te.compatible(left, right)
    assert ok and code == "ontology_admits"
    child = te.crossover_child(left, right, Counter(), set())
    assert child is not None
    assert child["lineage"]["operation"] == "crossover"
    assert child["lineage"]["step_mutated"] == "condition"  # the step the LEFT parent died at
    assert child["lineage"]["parents"] == [left.cell, right.cell]
    assert child["family"] == "lead_lag" and child["symbol"] == "EURUSD"
    assert child["params"]["entry_z"] == 1.5                # the segment taken from the right
    assert child["params"]["lookback"] == 100               # everything else is the left's
    assert child["source"] == "trajectory_evolution:crossover"


def test_a_session_window_mechanism_never_crosses_with_a_continuous_one(desk: Path) -> None:
    window, continuous = _genome("n4"), _genome("n1")
    ok, code, _why = te.compatible(window, continuous)
    assert not ok and code == "session_window_vs_continuous"
    refusals: Counter = Counter()
    assert te.crossover_child(window, continuous, refusals, set()) is None
    assert refusals["session_window_vs_continuous"] == 1


def test_one_mechanism_never_crosses_with_itself_and_neither_do_two_equal_failures(desk: Path
                                                                                  ) -> None:
    a, b = _genome("n1"), _genome("n1")
    assert te.compatible(a, b)[1] == "same_mechanism"
    left, right = _genome("n2"), _genome("n4")
    right.failure_stage = left.failure_stage
    refusals: Counter = Counter()
    assert te.crossover_child(left, right, refusals, set()) is None
    assert refusals["same_failing_step"] == 1


# --------------------------------------------------------------------------- the door
def test_a_child_is_refused_for_an_unregistered_family_and_for_the_wrong_lane(desk: Path,
                                                                             monkeypatch) -> None:
    monkeypatch.setattr(te, "registered_families", lambda: frozenset({"lead_lag"}))
    refusals: Counter = Counter()
    assert te.mutate_child(_genome("n1"), refusals, set()) is None
    assert refusals["unregistered_family"] == 1

    monkeypatch.setattr(te, "registered_families", lambda: FAMILIES)
    equity = _genome("n6")                                  # Apple: the event lane, never hunted
    assert equity.failure_stage == "horizon"
    assert te.mutate_child(equity, refusals, set()) is None
    assert refusals["wrong_lane"] == 1


def test_a_banned_family_never_leaves_even_when_it_is_registered(desk: Path,
                                                                 monkeypatch) -> None:
    monkeypatch.setattr(te, "registered_families", lambda: FAMILIES | {"discovered"})
    g = _genome("n1")
    refusals: Counter = Counter()
    assert te._child([g], "mutate", "horizon", "EURUSD", "discovered", {"ttl_bars": 4},
                     "why", refusals, set()) is None
    assert refusals["banned_family"] == 1


def test_a_cell_already_tried_is_not_proposed_twice(desk: Path) -> None:
    g = _genome("n1")
    refusals: Counter = Counter()
    known: set[str] = set()
    first = te.mutate_child(g, refusals, known)
    assert first is not None and first["cell"] in known
    assert te.mutate_child(g, refusals, known) is None
    assert refusals["already_tried"] == 1


# --------------------------------------------------------------------------- the run
def test_a_full_run_donates_executable_children_and_writes_both_artifacts(
        desk: Path, donations: list) -> None:
    report = te.run(max_children=6, budget_s=60, seed=7)
    assert report["n_genomes"] == len(CELLS)
    assert report["by_failure_stage"]["condition"] == 2
    assert 0 < report["n_children"] <= 6
    assert report["donated"] == report["n_children"]
    assert sum(report["by_operation"].values()) == report["n_children"]
    assert report["rule"] == te.RULE
    assert set(report) >= {"at", "n_genomes", "by_failure_stage", "n_seeds", "n_children",
                           "by_operation", "compatibility_refusals", "donated", "unmeasured",
                           "rule"}
    rows = donations[0]
    for row in rows:
        assert row["family"] in FAMILIES and isinstance(row["params"], dict)
        assert row["symbol"] in REGISTRY and row["symbol"] != "Apple"
        assert row["source"].startswith("trajectory_evolution:")
        assert row["lineage"]["parents"] and row["lineage"]["step_mutated"]
        assert "IDEA" in row["evidence"]["starts_at"]
    assert te.OUT.exists() and te.MEMORY.exists()
    assert json.loads(te.OUT.read_text("utf-8"))["n_children"] == report["n_children"]


def test_the_factor_memory_persists_children_and_fertility_rises_when_one_cashes(
        desk: Path, donations: list) -> None:
    first = te.run(max_children=4, budget_s=60, seed=3)
    assert first["n_children"] >= 1
    mem_after_run1 = json.loads(te.MEMORY.read_text("utf-8"))
    parent = next(iter(mem_after_run1["genomes"]))
    kids = mem_after_run1["genomes"][parent]["children"]
    assert kids and all(k["outcome"] == "UNMEASURED" for k in kids)
    assert mem_after_run1["genomes"][parent]["proposed"] == len(kids)
    assert mem_after_run1["genomes"][parent]["cashed"] == 0
    assert mem_after_run1["runs"] == 1

    genomes, _i, _u, _c = te.assemble()
    seed_genome = next(g for g in genomes if g.cell == parent)
    before = tj.parent_weights(te.parent_rows(mem_after_run1, [seed_genome], {}))[0]

    # THE CHILD IS JUDGED, AND THE LOOP CLOSES ON THE NEXT RUN: the ledger gains its verdict, the
    # memory joins it back by cell id, and the parent's fertility moves. Nothing else changed.
    _append(te.VERDICTS, {"at": "2026-09-17T00:00:00+00:00", "cell": kids[0]["cell"],
                          "terminal_gate": "PASSED", "passed": True})
    second = te.run(max_children=0, budget_s=60, seed=3)
    mem_after_run2 = json.loads(te.MEMORY.read_text("utf-8"))
    row = mem_after_run2["genomes"][parent]
    assert row["children"][0]["outcome"] == "CERTIFIED"
    assert row["cashed"] == 1 and row["recent_children"] == len(kids) - 1
    assert second["memory"]["runs"] == 1 and mem_after_run2["runs"] == 2
    assert second["memory"]["child_outcomes"]["CERTIFIED"] == 1

    after = tj.parent_weights(te.parent_rows(mem_after_run2, [seed_genome], {}))[0]
    assert after > before


def test_a_rut_discounts_a_genome_through_novelty_rather_than_a_second_rule(desk: Path) -> None:
    g = _genome("n1")
    plain = te.parent_rows({"genomes": {}}, [g], {})[0]
    rut = te.parent_rows({"genomes": {}}, [g], {tuple(sorted(g.concepts)[:3]): {"failures": 40}})[0]
    assert rut["rut_hits"] == 1
    assert rut["recent_children"] == plain["recent_children"] + 1
    assert tj.parent_weights([rut])[0] < tj.parent_weights([plain])[0]


def test_the_budget_stops_the_generation_and_says_so(desk: Path, monkeypatch) -> None:
    genomes, _i, _u, _c = te.assemble()
    order = [g for g in genomes if g.node_id in ("n1", "n2", "n3")]
    monkeypatch.setattr(te, "seeds", lambda *a, **k: (order, {}))
    out = te.evolve(genomes, te.load_memory(), max_children=30,
                    deadline=time.monotonic() - 1.0, seed=5)
    assert out["stopped"] == "budget"
    assert out["children"] == []
    # And the cap is the other stop: one child, then the generation ends.
    capped = te.evolve(genomes, te.load_memory(), max_children=1,
                       deadline=time.monotonic() + 60, seed=5)
    assert len(capped["children"]) == 1 and capped["stopped"] == "max_children"


def test_the_cli_dry_run_measures_and_writes_nothing(desk: Path, donations: list, capsys) -> None:
    assert te.main(["--dry-run", "--max-children", "3", "--budget-s", "30", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "TRAJECTORY EVOLUTION" in out and te.RULE in out
    assert "DRY RUN" in out
    assert not te.OUT.exists() and not te.MEMORY.exists()
    assert donations == []


def test_an_absent_graph_is_unmeasured_rather_than_an_empty_verdict(desk: Path,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(te, "GRAPH", desk / "not_here.jsonl")
    report = te.run(dry_run=True, max_children=5, budget_s=30, seed=1)
    assert report["n_genomes"] == 0 and report["n_children"] == 0
    assert any(u["what"] == "research genomes" for u in report["unmeasured"])
    assert "unreadable or absent" in report["inputs"]["hypothesis_graph"]
