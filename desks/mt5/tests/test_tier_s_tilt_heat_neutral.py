"""THE COMBINED TIER S TILT IS HEAT-NEUTRAL AFTER ITS CLIP (verifier gap A, 2026-09-30).

exchange x capture x freeze were each heat-neutral, but their product was clipped to
[EXCHANGE_LO, TILT_HI] and never renormalised, so a sleeve pinned at 2.0 silently removed heat from
the book (and one pinned at the floor added it). `allocator_tilts.renormalise_clipped` restores the
heat-weighted mean to exactly 1.0 by scaling only the unclipped remainder.
"""
from __future__ import annotations

import pytest

from libs.tiers import allocator_tilts as at


def _mass(tilts: dict[str, float], heat: dict[str, float]) -> float:
    return sum(heat[k] * tilts[k] for k in heat)


def test_clip_at_ceiling_is_refunded_to_the_unclipped_remainder() -> None:
    heat = {"a": 0.02, "b": 0.09, "c": 0.09}
    raw = {"a": 5.0, "b": 1.0, "c": 0.9}      # a's unclipped product lies over the ceiling
    out, meta = at.renormalise_clipped(raw, heat)
    assert _mass(out, heat) == pytest.approx(sum(heat.values()), abs=1e-12)
    assert out["a"] == pytest.approx(at.TILT_HI)
    assert all(at.EXCHANGE_LO <= v <= at.TILT_HI for v in out.values())
    assert meta["heat_shortfall"] == pytest.approx(0.0, abs=1e-9)


def test_rescale_that_crosses_a_bound_pins_it_and_solves_again() -> None:
    heat = {"a": 1.0, "b": 1.0, "c": 1.0}
    raw = {"a": 0.0, "b": 1.8, "c": 0.3}      # zero stays zero; b hits 2.0 on the first scale
    out, meta = at.renormalise_clipped(raw, heat)
    assert out["a"] == 0.0
    assert out["b"] == pytest.approx(2.0)
    assert out["c"] == pytest.approx(1.0)
    assert _mass(out, heat) == pytest.approx(3.0)
    assert meta["n_pinned_at_bound"] == 1


def test_unreachable_target_is_reported_never_hidden() -> None:
    heat = {"a": 1.0, "b": 1.0}
    out, meta = at.renormalise_clipped({"a": 0.0, "b": 1.5}, heat)
    assert out == {"a": 0.0, "b": 2.0}
    assert meta["heat_shortfall"] == pytest.approx(0.0)
    out, meta = at.renormalise_clipped({"a": 0.0, "b": 0.0}, heat)
    assert meta["heat_shortfall"] == pytest.approx(2.0)   # all zeroed: exchange_zero refills


def test_build_combined_tilt_preserves_total_heat_and_pins_the_control() -> None:
    live = {"s1": 0.08, "s2": 0.06, "s3": 0.04, "s4": 0.02, "ctl": 0.03}
    group = {k: k for k in live}
    # the exchange wants s1 far above its live weight (factor clips high), drops s4 entirely
    ex = {"s1": 0.40, "s2": 0.06, "s3": 0.04, "s4": 0.0, "ctl": 0.03}
    cap = {"s1": {"capture": 2.0, "n": 200}, "s2": {"capture": 0.3, "n": 200}}
    rows = at.build(live, group, ex, cap, held_out=lambda k: k == "ctl", freeze=True,
                    oos_n_by_group={"s1": 400, "s2": 0, "s3": 10, "s4": 0})
    treated = {k: v for k, v in live.items() if k != "ctl"}
    tilts = {k: float(rows[k]["tilt"]) for k in live}
    assert rows["ctl"]["tilt"] == 1.0
    assert tilts["s4"] == 0.0
    # the raw product clipped at the ceiling for s1: without renormalisation the mass drifts
    raw_mass = sum(treated[k] * float(rows[k]["tilt_clipped_raw"]) for k in treated)
    assert abs(raw_mass - sum(treated.values())) > 1e-4
    assert _mass(tilts, treated) == pytest.approx(sum(treated.values()), abs=1e-5)
    assert all(at.EXCHANGE_LO <= t <= at.TILT_HI for t in tilts.values())
    # the total heat the tilted book carries is never below the 20% floor it was resolved at
    assert _mass(tilts, live) >= 0.20 - 1e-6
