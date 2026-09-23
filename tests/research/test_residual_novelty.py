"""Branch counting must not manufacture the breadth it exists to detect."""
from __future__ import annotations

import numpy as np

from libs.research.residual_novelty import (
    branch_report,
    participation_ratio,
    strip_factors,
)


def _market(rng, t: int) -> np.ndarray:
    return rng.normal(0.0, 0.01, t)


def test_costumes_of_one_edge_collapse_to_one_branch() -> None:
    """THE REGRESSION THIS MODULE ALMOST SHIPPED WITH.

    Nine strategies that are one edge plus noise must report ONE branch. A residual-only
    implementation returns NINE here, because when every candidate shares the edge, that edge IS
    the leading principal component and stripping it leaves independent noise. That is precisely
    the fake breadth the module exists to prevent, produced by the module itself.
    """
    rng = np.random.default_rng(0)
    t = 800
    mkt, core = _market(rng, t), rng.normal(0.0, 0.01, t)
    cols = [mkt + core + rng.normal(0.0, 0.002, t) for _ in range(9)]
    rep = branch_report(np.column_stack(cols), [f"costume{i}" for i in range(9)])
    assert rep.n_branches == 1
    assert rep.largest_branch == 9


def test_independent_edges_stay_separate_despite_shared_market() -> None:
    """The opposite error: common beta must not collapse genuinely different mechanisms."""
    rng = np.random.default_rng(1)
    t = 800
    mkt = _market(rng, t)
    cols = [mkt + rng.normal(0.0, 0.02, t) for _ in range(9)]
    rep = branch_report(np.column_stack(cols), [f"edge{i}" for i in range(9)])
    assert rep.n_branches >= 8


def test_mixture_separates_clones_from_independents() -> None:
    rng = np.random.default_rng(2)
    t = 800
    mkt, core = _market(rng, t), rng.normal(0.0, 0.01, t)
    clones = [mkt + core + rng.normal(0.0, 0.002, t) for _ in range(3)]
    singles = [mkt + rng.normal(0.0, 0.02, t) for _ in range(3)]
    labels = [f"c{i}" for i in range(3)] + [f"i{i}" for i in range(3)]
    rep = branch_report(np.column_stack(clones + singles), labels)
    assert rep.largest_branch == 3
    assert rep.n_branches == 4
    # the three clones share a branch id; the independents do not
    assert len({rep.branch_of[f"c{i}"] for i in range(3)}) == 1
    assert len({rep.branch_of[f"i{i}"] for i in range(3)}) == 3


def test_participation_ratio_bounds() -> None:
    """N for independent, 1 for identical -- the two anchors that make the number readable."""
    assert participation_ratio(np.eye(6)) == 6.0
    assert round(participation_ratio(np.ones((6, 6))), 6) == 1.0


def test_strip_factors_removes_the_shared_component() -> None:
    rng = np.random.default_rng(3)
    t = 500
    mkt = _market(rng, t)
    cols = [mkt + rng.normal(0.0, 0.005, t) for _ in range(5)]
    raw = np.column_stack(cols)
    resid = strip_factors(raw, 1)
    # Residual correlation between distinct columns must be far below the raw correlation.
    raw_c = np.corrcoef(raw, rowvar=False)
    res_c = np.corrcoef(resid, rowvar=False)
    off = ~np.eye(5, dtype=bool)
    assert np.abs(res_c[off]).mean() < np.abs(raw_c[off]).mean()


def test_labels_must_match_columns() -> None:
    try:
        branch_report(np.zeros((10, 3)), ["only", "two"])
    except ValueError:
        return
    raise AssertionError("mismatched labels must raise")


def test_degenerate_inputs_do_not_crash() -> None:
    """A flat or single-column set is a real state on this desk, not an exception."""
    assert branch_report(np.zeros((10, 0)), []).n_branches == 0
    assert branch_report(np.zeros((10, 1)), ["only"]).n_branches == 1
    flat = branch_report(np.zeros((10, 3)), ["a", "b", "c"])
    assert flat.n_strategies == 3
