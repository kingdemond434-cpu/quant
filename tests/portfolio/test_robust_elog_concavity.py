"""The solver treats its objective as non-convex and never certifies a beaten point (2026-10-06).

Counterexample that motivated it: two identical streams under a 0.20 mandate. The redundancy
charge h'(|C| - I)h = 2*h1*h2 is a saddle; the old ascent stopped at 0.10/0.10 with
`converged=True` while 0.20/0.00 scored higher. A PSD replacement was tried and discarded because
it made admission of a diversifier worse (see `_redundancy`), so the fix is in the solver:
multi-start, best-known feasible book, and a LOCAL (KKT) certificate that says it is local.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.robust_elog import (
    SleeveEvidence,
    Worlds,
    _corr_abs,
    fw_gap,
    fw_vertex,
    optimise,
    score_book,
)


def _identical_pair() -> tuple[list[SleeveEvidence], Worlds]:
    r = np.tile([0.002, -0.001], 100).astype(float)
    ev = [SleeveEvidence("a", r.copy()), SleeveEvidence("b", r.copy())]
    col = np.tile(np.array([0.01, -0.005], dtype=np.float32), 64)
    big = np.stack([np.stack([col, col], axis=1)] * 16)
    w = Worlds(r=big, names=("a", "b"), crisis=np.zeros(16, bool), mu_draws=np.zeros((16, 2)))
    return ev, w


@pytest.mark.parametrize("ub", [None, 0.15])
def test_mandated_identical_pair_escapes_the_saddle(ub: float | None) -> None:
    ev, w = _identical_pair()
    res = optimise(ev, hard_cap=0.2, target=0.2, worlds=w, max_per_sleeve=ub)
    grid = [x for x in np.linspace(0.0, 0.2, 41) if ub is None or max(x, 0.2 - x) <= ub + 1e-12]
    best = max(score_book(ev, {"a": x, "b": 0.2 - x}, worlds=w)["robust_score"] for x in grid)
    assert res.robust_score >= best - 1e-9, (res.heat, res.robust_score, best)
    assert res.n_starts >= 2
    assert res.certificate == "local_kkt_multistart"


def test_converged_never_marks_a_point_a_feasible_book_beats() -> None:
    ev, w = _identical_pair()
    res = optimise(ev, hard_cap=0.2, target=0.2, worlds=w, max_per_sleeve=0.15)
    rival = score_book(ev, {"a": 0.15, "b": 0.05}, worlds=w)["robust_score"]
    assert not (res.converged and rival > res.robust_score + 1e-12)


def test_the_charge_is_still_the_duplicated_risk_and_still_indefinite() -> None:
    ev, _w = _identical_pair()
    c = _corr_abs(ev)
    eig = np.linalg.eigvalsh(c - np.eye(2))
    assert eig.min() < 0 < eig.max()       # documented: the problem is non-convex


def test_fw_vertex_respects_bounds_and_mandate() -> None:
    g = np.array([3.0, -1.0, 2.0, 0.5])
    ub = np.array([0.05, 0.05, 0.05, 0.05])
    s = fw_vertex(g, 0.08, exact=False, upper=ub)
    assert s.sum() == pytest.approx(0.08)
    assert s[1] == 0.0
    assert fw_vertex(-np.abs(g), 0.08, exact=False, upper=ub).sum() == 0.0
    assert fw_vertex(-np.abs(g), 0.08, exact=True, upper=ub).sum() == pytest.approx(0.08)
    assert fw_gap(g, s, 0.08, exact=False, upper=ub) == pytest.approx(0.0, abs=1e-12)


def test_converged_means_the_published_gap_is_within_tolerance() -> None:
    ev, w = _identical_pair()
    for its in (1, 400):
        res = optimise(ev, hard_cap=0.2, target=None, worlds=w, iterations=its)
        assert res.converged == (res.optimality_gap <= res.gap_tolerance)
