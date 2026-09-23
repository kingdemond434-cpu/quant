"""SIZING ON THE LOWER BOUND, AND STRESSING k_eff (external review, 2026-09-06).

The one property that must hold absolutely: BOTH adjustments only ever reduce size. A confidence
correction that could ever justify a LARGER position than the point estimate would be a loosening
wearing the language of rigour, and this desk does not loosen.

The second: an edge whose lower bound does not exclude zero sizes at zero. The measured hunt5
edge of +0.159R over 65 observations is exactly that case, which is the finding.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_edgeconf", _ROOT / "desks" / "mt5" / "research" / "edge_confidence.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ec():
    return _load()


def test_the_correction_never_increases_size(ec) -> None:
    """THE ABSOLUTE PROPERTY. A rigour-flavoured loosening is still a loosening."""
    for n in (20, 50, 100, 400, 5000):
        for mean in (0.05, 0.159, 0.5, 2.0):
            out = ec.lower_bound(ec.Edge("e", mean_r=mean, sd_r=1.1, n=n))
            assert out["size_on"] <= mean + 1e-12, (
                f"n={n} mean={mean} sized on {out['size_on']} > the point estimate -- the "
                "confidence correction produced a LARGER position, which is a loosening")


def test_more_observations_shrink_the_haircut(ec) -> None:
    """The sample does the work: 400 observations barely move, 25 get cut hard."""
    thin = ec.lower_bound(ec.Edge("thin", 0.159, 1.1, 25))
    thick = ec.lower_bound(ec.Edge("thick", 0.159, 1.1, 1600))
    assert thick["size_on"] > thin["size_on"]
    assert thick["haircut"] < thin["haircut"]


def test_the_desks_own_measured_edge_does_not_exclude_zero(ec) -> None:
    """THE FINDING. +0.159R over 65 observations has a 95% lower bound at or below zero, so
    nothing may be sized on it -- 65 observations do not distinguish that edge from no edge."""
    out = ec.lower_bound(ec.Edge("hunt5", mean_r=0.159, sd_r=1.10, n=65))
    assert out["size_on"] == 0.0
    assert out["status"] == "NO_EDGE_AT_BOUND"
    assert "does not exclude zero" in out["why"]


def test_a_thin_sample_is_refused_rather_than_floored(ec) -> None:
    """Below the minimum the lower bound is almost always negative, so any number would be an
    artefact of the floor rather than a measurement."""
    out = ec.lower_bound(ec.Edge("thin", 0.3, 1.2, 5))
    assert out["status"] == "INSUFFICIENT" and out["size_on"] == 0.0
    assert "artefact of the floor" in out["why"]


def test_a_wider_dispersion_cuts_harder_at_equal_mean(ec) -> None:
    calm = ec.lower_bound(ec.Edge("calm", 0.159, 0.4, 100))
    wild = ec.lower_bound(ec.Edge("wild", 0.159, 2.0, 100))
    assert calm["size_on"] > wild["size_on"]


def test_the_edge_multiplier_matches_the_correlation_bound(ec) -> None:
    """Both halves of the sizing input are corrected at the same confidence level, so neither is
    silently more forgiving than the other."""
    assert abs(ec.EDGE_Z - 1.645) < 1e-9


# --------------------------------------------------------------------------- k_eff stress
def test_stress_never_raises_effective_breadth(ec) -> None:
    """The binding k_eff is the WORSE of measured and stressed, always."""
    for n in (2, 3, 5, 12):
        for rho in (0.0, 0.1, 0.5, 0.9):
            b = ec.stressed_breadth(n, rho)
            assert b["k_eff_binding"] <= b["k_eff_measured"] + 1e-12, (
                f"n={n} rho={rho}: stress RAISED effective breadth, which would raise heat")


def test_quiet_correlations_give_up_real_heat(ec) -> None:
    """The cost is deliberate: heat sized on quiet-period independence is heat sized for the
    period in which it does not matter."""
    b = ec.stressed_breadth(5, 0.10)
    assert b["k_eff_measured"] > 3.0
    assert b["k_eff_stressed"] < 1.5
    assert b["given_up"] > 0.3


def test_already_correlated_sleeves_give_up_nothing(ec) -> None:
    """A desk already measuring crisis-level correlation is not penalised twice."""
    b = ec.stressed_breadth(5, 0.85)
    assert b["given_up"] == 0.0
    assert b["k_eff_binding"] == b["k_eff_measured"]


def test_heat_scales_with_the_root_of_the_binding_breadth(ec) -> None:
    import math
    b = ec.stressed_breadth(4, 0.2)
    # Both fields are rounded to 4dp by the module, so sqrt(rounded) and rounded(sqrt) differ
    # in the fifth place. The property under test is the RELATION, not the rounding.
    assert abs(b["heat_scale_binding"] - math.sqrt(b["k_eff_binding"])) < 1e-3


def test_a_single_sleeve_has_one_effective_bet(ec) -> None:
    for rho in (0.0, 0.5, 0.99):
        assert abs(ec.k_eff(1, rho) - 1.0) < 1e-9
