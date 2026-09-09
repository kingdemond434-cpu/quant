"""The queue survives the worker, and an event can start work.

I2's gap named two things: "no leg is yet TRIGGERED by an event (the cycle still runs in source
order), and there is no durable task queue". The tests that matter here are the ones that would
be false for a list with a nice interface:

  * a worker that DIES holding a task returns it, without anyone noticing the death;
  * a crash mid-write costs the transition being written and never the queue;
  * a poison task stops after its attempts instead of retrying forever, because a task that
    retries for a week looks exactly like a queue that is working;
  * an event queues work ONCE, however many times the log is drained.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.task_queue import DEFAULT_LEASE_S, TaskQueue  # noqa: E402

T0 = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "queue.jsonl", events_path=tmp_path / "events.jsonl")


# --------------------------------------------------------------------------- the basics
def test_a_submitted_task_is_claimed_once_and_completed(q):
    t = q.submit("recertify", payload={"cell": "XAUUSD.asia"}, priority=1.0)
    assert t and t.state == "READY" and t.attempts == 0
    got = q.claim("worker-a", now=T0)
    assert got.id == t.id and got.state == "LEASED" and got.worker == "worker-a"
    assert got.attempts == 1
    assert q.claim("worker-b", now=T0) is None, "one task was handed to two workers"
    assert q.complete(got.id, "worker-a")
    assert q.tasks()[t.id].state == "DONE"
    assert q.claim("worker-b", now=T0) is None


def test_the_most_valuable_task_goes_first_and_ties_break_by_age(q):
    q.submit("a", priority=0.1)
    big = q.submit("b", priority=9.0)
    q.submit("c", priority=0.1)
    assert q.claim("w", now=T0).id == big.id
    first_of_the_ties = q.claim("w", now=T0)
    assert first_of_the_ties.kind == "a", "a task was starved by an equal-valued newcomer"


def test_kinds_filter_what_a_worker_will_take(q):
    q.submit("heavy", priority=9.0)
    light = q.submit("light", priority=0.1)
    assert q.claim("w", kinds=["light"], now=T0).id == light.id


# ------------------------------------------------------- THE DURABILITY, WHICH IS THE POINT
def test_a_worker_that_dies_returns_its_task_when_the_lease_expires(q):
    """THE PROPERTY A LIST DOES NOT HAVE. Nothing detects the death; the lease simply stops
    being renewed, and the task is available again to whoever asks next."""
    t = q.submit("long_job")
    q.claim("doomed", lease_s=60, now=T0)
    assert q.claim("other", now=T0) is None, "a live lease was stolen"
    later = T0 + timedelta(seconds=61)
    got = q.claim("other", now=later)
    assert got is not None and got.id == t.id and got.worker == "other"
    assert got.attempts == 2, "the second attempt was not counted"


def test_a_long_job_can_renew_and_keep_its_lease(q):
    t = q.submit("long_job")
    q.claim("w", lease_s=60, now=T0)
    assert q.renew(t.id, "w", lease_s=600, now=T0 + timedelta(seconds=30))
    assert q.claim("other", now=T0 + timedelta(seconds=120)) is None
    assert not q.renew(t.id, "someone-else"), "a renewal was accepted from a non-holder"


def test_an_unreadable_lease_is_an_expired_one_and_never_a_permanent_lock(q):
    t = q.submit("x")
    q.claim("w", now=T0)
    row = dict(q.tasks()[t.id].to_dict(), lease_until="not a timestamp")
    q._append(row)
    assert q.claim("other", now=T0) is not None, (
        "a corrupt lease field locked the task forever; a queue must fail toward available")


def test_a_torn_line_from_a_crash_costs_that_transition_and_not_the_queue(q):
    a = q.submit("a")
    q.submit("b")
    with q.path.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "half-written", "kind": "c"')          # no newline, no closing brace
    tasks = q.tasks()
    assert set(tasks) == {a.id, [t for t in tasks if t != a.id][0]}
    assert len(tasks) == 2 and all(t.state == "READY" for t in tasks.values())
    assert q.claim("w", now=T0) is not None, "the queue stopped working after a torn write"


def test_state_survives_a_new_handle_on_the_same_file(tmp_path):
    """Durable means on disk, not in a process. A second `TaskQueue` over the same path is the
    same queue -- which is what lets the hourly cycle and a one-off script share one."""
    one = TaskQueue(tmp_path / "q.jsonl")
    t = one.submit("x", priority=2.0)
    one.claim("w", now=T0)
    two = TaskQueue(tmp_path / "q.jsonl")
    assert two.tasks()[t.id].state == "LEASED" and two.tasks()[t.id].worker == "w"
    assert two.complete(t.id, "w")
    assert one.tasks()[t.id].state == "DONE"


# ------------------------------------------------------------------------- poison and retry
def test_a_failure_returns_the_task_until_its_attempts_run_out(q):
    t = q.submit("flaky", max_attempts=2)
    q.claim("w", now=T0)
    back = q.fail(t.id, "w", why="venue timeout")
    assert back.state == "READY" and back.worker == "" and back.why == "venue timeout"
    q.claim("w", now=T0)
    dead = q.fail(t.id, "w", why="venue timeout again")
    assert dead.state == "DEAD", "a poison task went back on the queue after its last attempt"
    assert q.claim("w", now=T0 + timedelta(days=7)) is None
    assert q.census()["dead"] == [t.id]


def test_completing_is_idempotent_and_a_stranger_cannot_complete_anothers_task(q):
    t = q.submit("x")
    q.claim("w", now=T0)
    assert q.complete(t.id, "w") and q.complete(t.id, "w")
    assert not q.complete("no-such-task")
    other = q.submit("y")
    q.claim("w", now=T0)
    assert not q.complete(other.id, "stranger")


# ------------------------------------------------------------------------------ dedupe
def test_a_dedupe_key_collapses_live_work_and_stops_once_it_has_finished(q):
    first = q.submit("recert", dedupe_key="cell-1")
    assert q.submit("recert", dedupe_key="cell-1") is None, "the same work queued twice"
    q.claim("w", now=T0)
    assert q.submit("recert", dedupe_key="cell-1") is None, "queued again while it was running"
    q.complete(first.id, "w")
    again = q.submit("recert", dedupe_key="cell-1")
    assert again is not None and again.id != first.id, (
        "a key collapsed work forever; a nightly task named by its date would run once ever")


def test_an_empty_dedupe_key_never_collapses_anything(q):
    assert q.submit("x") and q.submit("x")
    assert len(q.tasks()) == 2


# ---------------------------------------------------------- THE EVENT TRIGGER, WHICH IS I2
def _event(kind: str, at: str, **fields) -> str:
    return json.dumps({"kind": kind, "at": at, **fields})


def test_an_event_queues_the_task_it_is_subscribed_to(q):
    """I2's first gap, in one call: the cycle ran in source order and an arrival had nowhere
    to go."""
    q.subscribe("CERTIFICATE_MINTED", "recertify", priority=2.0, dedupe_on=("certificate",))
    q.events_path.write_text(
        _event("CERTIFICATE_MINTED", "2026-09-09T03:07:00+00:00", certificate="XAUUSD.asia")
        + "\n" + _event("LEG_EVENT", "2026-09-09T03:08:00+00:00", leg="mine") + "\n", "utf-8")
    got = q.drain_events()
    assert got["queued"] == 1 and got["seen"] == 2
    (task,) = q.tasks().values()
    assert task.kind == "recertify" and task.priority == 2.0
    assert task.payload["certificate"] == "XAUUSD.asia"
    assert task.source_event == "2026-09-09T03:07:00+00:00"


def test_draining_twice_queues_nothing_twice(q):
    """THE WATERMARK. Without it an hourly drain re-queues the whole log every hour -- and the
    dedupe key would HIDE that, which is worse than the bug: the queue would look quiet while
    nothing new was running."""
    q.subscribe("CERTIFICATE_MINTED", "recertify")
    q.events_path.write_text(
        _event("CERTIFICATE_MINTED", "2026-09-09T03:07:00+00:00", certificate="a") + "\n",
        "utf-8")
    assert q.drain_events()["queued"] == 1
    assert q.drain_events()["queued"] == 0
    assert len(q.tasks()) == 1
    with q.events_path.open("a", encoding="utf-8") as fh:
        fh.write(_event("CERTIFICATE_MINTED", "2026-09-09T04:00:00+00:00", certificate="b")
                 + "\n")
    assert q.drain_events()["queued"] == 1
    assert len(q.tasks()) == 2


def test_a_burst_of_one_event_queues_one_task_when_the_key_says_so(q):
    q.subscribe("CERTIFICATE_MINTED", "recertify", dedupe_on=("certificate",))
    q.events_path.write_text("".join(
        _event("CERTIFICATE_MINTED", f"2026-09-09T03:0{i}:00+00:00", certificate="same") + "\n"
        for i in range(5)), "utf-8")
    got = q.drain_events()
    assert got["queued"] == 1 and got["skipped"] == 4
    assert len(q.tasks()) == 1


def test_no_subscription_means_no_work_and_says_so(q):
    q.events_path.write_text(_event("ANYTHING", "2026-09-09T03:07:00+00:00") + "\n", "utf-8")
    got = q.drain_events()
    assert got["queued"] == 0 and got["why"] == "no subscriptions"


def test_an_absent_or_unreadable_event_log_drains_nothing_rather_than_raising(q):
    q.subscribe("X", "y")
    assert q.drain_events()["queued"] == 0
    q.events_path.write_text("not json\n{}\n", "utf-8")
    assert q.drain_events()["queued"] == 0


# ------------------------------------------------------------------------------ the census
def test_the_census_counts_an_expired_lease_apart_from_a_live_one(q):
    """A queue whose workers keep dying looks identical to a busy one in a state histogram, so
    the thing an operator needs is exactly the number a histogram hides."""
    q.submit("a")
    q.submit("b")
    q.claim("doomed", lease_s=60, now=T0)
    live = q.census(now=T0)
    assert live["by_state"]["LEASED"] == 1 and live["expired_leases"] == 0
    stale = q.census(now=T0 + timedelta(seconds=120))
    assert stale["by_state"]["LEASED"] == 1 and stale["expired_leases"] == 1
    assert "returns its work without anyone noticing the death" in stale["rule"]


def test_the_census_reports_the_oldest_waiting_task(q):
    assert q.census()["oldest_ready"] == ""
    first = q.submit("a")
    q.submit("b")
    assert q.census()["oldest_ready"] == first.created_at


def test_the_queue_runs_nothing_itself():
    """It hands out work and records outcomes; the caller executes. A queue that imported its
    handlers would make every producer a dependency of every consumer."""
    src = (_ROOT / "libs" / "ops" / "task_queue.py").read_text("utf-8")
    assert "subprocess" not in src and "importlib" not in src
    assert "def claim(" in src and "def complete(" in src
