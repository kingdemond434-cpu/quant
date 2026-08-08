"""F3's SECOND BRANCH — validating a mechanism that is only supposed to work in some states.

WHY A BRANCH AND NOT A LOOSENING. `libs/validation/gate_power.py` measured what F3 actually does
to a planted conditional edge, and the number is not a tuning problem::

    planted effect      0.0    0.01   0.02   0.05   0.10   0.20   0.40
    STABLE edge kept   0.23   0.37   0.45   0.78   1.00   1.00   1.00
    CONDITIONAL kept   0.24   0.32   0.35   0.44   0.50   0.55   0.51

A stable edge saturates: make it big enough and F3 always keeps it. A CONDITIONAL edge asymptotes
at about one half, and it does so for a structural reason that no amount of effect size fixes. F3
requires both walk-forward arms net-positive. When the mechanism is genuinely inactive in one arm,
that arm is noise, and noise is positive by chance roughly half the time REGARDLESS of how strong
the edge is in the arm where it does fire. The gate is not underpowered against conditional alpha;
it is measuring the wrong thing about it, and its ~50% ceiling is a coin flip dressed as a test.

**THE WRONG FIX IS TO LOWER F3, AND IT IS WRONG FOR A REASON WORTH WRITING DOWN.** F3's both-arms
rule is exactly what stops a global claim being made on one lucky half of the sample. Relaxing it
globally to rescue conditional mechanisms would open that hole for every candidate, including the
overwhelming majority that are noise. So global F3 is untouched. Conditional mechanisms take a
DIFFERENT and in most respects HARDER path, and they must declare which path they are on BEFORE
untouched data is opened.

**THE ONE THING THIS MODULE EXISTS TO MAKE IMPOSSIBLE.** The sequence::

    candidate fails
        -> search its results for a slice where it worked
        -> declare that slice a "regime"
        -> call the candidate rescued

is not validation, it is the multiple-testing problem with a narrative attached, and it is the
most attractive defect on this desk because the story is always available after the fact. A state
declared after the failure was observed is a POST-HOC RESCUE and this module returns
`POST_HOC_RESCUE` for it every time, no matter how good the conditional numbers are. The legitimate
move is to emit a NEW preregistered hypothesis and test it on data nobody has touched, and
`rescue_to_new_hypothesis` builds exactly that object.

Classifies and reports. Promotes nothing. The gauntlet keeps its promotion authority; a conditional
mechanism that passes here has earned the RIGHT TO BE TESTED, not the right to be traded.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

__all__ = [
    "MIN_STATE_OCCURRENCES",
    "MIN_STATE_SHARE",
    "REQUIREMENTS",
    "ConditionalEvidence",
    "Preregistration",
    "adjudicate",
    "requirement_status",
    "rescue_to_new_hypothesis",
    "state_recurrence_ok",
    "summarise",
]

#: Distinct, non-overlapping occurrences of the state required before any conditional claim.
#: NOT a count of bars: a state that occurred once and lasted six months is one observation of one
#: episode, and a conditional mechanism validated on it is a claim about that episode.
MIN_STATE_OCCURRENCES: int = 8

#: The state must also be a real slice rather than a hand-picked window. Below this share of the
#: sample the "regime" is more plausibly a selected subset than a recurring market condition.
MIN_STATE_SHARE: float = 0.05

#: The eight things a conditional mechanism owes, from the specification. Each maps to a field on
#: `ConditionalEvidence`, so a missing requirement is a missing MEASUREMENT rather than a missing
#: paragraph -- prose cannot satisfy any of these.
REQUIREMENTS: tuple[str, ...] = (
    "EX_ANTE_STATE_DEFINITION",
    "AS_OF_OBSERVABILITY",
    "MECHANISM_FOR_CONDITIONALITY",
    "STATE_RECURRENCE",
    "CLASSIFIER_STABILITY",
    "CONDITIONAL_COSTS",
    "TRANSITION_ANALYSIS",
    "UNTOUCHED_OOS",
)


@dataclass(frozen=True)
class Preregistration:
    """The declaration that must exist BEFORE untouched data is opened.

    `sequence` is the ordering device and it is the whole mechanism. It is a monotone counter of
    evaluation events on this desk -- a preregistration whose sequence is greater than the sequence
    at which the candidate was first evaluated was written AFTER the results were seen, and no
    amount of good faith changes what that does to the error rate.
    """

    hypothesis_id: str
    #: GLOBAL_MECHANISM or STATE_CONDITIONAL_MECHANISM. Declared, not inferred from results.
    mechanism_class: str
    #: Machine-readable state predicate, e.g. "funding_8h_annualised > 0.35 and oi_change_24h < 0".
    #: Empty for a global mechanism.
    state_definition: str = ""
    #: Why the mechanism should be inactive outside the state. "It only worked there" is NOT a
    #: mechanism and the adjudication rejects it by name.
    conditionality_mechanism: str = ""
    #: Desk evaluation counter at the moment this was written.
    sequence: int = 0

    @property
    def is_conditional(self) -> bool:
        return self.mechanism_class == "STATE_CONDITIONAL_MECHANISM"

    @property
    def digest(self) -> str:
        """Content hash. Two preregistrations that differ in the state predicate are not the same
        preregistration, however similar their prose."""
        blob = "|".join((self.hypothesis_id, self.mechanism_class, self.state_definition,
                         self.conditionality_mechanism))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ConditionalEvidence:
    """What was measured. Every field defaults to the UNMEASURED value, never to the passing one."""

    hypothesis_id: str
    #: Desk evaluation counter at the candidate's FIRST evaluation. Compared against the
    #: preregistration's sequence to detect a rescue.
    first_evaluated_sequence: int = 0
    #: Distinct entries into the state across the sample.
    state_occurrences: int = 0
    #: Fraction of sample bars inside the state.
    state_share: float = 0.0
    #: Can the state be computed from information available AT the decision timestamp?
    as_of_observable: bool = False
    #: Agreement of the state classifier across bootstrap/refit. 0 = unmeasured.
    classifier_stability: float = 0.0
    #: Net bps inside the state, AFTER conditional costs (a state is often a state because
    #: liquidity is different in it, and using pooled costs there is a leak).
    in_state_net_bps: float = 0.0
    #: Net bps outside the state. Expected to be ~0 for a true conditional mechanism.
    out_state_net_bps: float = 0.0
    #: Observations inside the state. Thin arms are the reason F3's second arm is a coin flip.
    in_state_n: int = 0
    out_state_n: int = 0
    #: Net bps during state TRANSITIONS. The mechanism may reverse while the state is changing,
    #: and a book that trades through transitions eats that without ever seeing it.
    transition_net_bps: float | None = None
    #: Whether conditional cost curves were used rather than pooled ones.
    conditional_costs_measured: bool = False
    #: Untouched out-of-sample net bps inside the state. None = the lockbox was never opened.
    untouched_oos_net_bps: float | None = None
    untouched_oos_n: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


def state_recurrence_ok(ev: ConditionalEvidence) -> tuple[bool, str]:
    """Is the state a RECURRING market condition or a selected window?"""
    if ev.state_occurrences <= 0:
        return False, "state occurrences UNMEASURED -- cannot distinguish a regime from a window"
    if ev.state_occurrences < MIN_STATE_OCCURRENCES:
        return False, (
            f"{ev.state_occurrences} distinct occurrence(s) against a floor of "
            f"{MIN_STATE_OCCURRENCES}. A state that happened rarely and lasted a long time is ONE "
            "observation of one episode however many bars it contains")
    if ev.state_share < MIN_STATE_SHARE:
        return False, (
            f"the state covers {ev.state_share:.1%} of the sample, below {MIN_STATE_SHARE:.0%}. "
            "At this share a 'regime' is more plausibly a selected subset than a condition")
    return True, (f"{ev.state_occurrences} distinct occurrences over {ev.state_share:.1%} of the "
                  "sample")


def requirement_status(prereg: Preregistration,
                       ev: ConditionalEvidence) -> dict[str, tuple[bool, str]]:
    """Each of the eight requirements, measured. Order is the specification's order."""
    rec_ok, rec_why = state_recurrence_ok(ev)
    weak = ("it only worked there", "worked in that regime", "the numbers were better",
            "post hoc", "post-hoc")
    mech = prereg.conditionality_mechanism.strip()
    mech_ok = bool(mech) and not any(w in mech.lower() for w in weak)
    return {
        "EX_ANTE_STATE_DEFINITION": (
            bool(prereg.state_definition.strip()),
            "machine-readable state predicate declared" if prereg.state_definition.strip()
            else "no state predicate: a state described in prose cannot be applied as-of, and "
                 "cannot be shown to have been the same state at every occurrence"),
        "AS_OF_OBSERVABILITY": (
            ev.as_of_observable,
            "state computable at the decision timestamp" if ev.as_of_observable
            else "the state is NOT computable from information available at the decision "
                 "timestamp. A conditional edge whose condition is known only afterwards is a "
                 "description of the past, and it will backtest beautifully"),
        "MECHANISM_FOR_CONDITIONALITY": (
            mech_ok,
            f"conditionality explained: {mech[:120]}" if mech_ok
            else "no mechanism for WHY the edge should be inactive outside the state. 'It only "
                 "worked there' is the observation that needs explaining, not the explanation"),
        "STATE_RECURRENCE": (rec_ok, rec_why),
        "CLASSIFIER_STABILITY": (
            ev.classifier_stability >= 0.7,
            f"classifier agreement {ev.classifier_stability:.2f}" if ev.classifier_stability > 0
            else "state-classifier stability UNMEASURED. If the classifier relabels the same bars "
                 "differently on a refit, the 'state' is a property of the fit"),
        "CONDITIONAL_COSTS": (
            ev.conditional_costs_measured,
            "conditional cost curves applied" if ev.conditional_costs_measured
            else "pooled costs used inside a state that likely HAS different liquidity -- the "
                 "commonest way a conditional edge is manufactured out of a cost assumption"),
        "TRANSITION_ANALYSIS": (
            ev.transition_net_bps is not None,
            f"transition net {ev.transition_net_bps:+.3f}bp" if ev.transition_net_bps is not None
            else "transition periods UNMEASURED. The book trades through every entry and exit of "
                 "the state, and pays whatever happens there whether or not it was measured"),
        "UNTOUCHED_OOS": (
            ev.untouched_oos_net_bps is not None and ev.untouched_oos_n > 0,
            f"untouched OOS {ev.untouched_oos_net_bps:+.3f}bp over {ev.untouched_oos_n} obs"
            if ev.untouched_oos_net_bps is not None
            else "the lockbox was never opened. Everything above was measured on data the "
                 "hypothesis has already seen"),
    }


def adjudicate(prereg: Preregistration, ev: ConditionalEvidence) -> tuple[str, str]:
    """(verdict, why).

    POST_HOC_RESCUE | NOT_CONDITIONAL | INSUFFICIENT_STATE_EVIDENCE | CONDITIONAL_UNPROVEN |
    CONDITIONAL_VALIDATED

    The order of the checks is load-bearing: the rescue check runs FIRST and cannot be reached
    past by strong evidence, because strong evidence is precisely what a post-hoc slice search
    produces.
    """
    if prereg.hypothesis_id != ev.hypothesis_id:
        return "POST_HOC_RESCUE", (
            f"preregistration is for {prereg.hypothesis_id!r} and the evidence is for "
            f"{ev.hypothesis_id!r}. Borrowing another hypothesis's declaration is the rescue "
            "pattern with an extra step")
    if not prereg.is_conditional:
        return "NOT_CONDITIONAL", (
            f"declared {prereg.mechanism_class!r}, so global F3 applies unchanged. This branch is "
            "not available to a candidate that declared a global mechanism and then failed one")
    if prereg.sequence > ev.first_evaluated_sequence:
        return "POST_HOC_RESCUE", (
            f"the state was declared at sequence {prereg.sequence}, AFTER the candidate was first "
            f"evaluated at {ev.first_evaluated_sequence}. The slice was chosen with the results "
            "visible, so its significance is unbounded and no conditional number here can be "
            "trusted. The legitimate move is a NEW preregistered hypothesis on untouched data -- "
            "see rescue_to_new_hypothesis()")
    reqs = requirement_status(prereg, ev)
    failed = [k for k, (ok, _) in reqs.items() if not ok]
    hard = [k for k in failed if k in ("EX_ANTE_STATE_DEFINITION", "AS_OF_OBSERVABILITY",
                                       "MECHANISM_FOR_CONDITIONALITY", "STATE_RECURRENCE")]
    if hard:
        return "INSUFFICIENT_STATE_EVIDENCE", (
            f"{len(hard)} structural requirement(s) unmet: {hard}. "
            + reqs[hard[0]][1])
    if failed:
        return "CONDITIONAL_UNPROVEN", (
            f"the state is real and declared in advance, but {len(failed)} requirement(s) remain "
            f"UNMEASURED: {failed}. " + reqs[failed[0]][1] + ". This is not a kill -- it is the "
            "list of what must be measured before the claim can be cashed")
    # Every requirement measured. The economics still have to be there, and the SHAPE has to
    # match a conditional mechanism rather than a global one hiding behind a state.
    if ev.in_state_net_bps <= 0:
        return "CONDITIONAL_UNPROVEN", (
            f"in-state net {ev.in_state_net_bps:+.3f}bp is not positive. The mechanism does not "
            "fire even where it was declared to fire")
    if ev.untouched_oos_net_bps is not None and ev.untouched_oos_net_bps <= 0:
        return "CONDITIONAL_UNPROVEN", (
            f"in-state edge {ev.in_state_net_bps:+.3f}bp did not survive untouched OOS "
            f"({ev.untouched_oos_net_bps:+.3f}bp). This is the branch working as intended")
    if abs(ev.out_state_net_bps) > abs(ev.in_state_net_bps):
        return "NOT_CONDITIONAL", (
            f"out-of-state |{ev.out_state_net_bps:+.3f}|bp exceeds in-state "
            f"|{ev.in_state_net_bps:+.3f}|bp. Whatever this is, the declared state is not the "
            "condition -- send it back to global F3, which is the correct gate for it")
    return "CONDITIONAL_VALIDATED", (
        f"all eight requirements measured; in-state {ev.in_state_net_bps:+.3f}bp over "
        f"{ev.in_state_n} obs, out-of-state {ev.out_state_net_bps:+.3f}bp, untouched OOS "
        f"{ev.untouched_oos_net_bps:+.3f}bp over {ev.untouched_oos_n} obs. Earns the right to be "
        "TESTED further and sized as a conditional exposure -- not a promotion, which the "
        "gauntlet still owns")


def rescue_to_new_hypothesis(prereg: Preregistration, ev: ConditionalEvidence,
                             *, sequence_now: int) -> Preregistration:
    """Turn a post-hoc observation into a legitimate FORWARD hypothesis. §16's escape hatch.

    The observation "it worked in state X" is genuine information and throwing it away would be
    its own waste. What it is NOT is evidence about state X, because the state was chosen by
    looking. So it becomes a new preregistration, stamped at the CURRENT sequence, which can only
    ever be tested against data that arrives from here on.

    The returned object deliberately carries a different `hypothesis_id`: reusing the old one is
    how a rescued slice quietly inherits the parent's history.
    """
    return Preregistration(
        hypothesis_id=f"{prereg.hypothesis_id}__cond_{prereg.digest[:8]}",
        mechanism_class="STATE_CONDITIONAL_MECHANISM",
        state_definition=prereg.state_definition,
        conditionality_mechanism=(
            prereg.conditionality_mechanism
            or f"DERIVED FROM A POST-HOC OBSERVATION on {ev.hypothesis_id}: the mechanism for the "
               "conditionality is NOT yet stated and must be before this is tested"),
        sequence=sequence_now,
    )


def summarise(pairs: list[tuple[Preregistration, ConditionalEvidence]]) -> dict[str, object]:
    """Report shape for `data/state_conditional.json`."""
    if not pairs:
        return {"candidates": 0, "headline": (
            "no conditional candidates declared. F3's measured ~50% ceiling on conditional "
            "mechanisms is therefore UNEXERCISED, not absent -- the branch exists and nothing "
            "has used it")}
    rows = []
    for p, e in pairs:
        v, why = adjudicate(p, e)
        reqs = requirement_status(p, e)
        rows.append({
            "hypothesis_id": e.hypothesis_id,
            "verdict": v,
            "why": why,
            "prereg_digest": p.digest,
            "prereg_sequence": p.sequence,
            "first_evaluated_sequence": e.first_evaluated_sequence,
            "requirements": {k: {"met": ok, "detail": d} for k, (ok, d) in reqs.items()},
            "requirements_met": sum(1 for ok, _ in reqs.values() if ok),
            "in_state_net_bps": e.in_state_net_bps,
            "out_state_net_bps": e.out_state_net_bps,
            "untouched_oos_net_bps": e.untouched_oos_net_bps,
        })
    order = {"CONDITIONAL_VALIDATED": 0, "CONDITIONAL_UNPROVEN": 1,
             "INSUFFICIENT_STATE_EVIDENCE": 2, "NOT_CONDITIONAL": 3, "POST_HOC_RESCUE": 4}
    rows.sort(key=lambda r: order[str(r["verdict"])])
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    rescues = counts.get("POST_HOC_RESCUE", 0)
    return {
        "candidates": len(pairs),
        "counts": counts,
        "rows": rows,
        "headline": (
            f"{counts.get('CONDITIONAL_VALIDATED', 0)} conditional mechanism(s) validated on "
            f"untouched data, {counts.get('CONDITIONAL_UNPROVEN', 0)} unproven, {rescues} refused "
            "as POST-HOC RESCUES" + (
                " -- a rescue is a slice chosen with the results visible, and its significance is "
                "unbounded no matter how good the numbers look" if rescues else "")),
        "note": ("Global F3 is UNCHANGED by this branch. gate_power measured F3 keeping only "
                 "~50% of planted conditional edges at every effect size, because a both-arms "
                 "rule tests noise in the arm where the mechanism is inactive. The answer is a "
                 "harder separate path for declared conditional mechanisms, never a lower bar "
                 "for everyone."),
    }


def power_gain_note(planted_kept_global: float, planted_kept_conditional: float) -> str:
    """One line quantifying what the branch is worth, for the review report.

    Deliberately a NOTE rather than a claim: the gain is only realised for candidates that declare
    conditional in advance, and nothing here estimates how many of those exist.
    """
    if planted_kept_conditional <= 0:
        return "conditional retention UNMEASURED -- run libs/validation/gate_power.py controls"
    ratio = planted_kept_global / planted_kept_conditional if planted_kept_conditional else math.inf
    return (f"F3 keeps {planted_kept_global:.0%} of planted STABLE edges and "
            f"{planted_kept_conditional:.0%} of planted CONDITIONAL ones ({ratio:.1f}x). The "
            "branch recovers that gap only for candidates that DECLARED conditional before the "
            "untouched data was opened; a candidate that declared global and then failed cannot "
            "reach it.")
