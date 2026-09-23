"""One immutable object from idea to retirement, and one legal way to move it.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    "Nobody creates a new anonymous representation midway. That prevents the class of bugs you've
     already seen where candidate state disappears between sweep -> shadow -> promotion."

That class of bug is not hypothetical here. Measured on 2026-08-29 alone:

  * `run_key` built `AUDCHF.asia#` while `sleeve_key` built `AUDCHF.overnight_gap_decay.asia`.
    Two identities for one sleeve, in the two modules that must agree which clock is which. The
    first check that ever compared them reported 34 of 35 certificates as having no clock --
    every one of them running.
  * 84 forward rows record NO family. Their mechanism is unrecoverable, so they cannot be
    credited to anything and they silently shrink every denominator in the census.
  * Three engines wrote two different spellings of `PROMOTION CANDIDATE`, and the promoter
    matched each on a different code path.
  * `forward_start` was restamped on every reconciler pass, so 36 of 49 clocks lost their age --
    one by 227 hours -- and no sleeve could ever have reached day 14.

Every one of those is the same disease: state re-derived rather than carried. A candidate that
gets rebuilt at each stage will eventually be rebuilt differently, and the difference only becomes
visible when a sleeve trades differently forward than it was certified.

THE ARTIFACT IS THE CARRIER. It is frozen, it holds the provenance a later reader needs to
reproduce the decision, and it is the SAME object at every stage. Nothing downstream invents its
own representation.

TRANSITIONS TAKE EVIDENCE. `transition()` is the only legal way to change state, it refuses moves
that are not on the graph, and it requires an evidence reference for every one. `artifact.status =
LIVE` is not available -- the dataclass is frozen, so the assignment raises rather than silently
succeeding. That is deliberate: this desk has already had a sleeve reach LIVE in one registry
while another registry knew nothing about it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any

#: The canonical lifecycle. Order matters: `STATES.index` defines what "forward" means, and a
#: transition that moves backwards is refused unless it is an explicit retirement or failure.
STATES = (
    "IDEA", "SPECIFIED", "IMPLEMENTED", "CHEAP_TEST", "OOS_VALIDATED", "GAUNTLET_PASS",
    "LOCKBOX_PASS", "FORWARD_SHADOW", "PAPER_EXECUTION", "PROMOTION_CANDIDATE",
    "LIVE_PROBATION", "LIVE", "RETIRED",
)

#: Terminal outcomes reachable from anywhere. A candidate can always die; it can never skip ahead.
TERMINAL = ("RETIRED", "REFUTED", "KILLED")

#: Why a candidate failed. POWER AND VALIDITY ARE SEPARATED ON PURPOSE: an underpowered sample
#: says nothing about whether the mechanism is real, while leakage says the result was never real.
#: Collapsing them teaches the search the wrong lesson -- it would abandon good mechanisms for
#: having been tested too little.
FAILURE_CLASSES = (
    "invalid_mechanism", "no_effect", "cost_failure", "leakage", "insufficient_power",
    "unstable_parameters", "regime_instability", "pbo", "multiplicity", "redundant_alpha",
    "execution_failure", "live_decay",
)

#: Failures that say the MECHANISM is wrong. Only these should reduce a region's posterior.
VALIDITY_FAILURES = frozenset({"invalid_mechanism", "no_effect", "leakage", "pbo",
                               "multiplicity", "cost_failure"})

#: Failures that say the TEST was too small or the world moved. These must not be read as
#: evidence against the mechanism (LAWS L1.49).
POWER_FAILURES = frozenset({"insufficient_power", "regime_instability", "unstable_parameters"})


class TransitionError(RuntimeError):
    """An illegal state change. Raised, never logged-and-continued."""


@dataclass(frozen=True)
class ResearchArtifact:
    """A candidate, carried whole. Frozen: `artifact.status = 'LIVE'` raises."""

    artifact_id: str
    hypothesis_id: str
    status: str = "IDEA"
    parent_ids: tuple[str, ...] = ()
    semantic_coordinate: str = ""
    mechanism: str = ""
    economic_rationale: str = ""
    payer: str = ""
    falsifiers: tuple[str, ...] = ()
    source_provenance: str = ""
    data_requirements: tuple[str, ...] = ()
    point_in_time_contract: str = ""
    code_hash: str = ""
    ast_hash: str = ""
    git_commit: str = ""
    config_hash: str = ""
    data_snapshot: str = ""
    trial_id: str = ""
    trial_count_at_birth: int = 0
    generation: int = 0
    mutation_operation: str = ""
    stage_results: tuple[dict[str, Any], ...] = ()
    reviewer_results: tuple[dict[str, Any], ...] = ()
    failure_class: str = ""
    created_at: str = ""
    history: tuple[dict[str, Any], ...] = ()

    def fingerprint(self) -> str:
        """Identity hash over the fields that make this a DIFFERENT strategy.

        Deliberately includes `code_hash` and `cost`-bearing config: a family function edited
        mid-window changes what the sleeve DOES without touching any name or parameter, and the
        forward series then splices two strategies into one expectancy. That is not a smaller
        sample, it is a wrong one.
        """
        payload = json.dumps({
            "hypothesis_id": self.hypothesis_id,
            "coordinate": self.semantic_coordinate,
            "mechanism": self.mechanism,
            "code_hash": self.code_hash,
            "config_hash": self.config_hash,
            "data_snapshot": self.data_snapshot,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:20]

    def is_specified(self) -> tuple[bool, str]:
        """Does this carry everything a real trial requires?"""
        missing = [f for f in ("hypothesis_id", "mechanism", "economic_rationale", "payer",
                               "semantic_coordinate", "point_in_time_contract")
                   if not getattr(self, f)]
        if not self.falsifiers:
            missing.append("falsifiers")
        if missing:
            return False, f"missing {', '.join(missing)}"
        return True, "specified"


def _legal(from_state: str, to_state: str) -> bool:
    if to_state in TERMINAL:
        return True                                  # a candidate may always die
    if from_state not in STATES or to_state not in STATES:
        return False
    # Forward by exactly one step. Skipping is how a candidate reaches LIVE without a lockbox
    # pass; nothing legitimate needs it, and the one thing that would is the bug this prevents.
    return STATES.index(to_state) == STATES.index(from_state) + 1


def transition(artifact: ResearchArtifact, to_state: str, *,
               evidence: str, actor: str = "system",
               failure_class: str = "") -> ResearchArtifact:
    """The ONLY legal way to move an artifact. Returns a new artifact; never mutates.

    EVIDENCE IS REQUIRED, not optional and not defaulted. A state change nobody can justify later
    is exactly how this desk ended up with sleeves marked LIVE in one registry and unknown in
    another. If there is no evidence to cite, the transition has not been earned.
    """
    if not evidence or not evidence.strip():
        raise TransitionError(
            f"{artifact.artifact_id}: {artifact.status} -> {to_state} refused, no evidence "
            f"cited. Every transition must name what justified it or it cannot be audited.")
    if not _legal(artifact.status, to_state):
        nxt = "terminal only"
        if artifact.status in STATES:
            i = STATES.index(artifact.status) + 1
            if i < len(STATES):
                nxt = STATES[i]
        raise TransitionError(
            f"{artifact.artifact_id}: {artifact.status} -> {to_state} is not on the state graph. "
            f"Legal next: {nxt}, or any of {TERMINAL}. Skipping stages is how a candidate "
            f"reaches LIVE without a lockbox pass.")
    if failure_class and failure_class not in FAILURE_CLASSES:
        raise TransitionError(
            f"failure_class={failure_class!r} is not one of {FAILURE_CLASSES}. An unclassified "
            f"failure teaches the search nothing, and a power failure misfiled as a validity "
            f"failure teaches it something false.")

    entry = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
             "from": artifact.status, "to": to_state, "actor": actor,
             "evidence": evidence, "failure_class": failure_class or None}
    return replace(artifact, status=to_state,
                   failure_class=failure_class or artifact.failure_class,
                   history=(*artifact.history, entry))


def new_artifact(hypothesis_id: str, **kw: Any) -> ResearchArtifact:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    seed = f"{hypothesis_id}|{now}|{kw.get('semantic_coordinate', '')}"
    aid = "A-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
    return ResearchArtifact(artifact_id=aid, hypothesis_id=hypothesis_id,
                            created_at=now, **kw)


def teaches_against_mechanism(failure_class: str) -> bool:
    """Should this failure lower the posterior for its mechanism's region?

    Only validity failures. An underpowered or regime-unstable result is evidence about the TEST,
    and letting it reduce a region's posterior is how a desk abandons a good mechanism for having
    been tested too little -- the exact error that produced seven "confidently barren" families
    from a validator later found broken in four ways.
    """
    return failure_class in VALIDITY_FAILURES


def to_record(a: ResearchArtifact) -> dict[str, Any]:
    d = asdict(a)
    d["fingerprint"] = a.fingerprint()
    return d
