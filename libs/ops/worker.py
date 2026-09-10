"""The thing that CLAIMS. Without it the queue is a capability the desk owns and does not use.

I2's recorded gap, in its own words: "the queue is durable and events can trigger work, but
NOTHING CLAIMS FROM IT YET: no leg calls claim(), so the hourly cycle still runs in source
order." That is the whole distance between a queue and a swarm. A worker is not much code; it is
the code that turns a list of intentions into work that happens.

WHAT SOURCE ORDER COSTS, and why this is worth building rather than leaving the cycle alone. In
source order every leg runs once an hour whether or not there is anything for it to do, in an
order nobody chose for a reason that no longer exists, and a leg that takes twenty minutes delays
every leg written below it. Claiming inverts all three: a worker takes the most valuable READY
task whatever produced it, N workers drain the same queue without coordinating, and a slow task
delays only itself.

THE DIVISION OF LABOUR IS THE POINT. The queue hands out work and records outcomes and RUNS
NOTHING -- `test_the_queue_runs_nothing_itself` pins that it imports neither subprocess nor
importlib, because a queue that imported its handlers would make every producer a dependency of
every consumer. So execution lives here, and this module does not know what any task means: it
is handed a mapping of kind -> callable and it calls them.

RESOURCE AWARENESS IS A REFUSAL TO CLAIM, NEVER AN ABANDONMENT. When the box is out of disk or
memory the worker declines to take new work and says so; it never claims a task and then drops
it, because a claimed task is unavailable to every other worker until its lease expires. Refusing
early leaves the work READY for a healthier worker or a healthier moment. (MEASURED on this box
2026-09-09: `stall_watch` reported 12.7 GB free while three research processes ran at 99%, 195%
and 100% CPU. A worker that claims regardless is how a full disk becomes a queue full of DEAD
tasks that were never actually attempted.)

WHAT IT DELIBERATELY DOES NOT DO:

    IT DOES NOT RETRY IN A LOOP. Bounded attempts live in the queue (a poison task goes DEAD
    after `max_attempts` rather than round the loop forever), and putting a second retry policy
    here would multiply the two.

    IT DOES NOT SWALLOW. A handler that raises fails the task WITH the exception text, so the
    reason survives in the journal; the worker itself stays up, because one bad task must not
    stop the drain.

    IT DOES NOT SPAWN. Concurrency is N processes over one queue file -- leases, not locks, and
    the durability tests already cover a worker that dies holding a task. Threads here would add
    a second concurrency model on top of the one the queue already has.
"""
from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.task_queue import DEFAULT_LEASE_S, Task, TaskQueue

#: Free disk below which no new work is claimed. Generation writes artifacts; a research pass
#: that fills the last gigabyte takes the gateway's logging and the git writer down with it, and
#: those are not recoverable by the thing that caused them.
MIN_FREE_GB = 2.0

#: Outcomes a run can have, so a caller can count them without parsing prose.
OUTCOMES: tuple[str, ...] = ("done", "failed", "no_handler", "idle", "at_capacity")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Lease:
    """Handed to a handler so a long job can keep its lease without knowing about the queue.

    A handler that runs longer than `lease_s` and never renews is INDISTINGUISHABLE from a worker
    that died -- which is exactly right, and exactly why a slow handler needs a way to say it is
    still alive.
    """

    task: Task
    _renew: Callable[[], bool]

    def renew(self) -> bool:
        return self._renew()

    @property
    def payload(self) -> dict[str, Any]:
        return self.task.payload


@dataclass
class Capacity:
    """Whether this box can take more work right now, and why not when it cannot."""

    ok: bool
    why: str = ""


def disk_capacity(root: Path, *, min_free_gb: float = MIN_FREE_GB) -> Capacity:
    """Free-space check that NEVER RAISES: an unreadable filesystem is not a licence to proceed.

    A capacity probe that throws would take down the worker it was added to protect, so a failed
    probe reads as at-capacity -- the conservative direction, and the one that leaves the work
    READY rather than claimed by a worker that is about to die.
    """
    try:
        free_gb = shutil.disk_usage(str(root)).free / 1e9
    except OSError as exc:
        return Capacity(False, f"cannot read free space at {root} ({exc.__class__.__name__})")
    if free_gb < min_free_gb:
        return Capacity(False, f"{free_gb:.1f} GB free, below the {min_free_gb:.1f} GB floor")
    return Capacity(True, f"{free_gb:.1f} GB free")


@dataclass
class Worker:
    """Claims from `queue`, runs the handler registered for the task's kind, records the outcome.

    `handlers` maps a task kind to a callable taking a `Lease` and returning anything JSON-ish
    (or None). It is passed in rather than discovered, so this module depends on no producer and
    no producer depends on it.
    """

    queue: TaskQueue
    handlers: Mapping[str, Callable[[Lease], Any]]
    name: str = "worker"
    kinds: Sequence[str] | None = None
    lease_s: int = DEFAULT_LEASE_S
    capacity: Callable[[], Capacity] | None = None
    log: list[str] = field(default_factory=list)

    def _capacity(self) -> Capacity:
        if self.capacity is None:
            return Capacity(True, "no capacity probe configured")
        try:
            return self.capacity()
        except Exception as exc:
            return Capacity(False, f"capacity probe raised {exc.__class__.__name__}")

    def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Claim at most one task and run it. Returns what happened and why.

        THE ORDER MATTERS: capacity is checked BEFORE claiming. Checking after would already have
        made the task unavailable to everyone else for a full lease.
        """
        at = now or _now()
        cap = self._capacity()
        if not cap.ok:
            return {"outcome": "at_capacity", "why": cap.why, "task": None}

        task = self.queue.claim(self.name, kinds=self.kinds, lease_s=self.lease_s, now=at)
        if task is None:
            return {"outcome": "idle", "why": "nothing ready", "task": None}

        handler = self.handlers.get(task.kind)
        if handler is None:
            # NAMED, NOT DROPPED. A task nobody can run must not sit LEASED until its lease
            # expires and then be claimed by the same worker again, forever: that is a queue that
            # looks busy while nothing advances. Failing it spends an attempt and reaches DEAD.
            why = (f"no handler registered for kind {task.kind!r} on worker {self.name!r} "
                   f"(registered: {sorted(self.handlers) or 'none'})")
            self.queue.fail(task.id, self.name, why=why)
            return {"outcome": "no_handler", "why": why, "task": task.id}

        lease = Lease(task=task, _renew=lambda: self.queue.renew(
            task.id, self.name, lease_s=self.lease_s))
        try:
            result = handler(lease)
        except Exception as exc:
            why = f"{exc.__class__.__name__}: {exc}"
            self.queue.fail(task.id, self.name, why=why)
            return {"outcome": "failed", "why": why, "task": task.id}
        self.queue.complete(task.id, self.name)
        return {"outcome": "done", "why": "", "task": task.id, "result": result}

    def drain(self, *, max_tasks: int = 0, deadline: datetime | None = None,
              now: datetime | None = None) -> dict[str, Any]:
        """Run until the queue is empty, the count is spent, or the deadline passes.

        A BOUND IS REQUIRED IN PRACTICE and both bounds are honest: `max_tasks` stops after N
        tasks, `deadline` stops before starting one it cannot promise to finish inside its lease.
        Stopping is reported with its reason, so an operator can tell "nothing to do" from "ran
        out of hour", which are opposite situations wearing the same empty result.
        """
        counts = dict.fromkeys(OUTCOMES, 0)
        ran = 0
        stopped = "queue drained"
        while True:
            at = now or _now()
            if max_tasks and ran >= max_tasks:
                stopped = f"max_tasks {max_tasks} reached"
                break
            if deadline is not None and at >= deadline:
                stopped = f"deadline {deadline.isoformat(timespec='seconds')} passed"
                break
            got = self.run_once(now=at)
            counts[got["outcome"]] += 1
            if got["outcome"] in ("idle", "at_capacity"):
                stopped = got["why"]
                break
            ran += 1
            self.log.append(f"{got['outcome']} {got.get('task', '')} {got['why']}".strip())
        return {"worker": self.name, "ran": ran, "counts": counts, "stopped": stopped}
