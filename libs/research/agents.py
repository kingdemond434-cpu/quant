"""Four roles that cannot do each other's jobs, and a loop that closes on evidence.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    "Do not use one giant omniscient agent."

One agent that reads evidence, invents a mechanism, writes the hypothesis AND decides whether it
survives is not four roles collaborating; it is one opinion laundered through four labels. It
will always find its own idea plausible, because nothing in the arrangement makes disagreement
possible. This desk spent today finding four defects that had survived for weeks precisely
because whoever built a component also judged whether it worked.

So the roles are separated by CONTRACT, not by prompt:

    EvidenceAgent    outputs OBSERVATIONS. May not name a strategy, a direction or an entry.
                     `Observation.assert_no_strategy` rejects it if it does.
    MechanismAgent   answers WHO IS FORCED TO TRADE, why, when, and why arbitrage has not removed
                     it. A mechanism with no payer is refused -- an effect nobody is compelled to
                     pay for has no reason to persist.
    HypothesisAgent  turns a mechanism into a falsifiable prediction with a semantic coordinate.
                     Refused without falsifiers.
    FalsifierAgent   tries to KILL the hypothesis BEFORE any code is written, using controls that
                     cost nothing: randomised clocks, shuffled conditioning, adjacent-time
                     placebo. This is the cheapest kill in the funnel and it runs first.

RD-AGENT'S LOOP, WITH ARTIFACTS AS THE STATE. Microsoft's R&D-Agent splits Research (propose) from
Development (implement) and cycles proposal -> design -> execution -> feedback, reporting 2x the
return of a benchmark factor library while using 70% FEWER factors. The headline is the factor
count: their gain came from deduplication and selection, not from generating more. `research_cycle`
mirrors the loop and routes every stage through `ResearchArtifact`, so state is carried rather
than re-derived -- the failure that gave this desk two identity builders and three verdict engines.

NO MODEL IS CALLED HERE. These are contracts and validators. An LLM may fill a role by producing
a payload that satisfies the dataclass, and the dataclass refuses it otherwise -- so the guarantee
holds whether the role is filled by a model, a script, or a person, and does not depend on any
prompt remaining unedited.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from libs.research.artifacts import ResearchArtifact, new_artifact, transition

#: Words that turn an OBSERVATION into a trade idea. The evidence role exists to report what is
#: seen; the moment it says "buy", the mechanism and hypothesis stages have been skipped and the
#: economics were never articulated.
_STRATEGY_WORDS = re.compile(
    r"\b(buy|sell|long|short|entry|exit|stop[- ]loss|take[- ]profit|signal|strategy|"
    r"go long|go short|trade this)\b", re.I)

#: A mechanism must answer all of these. Missing any one leaves an effect with no reason to
#: persist, which is indistinguishable from a pattern in noise.
_MECHANISM_QUESTIONS = ("who_is_forced", "why_forced", "when", "what_constraint",
                        "who_is_compensated", "why_not_arbitraged", "observable_footprint")

#: Controls every hypothesis must survive before code is written. All are free -- they permute
#: the data the hypothesis already needs -- which is why they belong first.
REQUIRED_CONTROLS = ("randomised_event_clock", "shuffled_conditioning_variable",
                     "adjacent_time_placebo", "sign_flipped_prediction")


class RoleViolation(RuntimeError):
    """A role did something another role's job. Raised, never softened to a warning."""


@dataclass(frozen=True)
class Observation:
    """What the evidence role may produce: a fact with a source. Never a trade."""

    text: str
    source: str
    instruments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise RoleViolation(
                "an observation with no source is an assertion, and this desk does not spend "
                "trials on assertions")
        hit = _STRATEGY_WORDS.search(self.text)
        if hit:
            raise RoleViolation(
                f"the evidence role produced a strategy word ({hit.group(0)!r}). Its output is "
                f"OBSERVATIONS; jumping to a trade skips the mechanism and hypothesis stages, "
                f"which is where the economics would have had to be articulated.")


@dataclass(frozen=True)
class Mechanism:
    """Who is forced to trade, why, and why the premium survives."""

    name: str
    who_is_forced: str
    why_forced: str
    when: str
    what_constraint: str
    who_is_compensated: str
    why_not_arbitraged: str
    observable_footprint: str
    evidence: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        missing = [q for q in _MECHANISM_QUESTIONS if not str(getattr(self, q, "")).strip()]
        if missing:
            raise RoleViolation(
                f"mechanism {self.name!r} does not answer {missing}. An effect with no compelled "
                f"participant has no reason to persist, and is indistinguishable from a pattern "
                f"in noise once the sample changes.")
        if not self.evidence:
            raise RoleViolation(
                f"mechanism {self.name!r} cites no observation. A mechanism invented without "
                f"evidence is the omniscient-agent failure this separation exists to prevent.")


@dataclass(frozen=True)
class Hypothesis:
    """A falsifiable prediction, tied to a mechanism and a coordinate."""

    hypothesis_id: str
    claim: str
    mechanism: Mechanism
    semantic_coordinate: str
    prediction: str
    falsifiers: tuple[str, ...]
    alternative_explanation: str
    distinguishing_test: str
    point_in_time_contract: str

    def __post_init__(self) -> None:
        if not self.falsifiers:
            raise RoleViolation(
                f"{self.hypothesis_id} carries no falsifier. A claim that cannot be wrong cannot "
                f"be tested, and this desk holds 15,380 candidates that were never asked.")
        if not self.alternative_explanation.strip() or not self.distinguishing_test.strip():
            raise RoleViolation(
                f"{self.hypothesis_id} must name the boring explanation AND the test that "
                f"separates it. Without that, a generic intraday effect wearing an institutional "
                f"story passes as a discovery.")


@dataclass
class FalsifierReport:
    """What the free controls did to the hypothesis, before a single bar was backtested."""

    hypothesis_id: str
    controls_run: tuple[str, ...]
    survived: bool
    killed_by: str = ""
    detail: str = ""

    def missing_controls(self) -> list[str]:
        return [c for c in REQUIRED_CONTROLS if c not in self.controls_run]


def falsify(hyp: Hypothesis,
            runner: Callable[[Hypothesis, str], bool]) -> FalsifierReport:
    """Run every required control. A control that is skipped is a control that FAILED.

    `runner(hypothesis, control) -> True if the hypothesis SURVIVES that control`.

    Skipping is treated as failure on purpose: an unrun control is unmeasured, and the whole
    value of this stage is that it is cheap enough to have no excuse. Letting a skip pass would
    make "we did not get to it" indistinguishable from "it held".
    """
    ran: list[str] = []
    for control in REQUIRED_CONTROLS:
        try:
            survived = runner(hyp, control)
        except Exception as exc:
            return FalsifierReport(hyp.hypothesis_id, tuple(ran), False, control,
                                   f"control raised {type(exc).__name__}: {str(exc)[:100]} -- a "
                                   f"control that errors has not been passed")
        ran.append(control)
        if not survived:
            return FalsifierReport(hyp.hypothesis_id, tuple(ran), False, control,
                                   f"killed by {control}: the effect reproduces under a control "
                                   f"that removes the mechanism, so the mechanism is not what "
                                   f"produces it")
    return FalsifierReport(hyp.hypothesis_id, tuple(ran), True, "",
                           f"survived all {len(REQUIRED_CONTROLS)} free controls")


def to_artifact(hyp: Hypothesis, report: FalsifierReport) -> ResearchArtifact:
    """Freeze a surviving hypothesis into the carrier every later stage reads.

    Refuses a hypothesis that has not survived falsification, and refuses one whose controls were
    not all run -- promoting an unfalsified idea into the funnel spends gauntlet compute on
    something a free check would have killed.
    """
    if not report.survived:
        raise RoleViolation(
            f"{hyp.hypothesis_id} was killed by {report.killed_by}; it may not become an "
            f"artifact. {report.detail}")
    missing = report.missing_controls()
    if missing:
        raise RoleViolation(
            f"{hyp.hypothesis_id} has unrun controls {missing}. Unmeasured is not passed, and "
            f"these cost nothing to run.")
    a = new_artifact(
        hyp.hypothesis_id,
        semantic_coordinate=hyp.semantic_coordinate,
        mechanism=hyp.mechanism.name,
        economic_rationale=hyp.mechanism.why_forced,
        payer=hyp.mechanism.who_is_forced,
        falsifiers=tuple(hyp.falsifiers),
        point_in_time_contract=hyp.point_in_time_contract,
        source_provenance="; ".join(o.source for o in hyp.mechanism.evidence)[:400],
    )
    return transition(a, "SPECIFIED",
                      evidence=(f"mechanism answers all {len(_MECHANISM_QUESTIONS)} questions; "
                                f"{report.detail}"),
                      actor="hypothesis_agent")


@dataclass
class CycleResult:
    artifact: ResearchArtifact | None
    stage: str
    detail: str
    falsifier: FalsifierReport | None = None


def research_cycle(observations: list[Observation],
                   propose_mechanism: Callable[[list[Observation]], Mechanism],
                   propose_hypothesis: Callable[[Mechanism], Hypothesis],
                   control_runner: Callable[[Hypothesis, str], bool]) -> CycleResult:
    """RD-Agent's Research -> Development -> Feedback loop, with the artifact as its state.

    Each stage is a separate callable so no single implementation can fill two roles. The stage
    that fails is NAMED in the result, because "the idea did not work" teaches nothing while
    "the mechanism had no payer" teaches where to look next -- which is the whole content of
    QuantaAlpha's credit assignment.
    """
    if not observations:
        return CycleResult(None, "EVIDENCE", "no observations; nothing to reason from")
    try:
        mech = propose_mechanism(observations)
    except RoleViolation as exc:
        return CycleResult(None, "MECHANISM", str(exc))
    try:
        hyp = propose_hypothesis(mech)
    except RoleViolation as exc:
        return CycleResult(None, "HYPOTHESIS", str(exc))
    report = falsify(hyp, control_runner)
    if not report.survived:
        return CycleResult(None, "FALSIFIER", report.detail, report)
    try:
        art = to_artifact(hyp, report)
    except RoleViolation as exc:
        return CycleResult(None, "FREEZE", str(exc), report)
    return CycleResult(art, "SPECIFIED",
                       f"{hyp.hypothesis_id} survived falsification and is frozen", report)
