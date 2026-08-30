"""Six ways to fail, six different lessons. Collapsing them teaches the wrong research policy.

WHY THIS EXISTS (external audit, 2026-08-29 -- the sharpest point in it)

    "'The idea failed', 'we measured it badly', 'the implementation failed', 'costs killed it',
     'it duplicated another alpha', and 'we lacked the required data' must be six different
     machine states. If all of those collapse to FAIL, the AI will learn the wrong research
     policy."

Exactly right, and this desk was collapsing them. `positioning_extreme` spent months measured by
distance-from-a-60-bar-mean while real COT sat on disk; every failure it produced was recorded as
evidence against POSITIONING AS A MECHANISM, when it was evidence against a bad proxy. The
allocator then correctly learned to stop funding positioning research -- correctly, from data
that was wrong.

THE SIX STATES, and what each one is allowed to teach:

    MECHANISM_REFUTED     the effect is not there. THE ONLY state that may lower a mechanism's
                          posterior, and it requires the measurement to have been attributable.
    MEASUREMENT_FAILED    the observable was a poor stand-in. Teaches nothing about the
                          mechanism; generates a MEASUREMENT mutation.
    IMPLEMENTATION_FAILED leakage, a bug, a broken clock. Teaches nothing about the mechanism;
                          generates an IMPLEMENTATION fix.
    COST_FAILED           gross positive, net negative. The effect IS REAL and does not pay HERE.
                          Teaches about venue and horizon, never about the mechanism.
    REDUNDANT             it works and duplicates an existing survivor. The mechanism is
                          VALIDATED; only its portfolio value is zero.
    DATA_UNAVAILABLE      the required observable does not exist yet. Generates a
                          DATA-ACQUISITION job and leaves the mechanism completely untouched.

THE ASYMMETRY THAT MATTERS. Five of the six must NOT reduce a mechanism's posterior. Only
MECHANISM_REFUTED may, and only when the measurement that produced it was attributable in the
first place. A desk that lets a cost failure or a bad proxy bury a mechanism will systematically
abandon exactly the edges that are hardest to measure -- which are the ones least likely to be
crowded, and therefore the ones most worth having.

DATA FAILURE IS A TASK, NOT A VERDICT. When a mechanism repeatedly blocks on a missing observable,
`data_needs` turns that into a ranked acquisition job. "We lacked the data" is the one failure
that is entirely within the desk's power to fix, and burying it is how a research programme
quietly shrinks to whatever it already happens to measure.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

#: The six states. Order is severity of what they say about the MECHANISM, weakest first.
STATES = (
    "DATA_UNAVAILABLE",
    "REDUNDANT",
    "COST_FAILED",
    "IMPLEMENTATION_FAILED",
    "MEASUREMENT_FAILED",
    "MECHANISM_REFUTED",
)

#: The ONLY state that may lower a mechanism's posterior -- and even then, only if the
#: measurement behind it was attributable.
TEACHES_AGAINST_MECHANISM = frozenset({"MECHANISM_REFUTED"})

#: What each state should cause next. A failure with no next action is a failure the desk cannot
#: act on, which is the same as a failure it did not record.
NEXT_ACTION: dict[str, str] = {
    "DATA_UNAVAILABLE": "acquire_data",
    "REDUNDANT": "shelve_pending_book_change",
    "COST_FAILED": "mutate_horizon_or_venue",
    "IMPLEMENTATION_FAILED": "fix_implementation",
    "MEASUREMENT_FAILED": "mutate_measurement",
    "MECHANISM_REFUTED": "explore_different_region",
}


@dataclass
class Diagnosis:
    """Why a candidate failed, and what the desk is allowed to conclude from it."""

    state: str
    reason: str
    mechanism: str = ""
    measurement_class: str = ""
    missing_observable: str = ""
    gross_positive: bool | None = None
    nearest_duplicate: str = ""

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {self.state!r}")

    @property
    def updates_mechanism_posterior(self) -> bool:
        """May this failure make the desk believe less in the mechanism?

        Requires BOTH a refutation AND an attributable measurement. A refutation produced by a
        heuristic proxy refutes the proxy, and recording it against the mechanism is how a desk
        abandons an edge it never actually tested.
        """
        if self.state not in TEACHES_AGAINST_MECHANISM:
            return False
        return self.measurement_class in ("DIRECT", "VALIDATED_PROXY")

    @property
    def next_action(self) -> str:
        return NEXT_ACTION[self.state]

    def explain(self) -> str:
        if not self.updates_mechanism_posterior and self.state == "MECHANISM_REFUTED":
            return (f"MECHANISM_REFUTED but the measurement was {self.measurement_class or 'un'
                    'recorded'} -- this refutes the PROXY, not {self.mechanism}. Posterior "
                    f"unchanged; the mechanism needs a better observable before it can be judged.")
        return f"{self.state}: {self.reason} -> {self.next_action}"


def diagnose(*, mechanism: str, measurement_class: str, exp_r_gross: float | None,
             exp_r_net: float | None, novelty_verdict: str | None,
             missing_observable: str = "", implementation_error: str = "",
             n_trades: int = 0) -> Diagnosis:
    """Classify a failure into exactly one of the six states.

    ORDER IS THE WHOLE ALGORITHM. Checks run from "says least about the mechanism" to "says most",
    so a candidate that is BOTH missing data AND unprofitable is recorded as a data failure --
    because with the observable missing, the unprofitability is not evidence about anything.
    Reversing the order would let the weakest explanation claim the strongest conclusion.
    """
    if missing_observable:
        return Diagnosis(
            state="DATA_UNAVAILABLE", mechanism=mechanism,
            measurement_class=measurement_class, missing_observable=missing_observable,
            reason=(f"{mechanism} requires {missing_observable}, which the desk does not have. "
                    f"Nothing about the mechanism was tested."))

    if implementation_error:
        return Diagnosis(
            state="IMPLEMENTATION_FAILED", mechanism=mechanism,
            measurement_class=measurement_class,
            reason=(f"the implementation raised or leaked ({implementation_error[:80]}); the "
                    f"result describes the code, not the market"))

    if measurement_class in ("HEURISTIC_PROXY", "UNMEASURABLE", ""):
        return Diagnosis(
            state="MEASUREMENT_FAILED", mechanism=mechanism,
            measurement_class=measurement_class,
            reason=(f"measured by a {measurement_class or 'unrecorded'} stand-in, so a negative "
                    f"result refutes the stand-in rather than {mechanism}"))

    if novelty_verdict == "REDUNDANT":
        return Diagnosis(
            state="REDUNDANT", mechanism=mechanism, measurement_class=measurement_class,
            reason=(f"{mechanism} is VALIDATED here -- it works. Its portfolio value is zero "
                    f"because the book already holds this bet."))

    # COST BEFORE MECHANISM. Gross positive and net negative means the effect exists and this
    # venue takes it. That is a fact about spreads and horizon, and filing it as a refutation
    # would blame the market for the broker.
    if (exp_r_gross is not None and exp_r_net is not None
            and exp_r_gross > 0 >= exp_r_net):
        return Diagnosis(
            state="COST_FAILED", mechanism=mechanism, measurement_class=measurement_class,
            gross_positive=True,
            reason=(f"gross {exp_r_gross:+.4f}R, net {exp_r_net:+.4f}R -- the effect is real and "
                    f"this venue's costs take all of it. A longer horizon or a cheaper "
                    f"instrument may keep it."))

    if n_trades < 20:
        return Diagnosis(
            state="MEASUREMENT_FAILED", mechanism=mechanism,
            measurement_class=measurement_class,
            reason=(f"only {n_trades} trades -- too few to refute anything. Recorded as a "
                    f"measurement problem rather than a refutation, because an underpowered "
                    f"sample is a fact about the test."))

    return Diagnosis(
        state="MECHANISM_REFUTED", mechanism=mechanism, measurement_class=measurement_class,
        reason=(f"attributable measurement ({measurement_class}), {n_trades} trades, net "
                f"{exp_r_net:+.4f}R -- the effect is not there"))


@dataclass
class DataNeed:
    """An observable that is repeatedly blocking work, ranked by what it would unblock."""

    observable: str
    mechanisms_blocked: list[str] = field(default_factory=list)
    hypotheses_blocked: int = 0
    candidate_sources: list[str] = field(default_factory=list)

    @property
    def value(self) -> float:
        """What acquiring this is worth: breadth of unblocking times depth.

        Mechanisms blocked matters more than hypotheses blocked -- fifty hypotheses about one
        mechanism unblock one region, while five mechanisms unblock five.
        """
        return len(set(self.mechanisms_blocked)) * 2.0 + self.hypotheses_blocked * 0.1


def data_needs(diagnoses: list[Diagnosis]) -> list[DataNeed]:
    """Turn repeated DATA_UNAVAILABLE failures into a ranked acquisition queue.

    This is the state that is entirely within the desk's power to fix. Burying it is how a
    research programme quietly shrinks to whatever it already happens to measure -- and this desk
    has now twice found that an observable it called impossible was a free HTTP request away.
    """
    by_obs: dict[str, DataNeed] = {}
    for d in diagnoses:
        if d.state != "DATA_UNAVAILABLE" or not d.missing_observable:
            continue
        need = by_obs.setdefault(d.missing_observable, DataNeed(observable=d.missing_observable))
        need.mechanisms_blocked.append(d.mechanism)
        need.hypotheses_blocked += 1
    return sorted(by_obs.values(), key=lambda n: -n.value)


def policy_report(diagnoses: list[Diagnosis]) -> dict[str, Any]:
    """What the desk is allowed to have learned from a batch of failures."""
    counts = Counter(d.state for d in diagnoses)
    teaching = [d for d in diagnoses if d.updates_mechanism_posterior]
    blocked_posteriors: dict[str, list[str]] = defaultdict(list)
    for d in diagnoses:
        if d.state == "MECHANISM_REFUTED" and not d.updates_mechanism_posterior:
            blocked_posteriors[d.mechanism].append(d.measurement_class or "unrecorded")
    return {
        "total": len(diagnoses),
        "by_state": dict(counts),
        "may_lower_a_posterior": len(teaching),
        "refutations_withheld": {k: v for k, v in blocked_posteriors.items()},
        "actions": dict(Counter(d.next_action for d in diagnoses)),
        "data_needs": [{"observable": n.observable, "value": round(n.value, 2),
                        "mechanisms": sorted(set(n.mechanisms_blocked)),
                        "hypotheses": n.hypotheses_blocked}
                       for n in data_needs(diagnoses)],
        "note": ("only MECHANISM_REFUTED with an attributable measurement may lower a "
                 "mechanism's posterior. A desk that lets cost failures or bad proxies bury "
                 "mechanisms abandons exactly the edges that are hardest to measure -- which "
                 "are the least crowded and therefore the most worth having."),
    }
