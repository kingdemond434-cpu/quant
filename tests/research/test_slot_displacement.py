"""R0265: displacement may reclaim a jammed slot and may never evict a working one.

The tests that matter here are the refusals. A displacement rule that is merely "useful" is easy;
one that cannot be turned into optional stopping is the point.
"""
from __future__ import annotations

from libs.research.slot_displacement import (
    BLOCKED,
    PROTECTED,
    RECLAIMABLE,
    classify_slot,
    plan_displacement,
)


def _slot(name, *, state="ACCRUING", evidence="ACCRUING", days=10):
    return {"name": name, "state": state, "evidence": evidence, "days": days}


def _healthy(n):
    return [_slot(f"live{i}") for i in range(n)]


# --- classification ---------------------------------------------------------------------------

def test_a_degenerate_verdict_is_reclaimable_even_while_it_reports_accruing():
    """THE case this module exists for, and the one a liveness check gets backwards.

    Measured 2026-08-05: defi_utilisation and walcl_reserve_impulse both carried verdict
    DEGENERATE -- an instrument fault -- while publishing evidence ACCRUING, because their
    artifacts were being rewritten on schedule. Fresh file, empty pipe.
    """
    state, why = classify_slot(_slot("defi_utilisation", state="DEGENERATE",
                                     evidence="ACCRUING", days=1))
    assert state == RECLAIMABLE
    assert "instrument failed" in why


def test_a_clock_with_zero_observations_is_reclaimable():
    state, _ = classify_slot(_slot("cny_premium", state="DEGENERATE",
                                   evidence="NO-EVIDENCE", days=0))
    assert state == RECLAIMABLE


def test_an_accruing_clock_is_protected():
    state, why = classify_slot(_slot("cashcarry", days=40))
    assert state == PROTECTED
    assert "pre-registered terms" in why


def test_unmeasured_is_blocked_not_reclaimed():
    """The deliberate asymmetry. Wrongly evicting destroys forward evidence nothing can re-earn;
    wrongly protecting costs a queue position. Those are not the same price, so the tie does not
    go to aggression here -- it goes to fixing the measurement."""
    for row in (_slot("ghost", evidence="UNMEASURED", days=None),
                _slot("nameless", days=None)):
        state, _ = classify_slot(row)
        assert state == BLOCKED


# --- the two invariants -----------------------------------------------------------------------

def test_a_healthy_incumbent_is_never_displaced_however_good_the_challenger():
    """Optional stopping, refused. If a challenger's arrival could evict a working clock, the desk
    could stop any test that was going badly and restart the story elsewhere."""
    slots = _healthy(12)
    challengers = [{"name": "spectacular", "runway": 0.001}]
    plan = plan_displacement(slots, challengers, cap=12)

    assert plan.displaced == ()
    assert plan.waiting == ("spectacular",)
    assert len(plan.protected) == 12


def test_a_displacement_never_moves_the_holm_cohort():
    """The bar is computed from m. If displacement could change m it would be a route to a looser
    bar, so one out means one in and the count is pinned."""
    slots = [*_healthy(9), *(_slot(f"broken{i}", state="DEGENERATE", days=0)
                            for i in range(3))]
    challengers = [{"name": f"c{i}", "runway": 1.0 + i} for i in range(3)]
    plan = plan_displacement(slots, challengers, cap=12)

    assert len(plan.displaced) == 3
    assert plan.m_before == plan.m_after == 12
    assert plan.count_neutral


def test_it_cannot_displace_more_slots_than_are_broken():
    slots = [*_healthy(11), _slot("broken", state="DEGENERATE", days=0)]
    challengers = [{"name": f"c{i}", "runway": float(i)} for i in range(5)]
    plan = plan_displacement(slots, challengers, cap=12)

    assert len(plan.displaced) == 1
    assert len(plan.waiting) == 4
    assert plan.count_neutral


# --- ordering ---------------------------------------------------------------------------------

def test_the_queue_is_ordered_by_expiry_shortest_runway_first():
    """L1.18a. A long-runway edge loses nothing by waiting; a short-runway one loses everything."""
    slots = [*_healthy(11), _slot("broken", state="DEGENERATE", days=0)]
    challengers = [{"name": "patient", "runway": 400.0},
                   {"name": "expiring", "runway": 1.2},
                   {"name": "middling", "runway": 20.0}]
    plan = plan_displacement(slots, challengers, cap=12)

    assert plan.displaced[0].challenger == "expiring"
    assert plan.waiting == ("middling", "patient")


def test_an_undeclared_runway_sorts_last_so_declaring_nothing_is_not_a_shortcut():
    slots = [*_healthy(11), _slot("broken", state="DEGENERATE", days=0)]
    challengers = [{"name": "silent"}, {"name": "declared", "runway": 99.0}]
    plan = plan_displacement(slots, challengers, cap=12)

    assert plan.displaced[0].challenger == "declared"
    assert plan.waiting == ("silent",)


# --- the graveyard rule -----------------------------------------------------------------------

def test_a_reclaimed_hypothesis_requeues_as_untested_never_refuted():
    """A DEGENERATE clock measured nothing. Filing it as a refutation would retire live research
    ground on a false mechanism of death and corrupt the family survival statistics (L1.17)."""
    slots = [*_healthy(11), _slot("broken", state="DEGENERATE", days=0)]
    plan = plan_displacement(slots, [{"name": "c", "runway": 1.0}], cap=12)

    assert plan.displaced[0].requeue_as == "UNTESTED"
    assert any("never REFUTED" in n for n in plan.notes)


# --- idle slots stay admission's job --------------------------------------------------------

def test_free_seats_are_taken_without_any_eviction():
    slots = _healthy(10)
    challengers = [{"name": f"c{i}", "runway": float(i)} for i in range(2)]
    plan = plan_displacement(slots, challengers, cap=12)

    assert plan.displaced == ()          # taking a free seat is not an eviction
    assert plan.waiting == ()
    assert plan.m_before == 10 and plan.m_after == 12


def test_the_live_2026_08_05_cohort_yields_three_reclaimable_slots():
    """Pins the measurement the row was raised on, so a future refactor that silently protects
    broken instruments again fails here rather than in six months of a stalled queue."""
    live = [
        _slot("defi_utilisation", state="DEGENERATE", evidence="ACCRUING", days=1),
        _slot("stablecoin_supply_momentum", days=13),
        _slot("cny_premium", state="DEGENERATE", evidence="NO-EVIDENCE", days=0),
        _slot("walcl_reserve_impulse", state="DEGENERATE", evidence="ACCRUING", days=1),
        _slot("cashcarry", state="since 2026-06-26", days=40),
        _slot("crossasset", state="since 2026-06-21", days=1),
        _slot("crypto_combined", state="since 2026-07-04", days=33),
        _slot("trend_30d", state="since 2026-07-04", days=33),
        _slot("trend_regime", state="since 2026-07-08", days=28),
        _slot("legacy_shadow", state="since 2026-06-21", days=46),
        _slot("ls_contrarian", state="roster", days=38),
        _slot("oi_divergence", state="roster", days=38),
    ]
    plan = plan_displacement(live, [{"name": "survivor", "runway": 5.0}], cap=12)

    assert len(plan.protected) == 9
    assert len(plan.displaced) == 1                    # one challenger offered, one slot opened
    assert plan.displaced[0].slot == "defi_utilisation"
    assert plan.count_neutral


def test_an_empty_cohort_is_unmeasured_not_wide_open():
    """derive_slots builds from hardcoded names, so it cannot legitimately return zero slots.
    An empty list means a read failure, and handing out `cap` clocks on the strength of a failure
    is the vacuous-pass shape: honest arithmetic over nothing (L1.57)."""
    plan = plan_displacement([], [{"name": "c", "runway": 1.0}], cap=12)

    assert plan.displaced == ()
    assert plan.waiting == ("c",)
    assert plan.m_before == plan.m_after == 0
    assert any("UNMEASURED" in n for n in plan.notes)


# --- the pre-registered kill: the five inert verdicts, wired -----------------------------------

_KILL = "FAILING FORWARD -> kill candidate (Sharpe -0.42 on 61 observations, t=-1.83)"


def _sleeve(name, *, verdict="", state="since 2026-06-01", evidence="ACCRUING", days=61):
    """A SLEEVE row, which is shaped differently from an axis row and that is the whole defect.

    `state` is a BIRTH DATE here, not a verdict -- so a classifier reading only `state` sees a
    healthy-looking clock no matter what its runner concluded.
    """
    return {"name": name, "state": state, "verdict": verdict, "evidence": evidence, "days": days}


def test_A_SLEEVE_THAT_REACHED_ITS_OWN_KILL_IS_RECLAIMABLE():
    """THE WIRE. Five runners have emitted this verdict since the shared gate shipped and nothing
    could act on it, because the string never reached a slot row."""
    state, why = classify_slot(_sleeve("crypto_combined", verdict=_KILL))
    assert state == RECLAIMABLE
    assert "pre-registered" in why


def test_the_same_sleeve_WITHOUT_the_verdict_field_is_protected():
    """The exact pre-fix state, kept as a test so the defect cannot return silently: a healthy
    birth date in `state` and the outcome dropped on the floor."""
    assert classify_slot(_sleeve("crypto_combined"))[0] == PROTECTED


def test_A_KILL_IS_FILED_AS_REFUTED_AND_AN_INSTRUMENT_FAULT_IS_NOT():
    """L1.17 turns on the mechanism of death, and the two errors point opposite ways.

    Filing a refutation as UNTESTED buys the same dead axis again forever; filing an instrument
    fault as REFUTED retires live ground that was never actually measured.
    """
    killed = _sleeve("crypto_combined", verdict=_KILL)
    jammed = _slot("defi_utilisation", state="DEGENERATE", evidence="ACCRUING", days=1)
    slots = [*_healthy(10), killed, jammed]
    plan = plan_displacement(slots, [{"name": "a", "runway": 1.0},
                                     {"name": "b", "runway": 2.0}], cap=12)

    by_slot = {d.slot: d.requeue_as for d in plan.displaced}
    assert by_slot["crypto_combined"] == "REFUTED"
    assert by_slot["defi_utilisation"] == "UNTESTED"


def test_A_KILLED_CLOCK_STILL_NEVER_MOVES_THE_HOLM_BAR():
    """The invariant that must survive this feature. Reclaiming a killed clock frees a SEAT; it
    is not a route to a smaller cohort, because a smaller cohort is a looser bar for everyone
    still running -- the phantom-edge direction."""
    slots = [*_healthy(11), _sleeve("crypto_combined", verdict=_KILL)]
    plan = plan_displacement(slots, [{"name": "challenger", "runway": 1.0}], cap=12)

    assert plan.count_neutral
    assert plan.m_before == plan.m_after


def test_A_HEALTHY_SLEEVE_IS_NEVER_EVICTED_BY_A_KILL_LOOKALIKE():
    """The verdict must be the runner's own, not any string mentioning failure. `forward_verdict`
    also emits ACCUMULATING and WEAK forward, and neither ends a clock."""
    for verdict in ("WEAK forward -> continue shadow, do not deploy (t=2.10 clears 1.96 ...)",
                    "ACCUMULATING (12/40 observations -- too few for the t to be trusted)",
                    "ON TRACK -> eligible for TINY live on human approval; t=2.4 >= 1.96"):
        assert classify_slot(_sleeve("x", verdict=verdict))[0] == PROTECTED, verdict


def test_an_axis_row_still_classifies_from_state_alone():
    """Axis rows put the verdict IN `state` and carry no `verdict` key. Reading the new field
    must not break the half of the cohort that already worked."""
    assert classify_slot({"name": "a", "state": _KILL, "evidence": "ACCRUING",
                          "days": 61})[0] == RECLAIMABLE
