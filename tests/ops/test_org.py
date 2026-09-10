"""Work that cannot be done must reach a person, and the ways that quietly fails.

WHAT WAS MISSING. The queue is durable and the worker claims from it, but neither knows who is
RESPONSIBLE. A task that exhausts its attempts goes DEAD and is never mentioned again -- so the
failure mode of the desk's own machinery is silence. That is the failure this desk keeps having:
`monitor_mt5_shadow_sync` returned FAILED every thirty minutes for ten days into a timer whose
exit code nobody read, and a gateway wrote no state for 24 days while the board said LATE.

THE LOAD-BEARING TEST IS `test_a_dead_task_reaches_a_person`. Everything else here is routing
bookkeeping; that one is the property the file exists for, and it is false for a queue with a
nice org chart bolted on.

THE ROSTER IS CHECKED, NOT ASSUMED, because every way it can be wrong fails silently at runtime:

    an UNOWNED kind queues and is never claimed, and reads on every census as a busy queue;
    a DOUBLY-OWNED kind is two roles racing with no rule for who wins;
    a CYCLE in the escalation chain is the worst -- a dead task circles between two roles
    forever, each hop looking like progress, and it never reaches anyone who can act.

A roster is trustworthy only if all three are impossible, so `validate` is tested against each.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.org import (  # noqa: E402
    ESCALATION_KIND,
    FROM_KEY,
    PARENT_KEY,
    Org,
    Role,
    desk_org,
)
from libs.ops.task_queue import TaskQueue  # noqa: E402


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


def _org() -> Org:
    return Org.from_roles([
        Role("worker_role", ("dig",), "boss", "does the digging"),
        Role("boss", ("plan",), "chief", "assigns the digging"),
        Role("chief", ("decide",), "", "answers to nobody -- a person reads here"),
    ])


# ------------------------------------------------------------------- THE ACCOUNTABILITY RULE
def test_a_dead_task_reaches_a_person(q) -> None:
    """THE POINT OF THE FILE. A task nobody could do travels UP until it reaches a role that
    answers to nobody. Without this it goes DEAD, the census counts it, and the work silently
    never happens."""
    org = _org()
    t = q.submit("dig", max_attempts=1)
    q.claim("w")
    q.fail(t.id, "w", why="the ground is frozen")
    assert q.tasks()[t.id].state == "DEAD"

    raised = org.escalate(q, q.tasks()[t.id])
    assert raised is not None and raised.kind == f"{ESCALATION_KIND}:boss"
    assert raised.payload["failed_kind"] == "dig"
    assert raised.payload["why"] == "the ground is frozen"
    assert raised.payload[PARENT_KEY] == t.id, "the escalation lost the task that caused it"


def test_the_top_role_escalates_nowhere_and_that_is_declared(q) -> None:
    """Inventing a supervisor for the top role would put the failure back into the machine that
    could not handle it."""
    org = _org()
    t = q.submit("decide", max_attempts=1)
    q.claim("w")
    q.fail(t.id, "w", why="needs a human")
    assert org.escalate(q, q.tasks()[t.id]) is None
    got = org.sweep_dead(q)
    assert got["not_escalated"] == [t.id] and "answers to nobody" in got["why"]


def test_the_sweep_escalates_each_failure_exactly_once(q) -> None:
    """Idempotent by dedupe key, the same watermark discipline the event drain uses: running it
    every pass must not queue the same failure hourly forever."""
    org = _org()
    t = q.submit("dig", max_attempts=1)
    q.claim("w")
    q.fail(t.id, "w", why="frozen")
    assert org.sweep_dead(q)["escalated"] == [t.id]
    assert org.sweep_dead(q)["escalated"] == [], "the same death escalated twice"
    assert sum(1 for x in q.tasks().values() if x.kind.startswith(ESCALATION_KIND)) == 1


def test_an_escalation_is_never_itself_escalated(q) -> None:
    """Otherwise a failure at the top of the chain generates escalations forever."""
    org = _org()
    t = q.submit("dig", max_attempts=1)
    q.claim("w")
    q.fail(t.id, "w", why="frozen")
    org.sweep_dead(q)
    esc = next(x for x in q.tasks().values() if x.kind.startswith(ESCALATION_KIND))
    q.claim("boss-worker", kinds=[esc.kind])
    q.fail(esc.id, "boss-worker", why="also stuck")
    while q.tasks()[esc.id].state != "DEAD":
        q.claim("boss-worker", kinds=[esc.kind])
        q.fail(esc.id, "boss-worker", why="also stuck")
    assert org.sweep_dead(q)["escalated"] == []


# ----------------------------------------------------------------- the roster must be routable
def test_a_kind_nobody_owns_is_refused_rather_than_queued(q) -> None:
    """It would sit READY forever and read on every census as a busy queue."""
    org = _org()
    assert org.delegate(q, "nobody_owns_this", frm="boss") is None
    assert not q.tasks(), "unowned work was queued anyway"


def test_two_roles_owning_one_kind_is_a_named_defect() -> None:
    org = Org.from_roles([
        Role("a", ("dig",), "top", ""), Role("b", ("dig",), "top", ""),
        Role("top", (), "", ""),
    ])
    (problem,) = [p for p in org.validate() if "dig" in p]
    assert "racing" in problem and "'a'" in problem and "'b'" in problem


def test_an_escalation_cycle_is_refused() -> None:
    """THE WORST ROSTER BUG. A dead task circles between two roles forever and every hop looks
    like progress, so the queue is busy and nothing reaches anyone."""
    org = Org.from_roles([
        Role("a", ("dig",), "b", ""), Role("b", ("plan",), "a", ""),
    ])
    problems = org.validate()
    assert any("cycles" in p for p in problems)
    assert any("answers to nobody" in p for p in problems), (
        "a roster where every path loops has no human at the end and must say so")


def test_escalating_to_a_role_that_does_not_exist_is_a_named_defect() -> None:
    org = Org.from_roles([Role("a", ("dig",), "ghost", ""), Role("top", (), "", "")])
    assert any("is not a role" in p and "reaches nobody" in p for p in org.validate())


# --------------------------------------------------------------------------- delegation
def test_delegated_work_records_where_it_came_from(q) -> None:
    """A result has to be traceable to the question that caused it."""
    org = _org()
    parent = q.submit("plan")
    child = org.delegate(q, "dig", frm="boss", parent=parent, payload={"site": "north"})
    assert child is not None
    assert child.payload["site"] == "north"
    assert child.payload[FROM_KEY] == "boss" and child.payload[PARENT_KEY] == parent.id
    assert org.lineage(q, child.id) == [child.id, parent.id]


def test_lineage_terminates_even_if_a_payload_points_at_itself(q) -> None:
    """A malformed parent link must not hang the census."""
    org = _org()
    t = q.submit("dig")
    row = dict(q.tasks()[t.id].to_dict())
    row["payload"] = {PARENT_KEY: t.id}
    q._append(row)
    assert org.lineage(q, t.id) == [t.id]


def test_a_role_knows_which_kinds_its_worker_should_take(q) -> None:
    """This is what a Worker is constructed with, so a role and its worker cannot drift apart."""
    org = _org()
    assert org.kinds_for("worker_role") == ("dig",)
    assert org.kinds_for("no_such_role") == ()
    assert org.owner_of("dig").name == "worker_role"
    assert org.supervisor_of("worker_role").name == "boss"
    assert org.supervisor_of("chief") is None


# ------------------------------------------------------------------ what a person reads
def test_the_census_names_work_nobody_owns(q) -> None:
    org = _org()
    q.submit("dig")
    q.submit("orphan_kind")
    c = org.census(q)
    assert c["unowned_kinds"] == ["orphan_kind"]
    assert c["roles"]["worker_role"]["open"] == 1
    assert c["roles"]["chief"]["answers_to"].startswith("(nobody")
    assert "never claimed" in c["why"]


# ------------------------------------------------------------------------ the desk's roster
def test_the_desks_own_roster_is_routable() -> None:
    """Constructed through `desk_org`, which refuses a chart that cannot route -- so this cannot
    pass while the shipped roster is broken."""
    org = desk_org()
    assert org.validate() == []
    tops = [r.name for r in org.roles.values() if r.is_top]
    assert tops == ["ops"], "exactly one role must answer to nobody, and it is where a person reads"


def test_every_desk_role_reaches_the_top() -> None:
    """Not implied by 'no cycles': a role could escalate into a chain that stops at a role which
    is not the top."""
    org = desk_org()
    for name in org.roles:
        hops, cur = 0, name
        while org.roles[cur].escalates_to:
            cur = org.roles[cur].escalates_to
            hops += 1
            assert hops < len(org.roles) + 1, f"{name} never terminates"
        assert org.roles[cur].is_top, f"{name} escalates to {cur!r}, which is not the top"


def test_the_desk_separates_deciding_capital_from_acting_on_it() -> None:
    """`portfolio` decides what gets capital and `execution` acts. A research role able to raise
    its own limits is the arrangement every one of the reviewed architectures warns about."""
    org = desk_org()
    assert "allocate" in org.roles["portfolio"].kinds
    assert "allocate" not in org.roles["execution"].kinds
    assert "allocate" not in org.roles["research"].kinds
    assert org.owner_of("place").name == "execution"
