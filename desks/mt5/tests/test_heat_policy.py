"""The heat law: one fixed envelope, growth chooses the exposure inside it.

The numbers in `gateway_config_fallback` are the principal's decision (20% target, 30% hard bar).
These tests fence the LOGIC around them -- that the mandate can only ever raise exposure to the
target, that the ceiling can only ever lower it, that only the integrity layer goes below, and
that the certification is measured rather than asserted.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.heat_policy import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    catastrophe_override,
    certify,
    per_sleeve_bounds,
    resolve,
)

#: A curve shaped like the measured one: rising to a peak above the target, then falling.
GOOD = {h: math.log(1 + a / 100) / 252
        for h, a in [(0.06, 169.8), (0.10, 179.9), (0.15, 184.5), (0.20, 184.2),
                     (0.25, 176.4), (0.30, 162.9)]}
#: A curve whose peak is far below the target: full utilisation is no longer growth-maximising.
BAD = {0.05: 0.0040, 0.10: 0.0050, 0.15: 0.0030, 0.20: 0.0010, 0.30: -0.0020}


def test_the_numbers_are_the_stated_policy() -> None:
    assert HEAT_TARGET == 0.20
    assert HEAT_HARD_CEILING == 0.30
    assert HEAT_TARGET < HEAT_HARD_CEILING, "the target must sit inside the envelope"


def test_mandate_raises_a_timid_optimum_to_the_target() -> None:
    v = resolve(0.0757, curve=GOOD)
    assert v.total_heat == pytest.approx(HEAT_TARGET)
    assert v.binding == "mandate"


def test_growth_above_the_target_is_allowed_up_to_the_ceiling() -> None:
    """"if growth optimum says its beyond 20 ... it can exceed to that, keep it under 30."""
    v = resolve(0.24, curve=GOOD)
    assert v.total_heat == pytest.approx(0.24)
    assert v.binding == "growth"


def test_the_hard_bar_is_hard() -> None:
    v = resolve(0.55, curve=GOOD)
    assert v.total_heat == pytest.approx(HEAT_HARD_CEILING)
    assert v.binding == "ceiling"
    assert any("HARD CEILING" in r for r in v.reasons)


def test_only_the_integrity_layer_goes_below_target() -> None:
    """A thin opportunity set is not a reason to de-risk; not knowing the exposure is."""
    thin = resolve(0.001, curve=GOOD)
    assert thin.total_heat == pytest.approx(HEAT_TARGET), "the mandate held"
    broken = resolve(0.24, curve=GOOD, prices_fresh=False)
    assert broken.total_heat == 0.0
    assert broken.binding == "catastrophe"
    assert any("stale" in r for r in broken.reasons)


def test_every_integrity_signal_can_stop_the_book_alone() -> None:
    for kw in ("broker_ok", "prices_fresh", "exposure_reconciled", "margin_ok", "allocator_ok"):
        heat, why = catastrophe_override(**{kw: False})
        assert heat == 0.0 and why, f"{kw} did not stop the book"
    assert catastrophe_override() == (None, ())


def test_mandate_off_leaves_the_optimum_alone() -> None:
    v = resolve(0.0757, curve=GOOD, mandate=False)
    assert v.total_heat == pytest.approx(0.0757)
    assert v.binding == "growth"


# ------------------------------------------------------------------------------- certification

def test_target_on_the_flat_top_certifies() -> None:
    ok, why = certify(GOOD, HEAT_TARGET)
    assert ok and "flat top" in why


def test_target_past_the_peak_does_not_certify_and_says_what_it_costs() -> None:
    ok, why = certify(BAD, HEAT_TARGET)
    assert not ok
    assert "NOT CERTIFIED" in why and "log/yr" in why


def test_a_curve_too_short_to_read_is_uncertified_not_certified() -> None:
    """Absence is never permission: two points cannot locate a peak (L1.28a)."""
    ok, why = certify({0.1: 0.004, 0.2: 0.005}, HEAT_TARGET)
    assert not ok and "UNCERTIFIED" in why


def test_a_curve_that_is_negative_everywhere_certifies_nothing() -> None:
    ok, why = certify({0.05: -0.001, 0.10: -0.002, 0.20: -0.004}, HEAT_TARGET)
    assert not ok and "No exposure" in why


def test_resolve_carries_the_certification_verdict() -> None:
    assert resolve(0.10, curve=GOOD).certified is True
    assert resolve(0.10, curve=BAD).certified is False


# ------------------------------------------------------------------------------ per-sleeve bounds

def test_a_shallower_drawdown_earns_a_larger_bound_but_never_the_whole_book() -> None:
    b = per_sleeve_bounds({"deep": 40.0, "shallow": 8.0}, HEAT_TARGET)
    assert b["shallow"] > b["deep"], "the drawdown derivation is not being applied"
    assert max(b.values()) <= 0.25 * HEAT_TARGET + 1e-12, (
        "the concentration leg is what stops a forced budget hiding in one quiet sleeve")


def test_an_unmeasured_drawdown_is_bounded_like_the_worst_measured_one() -> None:
    """A sleeve nobody has measured must not be the cheapest thing in the book (L1.28a)."""
    b = per_sleeve_bounds({"known": 33.7, "unmeasured": 0.0}, HEAT_TARGET)
    assert b["unmeasured"] == pytest.approx(b["known"])


def test_bounds_scale_with_the_book_they_are_bounding() -> None:
    small = per_sleeve_bounds({"a": 5.0}, 0.05)
    big = per_sleeve_bounds({"a": 5.0}, 0.30)
    assert small["a"] < big["a"]


# ------------------------------------------------------------------------ mechanism concentration

def test_a_dominant_mechanism_is_capped_and_the_rest_untouched() -> None:
    """MEASURED 2026-09-02: the solved book put 97% of its heat into `overnight_gap_decay` across
    seven exotic crosses. Discovery did not cause it -- that family is 232 of 23,465 docket cells
    against 20,341 from the family-free searcher -- the allocator did, and the redundancy term
    could not see it because those sleeves are weakly correlated day to day while sharing a
    mechanism and a 01:00 fill hour."""
    from research.heat_policy import MAX_FAMILY_HEAT_SHARE, enforce_family_cap

    heat = {"a1": 0.10, "a2": 0.10, "a3": 0.09, "b1": 0.01}
    fam = {"a1": "gap", "a2": "gap", "a3": "gap", "b1": "session"}
    bounds = enforce_family_cap(heat, fam, 0.30)
    held = sum(min(heat[k], bounds[k]) for k in heat if fam[k] == "gap")
    assert held == pytest.approx(MAX_FAMILY_HEAT_SHARE * 0.30, rel=1e-6)
    assert bounds["b1"] == float("inf"), "a family inside the cap must not be bounded at all"


def test_the_cap_preserves_the_optimiser_s_ordering_inside_the_mechanism() -> None:
    """Which sleeve the optimiser preferred within a family is its own answer; the cap decides
    only how much that family as a whole may hold."""
    from research.heat_policy import enforce_family_cap

    b = enforce_family_cap({"big": 0.20, "small": 0.05}, {"big": "gap", "small": "gap"}, 0.25)
    assert b["big"] / b["small"] == pytest.approx(0.20 / 0.05, rel=1e-6)


def test_a_book_already_diversified_is_never_touched() -> None:
    from research.heat_policy import enforce_family_cap

    heat = {"a": 0.05, "b": 0.05, "c": 0.05}
    fam = {"a": "one", "b": "two", "c": "three"}
    assert all(v == float("inf") for v in enforce_family_cap(heat, fam, 0.15).values())


def test_an_empty_or_zero_book_yields_no_bounds() -> None:
    from research.heat_policy import enforce_family_cap

    assert enforce_family_cap({}, {}, 0.0) == {}
    assert enforce_family_cap({"a": 0.0}, {"a": "x"}, 0.0) == {}


def test_the_floor_is_flat_and_the_whole_band_is_available() -> None:
    """"minimum cover 20% heat cap 24/7 deployed minimum ... if it allows up to 30 we let it do
    30" -- the principal, 2026-09-02. Readiness is reported, not gating."""
    for r in (0.0, 0.02, 1.0):
        assert resolve(0.005, curve=GOOD, readiness=r).total_heat == pytest.approx(HEAT_TARGET)
        assert resolve(0.24, curve=GOOD, readiness=r).total_heat == pytest.approx(0.24)
        assert resolve(0.45, curve=GOOD, readiness=r).total_heat == pytest.approx(
            HEAT_HARD_CEILING)


# ------------------------------------------------------------------- the four heats, asymmetric

def test_the_floor_counts_nominal_heat_and_the_ceiling_counts_effective_heat() -> None:
    """THE ASYMMETRY IS THE LAW, not an implementation detail (2026-09-05).

    The floor is a standing instruction about CAPITAL AT WORK -- measuring it in effective terms
    would let the desk claim it had deployed 20% while holding 45% nominal. The ceiling is
    catastrophe containment, and a catastrophe does not count tickets: four sleeves that are one
    hidden USD factor lose like one bet at four times the size. So the room ABOVE the floor is
    bought with independent risk and the floor itself never is.
    """
    from research.heat_policy import effective_ceiling

    one_bet = {"nominal": 0.28, "covariance": 0.26, "factor": 0.27, "tail": 0.25}
    cap, why, _detail = effective_ceiling(one_bet)
    assert cap == pytest.approx(HEAT_TARGET), why
    assert cap >= HEAT_TARGET, "the ceiling may take the upside; it may never take the floor"

    v = resolve(0.28, curve=GOOD, effective_heat=one_bet)
    assert v.binding == "effective_ceiling" and v.total_heat == pytest.approx(HEAT_TARGET)
    assert v.effective_ceiling == pytest.approx(HEAT_TARGET)
    assert v.effective["nominal"] == pytest.approx(0.28)
    # The nominal reading was never the binding one, and the artifact can prove it.
    assert v.effective["effective"] > 0.9 * v.effective["nominal"]

    spread = {"nominal": 0.28, "covariance": 0.09, "factor": 0.10, "tail": 0.08}
    assert resolve(0.28, curve=GOOD, effective_heat=spread).total_heat == pytest.approx(0.28)


def test_the_state_conditioned_target_never_leaves_the_band() -> None:
    """H*_t = argmax E[log W | X_t] over [floor, ceiling] -- learned, and still fenced."""
    from research.heat_policy import StateCurve

    for peak in (0.01, 0.20, 0.27, 0.55):
        curves = {"s": StateCurve("s", {h: -((h - peak) ** 2) for h in
                                        (0.05, 0.15, 0.20, 0.25, 0.30, 0.40)}, 64)}
        v = resolve(0.205, curve=GOOD, state="s", curves=curves)
        assert HEAT_TARGET - 1e-12 <= v.total_heat <= HEAT_HARD_CEILING + 1e-12, peak
