"""The allocator becomes an ensemble -- and the one clause that keeps it from loosening the proof.

WHAT WAS THROWN AWAY. `allocator_proof.certify` records a score for EVERY contested book -- HRP,
HERC, min-variance, mean-CVaR, three Kellys, the multi-period posterior book, equal-weight,
inverse-vol, risk parity, the incumbent -- and `select` returned exactly one name and discarded
the rest. When two books score 0.00191 and 0.00190, picking one outright is a claim the evidence
does not support: those are the same number.

THE TEMPERATURE IS NOT A NEW KNOB. The softmax scale is `MARGIN_FRAC * |best|` -- the desk's own
noise margin, the fraction of the incumbent's growth rate `allocator_proof` already demands before
it calls one book better than another. Nobody chose a temperature.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.allocator_blend import (  # noqa: E402
    MIN_WEIGHT,
    blend_books,
    blend_weights,
    select_blend,
)
from libs.portfolio.allocator_proof import MARGIN_FRAC  # noqa: E402

M = MARGIN_FRAC


# ------------------------------------------------------------------------------ the weights
def test_two_books_the_same_number_apart_share_the_allocation() -> None:
    """0.00191 and 0.00190 are the same number at this desk's own noise margin."""
    w, why = blend_weights({"hrp": 0.00191, "cvar": 0.00190}, margin_frac=M)
    assert set(w) == {"hrp", "cvar"}
    assert w["hrp"] > w["cvar"] > 0.2, w
    assert "noise margin" in why


def test_a_dominant_book_takes_essentially_everything() -> None:
    """The degenerate case must be the winner, or this changes answers it has no business
    changing."""
    w, _ = blend_weights({"hrp": 0.002, "cvar": 0.0002}, margin_frac=M)
    assert w["hrp"] > 0.99


def test_one_scorable_book_takes_all_of_it() -> None:
    w, why = blend_weights({"hrp": 0.002}, margin_frac=M)
    assert w == {"hrp": 1.0}
    assert "only scorable book" in why


def test_the_weights_are_a_convex_combination() -> None:
    w, _ = blend_weights({"a": 0.002, "b": 0.00199, "c": 0.00198}, margin_frac=M)
    assert all(v >= 0 for v in w.values())
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_a_ruinous_book_is_excluded_not_floored() -> None:
    """"Least ruinous" is not a ranking. `allocator_proof.select` already refuses to treat a
    non-finite score as one, and a blend must not re-admit it at a small weight."""
    w, _ = blend_weights({"hrp": 0.002, "wrecked": float("-inf"), "nan": float("nan")},
                         margin_frac=M)
    assert set(w) == {"hrp"}


def test_no_finite_score_means_no_book_may_size() -> None:
    w, why = blend_weights({"a": float("-inf")}, margin_frac=M)
    assert w == {}
    assert "nothing to size" in why


def test_slivers_are_dropped_and_the_rest_renormalised() -> None:
    """A book at 0.4% of the blend moves no position the broker can express -- the lot floor is
    0.01 -- and only adds names to the artifact."""
    w, _ = blend_weights({"a": 0.002, "b": 0.0019, "tiny": 0.0001}, margin_frac=M)
    assert "tiny" not in w
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v >= MIN_WEIGHT for v in w.values())


def test_a_zero_best_score_degenerates_to_the_argmax_rather_than_a_fake_spread() -> None:
    w, why = blend_weights({"a": 0.0, "b": -0.001}, margin_frac=M)
    assert w == {"a": 1.0}
    assert "no measurable scale" in why


# -------------------------------------------------------------------------------- the mixture
def test_a_sleeve_a_book_does_not_hold_counts_as_zero_not_as_absent() -> None:
    """Averaging only over the books that HOLD a sleeve is how an ensemble quietly becomes its
    most concentrated member: a sleeve held by one book at 4% would appear at 4% however little
    weight that book carries."""
    books = {"a": {"x": 0.04}, "b": {"y": 0.04}}
    mixed = blend_books(books, {"a": 0.25, "b": 0.75})
    assert mixed["x"] == pytest.approx(0.01)
    assert mixed["y"] == pytest.approx(0.03)


def test_total_heat_is_preserved_exactly() -> None:
    """A convex mixture of books that each sum to H sums to H, so the blend cannot smuggle
    exposure past heat_policy.resolve."""
    books = {"a": {"x": 0.06, "y": 0.04}, "b": {"x": 0.02, "z": 0.08}}
    mixed = blend_books(books, {"a": 0.4, "b": 0.6})
    assert sum(mixed.values()) == pytest.approx(0.10)


def test_a_mixture_of_non_ruinous_books_is_non_ruinous() -> None:
    """Ruin in a world is 1 + h'r <= 0, which is LINEAR in h -- so if every member survives a
    world, so does every convex combination, exactly rather than approximately. This is the
    property that makes blending safe at all, so it is checked rather than assumed."""
    import numpy as np
    rng = np.random.default_rng(0)
    r = rng.normal(0.0, 0.4, size=(500, 3))          # returns for three sleeves in 500 worlds
    names = ["x", "y", "z"]
    a = {"x": 0.10, "y": 0.05, "z": 0.0}
    b = {"x": 0.0, "y": 0.04, "z": 0.11}
    ha = np.array([a.get(n, 0.0) for n in names])
    hb = np.array([b.get(n, 0.0) for n in names])
    assert np.all(1.0 + r @ ha > 0) and np.all(1.0 + r @ hb > 0), "fixture must be non-ruinous"
    for wa in (0.0, 0.25, 0.5, 0.75, 1.0):
        mixed = blend_books({"a": a, "b": b}, {"a": wa, "b": 1.0 - wa})
        hm = np.array([mixed.get(n, 0.0) for n in names])
        assert np.all(1.0 + r @ hm > 0), wa


# ---------------------------------------------------------- the certification law is not loosened
def _cert(passed: bool, best: str, scores: dict[str, float]) -> dict:
    return {
        "passed": False, "best_baseline": best,
        "books": {"dynamic": {"x": 0.10}, "hrp": {"y": 0.10}, "cvar": {"z": 0.10}},
        "by_state": {"S": {"passed": passed, "best": best, "n_worlds": 99, "scores": scores,
                           "why": "state verdict"}},
        "min_state_worlds": 24,
    }


def test_a_book_that_LOST_its_state_is_excluded_not_down_weighted() -> None:
    """THE CLAUSE THAT MATTERS MOST. Blending the dynamic allocator back in at 15% after the proof
    refused it in this state would grant, quietly and fractionally, exactly the authority the
    proof denied -- the certification law loosened by arithmetic."""
    cert = _cert(passed=False, best="hrp", scores={"dynamic": 0.00195, "hrp": 0.002,
                                                   "cvar": 0.00198})
    out = select_blend(cert, "S", margin_frac=M)
    assert out["status"] == "BLENDED"
    assert "dynamic" not in out["weights"], out["weights"]
    assert set(out["weights"]) == {"hrp", "cvar"}
    assert "EXCLUDED from the mixture" in out["why"]


def test_dynamic_competes_on_its_score_when_it_WON_the_state() -> None:
    cert = _cert(passed=True, best="", scores={"dynamic": 0.002, "hrp": 0.00198})
    out = select_blend(cert, "S", margin_frac=M)
    assert "dynamic" in out["weights"]
    assert "competes in the mixture" in out["why"]


def test_no_certificate_is_a_refusal_and_never_an_unblended_fallback() -> None:
    for cert in (None, {}):
        out = select_blend(cert, "S", margin_frac=M)
        assert out["status"] == "REFUSED"
        assert out["book"] == {}


def test_a_state_the_proof_refused_outright_yields_no_book() -> None:
    """`select` returns "" when every book was wiped out there. The blend must not resurrect one."""
    cert = _cert(passed=False, best="hrp", scores={"hrp": float("-inf")})
    out = select_blend(cert, "S", margin_frac=M)
    assert out["status"] == "REFUSED" and out["book"] == {}


def test_a_weight_on_a_book_with_no_recorded_composition_is_dropped_and_named() -> None:
    """Silently rescaling would hand that weight to the others without saying so."""
    cert = _cert(passed=False, best="hrp", scores={"hrp": 0.002, "ghost": 0.00199})
    cert["books"].pop("cvar")
    cert["scores"] = {}
    out = select_blend(cert, "S", margin_frac=M)
    assert "ghost" not in out.get("weights", {})
    assert out["status"] in ("BLENDED", "SINGLE")


def test_a_single_winner_is_indistinguishable_from_the_old_behaviour() -> None:
    cert = _cert(passed=False, best="hrp", scores={"hrp": 0.002, "cvar": 0.0001})
    out = select_blend(cert, "S", margin_frac=M)
    assert out["status"] == "SINGLE"
    assert out["source"] == "hrp"
    assert out["book"] == {"y": 0.10}


def test_the_blended_book_holds_the_same_heat_as_its_members() -> None:
    cert = _cert(passed=False, best="hrp", scores={"hrp": 0.002, "cvar": 0.00199})
    out = select_blend(cert, "S", margin_frac=M)
    assert out["status"] == "BLENDED"
    assert out["total_heat"] == pytest.approx(0.10), out


# ------------------------------------------------------------------------------ the gateway wire
def test_the_gateway_falls_back_to_select_when_the_ensemble_breaks() -> None:
    """A broken ensemble must never cost the desk the book `select` already chose."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert "ensemble unavailable" in src
    assert "from libs.portfolio.allocator_blend import select_blend" in src
    assert 'mix.get("status") == "BLENDED"' in src
