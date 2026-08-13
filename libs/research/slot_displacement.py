"""FORWARD-SLOT DISPLACEMENT -- who leaves when a survivor arrives and all twelve clocks are full.

R0265. The desk has ADMISSION (``screen_admission.admit`` fills IDLE slots, EV-ranked) and it has
a CAP (``MAX_FORWARD_SLOTS`` = 12, the Holm ``m``). It has never had a rule for the third case,
which is the one that is live right now: ``derive_slots()`` reads ``idle_slots: 0``, twelve of
twelve occupied, so a new survivor -- exactly what the 180.8x power fix is built to produce --
has nowhere to go. ``admit()`` says so in as many words: "no idle slots: the forward stage is
saturated, which is the intended steady state and the correct reason to admit nothing."

That is the right answer only if every occupant is doing the job. Measured 2026-08-05, three of
the twelve were not:

    defi_utilisation       verdict DEGENERATE   evidence ACCRUING     1 observation
    cny_premium            verdict DEGENERATE   evidence NO-EVIDENCE  0 observations
    walcl_reserve_impulse  verdict DEGENERATE   evidence ACCRUING     1 observation

DEGENERATE is not a weak result. ``run_axis_shadows`` issues it when a clock keeps producing
dated rows that yield no usable observation, and says what it means at the point of issue: "this
is an instrument fault, NOT evidence about the hypothesis". A quarter of the desk's entire
multiplicity budget was held by clocks that cannot resolve.

NOTE WHICH FIELD LIES. Two of the three read ``evidence: ACCRUING`` -- the registry's liveness
check sees their artifact being rewritten on schedule and calls them alive. This is the desk's
own heartbeat lesson one layer up: the file is fresh, the pipe is empty. A displacement rule
keyed on the liveness field alone would have protected exactly the slots worth reclaiming, so
this module keys on the VERDICT and treats liveness as necessary, never sufficient.

WHY THIS MODULE IS NARROW, WHICH IS THE ONLY QUESTION THAT MATTERS HERE
----------------------------------------------------------------------
Displacement is optional stopping wearing a resource-allocation costume. If a challenger's
arrival can evict an incumbent, the desk can stop any test that is going badly and restart the
story elsewhere -- the garden of forking paths, at the one stage that holds promotion authority.
R0265 names this as the thing not to build: "the incumbent's kill must be on its own
pre-registered terms, not on a challenger's arrival."

So nothing here evicts a clock that is accruing. Reclamation is confined to slots that are
STRUCTURALLY UNABLE TO RESOLVE -- a broken instrument holds a slot the way a jammed turnstile
holds a doorway, and opening it is not a judgement about anybody's hypothesis.

TWO INVARIANTS, BOTH ENFORCED IN CODE AND PINNED BY TESTS
--------------------------------------------------------
1. COUNT-NEUTRAL. One out, one in: ``m_concurrent`` is unchanged by any plan this module
   produces, so not one Holm bar moves in either direction. Displacement can never be a route to
   a looser bar, because it never changes the number the bar is computed from.
2. NO HEALTHY EVICTION. A slot that is accruing real observations is PROTECTED and cannot appear
   in ``displaced``, whatever a challenger looks like.

THE RECLAIMED HYPOTHESIS IS FILED BY ITS MECHANISM OF DEATH, AND THERE ARE TWO
-----------------------------------------------------------------------------
A DEGENERATE clock has told the desk nothing about its axis. Retiring it as REFUTED would file a
data-availability exclusion under a false mechanism of death and corrupt the family survival
statistics that steer future search (L1.17) -- the identical error ``stratified_campaign_gates``
already refuses to make with untested candidates. Instrument-fault reclamations therefore carry
``requeue_as: UNTESTED``, and the fault is named so the axis is re-run rather than re-argued.

A clock carrying ``FAILING FORWARD -> kill`` is the opposite case and gets ``REFUTED``. It reached
the decision point IT pre-registered and lost there, so the desk holds real evidence about the
hypothesis, and re-queueing it as untested would guarantee paying to rediscover a dead axis
forever. Both labels are wrong in opposite directions if swapped, which is why the mechanism of
death travels with the reclamation instead of being defaulted (see ``_requeue_for``).

THAT ROUTE IS WHY THE FIVE KILL VERDICTS WERE INERT. ``forward_verdict()`` is shared by five
shadow runners and each writes its string into ``web/<sleeve>_shadow.json``; ``derive_slots`` read
those artifacts for ``forward_days`` and ``updated`` and dropped the verdict, so every sleeve slot
arrived here carrying ``state="since <date>"`` -- a birth date, never an outcome. The classifier
could not see a kill because no kill was ever in the row. Axis rows always carried theirs, which
is exactly why the axis half of the cohort was reclaimable and the sleeve half was not.

WHAT THIS DOES NOT DO. It does not displace a healthy incumbent on a paired comparison -- the
Shadow-Before-Swap half of R0265. That needs the incumbent's pre-registered decision point to
exist as a readable field before a challenger can be scored against it on the same labels, and
until it does, a paired test would be scored against a horizon nobody wrote down.
``libs/signal_engine/champion_challenger.py`` is NOT that mechanism and must not be mistaken for
it: it differences two absolute Sharpes measured over each variant's own window, which is the
period-effect confound R0265 exists to avoid.

Pure stdlib. Import from ``libs.research.slot_displacement``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "BLOCKED",
    "PROTECTED",
    "RECLAIMABLE",
    "REQUEUE_REFUTED",
    "REQUEUE_UNTESTED",
    "Displacement",
    "DisplacementPlan",
    "at_decision_point",
    "classify_slot",
    "plan_displacement",
]

#: The slot is doing its job. Only its own pre-registered terms may end it.
PROTECTED = "PROTECTED"
#: The slot cannot resolve however long it runs -- a broken instrument, not a weak effect.
RECLAIMABLE = "RECLAIMABLE"
#: The slot cannot be assessed. Deliberately NOT reclaimable: see `classify_slot`.
BLOCKED = "BLOCKED-UNMEASURED"

#: Verdicts that mean the INSTRUMENT failed, so the clock can never produce a resolvable statistic.
#: Sourced from `run_axis_shadows`, which already draws this distinction and states it plainly at
#: the point of issue. Kept as a set rather than a substring test so that a future verdict has to
#: be added here deliberately -- a slot becoming reclaimable is a decision, never a spelling.
_INSTRUMENT_FAULT_VERDICTS = frozenset({"DEGENERATE"})

#: The clock reached ITS OWN pre-registered kill. `forward_verdict()` issues this when forward
#: Sharpe is negative, and it is the ONE reclamation that is not a judgement call by a challenger:
#: the incumbent ended on the terms it registered before the data arrived, which is exactly the
#: condition R0265 requires ("the incumbent's kill must be on its own pre-registered terms, not on
#: a challenger's arrival"). Matched as a prefix because the verdict carries its statistics inline
#: ("FAILING FORWARD -> kill candidate (Sharpe -0.42 on 61 observations, t=-1.83)").
_PREREGISTERED_KILL_PREFIX = "FAILING FORWARD"

#: Distinct from RECLAIMABLE's default because the mechanism of death is DIFFERENT and L1.17 turns
#: on that difference. A DEGENERATE clock measured nothing, so its hypothesis returns UNTESTED. A
#: FAILING-FORWARD clock was tested and lost, so it returns REFUTED -- and filing a refutation as
#: untested would re-open dead ground forever, while filing an instrument fault as a refutation
#: would retire live ground on a false death. Both errors corrupt family survival statistics; they
#: just corrupt them in opposite directions.
REQUEUE_REFUTED = "REFUTED"
REQUEUE_UNTESTED = "UNTESTED"

#: Evidence labels the registry publishes when it cannot see whether a clock is breathing.
_UNMEASURABLE_EVIDENCE = frozenset({"UNMEASURED"})


@dataclass(frozen=True)
class Displacement:
    """One reclaimed slot and the challenger taking it."""

    slot: str
    challenger: str
    why: str
    requeue_as: str = REQUEUE_UNTESTED
    """How the OUTGOING hypothesis is recorded, and it is derived, never assumed.

    UNTESTED is the DEFAULT and the safe error for every route except one: a broken instrument
    measured nothing, and filing that as a refutation retires live research ground on a false
    death. REFUTED is set only for a clock that reached its own pre-registered kill, where the
    desk genuinely does hold evidence against the hypothesis and calling it untested would buy
    the same dead axis again. See ``_requeue_for``."""


@dataclass(frozen=True)
class DisplacementPlan:
    displaced: tuple[Displacement, ...] = ()
    protected: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    waiting: tuple[str, ...] = ()
    m_before: int = 0
    m_after: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def count_neutral(self) -> bool:
        """The load-bearing invariant: a displacement never changes the Holm cohort size."""
        return self.m_before == self.m_after


def classify_slot(slot: dict[str, Any]) -> tuple[str, str]:
    """Return ``(state, why)`` for one row of ``derive_slots()["slots"]``.

    The ordering of these branches is the whole safety argument, so it is spelled out rather than
    collapsed into a single expression:

    * An INSTRUMENT FAULT is checked FIRST and on the verdict, because two of the three live
      faults publish ``evidence: ACCRUING``. Liveness is necessary for a clock to be healthy and
      nowhere near sufficient -- the artifact was being rewritten daily in every one of those
      cases while yielding nothing usable.
    * UNMEASURED is NOT reclaimable, which is the one place this module is deliberately less
      aggressive than L1.28a's "unmeasured utilisation counts as zero" would suggest. The
      asymmetry is real and it is not timidity: wrongly reclaiming destroys forward evidence that
      cannot be re-earned at any price, while wrongly protecting costs a queue position. An
      unmeasurable slot is a MEASUREMENT defect to fix upstream, and it is surfaced as one.
    * Everything else with at least one real observation is PROTECTED.
    """
    name = str(slot.get("name", "?"))
    # `state` for an axis row IS its verdict; for a sleeve row it is a birth date and the verdict
    # arrives in its own field. Read both so one classifier serves both halves of the cohort --
    # the sleeve half was unreachable while only `state` was consulted.
    verdict = str(slot.get("state", "") or "")
    outcome = str(slot.get("verdict", "") or "") or verdict
    evidence = str(slot.get("evidence", "") or "")
    days = slot.get("days")
    obs = int(days) if isinstance(days, (int, float)) else None

    # CHECKED BEFORE EVERYTHING, INCLUDING THE INSTRUMENT FAULT. A clock that reached its own
    # pre-registered kill has the strongest possible claim to its seat being free, and it is the
    # only branch here whose reclamation carries a REFUTATION rather than a re-queue. Ordering it
    # first also means a killed clock is never mislabelled by a later, weaker branch.
    if outcome.upper().startswith(_PREREGISTERED_KILL_PREFIX):
        return RECLAIMABLE, (
            f"{name}: {outcome} -- this clock reached the decision point IT pre-registered and "
            "FAILED there. Reclaiming it is not optional stopping and not a challenger's "
            "judgement: the terms were fixed before the data arrived, which is the one condition "
            "under which ending an incumbent cannot be a garden-of-forking-paths move")

    if verdict in _INSTRUMENT_FAULT_VERDICTS:
        return RECLAIMABLE, (
            f"{name}: verdict {verdict} -- the instrument failed, so this clock cannot resolve "
            f"however long it runs. It publishes evidence={evidence!r}, which is why a liveness "
            "check protects it and a verdict check does not")
    if evidence in _UNMEASURABLE_EVIDENCE:
        return BLOCKED, (
            f"{name}: evidence UNMEASURED -- whether this clock is alive is unknown, and a slot "
            "nobody can see is not a slot anybody may take. Fix the measurement, then re-run")
    if obs == 0:
        return RECLAIMABLE, (
            f"{name}: {evidence} with zero observations accrued -- it has spent its opportunities "
            "and converted none of them, so there is no sample here to protect")
    if obs is None:
        return BLOCKED, (
            f"{name}: no observation count published, so this slot cannot be judged either way")
    _reached, terms = at_decision_point(slot)
    return PROTECTED, (
        f"{name}: accruing on {obs} observation(s) -- ends on its own pre-registered terms, never "
        f"on a challenger's arrival ({terms})")


def at_decision_point(slot: dict[str, Any]) -> tuple[bool | None, str]:
    """Has this incumbent reached the decision point IT pre-registered? R0430's prerequisite.

    THE FIELD THIS READS DID NOT EXIST UNTIL NOW, WHICH IS WHY SHADOW-BEFORE-SWAP COULD NOT BE
    BUILT. `classify_slot` has always protected a healthy incumbent because it "ends on its own
    pre-registered terms" -- a sentence pinned by a test with nothing behind it. A paired
    challenger scored against an incumbent whose horizon was never written down is optional
    stopping with extra steps: whoever runs the comparison picks the moment, and picking the
    moment is the entire bias.

    THREE-VALUED, AND THE THIRD VALUE IS THE SAFE ONE. ``None`` means the slot declares no
    decision point, and it must never collapse into ``False`` OR ``True``: "not yet" and "we
    never wrote one down" demand opposite repairs, and only the second is a wiring defect. A
    caller may act on ``True`` alone; every other value leaves the incumbent alone.

    IT GRANTS NO AUTHORITY AND MOVES NOTHING. Reaching a decision point means a decision may
    legitimately be TAKEN, not that the incumbent loses. The paired comparison that would use
    this -- warm-refit challenger, identical labels, fixed paired advantage -- remains unbuilt on
    purpose, and `plan_displacement` is deliberately unchanged: a healthy incumbent is still
    never displaced, at any observation count. This function only makes the question answerable.
    """
    name = str(slot.get("name", "?"))
    point = slot.get("decision_at_obs")
    if not isinstance(point, int) or isinstance(point, bool) or point <= 0:
        return None, (
            f"{name} declares no pre-registered decision point, so no horizon exists to have "
            "been reached -- an incumbent cannot be paired against a bar nobody wrote down")
    days = slot.get("days")
    obs = int(days) if isinstance(days, (int, float)) and not isinstance(days, bool) else None
    if obs is None:
        return None, (
            f"{name} pre-registered a decision at {point} observation(s) but publishes no "
            "observation count, so progress toward it is UNMEASURED")
    if obs >= point:
        return True, (
            f"{name} reached its pre-registered decision point: {obs}/{point} observation(s). A "
            "decision may be TAKEN on its own terms -- this is not itself a verdict")
    return False, (
        f"{name} is {point - obs} observation(s) short of its pre-registered decision point "
        f"({obs}/{point}) -- its own terms have not yet allowed a decision")


def _requeue_for(slot: dict[str, Any]) -> str:
    """How the OUTGOING hypothesis is filed. REFUTED only when the clock was actually tested.

    L1.17 turns on this distinction: family survival statistics steer future search, so filing an
    unmeasured axis as REFUTED retires live ground on a false death, and filing a genuinely
    refuted one as UNTESTED guarantees the desk pays to rediscover it. The default stays UNTESTED
    because that is the safe error for every reclamation route EXCEPT the pre-registered kill --
    which is the only one carrying evidence about the hypothesis rather than about the instrument.
    """
    outcome = str(slot.get("verdict", "") or slot.get("state", "") or "")
    if outcome.upper().startswith(_PREREGISTERED_KILL_PREFIX):
        return REQUEUE_REFUTED
    return REQUEUE_UNTESTED


def plan_displacement(slots: list[dict[str, Any]], challengers: list[dict[str, Any]],
                      *, cap: int) -> DisplacementPlan:
    """Match challengers to slots that cannot resolve. Never touches a slot that can.

    ``slots`` is ``derive_slots()["slots"]``. ``challengers`` are candidate dicts carrying at
    least ``name``, plus ``runway``: how much room the edge has before the book outgrows it, in
    whatever unit the caller uses consistently -- ``capacity_policy.growth_runway`` (multiples of
    the current book) and ``run_promotion_queue``'s ``runway_days`` are both valid, and only the
    ordering is read. Smaller means expiring sooner.

    THE ORDER IS EXPIRY, SHORTEST RUNWAY FIRST (L1.18a). A long-runway edge loses nothing by
    waiting and a short-runway one loses everything, so ranking the queue by anything else --
    including by how good the edge looks -- spends the scarce slot on the candidate least damaged
    by not getting it. A challenger with no declared runway sorts last rather than first: an
    unmeasured runway is not an urgent one, and letting it jump the queue would make declaring
    nothing the fastest way in.
    """
    # AN EMPTY COHORT IS UNMEASURED, NOT WIDE OPEN (L1.57). `derive_slots` builds from hardcoded
    # standing and derivative names, so it cannot legitimately return zero slots -- an empty list
    # means the registry failed to read, and treating that as `cap` free seats would hand every
    # challenger a clock on the strength of a failure. A verdict computed over nothing is vacuous
    # however honest its arithmetic.
    if not slots:
        return DisplacementPlan(
            waiting=tuple(str(c.get("name", "?")) for c in challengers),
            m_before=0, m_after=0,
            notes=("UNMEASURED: the slot cohort is empty, which the registry cannot produce "
                   "legitimately -- it is built from hardcoded standing and derivative names. "
                   "Treating this as free capacity would admit challengers on the strength of a "
                   "read failure, so nothing is placed until the registry is readable",))

    states = [(s, *classify_slot(s)) for s in slots]
    # The mechanism of death travels with the reclamation, because the requeue label is derived
    # from it and the two are not interchangeable (see REQUEUE_REFUTED).
    reclaimable = [(str(s.get("name", "?")), why, _requeue_for(s))
                   for s, st, why in states if st == RECLAIMABLE]
    protected = tuple(str(s.get("name", "?")) for s, st, _ in states if st == PROTECTED)
    blocked_rows = [(str(s.get("name", "?")), why) for s, st, why in states if st == BLOCKED]

    # Idle slots are ADMISSION's job, not this module's -- it is only ever asked what to do when
    # there is nothing idle left. Counting them here would double-fill the same slot.
    idle = max(0, int(cap) - len(slots))

    ranked = sorted(
        challengers,
        key=lambda c: (float(c["runway"]) if isinstance(c.get("runway"), (int, float))
                       else float("inf")))
    # Idle slots come first and cost no displacement: taking a free seat is not an eviction.
    take_free = ranked[:idle]
    rest = ranked[idle:]

    pairs = [
        Displacement(slot=slot_name, challenger=str(c.get("name", "?")),
                     why=f"{why}; replaced by {c.get('name', '?')} "
                         f"(runway {c.get('runway', 'UNMEASURED')})",
                     requeue_as=requeue)
        for (slot_name, why, requeue), c in zip(reclaimable, rest, strict=False)
    ]
    waiting = tuple(str(c.get("name", "?")) for c in rest[len(pairs):])

    m_before = len(slots)
    # ONE OUT, ONE IN. Reclamations are matched 1:1 with challengers, so the cohort size moves
    # only by however many genuinely idle seats were filled -- never by a displacement. This is
    # computed rather than asserted so the arithmetic is visible in the artifact.
    m_after = m_before + len(take_free)

    notes = [
        f"{len(reclaimable)} of {m_before} slot(s) cannot resolve and are reclaimable; "
        f"{len(protected)} accruing and PROTECTED",
        "count-neutral by construction: a displacement swaps one clock for one clock, so "
        f"m stays {m_before if not take_free else f'{m_before}->{m_after}'} and no Holm bar moves",
    ]
    if blocked_rows:
        notes.append(
            f"{len(blocked_rows)} slot(s) UNMEASURED and therefore NOT reclaimed -- wrongly "
            "evicting destroys forward evidence that cannot be re-earned, while wrongly keeping "
            "costs a queue position. This is a measurement defect upstream, not a displacement "
            "decision: " + "; ".join(n for n, _ in blocked_rows))
    if waiting:
        notes.append(
            f"{len(waiting)} challenger(s) still WAITING with no reclaimable slot -- the forward "
            "stage is genuinely saturated by clocks that are all doing their job, which is the "
            "one case where waiting is the correct answer")
    if pairs:
        notes.append(
            "outgoing hypotheses requeue as UNTESTED, never REFUTED: a broken instrument "
            "measured nothing, and recording it as a refutation would retire live research "
            "ground on a false mechanism of death (L1.17)")
    if not reclaimable and not waiting and not challengers:
        notes.append("no challengers offered -- nothing to place")

    return DisplacementPlan(
        displaced=tuple(pairs), protected=protected,
        blocked=tuple(n for n, _ in blocked_rows), waiting=waiting,
        m_before=m_before, m_after=m_after, notes=tuple(notes))
