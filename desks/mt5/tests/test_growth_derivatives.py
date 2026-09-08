"""Exact growth derivatives, and the two ways a derivative can lie about where to add risk.

The gradient ranks sleeves by what the next unit buys. The HESSIAN says how fast that stops being
true and which other sleeve it stops being true because of -- and it was not computed at all,
while `marginal_admission` spent ~1.2s per candidate re-solving the whole book to learn something
the closed form already knows to first order.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.growth_derivatives import (  # noqa: E402
    MEASURED,
    MIN_ROWS,
    UNMEASURED,
    best_next,
    derivatives,
)


def _panel(n_rows: int = 4000, n: int = 3, seed: int = 0, scale: float = 0.3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.02, scale, size=(n_rows, n))


# ------------------------------------------------------------------------ they are the real ones
def test_the_gradient_matches_a_finite_difference() -> None:
    """Closed form or not, it has to equal the thing it claims to be."""
    r = _panel()
    h = np.array([0.04, 0.03, 0.02])
    d = derivatives(r, h, names=["a", "b", "c"])
    assert d["status"] == MEASURED

    def g(hh: np.ndarray) -> float:
        return float(np.log(1.0 + r @ hh).mean())

    eps = 1e-6
    for i, name in enumerate(["a", "b", "c"]):
        up, dn = h.copy(), h.copy()
        up[i] += eps
        dn[i] -= eps
        fd = (g(up) - g(dn)) / (2 * eps)
        assert d["gradient"][name] == pytest.approx(fd, rel=1e-4), name


def test_the_hessian_matches_a_finite_difference_of_the_gradient() -> None:
    r = _panel()
    h = np.array([0.04, 0.03, 0.02])
    d = derivatives(r, h, names=["a", "b", "c"])
    H = np.asarray(d["hessian"])
    eps = 1e-6
    for i in range(3):
        for j in range(3):
            up, dn = h.copy(), h.copy()
            up[j] += eps
            dn[j] -= eps
            gi_up = float((r[:, i] / (1.0 + r @ up)).mean())
            gi_dn = float((r[:, i] / (1.0 + r @ dn)).mean())
            assert H[i, j] == pytest.approx((gi_up - gi_dn) / (2 * eps), rel=1e-3, abs=1e-9)


def test_the_hessian_is_symmetric_and_concave() -> None:
    """v'Hv = -E[(v'r)^2 / (1+h'r)^2] <= 0 for every v. A positive eigenvalue is an input defect,
    not a finding, and the module must say so rather than let a caller step uphill."""
    d = derivatives(_panel(), np.array([0.04, 0.03, 0.02]))
    H = np.asarray(d["hessian"])
    assert np.allclose(H, H.T)
    assert d["curvature_ok"] is True
    assert np.linalg.eigvalsh(H).max() <= 1e-9 * np.abs(H).max()


def test_two_identical_sleeves_have_a_maximally_negative_cross_partial() -> None:
    """A large negative off-diagonal means the pair COMPETES -- they load the same thing, and
    buying one makes the other worse. Duplicates are the extreme case, and the Hessian finds
    them from returns alone, which is the same statement `breadth_credit` makes from cluster
    occupancy by a completely different route."""
    r = _panel(n=2)
    r = np.column_stack([r[:, 0], r[:, 0], r[:, 1]])          # sleeve 0 and 1 are the same trade
    d = derivatives(r, np.array([0.03, 0.03, 0.03]), names=["a", "a_clone", "z"])
    H = np.asarray(d["hessian"])
    assert H[0, 1] == pytest.approx(H[0, 0], rel=1e-9)        # a clone is as costly as itself
    assert abs(H[0, 2]) < abs(H[0, 1]) * 0.5                  # the independent one competes less


# ---------------------------------------------------------------------- ruin is refused
def test_a_ruinous_row_is_dropped_and_counted_never_clipped() -> None:
    """Clipping 1 + h'r to an epsilon turns a wipeout into an enormous FINITE derivative pointing
    at whichever sleeve caused it -- a number that ranks where to ADD risk, produced by the world
    where the book died."""
    r = _panel()
    r[0, :] = -50.0                                            # this row wipes any positive book
    d = derivatives(r, np.array([0.04, 0.03, 0.02]))
    assert d["status"] == MEASURED
    assert d["n_ruined"] == 1
    assert all(abs(v) < 10.0 for v in d["gradient"].values()), d["gradient"]
    assert "dropped where" in d["why"]


def test_too_few_usable_rows_is_a_refusal() -> None:
    d = derivatives(_panel(n_rows=MIN_ROWS - 1), np.array([0.04, 0.03, 0.02]))
    assert d["status"] == UNMEASURED
    assert "got lucky" in d["why"]


def test_a_mismatched_book_is_refused_rather_than_broadcast() -> None:
    d = derivatives(_panel(), np.array([0.04, 0.03]))
    assert d["status"] == UNMEASURED
    assert "return columns" in d["why"]


def test_a_world_cube_is_flattened_rather_than_refused() -> None:
    """`Worlds.r` is (worlds, rows, sleeves) and the expectation is over both."""
    cube = _panel(n_rows=2000).reshape(4, 500, 3)
    d = derivatives(cube, np.array([0.04, 0.03, 0.02]))
    assert d["status"] == MEASURED and d["n_rows"] == 2000


# ------------------------------------------------------- the next 10 basis points, to second order
def test_the_step_is_scored_to_second_order_not_linearly() -> None:
    r = _panel()
    d = derivatives(r, np.array([0.04, 0.03, 0.02]), names=["a", "b", "c"])
    out = best_next(d, delta=0.001)
    assert out["status"] == MEASURED
    top = out["ranked"][0]
    assert top["gain_per_day"] == pytest.approx(
        0.001 * top["gradient"] + 0.5 * 1e-6 * top["curvature"], rel=1e-9)
    # the curvature term must actually reduce the gain -- the surface is concave
    assert top["gain_per_day"] < top["linear_gain"]


def test_the_step_gain_matches_actually_taking_the_step() -> None:
    """A second-order estimate that does not predict the real move is decoration."""
    r = _panel()
    h = np.array([0.04, 0.03, 0.02])
    d = derivatives(r, h, names=["a", "b", "c"])
    out = best_next(d, delta=0.001)
    g0 = float(np.log(1.0 + r @ h).mean())
    for row in out["ranked"]:
        i = ["a", "b", "c"].index(row["sleeve"])
        h1 = h.copy()
        h1[i] += 0.001
        actual = float(np.log(1.0 + r @ h1).mean()) - g0
        assert row["gain_per_day"] == pytest.approx(actual, rel=5e-3), row["sleeve"]


def test_a_sleeve_with_no_room_is_excluded_not_ranked() -> None:
    """A ranking whose top entry cannot be acted on is not an answer to the question."""
    d = derivatives(_panel(), np.array([0.04, 0.03, 0.02]), names=["a", "b", "c"])
    out = best_next(d, delta=0.001, cap={"a": 0.04, "b": 1.0, "c": 1.0},
                    held={"a": 0.04, "b": 0.03, "c": 0.02})
    assert "a" in out["blocked"]
    assert all(row["sleeve"] != "a" for row in out["ranked"])


def test_a_broken_curvature_refuses_to_rank() -> None:
    d = {"status": MEASURED, "curvature_ok": False, "why": "CONCAVITY VIOLATED",
         "names": ["a"], "gradient": {"a": 1.0}, "hessian_diag": {"a": 1.0}}
    out = best_next(d)
    assert out["status"] == UNMEASURED
    assert "not a bound" in out["why"]


def test_an_unmeasured_derivative_cannot_produce_a_ranking() -> None:
    out = best_next({"status": UNMEASURED, "why": "thin"})
    assert out["status"] == UNMEASURED
