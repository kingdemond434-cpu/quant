"""The tree finds the planted branch, the penalty stops it owning the tree, and None scores 0.

Every assertion here is about a property the ledger's D7/Q15 gap named: a beam that never comes
back, a subtree that monopolises, and an absence that gets read as a failing grade.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import lineage_dag, mcts  # noqa: E402

# --------------------------------------------------------------------- the synthetic tree

ROOT_ID = "r"


def _root() -> dict[str, dict[str, Any]]:
    return {ROOT_ID: mcts.init_node({"id": ROOT_ID, "kind": "mechanism", "parent": None,
                                     "label": "root", "state": "OPEN", "depth": 0})}


def _generator(branch: int = 3, depth: int = 3) -> mcts.Spawn:
    """A lazily grown balanced tree -- the search must EXPAND before it can find anything."""
    def gen(node: mcts.Node) -> Sequence[Mapping[str, Any]]:
        d = int(node.get("depth", 0))
        if d >= depth:
            return []
        return [{"id": f"{node['id']}/{i}", "kind": f"depth{d + 1}", "parent": node["id"],
                 "label": str(i), "depth": d + 1} for i in range(branch)]
    return gen


def _in(node_id: str, branch: str) -> bool:
    return node_id == branch or node_id.startswith(branch + "/")


def _planted(branch: str = "r/1", hot: float = 0.9,
             cold: float = 0.1) -> Callable[[mcts.Node], float | None]:
    def screen(node: mcts.Node) -> float | None:
        return hot if _in(str(node["id"]), branch) else cold
    return screen


# ------------------------------------------------------------------------ the PUCT formula

def test_puct_is_the_declared_formula_and_an_only_child_pays_no_penalty() -> None:
    nodes: dict[str, dict[str, Any]] = {
        "p": mcts.init_node({"id": "p", "visits": 4, "value": 0.5, "unmeasured": 0}),
        "a": mcts.init_node({"id": "a", "parent": "p", "prior": 0.25,
                             "visits": 3, "value": 0.6, "unmeasured": 0}),
        "b": mcts.init_node({"id": "b", "parent": "p", "prior": 0.75,
                             "visits": 1, "value": 0.2, "unmeasured": 0}),
    }
    got = mcts.puct_scores(nodes, "p", ["a", "b"])
    root_term = math.sqrt(4.0)
    # share(a) = 3/4, fair = 1/2 -> penalty = 0.5 * (0.75 - 0.5) / 0.5
    pen_a = mcts.PENALTY_WEIGHT * (0.75 - 0.5) / 0.5
    pen_b = 0.0  # share 1/4 is BELOW the even share; a starved sibling is never charged
    assert got["a"] == pytest.approx(0.6 + 1.4 * 0.25 * root_term / 4.0 - pen_a)
    assert got["b"] == pytest.approx(0.2 + 1.4 * 0.75 * root_term / 2.0 - pen_b)
    # An only child monopolises nothing, because there was nothing else to take.
    assert mcts.subtree_visit_penalty(nodes, "a", ["a"]) == 0.0


def test_the_exploration_term_counts_attempts_so_an_unscreenable_child_stops_monopolising() -> None:
    nodes: dict[str, dict[str, Any]] = {
        "p": mcts.init_node({"id": "p", "visits": 0, "unmeasured": 9}),
        "a": mcts.init_node({"id": "a", "parent": "p", "visits": 0, "unmeasured": 9}),
        "b": mcts.init_node({"id": "b", "parent": "p", "visits": 0, "unmeasured": 0}),
    }
    got = mcts.puct_scores(nodes, "p", ["a", "b"])
    assert mcts.value(nodes["a"]) == 0.0, "nine blanks moved no value -- that is the whole point"
    assert got["b"] > got["a"], "absence must stop buying full optimism without being scored"
    assert mcts.attempts(nodes["a"]) == 9 and mcts.visits(nodes["a"]) == 0


# ---------------------------------------------------------------- selection and expansion

def test_select_returns_the_whole_path_and_never_enters_a_pruned_branch() -> None:
    nodes = _root()
    nodes["r/0"] = mcts.init_node({"id": "r/0", "parent": "r", "state": "PRUNED", "prior": 0.99})
    nodes["r/1"] = mcts.init_node({"id": "r/1", "parent": "r", "state": "OPEN", "prior": 0.01})
    nodes["r/1/0"] = mcts.init_node({"id": "r/1/0", "parent": "r/1"})
    assert mcts.select(ROOT_ID, nodes) == ["r", "r/1", "r/1/0"]
    nodes["r/1"]["state"] = "PRUNED"
    assert mcts.select(ROOT_ID, nodes) == ["r"], "every child closed makes the root the leaf"
    with pytest.raises(KeyError):
        mcts.select("nowhere", nodes)


def test_expand_adds_each_child_once_and_never_resets_evidence_it_finds() -> None:
    nodes = _root()
    first = mcts.expand(nodes[ROOT_ID], _generator(), nodes)
    assert sorted(first) == ["r/0", "r/1", "r/2"]
    assert nodes[ROOT_ID]["children"] == ["r/0", "r/1", "r/2"]
    mcts.backpropagate(["r/1"], 0.8, nodes)
    assert mcts.expand(nodes[ROOT_ID], _generator(), nodes) == [], "re-expansion adds nothing"
    assert mcts.visits(nodes["r/1"]) == 1 and mcts.value(nodes["r/1"]) == pytest.approx(0.8)


def test_children_index_reads_parent_pointers_and_declared_ids_and_path_walks_back() -> None:
    nodes = _root()
    nodes["r/0"] = mcts.init_node({"id": "r/0", "parent": "r"})
    nodes["orphan"] = mcts.init_node({"id": "orphan", "parent": None})
    nodes[ROOT_ID]["children"] = ["orphan", "ghost"]          # declared, one of them absent
    idx = mcts.children_index(nodes)
    assert idx["r"] == ["orphan", "r/0"] and "ghost" not in idx["r"]
    assert mcts.path_to(nodes, "r/0") == ["r", "r/0"]
    nodes["r"]["parent"] = "r/0"                              # a cycle must truncate, not hang
    assert mcts.path_to(nodes, "r/0") == ["r", "r/0"]


# ------------------------------------------------------------- rollout and backpropagation

def test_unmeasured_rollouts_update_nothing_and_are_counted() -> None:
    node = mcts.init_node({"id": "n"})
    for screen in (lambda _n: None, lambda _n: float("nan"), lambda _n: float("inf"),
                   lambda _n: "not a number"):
        assert mcts.rollout(node, screen) is None
    assert mcts.unmeasured(node) == 4
    assert mcts.visits(node) == 0, "UNMEASURED is not a visit"
    assert mcts.value(node) == 0.0, "and it is emphatically not a zero reward"
    assert node["value_sum"] == 0.0


def test_rollout_clips_an_out_of_range_reward_and_records_that_it_did() -> None:
    node = mcts.init_node({"id": "n"})
    assert mcts.rollout(node, lambda _n: 3.5) == 1.0
    assert mcts.rollout(node, lambda _n: -2.0) == 0.0
    assert node["clipped"] == 2
    assert mcts.rollout(node, lambda _n: 0.4) == pytest.approx(0.4) and node["clipped"] == 2


def test_backpropagate_arithmetic_is_a_running_mean_over_the_whole_path() -> None:
    nodes = {nid: mcts.init_node({"id": nid}) for nid in ("r", "a", "b")}
    assert mcts.backpropagate(["r", "a", "b"], 1.0, nodes) == 3
    assert mcts.backpropagate(["r", "a"], 0.0, nodes) == 2
    assert mcts.visits(nodes["r"]) == 2 and mcts.value(nodes["r"]) == pytest.approx(0.5)
    assert mcts.visits(nodes["a"]) == 2 and mcts.value(nodes["a"]) == pytest.approx(0.5)
    assert mcts.visits(nodes["b"]) == 1 and mcts.value(nodes["b"]) == pytest.approx(1.0)
    assert mcts.backpropagate(["r", "absent"], 1.0, nodes) == 1, "a missing id is skipped"
    assert mcts.value(nodes["r"]) == pytest.approx(2.0 / 3.0)


# ------------------------------------------------------------------- the whole search loop

def test_puct_finds_the_planted_branch_within_a_bounded_number_of_iterations() -> None:
    nodes = _root()
    rep = mcts.run(nodes, ROOT_ID, _generator(), _planted(), iterations=60, seed=7)
    assert rep.status == "OK" and rep.evaluations == 60 and rep.unmeasured == 0
    kids = {c: mcts.visits(nodes[c]) for c in ("r/0", "r/1", "r/2")}
    assert kids["r/1"] > kids["r/0"] and kids["r/1"] > kids["r/2"], kids
    assert kids["r/1"] > sum(v for c, v in kids.items() if c != "r/1"), (
        "visits must CONCENTRATE on the rewarding branch, not merely lean toward it")
    assert rep.concentration > 0.5
    top = rep.best[0]
    assert _in(str(top["id"]), "r/1") and top["value"] == pytest.approx(0.9)
    assert top["path"][0] == ROOT_ID and top["path"][1] == "r/1"
    assert rep.nodes_added > 3, "the tree grew past the root's own children"
    assert len(rep.trace) == 60 and rep.trace[0]["expanded"], "iteration 0 expands the root"


def _no_penalty(_n: mcts.Nodes, _t: str, _s: Sequence[str]) -> float:
    """Plain PUCT, for the measurement the penalty has to beat."""
    return 0.0


def test_the_penalty_stops_one_subtree_from_monopolising_without_inverting_the_ranking() -> None:
    """Measured at 90 iterations, seed 3, on a 0.7-vs-0.3 reward gap: plain PUCT gives the
    winning branch 71.1% of the visits and the penalised search 57.8%, so its two rivals get 38
    visits instead of 26. The penalty BINDS and does not INVERT -- the better branch still leads,
    which is the property that keeps this an allocator rather than a handicap."""
    gen, screen = _generator(branch=3, depth=1), _planted("r/0", hot=0.7, cold=0.3)
    penalised, free = _root(), _root()
    with_pen = mcts.run(penalised, ROOT_ID, gen, screen, iterations=90, seed=3)
    without = mcts.run(free, ROOT_ID, gen, screen, iterations=90, seed=3, penalty=_no_penalty)
    assert without.concentration - with_pen.concentration > 0.05, (
        f"the penalty must BIND: {without.concentration:.3f} -> {with_pen.concentration:.3f}")
    rivals = [sum(mcts.visits(t[c]) for c in ("r/1", "r/2")) for t in (penalised, free)]
    assert rivals[0] > rivals[1] * 1.2, f"the starved siblings must get more attention: {rivals}"
    assert with_pen.concentration < 0.7, "no subtree may own two thirds of the attention"
    assert with_pen.best[0]["id"].startswith("r/0"), (
        "and it must not INVERT the ranking -- the better branch still leads")
    assert mcts.visits(penalised["r/0"]) > mcts.visits(penalised["r/1"])


def test_a_branch_nothing_can_screen_stays_unmeasured_and_stops_taking_the_budget() -> None:
    def screen(node: mcts.Node) -> float | None:
        return None if _in(str(node["id"]), "r/0") else 0.5
    nodes = _root()
    rep = mcts.run(nodes, ROOT_ID, _generator(branch=3, depth=1), screen, iterations=40, seed=11)
    assert mcts.visits(nodes["r/0"]) == 0 and mcts.value(nodes["r/0"]) == 0.0
    assert mcts.unmeasured(nodes["r/0"]) > 0 and rep.unmeasured > 0
    assert mcts.attempts(nodes["r/1"]) > mcts.attempts(nodes["r/0"]), (
        "an unscreenable branch must stop being re-selected at full optimism")
    row = next(r for r in mcts.frontier(nodes, 9) if r["id"] == "r/0")
    assert row["measured"] is False and row["value"] == 0.0


def test_a_search_that_measured_nothing_reports_UNMEASURED_rather_than_a_verdict() -> None:
    nodes = _root()
    rep = mcts.run(nodes, ROOT_ID, _generator(branch=2, depth=1), lambda _n: None,
                   iterations=8, seed=1)
    assert rep.status == "UNMEASURED" and rep.evaluations == 0 and rep.unmeasured == 8
    assert rep.concentration == 0.0
    assert "never a verdict" in rep.why
    assert all(mcts.visits(n) == 0 for n in nodes.values())
    assert json.loads(json.dumps(rep.to_dict()))["status"] == "UNMEASURED"


def test_budget_evals_buys_more_than_one_screen_per_iteration() -> None:
    nodes = _root()
    rep = mcts.run(nodes, ROOT_ID, _generator(branch=4, depth=2), _planted("r/2"),
                   iterations=10, seed=5, budget_evals=3)
    assert rep.evaluations > 10, "a wider step must spend more screens than a narrow one"
    assert max(t["evals"] for t in rep.trace) == 3


# ------------------------------------------------------------------ frontier, determinism

def test_frontier_ranks_measured_leaves_by_value_and_sinks_the_unmeasured_ones() -> None:
    nodes = _root()
    for nid, visits, val in (("r/0", 3, 0.2), ("r/1", 5, 0.9), ("r/2", 0, 0.0)):
        nodes[nid] = mcts.init_node({"id": nid, "parent": "r", "kind": "leaf", "label": nid,
                                     "visits": visits, "value": val, "spec": {"symbol": nid}})
    nodes["r/3"] = mcts.init_node({"id": "r/3", "parent": "r", "state": "PRUNED", "visits": 9,
                                   "value": 1.0})
    rows = mcts.frontier(nodes, 9)
    assert [r["id"] for r in rows] == ["r/1", "r/0", "r/2"], "a pruned leaf is not on the frontier"
    assert [r["measured"] for r in rows] == [True, True, False]
    assert rows[0]["path"] == ["r", "r/1"] and rows[0]["spec"] == {"symbol": "r/1"}
    assert mcts.frontier(nodes, 1) == rows[:1]
    assert mcts.frontier(nodes, 9, root_id="elsewhere") == []


def test_two_runs_with_the_same_seed_produce_the_same_tree_and_the_same_trace() -> None:
    start = _root()
    a_nodes, b_nodes = copy.deepcopy(start), copy.deepcopy(start)
    a = mcts.run(a_nodes, ROOT_ID, _generator(), _planted(), iterations=25, seed=42)
    b = mcts.run(b_nodes, ROOT_ID, _generator(), _planted(), iterations=25, seed=42)
    dump = json.dumps
    assert dump(a.to_dict(), sort_keys=True) == dump(b.to_dict(), sort_keys=True)
    assert dump(a_nodes, sort_keys=True) == dump(b_nodes, sort_keys=True)
    c_nodes = copy.deepcopy(start)
    c = mcts.run(c_nodes, ROOT_ID, _generator(), _planted(), iterations=25, seed=43)
    assert c.evaluations == a.evaluations, "a different seed is still the same declared budget"


def test_the_fields_this_library_adds_survive_a_json_round_trip_so_the_caller_can_save_them(
) -> None:
    nodes = _root()
    mcts.run(nodes, ROOT_ID, _generator(branch=2, depth=2), _planted("r/1"),
             iterations=12, seed=2)
    reloaded = json.loads(json.dumps(nodes))
    assert set(reloaded[ROOT_ID]) >= {"visits", "value", "value_sum", "unmeasured", "children"}
    resumed = mcts.run(reloaded, ROOT_ID, _generator(branch=2, depth=2), _planted("r/1"),
                       iterations=4, seed=2)
    assert resumed.status == "OK"
    assert mcts.visits(reloaded[ROOT_ID]) == 16, "a resumed search adds to the saved counts"


# -------------------------------------------------------------- evidence, priors, the ruts

def test_prior_reads_the_three_shapes_a_caller_might_have_written() -> None:
    assert mcts.prior({"prior": 0.42}) == pytest.approx(0.42)
    assert mcts.evidence({"evidence": {"alpha": 3.0, "beta": 1.0}}) == (3.0, 1.0)
    assert mcts.prior({"evidence": {"alpha": 3.0, "beta": 1.0}}) == pytest.approx(0.75)
    assert mcts.prior({"alpha": 1.0, "beta": 3.0}) == pytest.approx(0.25)
    assert mcts.evidence({"successes": 2, "trials": 10}) == (3.0, 9.0)
    assert mcts.prior({}) == pytest.approx(0.5), "no evidence is an even prior, never a zero"
    assert mcts.prior({"prior": "nonsense"}) == pytest.approx(0.5)
    assert mcts.prior({"prior": 7.0}) == pytest.approx(0.5), "an out-of-range prior is ignored"


def test_lineage_dag_ruts_become_a_selection_penalty_and_compose_with_the_visit_share() -> None:
    failed = [lineage_dag.Node(artifact_id=f"a{i}", failure_class="no_effect",
                               concepts=("momentum", "volume", "short_horizon"))
              for i in range(30)]
    ruts = lineage_dag.subtree_penalty(failed)
    assert ruts, "30 validity failures on one triple is a rut by lineage_dag's own threshold"
    pen = mcts.concept_rut_penalty(ruts)
    nodes: dict[str, dict[str, Any]] = {
        "p": mcts.init_node({"id": "p", "visits": 2}),
        "rutted": mcts.init_node({"id": "rutted", "parent": "p", "visits": 2,
                                  "concepts": ("momentum", "volume", "short_horizon", "gold")}),
        "fresh": mcts.init_node({"id": "fresh", "parent": "p", "visits": 0}),
    }
    mult = float(next(iter(ruts.values()))["penalty"])
    assert pen(nodes, "rutted", ["rutted", "fresh"]) == pytest.approx(
        mcts.PENALTY_WEIGHT * (1.0 - mult))
    assert pen(nodes, "fresh", ["rutted", "fresh"]) == 0.0, "no concepts declared, no rut proved"
    both = mcts.combine_penalties(mcts.subtree_visit_penalty, pen)
    assert both(nodes, "rutted", ["rutted", "fresh"]) == pytest.approx(
        mcts.subtree_visit_penalty(nodes, "rutted", ["rutted", "fresh"])
        + pen(nodes, "rutted", ["rutted", "fresh"]))


# ------------------------------------------------------------ projects and their manager

MACRO: dict[str, Any] = {
    "label": "macro_liquidity",
    "levels": [["metals", "fx"],
               {"metals": ["real_yield", "carry"], "fx": ["carry"]},
               ["XAUUSD", "XAGUSD"]],
    "spec": {"base_family": "joint_genome"},
    "prior": 0.3,
}
KINDS = ("project", "asset_class", "mechanism", "cross_market_analogue")


def test_project_tree_has_the_declared_shape_and_its_leaves_are_cell_specs() -> None:
    nodes = mcts.project_tree([MACRO], KINDS)
    rid = mcts.node_id("project", None, "macro_liquidity")
    assert rid == "root|project:macro_liquidity" and rid in nodes
    assert len(nodes) == 1 + 2 + 3 + 6, "root, asset classes, mechanisms, instruments"
    by_kind: dict[str, int] = {}
    for n in nodes.values():
        by_kind[str(n["kind"])] = by_kind.get(str(n["kind"]), 0) + 1
    assert by_kind == {"project": 1, "asset_class": 2, "mechanism": 3,
                       "cross_market_analogue": 6}
    idx = mcts.children_index(nodes)
    leaves = [n for nid, n in nodes.items() if not idx[nid]]
    assert len(leaves) == 6 and all(n["kind"] == "cross_market_analogue" for n in leaves)
    assert all(n["spec"] is None for nid, n in nodes.items() if idx[nid]), (
        "only a leaf is a cell; an interior node is a question")
    gold = nodes["root|project:macro_liquidity|asset_class:metals|mechanism:real_yield"
                 "|cross_market_analogue:XAUUSD"]
    assert gold["spec"] == {"base_family": "joint_genome", "project": "macro_liquidity",
                            "branch": "metals/real_yield", "symbol": "XAUUSD"}
    assert all("symbol" in n["spec"] for n in leaves), "research_tree._donate pops `symbol`"
    assert nodes[rid]["prior"] == pytest.approx(0.3)
    assert mcts.path_to(nodes, gold["id"])[:2] == [
        rid, "root|project:macro_liquidity|asset_class:metals"]


def test_project_tree_refuses_a_tree_it_cannot_name() -> None:
    with pytest.raises(ValueError, match="depth_kinds is empty"):
        mcts.project_tree([MACRO], ())
    with pytest.raises(ValueError, match="needs a label"):
        mcts.project_tree([{"levels": [["a"]]}], KINDS)
    flat = mcts.project_tree([{"label": "bare"}], ("project",))
    assert list(flat) == ["root|project:bare"], "a project with no levels is just its root"
    assert flat["root|project:bare"]["spec"] == {"project": "bare", "branch": "",
                                                 "symbol": "bare"}


def test_a_prebuilt_project_tree_is_searchable_without_any_generator() -> None:
    nodes = mcts.project_tree([MACRO], KINDS)
    rid = mcts.node_id("project", None, "macro_liquidity")

    def screen(node: mcts.Node) -> float | None:
        spec = node.get("spec")
        if not isinstance(spec, Mapping):
            return None
        return 0.9 if spec.get("symbol") == "XAUUSD" else 0.2

    rep = mcts.run(nodes, rid, lambda _n: [], screen, iterations=40, seed=4)
    assert rep.status == "OK" and rep.nodes_added == 0
    assert rep.best[0]["spec"]["symbol"] == "XAUUSD"
    assert rep.best[0]["value"] == pytest.approx(0.9)


def test_allocate_honours_the_floor_spends_the_whole_budget_and_breaks_ties_by_index() -> None:
    assert mcts.allocate([1.0, 0.0], 20, floor=0.1) == [18, 2]
    assert mcts.allocate([0.0, 0.0], 10) == [5, 5], "no measured value is an EVEN split"
    assert mcts.allocate([3.0, 1.0], 12, floor=0.25) == [8, 4], (
        "3 each as the floor, then 6 split 3:1 -> 4.5/1.5, the half breaking to index 0")
    assert sum(mcts.allocate([5.0, 1.0, 1.0], 37)) == 37
    assert mcts.allocate([1.0, 1.0, 1.0], 2) == [1, 1, 0], (
        "below one rollout per project the shortfall is arithmetic, not policy")
    assert mcts.allocate([], 10) == [] and mcts.allocate([1.0], 0) == [0]
    assert mcts.allocate([float("nan"), 1.0], 10, floor=0.1) == [1, 9]


def _flat_project(name: str, val: float, *, symbols: Sequence[str]) -> mcts.Project:
    nodes = mcts.project_tree([{"label": name, "levels": [list(symbols)]}],
                              ("project", "cross_market_analogue"))
    rid = mcts.node_id("project", None, name)
    for nid, node in nodes.items():
        if nid != rid:
            node.update({"visits": 5, "value": val, "value_sum": 5 * val})
    return mcts.Project(name=name, root_id=rid, nodes=nodes)


def test_experiment_manager_prefers_the_richer_project_and_never_starves_the_other() -> None:
    rich = _flat_project("rich", 0.9, symbols=("XAUUSD", "XAGUSD", "EURUSD"))
    poor = _flat_project("poor", 0.1, symbols=("US500", "USOIL", "GBPJPY"))
    out = mcts.experiment_manager([rich, poor], 20, lambda n: 0.9 if "rich" in n["id"] else 0.1)
    got = {r["name"]: r for r in out["projects"]}
    assert out["status"] == "OK" and out["granted"] == 20 and out["unfunded"] == 0
    assert got["rich"]["allocated"] > got["poor"]["allocated"], got
    assert got["poor"]["allocated"] >= 2, "the floor is what the starved project is owed"
    assert got["poor"]["evaluations"] > 0, "a floor nobody spends is not a floor"
    assert got["rich"]["weight"] > got["poor"]["weight"]
    assert out["deepen"] and out["deepen"][0]["project"] == "rich"
    held = {"rich": rich, "poor": poor}
    assert all(held[d["project"]].nodes[d["branch_id"]]["parent"]
               == held[d["project"]].root_id for d in out["deepen"]), (
        "a branch to deepen is a CHILD of the project root, never the root and never an ancestor")
    assert out["evaluations"] == sum(r["evaluations"] for r in out["projects"])


def test_the_branch_to_deepen_is_the_root_child_that_carried_the_best_leaf() -> None:
    nodes = mcts.project_tree([MACRO], KINDS)
    rid = mcts.node_id("project", None, "macro_liquidity")
    proj = mcts.Project(name="macro", root_id=rid, nodes=nodes)

    def screen(node: mcts.Node) -> float | None:
        spec = node.get("spec")
        return None if not isinstance(spec, Mapping) else (
            0.95 if spec.get("branch") == "metals/carry" else 0.05)

    out = mcts.experiment_manager([proj], 30, screen)
    top = out["deepen"][0]
    assert top["branch_id"] == rid + "|asset_class:metals"
    assert top["label"] == "metals" and top["kind"] == "asset_class"
    assert top["best_leaf"] != top["branch_id"], "the branch is an ANCESTOR of the leaf"
    assert top["best_leaf"].startswith(top["branch_id"] + "|mechanism:carry")
    assert top["spec"]["branch"] == "metals/carry"


def test_experiment_manager_splits_evenly_when_no_project_has_been_measured_yet() -> None:
    a = mcts.Project(name="a", root_id=mcts.node_id("project", None, "a"),
                     nodes=mcts.project_tree([{"label": "a", "levels": [["X", "Y"]]}],
                                             ("project", "cross_market_analogue")))
    b = mcts.Project(name="b", root_id=mcts.node_id("project", None, "b"),
                     nodes=mcts.project_tree([{"label": "b", "levels": [["Z", "W"]]}],
                                             ("project", "cross_market_analogue")))
    out = mcts.experiment_manager([a, b], 12, lambda _n: None)
    assert [r["allocated"] for r in out["projects"]] == [6, 6]
    assert out["status"] == "UNMEASURED" and out["evaluations"] == 0
    assert out["unmeasured"] == 12 and out["deepen"] == []
    assert all(r["status"] == "UNMEASURED" for r in out["projects"])
