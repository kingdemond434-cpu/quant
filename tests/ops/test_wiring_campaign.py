"""A census that nothing acts on is a number that gets larger.

THE STEP BEING TESTED is the one between measuring and fixing. `wiring_audit` says 118 modules are
unreachable; this turns the worst of them into durable, OWNED tasks with a supervisor above each,
so a finding cannot be produced hourly and ignored indefinitely -- which is the shape every
long-running failure on this desk has taken.

IT IS ALSO THE FIRST PRODUCER THE QUEUE HAS EVER HAD. `task_queue`, `worker` and `org` were each
built and left unwired, which is precisely the defect the audit exists to find, occurring in the
modules written to fix it. These tests are what stop that being true a second time.

THE COLLISION TEST IS THE IMPORTANT ONE. `retire` was already owned by the PORTFOLIO role and
means pulling capital from a decayed sleeve. Queueing module cleanup under that name would have
routed "delete some dead code" to the organ that de-allocates capital -- and the roster would have
accepted it, because one kind can have exactly one owner and nothing checks that two callers mean
the same thing by it. The kind namespace is shared, so a collision is silent by construction and a
test is the only thing that can see it.

WHAT IS DELIBERATELY NOT TESTED, because it is deliberately not done: this does not edit code. A
wiring fix is a choice of consumer and call site, and for most findings that is a design decision
rather than a mechanical one -- `libs.research.alpha_rl` is an 880-line Q-learner, and the
question is not which line calls it but at what cadence, on what budget, feeding what. Queueing
the decision with its evidence attached is the honest automation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.org import ESCALATION_KIND, desk_org  # noqa: E402
from libs.ops.task_queue import TaskQueue  # noqa: E402
from libs.ops.wiring_audit import Finding  # noqa: E402
from libs.ops.wiring_campaign import (  # noqa: E402
    MONEY_KEY,
    RETIRE_KIND,
    WIRE_KIND,
    enqueue,
    priority_of,
    progress,
    run,
)


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


def _f(module: str, *, lines: int = 100, tested: bool = True, money: bool = False,
       kind: str = "no_importer", verdict: str = "WIRE") -> Finding:
    return Finding(module=module, kind=kind, verdict=verdict, why="because", lines=lines,
                   has_tests=tested, public=("go",), money_path=money)


# --------------------------------------------------------------- THE COLLISION THAT WAS SILENT
def test_module_retirement_is_not_the_kind_that_pulls_capital() -> None:
    """`retire` belongs to PORTFOLIO and means de-allocating a decayed sleeve. Deleting dead code
    is not that act, and one kind cannot carry both -- the roster accepts the collision and the
    routing is silently wrong in the direction that touches money."""
    org = desk_org()
    assert RETIRE_KIND != "retire"
    assert org.owner_of("retire").name == "portfolio"
    assert org.owner_of(RETIRE_KIND).name == "ops"
    assert org.owner_of(WIRE_KIND).name == "ops"


# ------------------------------------------------------------------------------ queueing
def test_the_worst_findings_are_queued_and_the_batch_bounds_it(q) -> None:
    found = [_f(f"libs.m{i}", lines=1000 - i) for i in range(20)]
    got = enqueue(q, found, batch=5)
    assert got["queued"] == [f"libs.m{i}" for i in range(5)]
    assert len(q.tasks()) == 5


def test_a_module_already_queued_is_not_queued_again(q) -> None:
    """The audit reports the same module every hour; the campaign must not queue it every hour."""
    found = [_f("libs.same")]
    assert enqueue(q, found, batch=5)["queued"] == ["libs.same"]
    second = enqueue(q, found, batch=5)
    assert second["queued"] == [] and "already live" in second["skipped"][0]
    assert len(q.tasks()) == 1


def test_a_module_becomes_queueable_again_once_its_task_is_finished(q) -> None:
    """Dedupe against LIVE work only -- otherwise a module that was wired badly and reverted could
    never be re-queued."""
    (t,) = [q.tasks()[i] for i in enqueue(q, [_f("libs.again")], batch=1) and q.tasks()]
    q.claim("w")
    q.complete(t.id, "w")
    assert enqueue(q, [_f("libs.again")], batch=1)["queued"] == ["libs.again"]


def test_the_evidence_travels_with_the_task(q) -> None:
    """A task that says only "wire libs.x" sends its worker back to the audit to find out why."""
    enqueue(q, [_f("libs.evidence", lines=880, money=True)], batch=1)
    (t,) = q.tasks().values()
    assert t.payload["module"] == "libs.evidence" and t.payload["lines"] == 880
    assert t.payload[MONEY_KEY] is True
    assert t.payload["public"] == ["go"] and t.payload["reason"]


def test_priority_ranks_investment_already_made(q) -> None:
    """Lines proxy investment, tests double it (a tested module can be wired AND verified), and a
    one-link-short row outranks a plain orphan of equal size because its alarm is already
    silenced -- nothing else will report it."""
    big, small = _f("libs.big", lines=900), _f("libs.small", lines=90)
    assert priority_of(big) > priority_of(small)
    assert priority_of(_f("libs.t", lines=100)) > priority_of(_f("libs.u", lines=100, tested=False))
    hidden = _f("libs.h", lines=100, kind="sole_importer_unreachable")
    assert priority_of(hidden) > priority_of(_f("libs.p", lines=100))


def test_the_two_verdicts_are_queued_under_different_kinds(q) -> None:
    enqueue(q, [_f("libs.w"), _f("libs.r", tested=False, verdict="RETIRE")], batch=5)
    kinds = {t.payload["module"]: t.kind for t in q.tasks().values()}
    assert kinds == {"libs.w": WIRE_KIND, "libs.r": RETIRE_KIND}


# --------------------------------------------------------------------------- accountability
def test_a_wiring_task_that_dies_reaches_a_person(q) -> None:
    """THE PROPERTY THE WHOLE STACK EXISTS FOR. A module the campaign cannot fix is exactly what
    a person needs telling about, and the failure mode of every earlier version of this idea was
    that nobody was told."""
    enqueue(q, [_f("libs.impossible")], batch=1)
    (t,) = q.tasks().values()
    for _ in range(t.max_attempts):
        q.claim("w", kinds=[WIRE_KIND])
        q.fail(t.id, "w", why="no sensible consumer exists")
    assert q.tasks()[t.id].state == "DEAD"
    got = desk_org().sweep_dead(q)
    assert got["escalated"] == [t.id], "a module that defeated the campaign vanished quietly"


def test_the_escalation_sweep_runs_even_when_nothing_new_is_queued(tmp_path) -> None:
    """Otherwise a full queue means dead work is never swept, which is when it matters most."""
    q = TaskQueue(tmp_path / "q.jsonl")
    enqueue(q, [_f("libs.dies")], batch=1)
    (t,) = q.tasks().values()
    for _ in range(t.max_attempts):
        q.claim("w", kinds=[WIRE_KIND])
        q.fail(t.id, "w", why="nope")
    out = run(_ROOT, q, batch=0)
    assert out["queued"] == [] and out["escalated"] == [t.id]
    assert any(x.kind.startswith(ESCALATION_KIND) for x in q.tasks().values())


# ------------------------------------------------------------------------------ progress
def test_the_only_number_that_counts_is_how_many_remain(q) -> None:
    """Completed tasks that did not reduce the census are wiring that did not land, and a
    progress report keyed on completions would call that success."""
    p = progress(q, _ROOT)
    assert p["remaining_unreachable"] > 0
    assert "did not reduce it" in p["why"]
    enqueue(q, [_f("libs.x")], batch=1)
    assert progress(q, _ROOT)["queued_open"] == 1


def test_a_real_pass_over_this_repository_queues_real_modules(q) -> None:
    """The integration check: the campaign has to work on the tree it ships with."""
    out = run(_ROOT, q, batch=4)
    assert out["audit_total"] > 0
    assert len(out["queued"]) == 4
    assert all(m.startswith("libs.") for m in out["queued"])
    again = run(_ROOT, q, batch=4)
    assert not (set(out["queued"]) & set(again["queued"])), "a module was queued twice"


def test_the_campaign_edits_no_code() -> None:
    """It queues decisions; it does not invent call sites and ship them to a money path."""
    src = (_ROOT / "libs" / "ops" / "wiring_campaign.py").read_text("utf-8")
    for banned in ("write_text", "subprocess", "os.system", "unlink", "Edit"):
        assert banned not in src, f"the campaign reaches for {banned}"
