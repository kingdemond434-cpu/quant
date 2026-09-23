"""Who owns this work, who they answer to, and what happens when nobody can do it.

THE GAP THIS CLOSES. The queue is durable and the worker claims from it, but neither knows who is
RESPONSIBLE for anything. A task is claimed by whichever worker asks first, and a task that
exhausts its attempts goes DEAD and is never mentioned again -- so the failure mode of this desk's
own research machinery is silence, which is the failure mode it has had all along
(`monitor_mt5_shadow_sync` returned FAILED every thirty minutes for ten days into a timer whose
exit code nobody read; a gateway wrote no state for 24 days while the board said LATE).

An external review of this desk put it precisely: it has far more quantitative machinery than the
agent-orchestration products it was compared against, and less of "a persistent employee with an
inbox, a responsibility, a task status and an escalation path". This file is that half, and only
that half -- it adds no intelligence, it assigns accountability.

THREE THINGS, AND THE THIRD IS THE POINT:

    OWNERSHIP    a task KIND belongs to exactly one role. Two roles owning one kind is a race
                 with a rota; none owning it is work that arrives and is never done. Both are
                 reported as defects rather than resolved by picking a winner.

    DELEGATION   a role creates work for another role and the child records its parent, so a
                 result can be traced back to the question that caused it.

    ESCALATION   THE ONE THAT MATTERS. A task that reaches DEAD does not vanish; it becomes a
                 task for the owner's supervisor, carrying the reason it died. Work that cannot
                 be done travels UP until it reaches a role that answers to nobody -- which on
                 this desk is the human. Nothing is allowed to fail quietly.

THE CHAIN MUST TERMINATE, and `validate` refuses a roster where it does not. An escalation cycle
is worse than no escalation: a dead task circles between two roles forever, each escalation
looking like progress, and it never reaches anyone who can act.

NO SCHEDULING, NO EXECUTION, NO INTELLIGENCE. The queue stores, the worker runs, this decides
who. Keeping them apart is what lets each be tested for one property.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.ops.task_queue import Task, TaskQueue

#: The payload key carrying the task this one was delegated from. Read by `lineage`.
PARENT_KEY = "_parent_task"
#: The payload key carrying the role that delegated it.
FROM_KEY = "_from_role"
#: Kind prefix an escalation takes, so an escalated task is never mistaken for fresh work.
ESCALATION_KIND = "escalation"

#: Where a failure goes when its owner answers to nobody. NO ROLE OWNS THIS, deliberately: no
#: worker can claim it, so it sits in the queue and on the census until a person acts on it.
#:
#: THE FIRST DRAFT STOPPED INSTEAD (bug, caught by `test_a_wiring_task_that_dies_reaches_a_person`
#: 2026-09-10). `escalate` returned None when the owner was the top role, on the reasoning that
#: inventing a supervisor puts the failure back into the machine that could not handle it. That
#: reasoning is right and the conclusion was wrong: work owned by the TOP role -- which on this
#: desk includes every wiring task -- then died with no record at all. "Answers to nobody" has to
#: mean REACHES A PERSON; it cannot mean stops here, or the top of the chart is a place failures
#: go to be forgotten, which is the defect this whole file was written against.
HUMAN_INBOX = f"{ESCALATION_KIND}:human"


@dataclass(frozen=True)
class Role:
    """One accountable position: what it owns, and who it answers to."""

    name: str
    kinds: tuple[str, ...]
    escalates_to: str
    why: str

    @property
    def is_top(self) -> bool:
        """A role answering to nobody. On this desk that is where a human reads."""
        return not self.escalates_to


@dataclass
class Org:
    """A roster of roles and the routing rules derived from it."""

    roles: dict[str, Role] = field(default_factory=dict)

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_roles(cls, roles: list[Role]) -> Org:
        return cls(roles={r.name: r for r in roles})

    def validate(self) -> list[str]:
        """Every way a roster can be wrong, named. Empty means it can be trusted.

        Checked rather than assumed because each of these fails SILENTLY at runtime: an unowned
        kind is work that queues and is never claimed, a doubly-owned kind is two roles racing,
        and a cycle is a dead task circling forever while every hop looks like progress.
        """
        problems: list[str] = []
        seen: dict[str, str] = {}
        for role in self.roles.values():
            for kind in role.kinds:
                if kind in seen:
                    problems.append(
                        f"kind {kind!r} is owned by both {seen[kind]!r} and {role.name!r}: two "
                        f"roles racing for the same work, with no rule for who wins")
                seen[kind] = role.name
            if role.escalates_to and role.escalates_to not in self.roles:
                problems.append(f"{role.name!r} escalates to {role.escalates_to!r}, which is not "
                                f"a role: work that dies here reaches nobody")
        tops = [r.name for r in self.roles.values() if r.is_top]
        if self.roles and not tops:
            problems.append("no role answers to nobody: every escalation path is a loop, so work "
                            "that cannot be done never reaches a human")
        for role in self.roles.values():
            seen_names, cur = {role.name}, role
            while cur.escalates_to and cur.escalates_to in self.roles:
                if cur.escalates_to in seen_names:
                    problems.append(
                        f"escalation from {role.name!r} cycles through {cur.escalates_to!r}: a "
                        f"dead task circles forever and every hop looks like progress")
                    break
                seen_names.add(cur.escalates_to)
                cur = self.roles[cur.escalates_to]
        return problems

    # ------------------------------------------------------------------ routing
    def owner_of(self, kind: str) -> Role | None:
        for role in self.roles.values():
            if kind in role.kinds:
                return role
        return None

    def kinds_for(self, role_name: str) -> tuple[str, ...]:
        """What a worker running as this role should pass to `Worker(kinds=...)`."""
        role = self.roles.get(role_name)
        return role.kinds if role else ()

    def supervisor_of(self, role_name: str) -> Role | None:
        role = self.roles.get(role_name)
        if role is None or role.is_top:
            return None
        return self.roles.get(role.escalates_to)

    # ------------------------------------------------------------------ work
    def delegate(self, queue: TaskQueue, kind: str, *, frm: str = "",
                 payload: dict[str, Any] | None = None, parent: Task | None = None,
                 priority: float = 0.0, dedupe_key: str = "") -> Task | None:
        """Create work for whichever role owns `kind`, recording where it came from.

        REFUSES AN UNOWNED KIND rather than queueing it. A task nobody owns is claimed by nobody
        and sits READY forever, which reads on every census as a busy queue.
        """
        if self.owner_of(kind) is None:
            return None
        body = dict(payload or {})
        if frm:
            body[FROM_KEY] = frm
        if parent is not None:
            body[PARENT_KEY] = parent.id
        return queue.submit(kind, payload=body, priority=priority, dedupe_key=dedupe_key)

    def escalate(self, queue: TaskQueue, task: Task, *, why: str = "") -> Task | None:
        """Hand a task that could not be done to the owner's supervisor.

        THE ACCOUNTABILITY RULE. Without this a DEAD task is simply gone: the queue's census
        counts it, nobody is told, and the work silently never happens. With it, failure travels
        up until it reaches a role that answers to nobody -- and on this desk that is a person.

        A task whose owner is the TOP role goes to `HUMAN_INBOX` rather than to another role: no
        worker owns that kind, so it cannot be claimed, and it stays on the queue and the census
        until a person acts. Inventing a supervisor would put the failure back into the machine
        that could not handle it; stopping would lose it entirely, which is worse.
        """
        owner = self.owner_of(task.kind)
        if owner is None:
            return None
        boss = self.supervisor_of(owner.name)
        body = dict(task.payload)
        body.update({
            PARENT_KEY: task.id,
            FROM_KEY: owner.name,
            "failed_kind": task.kind,
            "attempts": task.attempts,
            "why": why or task.why,
        })
        if boss is None:
            body["needs"] = (f"a person: {owner.name!r} answers to nobody, so this failure has "
                             f"nowhere further to go inside the machine")
        return queue.submit(f"{ESCALATION_KIND}:{boss.name}" if boss else HUMAN_INBOX,
                            payload=body, priority=max(task.priority, 1.0),
                            dedupe_key=f"{ESCALATION_KIND}:{task.id}")

    def sweep_dead(self, queue: TaskQueue) -> dict[str, Any]:
        """Escalate every DEAD task that has not been escalated yet. Idempotent.

        ONCE MEANS EVER, AND `submit`'s DEDUPE IS NOT ENOUGH (bug, caught by
        `test_an_escalation_is_never_itself_escalated`). The queue collapses a dedupe key only
        against LIVE work -- deliberately, so a nightly task named by its date runs again
        tomorrow. Applied here that is wrong in a way that loops: once the escalation ITSELF
        reached DEAD, the key stopped collapsing, the original failure was escalated again, and
        the pair regenerated each other every sweep forever.
        So the marker is existence, not liveness: an escalation carrying this task's id is proof
        it has been raised, whatever became of it afterwards.
        """
        tasks = queue.tasks()
        already = {t.dedupe_key for t in tasks.values() if t.dedupe_key.startswith(ESCALATION_KIND)}
        raised: list[str] = []
        skipped: list[str] = []
        for t in tasks.values():
            if t.state != "DEAD" or t.kind.startswith(ESCALATION_KIND):
                continue
            if f"{ESCALATION_KIND}:{t.id}" in already:
                continue
            got = self.escalate(queue, t)
            (raised if got is not None else skipped).append(t.id)
        return {"escalated": raised, "not_escalated": skipped,
                "needs_person": [t for t in raised
                                 if queue.tasks() and any(
                                     x.payload.get(PARENT_KEY) == t and x.kind == HUMAN_INBOX
                                     for x in queue.tasks().values())],
                "why": ("a failure whose owner answers to nobody goes to HUMAN_INBOX, which no "
                        "role owns and no worker can claim -- so it stays on the queue and the "
                        "census until a person acts, rather than stopping at the top of the "
                        "chart where failures would go to be forgotten")}

    # ------------------------------------------------------------------ what a person reads
    def lineage(self, queue: TaskQueue, task_id: str) -> list[str]:
        """The chain of task ids from `task_id` back to the work that caused it."""
        tasks, chain, seen = queue.tasks(), [], set()
        cur = tasks.get(task_id)
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            chain.append(cur.id)
            nxt = cur.payload.get(PARENT_KEY)
            cur = tasks.get(str(nxt)) if nxt else None
        return chain

    def census(self, queue: TaskQueue) -> dict[str, Any]:
        """Who owns what, what is open against each role, and what nobody owns."""
        tasks = list(queue.tasks().values())
        by_role: dict[str, dict[str, Any]] = {}
        for name, role in sorted(self.roles.items()):
            mine = [t for t in tasks if t.kind in role.kinds]
            by_role[name] = {
                "owns": list(role.kinds),
                "answers_to": role.escalates_to or "(nobody -- a person reads here)",
                "open": sum(1 for t in mine if t.state in ("READY", "LEASED")),
                "dead": sum(1 for t in mine if t.state == "DEAD"),
            }
        unowned = sorted({t.kind for t in tasks
                          if self.owner_of(t.kind) is None
                          and not t.kind.startswith(ESCALATION_KIND)})
        return {"roles": by_role, "unowned_kinds": unowned,
                "problems": self.validate(),
                "why": ("a kind nobody owns queues and is never claimed, which reads on every "
                        "other census as a busy queue")}


#: THE DESK'S OWN ROLES, named after the organs that already exist rather than after a generic
#: org chart. Each `kinds` entry is a task kind the queue can carry; the roles are the ones this
#: desk's pipeline already has, so the roster describes the machine instead of proposing a new one.
DESK_ROLES: tuple[Role, ...] = (
    Role("research", ("generate", "mine", "compile", "deepen"), "portfolio",
         "hypothesis production: the miners, the compiler, the deepening worker"),
    Role("validation", ("gauntlet", "certify", "recertify"), "portfolio",
         "the gauntlet and the certificate: idea creation is deliberately not idea validation"),
    Role("adversary", ("falsify", "red_team"), "portfolio",
         "kill the champion -- an inventor evaluating their own idea is not a test"),
    Role("portfolio", ("allocate", "admit", "retire"), "ops",
         "marginal E[log W], heat, retirement: the only role that decides what gets capital"),
    Role("execution", ("place", "manage", "reconcile"), "ops",
         "the gateway lane: it acts on decisions and makes none"),
    # `retire_module` is deliberately NOT `retire`: that kind belongs to `portfolio` and means
    # pulling capital from a decayed sleeve. Deleting dead code and de-allocating capital are not
    # the same act, and one kind cannot carry both -- the roster would accept the collision, and
    # the routing would be silently wrong in the direction that touches money.
    Role("ops", ("wire", "retire_module", "adopt", "heal", ESCALATION_KIND + ":ops"), "",
         "the machine itself -- and it answers to nobody, which is where a person reads"),
)


def desk_org() -> Org:
    """The desk's roster, validated at construction so a broken chart cannot be used."""
    org = Org.from_roles(list(DESK_ROLES))
    problems = org.validate()
    if problems:
        raise ValueError("the desk roster is not routable: " + "; ".join(problems))
    return org
