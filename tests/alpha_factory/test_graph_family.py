"""Research graph and alpha family tree."""

from __future__ import annotations

import pytest

from libs.alpha_factory.alpha_family_tree import AlphaFamilyTree
from libs.alpha_factory.errors import AlphaFactoryError
from libs.alpha_factory.research_graph import ResearchGraph


def test_family_tree_lineage_and_best() -> None:
    tree = AlphaFamilyTree()
    tree.add("trend_v1", mutation_type="root", performance=1.0)
    tree.add("trend_v2", parent_id="trend_v1", mutation_type="add_filter", performance=1.5)
    tree.add("trend_v3", parent_id="trend_v2", mutation_type="add_capacity", performance=2.0)
    tree.add("mom_v1", mutation_type="root", performance=0.5)
    assert [n.alpha_id for n in tree.lineage("trend_v3")] == ["trend_v1", "trend_v2", "trend_v3"]
    assert [n.alpha_id for n in tree.children("trend_v1")] == ["trend_v2"]
    assert [n.alpha_id for n in tree.best_lineage()] == ["trend_v1", "trend_v2", "trend_v3"]


def test_family_tree_errors() -> None:
    tree = AlphaFamilyTree()
    tree.add("a")
    with pytest.raises(AlphaFactoryError):
        tree.add("a")  # duplicate
    with pytest.raises(AlphaFactoryError):
        tree.add("b", parent_id="missing")
    assert tree.get("missing") is None
    assert AlphaFamilyTree().best_lineage() == []


def test_research_graph_paths_and_feature_importance() -> None:
    g = ResearchGraph()
    g.add_node("idea1", "idea")
    g.add_node("feat1", "feature")
    g.add_node("alpha1", "alpha")
    g.add_node("perf1", "performance", value=2.0)
    g.add_node("perf_lo", "performance", value=0.1)
    g.add_node("feat2", "feature")
    g.add_node("alpha2", "alpha")
    g.add_edge("idea1", "feat1")
    g.add_edge("feat1", "alpha1")
    g.add_edge("alpha1", "perf1")
    g.add_edge("feat2", "alpha2")
    g.add_edge("alpha2", "perf_lo")

    assert g.neighbors("idea1") == ["feat1"]
    assert g.predecessors("alpha1") == ["feat1"]
    assert g.nodes_of_type("feature") == ["feat1", "feat2"]
    assert g.path_exists("idea1", "perf1")
    assert not g.path_exists("perf1", "idea1")
    # only feat1 feeds a winning (perf >= 1.0) alpha
    assert g.feature_importance(min_performance=1.0) == {"feat1": 1}


def test_research_graph_diamond_revisits_nodes() -> None:
    # A diamond (two features feed one alpha) exercises the "already seen" BFS branches.
    g = ResearchGraph()
    g.add_node("idea", "idea")
    g.add_node("featA", "feature")
    g.add_node("featB", "feature")
    g.add_node("alpha", "alpha")
    g.add_node("perf", "performance", value=2.0)
    g.add_edge("idea", "featA")
    g.add_edge("idea", "featB")
    g.add_edge("featA", "alpha")
    g.add_edge("featB", "alpha")
    g.add_edge("alpha", "perf")
    assert g.path_exists("idea", "perf")  # alpha reached via two paths
    assert g.feature_importance(min_performance=1.0) == {"featA": 1, "featB": 1}


def test_research_graph_errors() -> None:
    g = ResearchGraph()
    with pytest.raises(AlphaFactoryError):
        g.add_node("x", "not_a_type")
    g.add_node("a", "idea")
    with pytest.raises(AlphaFactoryError):
        g.add_edge("a", "missing")
    assert not g.path_exists("a", "missing")
