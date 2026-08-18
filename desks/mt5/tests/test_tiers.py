"""220.1: the objective is validated survivors per compute-hour, not backtests
per second. A faster engine producing the same survivors is worth nothing; one
producing WRONG survivors is worth less than nothing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.tiers import (  # noqa: E402
    ACCELERATION_THRESHOLD, MIN_RANK_AGREEMENT, Equivalence, Funnel, Profile,
    check_equivalence, rank_agreement)


def _profile(shares: dict, unit: float = 0.002) -> Profile:
    p = Profile()
    for name, n in shares.items():
        for _ in range(n):
            with p.stage(name):
                time.sleep(unit)
    return p


# ------------------------------------------------------- profile before CUDA

def test_no_profile_means_no_acceleration():
    """220.5 forbids accelerating an unmeasured bottleneck."""
    v = Profile().verdict()
    assert not v["accelerate"] and "unmeasured" in v["why"]


def test_a_small_bottleneck_is_not_worth_accelerating():
    """An accelerator on a stage that is a fifth of wall time buys a fifth, and
    costs permanent maintenance on a hot path."""
    # Four roughly equal stages: the largest is ~25%, well under the 40% bar.
    p = _profile({"backtest": 1, "fetch": 1, "fit": 1, "score": 1})
    v = p.verdict()
    assert v["share"] < ACCELERATION_THRESHOLD
    assert not v["accelerate"]
    assert "INFINITELY" in v["why"]


def test_a_dominant_stage_justifies_acceleration_by_measurement():
    p = _profile({"backtest": 12, "fetch": 1})
    v = p.verdict()
    assert v["accelerate"] and v["stage"] == "backtest"
    assert "BY MEASUREMENT" in v["why"]


def test_the_ladder_is_cheapest_engineering_first():
    """Skipping to CUDA because it is interesting is the failure the ladder
    exists to stop."""
    v = _profile({"backtest": 12, "x": 1}).verdict()
    assert v["ladder"] == ["numba", "c++", "rust", "gpu", "cuda"]
    assert "STOP at the first" in v["stop_rule"]


def test_the_ladder_says_to_re_profile_after_each_rung():
    v = _profile({"backtest": 12, "x": 1}).verdict()
    assert "re-run after" in v["stop_rule"]


def test_shares_sum_to_one():
    p = _profile({"a": 3, "b": 3})
    assert abs(sum(p.share(n) for n in p.stages) - 1.0) < 1e-9


def test_the_bottleneck_is_the_largest_stage_not_the_most_called():
    p = Profile()
    for _ in range(50):
        with p.stage("many_cheap"):
            pass
    with p.stage("one_expensive"):
        time.sleep(0.02)
    assert p.bottleneck().name == "one_expensive"


def test_the_render_states_the_verdict_either_way():
    assert "DO NOT ACCELERATE" in _profile({"a": 1, "b": 1, "c": 1, "d": 1}).render()
    assert "ACCELERATE: backtest" in _profile({"backtest": 12, "b": 1}).render()


# ------------------------------- ordering matters more than precision

def test_a_less_precise_tier_that_preserves_ORDER_passes():
    """A cheap tier is permitted to be less precise."""
    truth = [1.0, 2.0, 3.0, 4.0]
    cheap = [1.05, 2.04, 3.06, 4.05]
    e = check_equivalence(truth, cheap, tolerance=0.10)
    assert e.passes and e.rank_agreement == 1.0


def test_an_ordering_inversion_FAILS_even_when_every_error_is_tiny():
    """THE CHECK CORRELATION CANNOT MAKE. Two engines agreeing to four decimals
    can still invert the top two, and inverting the top two is the only
    comparison the funnel actually performs."""
    truth = [1.0000, 1.0001, 0.5]
    cheap = [1.0001, 1.0000, 0.5]
    e = check_equivalence(truth, cheap, tolerance=1.0)
    assert not e.passes
    assert e.max_abs_error < 1e-3
    assert "eliminated before anything expensive" in e.why


def test_a_failing_tier_is_told_to_be_disabled_not_tuned():
    e = check_equivalence([1.0, 1.1], [1.1, 1.0], tolerance=1.0)
    assert "DISABLE this tier" in e.why and "do not tune the tolerance" in e.why


def test_ties_in_the_truth_engine_are_not_inversions():
    """Inverting two candidates the reference cannot separate is not an error of
    the cheap tier."""
    a, inv = rank_agreement([1.0, 1.0, 2.0], [1.0, 0.9, 2.0])
    assert a == 1.0 and inv == []


def test_a_precision_failure_is_named_as_one_and_not_as_correctness():
    truth = [1.0, 2.0, 3.0]
    cheap = [1.5, 2.5, 3.5]
    e = check_equivalence(truth, cheap, tolerance=0.1)
    assert not e.passes
    assert "precision failure rather than a correctness one" in e.why
    assert "moving it to fit the result" in e.why


def test_an_empty_corpus_is_an_unvalidated_tier():
    e = check_equivalence([], [], tolerance=0.1)
    assert not e.passes and "may not screen" in e.why


def test_a_non_finite_cheap_result_fails():
    e = check_equivalence([1.0, 2.0], [float("nan"), 2.0], tolerance=1.0)
    assert not e.passes


def test_the_inversions_are_reported_with_both_scores():
    e = check_equivalence([1.0, 1.1], [1.1, 1.0], tolerance=1.0)
    assert e.inversions and len(e.inversions[0]) == 6
    assert "truth ranks" in e.render()


def test_perfect_agreement_reports_cleanly():
    e = check_equivalence([3.0, 2.0, 1.0], [3.0, 2.0, 1.0], tolerance=1e-9)
    assert e.passes and "ordering preserved" in e.why


# ------------------------------------------------------------------ the funnel

def test_the_expensive_stage_sees_a_small_number():
    """220.3. An expensive simulator is never run on a hypothesis a cheap one
    can kill."""
    f = Funnel([("tier A cheap", 100_000, 1e-6),
                ("tier B research", 5_000, 1e-3),
                ("tier C truth", 100, 1.0)])
    p = f.plan(10_000_000)
    truth = next(r for r in p["rows"] if r["stage"] == "tier C truth")
    assert truth["evaluated"] == 5_000
    assert p["final"] == 100


def test_a_funnel_that_does_not_narrow_is_reported_as_expensive():
    f = Funnel([("A", 10_000_000, 1e-6), ("C truth", 10_000_000, 1.0)])
    p = f.plan(10_000_000)
    assert p["total_cost"] > 1e6


def test_the_funnel_render_shows_the_shape():
    f = Funnel([("A", 1000, 1e-6), ("C", 10, 1.0)])
    txt = f.render(1_000_000)
    assert "evaluated" in txt and "forward candidate" in txt


# ------------------------------------------------- what this module refuses to be

def test_no_gpu_engine_is_shipped_ahead_of_a_profile():
    """Writing a CUDA kernel before the profile would violate the very section
    it claims to implement, and an accelerator is permanent maintenance on a hot
    path."""
    src = (_DESK / "mt5desk" / "tiers.py").read_text(encoding="utf-8")
    for banned in ("import cupy", "import numba", "import torch", "cuda.jit"):
        assert banned not in src
    assert "profile first" in src.lower()
