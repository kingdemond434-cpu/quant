"""THE 20% TARGET HOLDS THE BOOK UP WHEN IT IS FREE, AND YIELDS WHEN IT COSTS GROWTH (2026-10-06).

This file pinned a FLAT 24/7 floor from 2026-09-02 / 09-05 ("keep minimum 24 7 deployed heat
floor 20"). The principal superseded that on 2026-10-06 -- "Cash is an allocation. If nothing has
positive robust marginal value after costs and uncertainty, the growth-optimal answer can be
little or no exposure" (10:48Z), "allow exposure to rise or fall when justified" (12:35Z) -- and
approved replacing the floor in the allocator thread at 15:42Z.

WHAT IS STILL FENCED, and why the file keeps its name. The target is not negotiable by a
SCORING FUNCTION: readiness, drift sentinels, novelty flags, concentration penalties and
correlation estimates still cannot pull the book below 20% while the measured growth curve says
20% is free (at or below its peak, or on its flat top within CERTIFY_TOLERANCE). The only thing
that releases it is that curve itself -- the robust E[log W] measurement Rule 1 asks for.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import heat_policy as hp  # noqa: E402

#: A curve on which 20% is free: growth still rising at the target, peak at 25%.
FREE = {0.05: 0.0005, 0.10: 0.0010, 0.20: 0.0018, 0.25: 0.0020, 0.30: 0.0015}
#: A curve on which 20% gives up real growth: the peak is at 10%.
COSTLY = {0.05: 0.0015, 0.10: 0.0020, 0.20: 0.0010, 0.30: -0.0010}
#: Growth negative at every heat measured.
NEGATIVE = {0.05: -0.0001, 0.10: -0.0004, 0.20: -0.0010, 0.30: -0.0030}


def _resolve(free_optimum: float = 0.03, **kw):
    kw.setdefault("mandate", True)
    return hp.resolve(free_optimum, **kw)


def test_a_free_target_holds_the_book_up() -> None:
    v = _resolve(curve=FREE, readiness=0.0)
    assert v.floor == pytest.approx(hp.HEAT_TARGET)
    assert v.total_heat >= hp.HEAT_TARGET - 1e-9
    assert v.binding == "mandate"


@pytest.mark.parametrize("readiness", [0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0])
def test_readiness_never_moves_the_target(readiness: float) -> None:
    """Readiness is REPORTED; it is never an input to the floor (the defect once removed)."""
    v = _resolve(curve=FREE, readiness=readiness)
    assert v.floor == pytest.approx(hp.HEAT_TARGET)
    assert v.total_heat >= hp.HEAT_TARGET - 1e-9


def test_a_target_that_costs_growth_yields_to_the_optimum() -> None:
    v = _resolve(0.10, curve=COSTLY, readiness=1.0)
    assert v.floor == 0.0
    assert v.total_heat == pytest.approx(0.10)
    assert v.binding == "growth"


def test_negative_growth_everywhere_resolves_to_cash() -> None:
    v = _resolve(0.0, curve=NEGATIVE, readiness=1.0)
    assert v.total_heat == 0.0
    assert v.binding == "cash"


def test_an_unmeasured_curve_keeps_the_target() -> None:
    """Only a MEASUREMENT may release the target (audit ruling on PR #261): no curve, the 20%
    holds exactly as it did before the two-sided change."""
    for curve in ({}, None, {0.2: 0.001, 0.3: 0.002}):
        v = _resolve(0.03, curve=curve, readiness=1.0)
        assert v.floor == pytest.approx(hp.HEAT_TARGET)
        assert v.total_heat >= hp.HEAT_TARGET - 1e-9


def test_concentration_never_cuts_below_a_free_target() -> None:
    for eff in (0.0, 0.01, 0.05, 0.5, 1.0):
        v = _resolve(0.03, curve={0.2: 0.01, 0.3: 0.02, 0.45: 0.03}, readiness=1.0,
                     effective_heat=eff)
        assert v.total_heat >= hp.HEAT_TARGET - 1e-9, (eff, v.total_heat)


def test_a_state_curve_moves_heat_both_ways_above_a_free_target() -> None:
    glob = {0.20: 0.0010, 0.22: 0.0012, 0.24: 0.0014, 0.26: 0.0016, 0.28: 0.0018, 0.30: 0.0017}
    calm = {0.20: 0.0010, 0.22: 0.0015, 0.24: 0.0012, 0.26: 0.0008, 0.28: 0.0005, 0.30: 0.0001}
    v = _resolve(0.28, curve=glob, state="calm",
                 curves={"calm": hp.StateCurve("calm", calm, 64)})
    assert v.total_heat == pytest.approx(0.22)
    assert v.total_heat >= v.floor
    up = _resolve(0.24, curve=glob, state="up", curves={"up": hp.StateCurve(
        "up", {0.20: 0.0, 0.22: 0.0, 0.24: 0.0, 0.26: 0.0, 0.28: 0.0, 0.30: 0.002}, 64)})
    assert up.total_heat == pytest.approx(0.30) and up.binding == "state_growth"


def test_a_thin_state_bucket_cannot_cut() -> None:
    thin = {"stress": hp.StateCurve("stress", {0.05: 0.01, 0.2: -0.02, 0.3: -0.03}, 4)}
    v = _resolve(0.25, curve=FREE, state="stress", curves=thin)
    assert v.total_heat >= 0.25 - 1e-9


def test_the_survival_bar_still_clips() -> None:
    v = _resolve(0.30, curve=FREE, survival_ceiling=0.22, readiness=1.0)
    assert v.total_heat <= 0.22 + 1e-9
    assert v.binding == "survival_ceiling"


def test_room_above_the_target_is_still_earned_not_granted() -> None:
    v = _resolve(0.30, curve={0.2: 0.01, 0.3: 0.005, 0.45: -0.01}, readiness=1.0)
    assert v.total_heat <= hp.HEAT_HARD_CEILING + 1e-9
    assert v.total_heat < 0.45


def test_mandate_off_is_pure_growth() -> None:
    off = hp.resolve(0.03, curve=FREE, readiness=1.0, mandate=False)
    assert off.floor == 0.0 and off.total_heat == pytest.approx(0.03)
