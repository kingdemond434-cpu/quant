"""Something finally claims, and the ways that go wrong are the tests.

I2's gap named two halves. The queue was the first and landed; this is the second, in its own
words: "NOTHING CLAIMS FROM IT YET: no leg calls claim(), so the hourly cycle still runs in source
order." A worker is small. What makes it worth its own file is that every interesting property is
about the FAILURE paths, because a worker that only works when handlers work is a for-loop.

THE FOUR THAT MATTER, none of which a for-loop has:

    A BAD TASK MUST NOT STOP THE DRAIN. One handler raising has to fail that task, keep its
    reason, and leave the worker running -- otherwise a single poison payload silences the whole
    swarm and the queue fills behind it.

    A TASK NOBODY CAN RUN MUST NOT LOOK LIKE WORK IN PROGRESS. With no handler registered, the
    obvious implementation leaves it LEASED, the lease expires, the same worker claims it again,
    forever: a queue that reads BUSY while nothing advances, which is worse than an error because
    nothing reports it.

    CAPACITY IS CHECKED BEFORE CLAIMING. Checking after has already made the task unavailable to
    every other worker for a full lease -- so a full disk would empty the queue into nothing.

    THE PROBE ITSELF MUST NOT BE THE OUTAGE. A capacity check that raises has to read
    at-capacity, never propagate: it was added to protect the worker, not to take it down.

CONCURRENCY IS N PROCESSES OVER ONE FILE, leases rather than locks, which the queue's own tests
already cover. Nothing here spawns anything, and `test_the_worker_spawns_nothing` keeps it that
way -- a second concurrency model layered on the first is how two correct designs make one
incorrect system.
"""
from __future__ import annotations

import ast
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.task_queue import TaskQueue  # noqa: E402
from libs.ops.worker import Capacity, Lease, Worker, disk_capacity  # noqa: E402

T0 = datetime(2026, 9, 9, 18, 0, tzinfo=UTC)


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


def _worker(q, handlers, **kw) -> Worker:
    return Worker(queue=q, handlers=handlers, name=kw.pop("name", "w1"), **kw)


# ------------------------------------------------------------------------------ the happy path
def test_a_worker_claims_runs_and_completes(q) -> None:
    seen: list[dict] = []
    t = q.submit("generate", payload={"family": "jump"})
    w = _worker(q, {"generate": lambda lease: seen.append(lease.payload) or "ok"})
    got = w.run_once(now=T0)
    assert got["outcome"] == "done" and got["task"] == t.id and got["result"] == "ok"
    assert seen == [{"family": "jump"}]
    assert q.tasks()[t.id].state == "DONE"
    assert w.run_once(now=T0)["outcome"] == "idle"


def test_the_most_valuable_task_is_taken_first(q) -> None:
    q.submit("generate", payload={"n": 1}, priority=0.1)
    q.submit("generate", payload={"n": 9}, priority=9.0)
    order: list[int] = []
    w = _worker(q, {"generate": lambda lease: order.append(lease.payload["n"])})
    w.drain(now=T0)
    assert order == [9, 1]


def test_kinds_narrow_what_a_worker_will_take(q) -> None:
    """A swarm is heterogeneous: a generation worker and a certification worker share one queue
    and must not take each other's work."""
    q.submit("certify", priority=9.0)
    light = q.submit("generate", priority=0.1)
    w = _worker(q, {"generate": lambda lease: None}, kinds=["generate"])
    assert w.run_once(now=T0)["task"] == light.id
    assert q.tasks()[light.id].state == "DONE"
    assert q.tasks()[next(i for i in q.tasks() if i != light.id)].state == "READY"


# ---------------------------------------------------------------------- THE FAILURE PATHS
def test_a_handler_that_raises_fails_the_task_and_keeps_the_worker_running(q) -> None:
    """One poison payload must not silence the swarm, and the reason must survive."""
    bad = q.submit("generate", payload={"bad": True})
    good = q.submit("generate", payload={"bad": False})

    def handler(lease: Lease):
        if lease.payload["bad"]:
            raise ValueError("no bars for this symbol")
        return "fine"

    w = _worker(q, {"generate": handler})
    first = w.run_once(now=T0)
    assert first["outcome"] == "failed" and "no bars for this symbol" in first["why"]
    assert "ValueError" in q.tasks()[bad.id].why, "the exception type was lost"

    # DRAINED, NOT STEPPED. A failed task returns to READY and is now the OLDEST ready task, so
    # the very next claim takes it again -- the queue's documented order (priority, then age),
    # not a defect, and it costs only the attempts the queue already bounds. The property that
    # matters is therefore about the drain finishing, not about which task comes second: the bad
    # one reaches DEAD, the good one still runs, and the worker is alive at the end of both.
    got = w.drain(now=T0)
    assert q.tasks()[bad.id].state == "DEAD"
    assert q.tasks()[good.id].state == "DONE", (
        "one poison payload stranded the rest of the queue behind it")
    assert got["counts"]["done"] == 1 and got["counts"]["failed"] == 2


def test_a_kind_with_no_handler_is_failed_by_name_rather_than_left_leased(q) -> None:
    """THE ONE THAT LOOKS LIKE WORK. Left LEASED it expires, is re-claimed by the same worker,
    and repeats forever -- a queue reading BUSY while nothing advances."""
    t = q.submit("unknown_kind")
    w = _worker(q, {"generate": lambda lease: None})
    got = w.run_once(now=T0)
    assert got["outcome"] == "no_handler"
    assert "unknown_kind" in got["why"] and "generate" in got["why"], (
        "the reason names neither the kind nor what this worker can run, so an operator cannot "
        "tell a typo from a worker started with the wrong handler set")
    assert q.tasks()[t.id].state == "READY", "an attempt was not spent"
    for _ in range(5):
        w.run_once(now=T0)
    assert q.tasks()[t.id].state == "DEAD", "an unrunnable task never stopped being retried"


def test_attempts_are_bounded_by_the_queue_and_not_re_implemented_here(q) -> None:
    """Two retry policies multiply. The queue owns this one."""
    t = q.submit("generate", max_attempts=2)
    w = _worker(q, {"generate": lambda lease: (_ for _ in ()).throw(RuntimeError("boom"))})
    w.run_once(now=T0)
    assert q.tasks()[t.id].state == "READY"
    w.run_once(now=T0)
    assert q.tasks()[t.id].state == "DEAD"
    assert w.run_once(now=T0)["outcome"] == "idle"


# ----------------------------------------------------------------------------- capacity
def test_a_worker_at_capacity_does_not_claim_at_all(q) -> None:
    """Checking after the claim has already taken the task away from every healthier worker for
    a full lease."""
    t = q.submit("generate")
    w = _worker(q, {"generate": lambda lease: None},
                capacity=lambda: Capacity(False, "0.4 GB free, below the 2.0 GB floor"))
    got = w.run_once(now=T0)
    assert got["outcome"] == "at_capacity" and "0.4 GB free" in got["why"]
    assert q.tasks()[t.id].state == "READY", (
        "the task was claimed by a worker that could not run it")
    healthy = _worker(q, {"generate": lambda lease: "ran"}, name="w2")
    assert healthy.run_once(now=T0)["outcome"] == "done"


def test_a_capacity_probe_that_raises_reads_as_at_capacity(q) -> None:
    """It was added to protect the worker, so it must not be the thing that takes it down."""
    q.submit("generate")
    w = _worker(q, {"generate": lambda lease: None},
                capacity=lambda: (_ for _ in ()).throw(OSError("stat failed")))
    got = w.run_once(now=T0)
    assert got["outcome"] == "at_capacity" and "OSError" in got["why"]


def test_the_disk_probe_reports_free_space_and_never_raises(tmp_path) -> None:
    assert disk_capacity(tmp_path, min_free_gb=0.0).ok
    tight = disk_capacity(tmp_path, min_free_gb=10 ** 9)
    assert not tight.ok and "below the" in tight.why
    missing = disk_capacity(tmp_path / "nope" / "deeper", min_free_gb=0.0)
    assert not missing.ok and "cannot read free space" in missing.why


# ------------------------------------------------------------------------------- the lease
def test_a_long_handler_can_renew_and_keep_its_task(q) -> None:
    """A handler that outruns its lease without renewing is indistinguishable from a worker that
    died -- correctly. Renewal is how a slow job says otherwise."""
    t = q.submit("generate")
    holder = _worker(q, {"generate": lambda lease: lease.renew()}, lease_s=60)
    assert holder.run_once(now=T0)["result"] is True
    q.submit("generate")
    slow = _worker(q, {"generate": lambda lease: None}, lease_s=60, name="slow")
    slow.queue.claim("slow", lease_s=60, now=T0)
    assert q.claim("other", now=T0) is None
    assert q.claim("other", now=T0 + timedelta(seconds=61)) is not None, (
        "a lease that was never renewed still held the task")
    assert q.tasks()[t.id].state == "DONE"


# -------------------------------------------------------------------------------- draining
def test_drain_empties_the_queue_and_says_why_it_stopped(q) -> None:
    for i in range(4):
        q.submit("generate", payload={"i": i})
    w = _worker(q, {"generate": lambda lease: None})
    got = w.drain(now=T0)
    assert got["ran"] == 4 and got["counts"]["done"] == 4
    assert got["stopped"] == "nothing ready"


def test_drain_stops_at_max_tasks_and_says_so(q) -> None:
    for i in range(5):
        q.submit("generate", payload={"i": i})
    w = _worker(q, {"generate": lambda lease: None})
    got = w.drain(max_tasks=2, now=T0)
    assert got["ran"] == 2 and "max_tasks 2" in got["stopped"]
    assert sum(1 for t in q.tasks().values() if t.state == "READY") == 3


def test_drain_stops_at_a_deadline_rather_than_starting_work_it_cannot_finish(q) -> None:
    """"Nothing to do" and "ran out of hour" are opposite situations and both produce an empty
    result, so the reason has to distinguish them."""
    q.submit("generate")
    w = _worker(q, {"generate": lambda lease: None})
    got = w.drain(deadline=T0, now=T0)
    assert got["ran"] == 0 and "deadline" in got["stopped"]
    assert q.tasks()[next(iter(q.tasks()))].state == "READY"


def test_two_workers_over_one_queue_never_run_the_same_task(q) -> None:
    """The swarm, in one assertion. No coordination between them beyond the file."""
    for i in range(6):
        q.submit("generate", payload={"i": i})
    seen_a, seen_b = [], []
    a = _worker(q, {"generate": lambda le: seen_a.append(le.payload["i"])}, name="a")
    b = _worker(q, {"generate": lambda le: seen_b.append(le.payload["i"])}, name="b")
    while a.run_once(now=T0)["outcome"] == "done" or b.run_once(now=T0)["outcome"] == "done":
        pass
    assert sorted(seen_a + seen_b) == list(range(6))
    assert not (set(seen_a) & set(seen_b)), "one task was run twice"


def test_the_worker_spawns_nothing_and_discovers_nothing(q) -> None:
    """Handlers are passed in, never imported: a worker that discovered them would make every
    producer a dependency of every consumer, which is the coupling the queue was built to avoid.
    And concurrency stays N processes over one file -- threads here would be a second model on
    top of the leases that already work.

    READ AS IMPORTS, NOT AS TEXT. The module EXPLAINS at length why it spawns nothing, so a
    substring search flags the prose that documents the ban -- a test that cannot tell a
    prohibition from its violation forces the next author to delete the explanation to make it
    pass. The same reasoning `_executable_lines` was written for in the adopt-release suite.
    """
    tree = ast.parse((_ROOT / "libs" / "ops" / "worker.py").read_text("utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for banned in ("subprocess", "importlib", "threading", "multiprocessing", "asyncio"):
        assert banned not in imported, f"worker.py imports {banned}"
    assert "task_queue" not in imported or "libs" in imported
