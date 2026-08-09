"""AGENT AUTHORITY — model intelligence is not model authority.

THE PRINCIPLE, AND IT IS THE WHOLE MODULE. A better model does not get more permissions. Capability
and authority are separate axes, and the failure this prevents is the quiet one: a seat is upgraded
for good reasons, nobody re-derives what it is allowed to touch, and six weeks later something with
research-grade judgement has order authority nobody ever granted it. `escalate` therefore refuses a
level change justified by capability, and says so in those words.

**THE LADDER.** Every autonomous component sits at exactly one level, and each rung names what it
may reach:

    L0 PUBLIC_READ          public data only. The GPT hunter lives here and needs nothing more.
    L1 PRIVATE_READ         the desk's own datasets and artifacts, read-only.
    L2 RESEARCH_COMPUTE     may run studies and write research artifacts.
    L3 SHADOW_ACTION        may emit signals that are recorded and never sent.
    L4 CANARY_PROPOSAL      may PROPOSE an order. Cannot send one.
    L5 LIMITED_EXECUTION    may send orders inside a hard, pre-agreed cap.
    L6 NORMAL_EXECUTION     may send capital-sensitive orders.

**PROMOTION NEEDS EVIDENCE THAT THE LEVEL ITSELF WAS EARNED**, and one rung at a time. A skipped
rung is refused rather than warned about, for the same reason `libs/research/alpha_state.py` refuses
a skipped evidence rung: an undone thing and an impossible thing look identical until the morning
they do not.

**BLAST RADIUS IS THE OTHER HALF.** A permission level says what a component may do when working.
Blast radius says what it destroys when wrong -- and those are different questions, which is why a
component is sized by the SECOND. Minimum privilege is not "as little as possible"; it is the least
that still lets the component earn what it earns, and `least_privilege_gap` reports the difference
between what a seat holds and what its work actually requires.

**WHAT THIS MODULE DOES NOT DO, DELIBERATELY.** It grants nothing, signs nothing and cannot enable
trading. It is a description of policy that can be checked in CI, so that a drift between the
intended grant and the actual one becomes a test failure instead of an incident. Arming live
trading remains the principal's act, and `scripts/run_deadman_switch.py` is untouched by anything
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CAPITAL_SENSITIVE",
    "LEVELS",
    "AgentGrant",
    "BlastRadius",
    "escalate",
    "least_privilege_gap",
    "level_index",
    "permitted",
    "summarise",
]

#: Ordered least to most dangerous. Index is the authority; the names are for humans.
LEVELS: tuple[str, ...] = (
    "L0_PUBLIC_READ",
    "L1_PRIVATE_READ",
    "L2_RESEARCH_COMPUTE",
    "L3_SHADOW_ACTION",
    "L4_CANARY_PROPOSAL",
    "L5_LIMITED_EXECUTION",
    "L6_NORMAL_EXECUTION",
)

#: At and above this rung an agent can move money. Everything here is the principal's to grant.
CAPITAL_SENSITIVE: frozenset[str] = frozenset({"L5_LIMITED_EXECUTION", "L6_NORMAL_EXECUTION"})


def level_index(level: str) -> int:
    if level not in LEVELS:
        raise ValueError(f"unknown authority level {level!r}; the ladder is {LEVELS}")
    return LEVELS.index(level)


@dataclass(frozen=True)
class BlastRadius:
    """What this component destroys when it is WRONG, not what it does when it is right."""

    #: Has anyone actually ASSESSED this component's blast radius? Separate from the numbers on
    #: purpose. A read-only hunter genuinely has zero financial blast radius, and inferring
    #: "unmeasured" from a zero would flag the safest component on the desk as the least known --
    #: which trains the reader to ignore the field. Zero is an answer; silence is not.
    assessed: bool = False
    #: Worst-case loss as a fraction of portfolio equity if the component misbehaves for a full
    #: cycle before anyone notices. Meaningful only when `assessed`.
    financial: float = 0.0
    #: Largest position it could open or fail to close, same units.
    position: float = 0.0
    #: Can it destroy or corrupt data that cannot be re-acquired? Recorder output, for instance.
    irrecoverable_data: bool = False
    #: Can it stop other components from running?
    operational: bool = False
    #: Can its failure propagate -- can it grant, spawn or instruct another component?
    propagation: bool = False
    #: Is it confined to an isolated sub-account / withdrawal-disabled key / scoped tool set?
    sandboxed: bool = True

    @property
    def measured(self) -> bool:
        return self.assessed

    @property
    def severity(self) -> str:
        if not self.assessed:
            return "UNMEASURED"
        if self.propagation or self.irrecoverable_data:
            return "UNBOUNDED"
        if self.financial >= 0.10:
            return "SEVERE"
        if self.financial >= 0.01:
            return "MATERIAL"
        if self.financial > 0.0 or self.position > 0.0:
            return "CONTAINED"
        return "NONE"


@dataclass(frozen=True)
class AgentGrant:
    """One component's authority, and the evidence that earned it."""

    agent_id: str
    level: str = "L0_PUBLIC_READ"
    #: The highest level this component's WORK actually requires. If it is below `level`, the
    #: component is over-privileged and the gap is pure downside.
    level_required_by_work: str = "L0_PUBLIC_READ"
    blast: BlastRadius = field(default_factory=BlastRadius)
    #: Independently verified evidence supporting the CURRENT level. Free text, one per check.
    evidence: tuple[str, ...] = field(default_factory=tuple)
    #: Set when the principal personally granted a capital-sensitive rung. Nothing automated may
    #: set this, and nothing in this repository does.
    principal_authorised: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        level_index(self.level)
        level_index(self.level_required_by_work)

    @property
    def capital_sensitive(self) -> bool:
        return self.level in CAPITAL_SENSITIVE


def permitted(grant: AgentGrant, action_level: str) -> tuple[bool, str]:
    """May this component take an action requiring `action_level`? FAIL CLOSED on anything odd."""
    need = level_index(action_level)
    have = level_index(grant.level)
    if need > have:
        return False, (
            f"{grant.agent_id} holds {grant.level} and the action needs {action_level}. REFUSED. "
            "A component that can do more than it was granted is the incident, not the capability")
    if action_level in CAPITAL_SENSITIVE and not grant.principal_authorised:
        return False, (
            f"{grant.agent_id} nominally holds {grant.level}, but {action_level} is "
            "CAPITAL-SENSITIVE and carries no principal authorisation. REFUSED -- arming live "
            "trading is the principal's act and cannot be reached by configuration")
    return True, f"{grant.agent_id}: {action_level} is within {grant.level}"


def escalate(grant: AgentGrant, *, to_level: str, evidence: tuple[str, ...],
             capability_improved: bool = False) -> tuple[AgentGrant | None, str]:
    """Promote one rung, on evidence about the RUNG. Returns None when refused.

    `capability_improved` exists so the wrong reason can be named explicitly rather than merely
    being absent. A smarter model is the single most common argument for more authority and the
    single worst one: nothing about a better research seat demonstrates that it should be able to
    send an order.
    """
    have, want = level_index(grant.level), level_index(to_level)
    if want <= have:
        return None, (f"{grant.agent_id}: {to_level} is not above {grant.level}. Use a direct "
                      "demotion for reductions -- this function only promotes")
    if want != have + 1:
        return None, (
            f"{grant.agent_id}: {grant.level} -> {to_level} skips "
            f"{LEVELS[have + 1:want]}. REFUSED. A skipped rung is not a faster promotion, it is an "
            "ungoverned one, and the rungs exist because each names a different failure")
    if not evidence:
        return None, (f"{grant.agent_id}: no evidence offered for {to_level}. REFUSED -- an "
                      "authority level granted without evidence is a level nobody can defend "
                      "later, including the person who granted it")
    if to_level in CAPITAL_SENSITIVE and not grant.principal_authorised:
        return None, (
            f"{grant.agent_id}: {to_level} is CAPITAL-SENSITIVE. REFUSED without the principal's "
            "own authorisation -- no amount of evidence promotes a component into being able to "
            "move money, because that decision is not a technical one")
    return (AgentGrant(agent_id=grant.agent_id, level=to_level,
                       level_required_by_work=grant.level_required_by_work,
                       blast=grant.blast, evidence=grant.evidence + tuple(evidence),
                       principal_authorised=grant.principal_authorised, notes=grant.notes),
            f"{grant.agent_id}: {grant.level} -> {to_level} on {len(evidence)} new piece(s) of "
            f"evidence"
            + (". Note that capability also improved; that was NOT the reason and must never be"
               if capability_improved else ""))


def least_privilege_gap(grant: AgentGrant) -> tuple[int, str]:
    """Rungs held above what the work needs. Zero is the target; the gap is pure downside.

    Over-privilege buys nothing. The component does exactly the same work at the lower rung, and
    the only difference is the size of the hole when it is wrong.
    """
    gap = level_index(grant.level) - level_index(grant.level_required_by_work)
    if gap <= 0:
        return 0, (f"{grant.agent_id}: holds {grant.level}, work needs "
                   f"{grant.level_required_by_work} -- no excess authority")
    return gap, (
        f"{grant.agent_id}: holds {grant.level} but its work only needs "
        f"{grant.level_required_by_work} -- {gap} rung(s) of EXCESS authority. It would do "
        f"identical work at {grant.level_required_by_work}, so the gap buys nothing and widens "
        "the hole when something goes wrong"
        + (f". Severity if wrong: {grant.blast.severity}"
           if grant.blast.severity != "UNMEASURED" else
           ". Blast radius is UNMEASURED, so the cost of that gap is unknown, not small"))


def summarise(grants: list[AgentGrant]) -> dict[str, object]:
    """Report shape. Names every over-privileged seat and every unmeasured blast radius."""
    if not grants:
        return {"measured": False, "agents": 0, "headline": (
            "no agent authority declared -- which components may reach which surfaces is "
            "UNMEASURED. That is not a permissive state, it is an unknown one, and it is exactly "
            "the state in which an upgrade quietly widens what something is allowed to touch")}
    rows = []
    for g in grants:
        gap, gwhy = least_privilege_gap(g)
        rows.append({
            "agent_id": g.agent_id, "level": g.level,
            "level_required_by_work": g.level_required_by_work,
            "excess_rungs": gap, "gap_why": gwhy,
            "capital_sensitive": g.capital_sensitive,
            "principal_authorised": g.principal_authorised,
            "blast_severity": g.blast.severity,
            "sandboxed": g.blast.sandboxed,
            "evidence_count": len(g.evidence),
        })
    over = [r for r in rows if int(str(r["excess_rungs"])) > 0]
    unmeasured = [r["agent_id"] for r in rows if r["blast_severity"] == "UNMEASURED"]
    unbounded = [r["agent_id"] for r in rows if r["blast_severity"] == "UNBOUNDED"]
    unauthorised = [r["agent_id"] for r in rows
                    if r["capital_sensitive"] and not r["principal_authorised"]]
    unsandboxed = [r["agent_id"] for r in rows if not r["sandboxed"]]
    return {
        "measured": True,
        "agents": len(grants),
        "rows": rows,
        "over_privileged": [r["agent_id"] for r in over],
        "unmeasured_blast_radius": unmeasured,
        "unbounded_blast_radius": unbounded,
        "capital_sensitive_without_principal": unauthorised,
        "not_sandboxed": unsandboxed,
        "headline": (
            f"{len(grants)} component(s); {len(over)} hold authority above what their work needs"
            + (f" ({[r['agent_id'] for r in over]})" if over else "")
            + (f"; {len(unauthorised)} sit on a CAPITAL-SENSITIVE rung with no principal "
               f"authorisation {unauthorised} -- these must be refused at the call site"
               if unauthorised else "")
            + (f"; blast radius UNMEASURED for {unmeasured}" if unmeasured else "")),
        "note": ("Model intelligence is not model authority: a capability upgrade never promotes a "
                 "component, and `escalate` refuses a level change argued from capability. "
                 "Promotion is one rung at a time on evidence about that rung, and no evidence "
                 "reaches a capital-sensitive rung without the principal. This module describes "
                 "and checks policy -- it grants nothing, signs nothing, and cannot arm trading."),
    }
