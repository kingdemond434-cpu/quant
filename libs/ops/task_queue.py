"""A DURABLE TASK QUEUE, and the subscriptions that let an EVENT start work.

WHAT WAS MISSING (Tier-1 I2, and the gap said it exactly). `libs/ops/events.py` landed the
append-only log and every hourly leg writes to it, but:

    no leg is yet TRIGGERED by an event (the cycle still runs in source order), and there is
    no durable task queue.

Those are one defect with two faces. A cycle that runs in source order does the same fifty-nine
things every hour whether or not anything happened, and it cannot do a sixtieth because a new
certificate arrived at 03:07 -- the arrival has nowhere to go. A queue with no durability is no
better: work claimed by a process the box kills at 20:00 is simply gone, and nothing says so.

WHAT MAKES THIS DURABLE RATHER THAN A LIST

  * APPEND-ONLY JOURNAL. Every state change is one line appended to one file, and state is the
    fold of those lines. A crash mid-write leaves a truncated last line, which `_rows` skips --
    so the worst a crash costs is the transition that was being written, never the queue.
  * LEASES, NOT LOCKS. A claim is a lease with a deadline. A worker that dies holding a task
    stops renewing it, the lease expires, and the task is READY again for whoever asks next.
    That is the property a list does not have and the reason the box can be killed at any point
    in an hourly cycle without losing the work in flight.
  * ATTEMPTS ARE COUNTED AND BOUNDED. A task that fails `max_attempts` times goes DEAD rather
    than round the loop forever, because a poison task that retries for a week looks exactly
    like a queue that is working.
  * DEDUPE BY KEY. The same event replayed, or two producers noticing the same thing, must not
    queue the same work twice. `dedupe_key` collapses them while the earlier copy is still
    live, and stops collapsing once it has finished -- so a nightly job named by its date
    queues once a night rather than once ever.

WHAT IT DELIBERATELY IS NOT

It is not a worker pool and it does not schedule across machines: that is I3, and I3 is gated on
hardware this desk does not have. A `claim` is a function a process calls; who calls it, on which
box, with how much RAM, remains the open half of I2 and is written down as such rather than
implied by the existence of a queue.

It also never RUNS anything. The queue hands out work and records outcomes; the caller executes.
A queue that imported its handlers would make every producer a dependency of every consumer, and
this desk has had that shape before.
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_LEASE_S",
    "MAX_ATTEMPTS",
    "STATES",
    "Task",
    "TaskQueue",
]

#: A task's states. DEAD is terminal and deliberately not "failed": a task that has exhausted
#: its attempts is a task nobody may retry, and the word has to say so.
STATES: tuple[str, ...] = ("READY", "LEASED", "DONE", "DEAD")

#: How long a claim is good for. Long enough that a slow leg is not stolen mid-run, short enough
#: that a killed worker's task is back within one hourly cycle.
DEFAULT_LEASE_S = 900

#: Attempts before a task is DEAD. Three, because the failures worth retrying on this desk are
#: transient reads and a locked file, and a fourth attempt has never fixed either.
MAX_ATTEMPTS = 3


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat()


@dataclass
class Task:
    """One unit of work and everything needed to decide whether to hand it out."""

    id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: float = 0.0
    state: str = "READY"
    attempts: int = 0
    max_attempts: int = MAX_ATTEMPTS
    dedupe_key: str = ""
    worker: str = ""
    lease_until: str = ""
    created_at: str = ""
    updated_at: str = ""
    why: str = ""
    source_event: str = ""

    def is_ready(self, now: datetime) -> bool:
        """READY, or LEASED to a worker that stopped renewing. The second half IS the durability:
        a task whose holder died is available again without anyone noticing the death."""
        if self.state == "READY":
            return True
        if self.state != "LEASED":
            return False
        try:
            return datetime.fromisoformat(self.lease_until) <= now
        except (TypeError, ValueError):
            return True                      # an unreadable lease is an expired one, never a lock

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


class TaskQueue:
    """A file-backed queue. One journal, one watermark, no daemon.

    Every method folds the journal from disk before acting, so two processes on one box see one
    another's writes without a lock: the journal is append-only and a single `write` of one line
    under `O_APPEND` is atomic on both platforms this desk runs on. Two workers CAN claim the
    same task in the same instant; the fold resolves it by taking the LAST claim, and the loser
    finds the task leased to someone else when it tries to complete. That is stated rather than
    hidden because it is the honest cost of not running a broker, and the work is idempotent by
    construction on this desk (every leg rewrites its artifact).
    """

    def __init__(self, path: Path, *, events_path: Path | None = None) -> None:
        self.path = Path(path)
        self.events_path = Path(events_path) if events_path else None
        self.subs_path = self.path.with_suffix(".subs.json")
        self.watermark_path = self.path.with_suffix(".watermark")

    # ------------------------------------------------------------------ the journal
    def _rows(self) -> list[dict[str, Any]]:
        try:
            text = self.path.read_text("utf-8")
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue                     # a torn last line from a crash: skip, never guess
            if isinstance(row, dict) and row.get("id"):
                out.append(row)
        return out

    def _append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, sort_keys=True, default=str) + "\n"
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def tasks(self) -> dict[str, Task]:
        """The queue, folded from the journal. Later rows win, which is what makes an append a
        state change rather than a duplicate."""
        out: dict[str, Task] = {}
        for row in self._rows():
            known = {k: v for k, v in row.items() if k in Task.__dataclass_fields__}
            tid = str(known.get("id"))
            if tid in out:
                for k, v in known.items():
                    setattr(out[tid], k, v)
            else:
                out[tid] = Task(**known)
        return out

    # ------------------------------------------------------------------ submitting
    def submit(self, kind: str, *, payload: dict[str, Any] | None = None,
               priority: float = 0.0, dedupe_key: str = "",
               max_attempts: int = MAX_ATTEMPTS, source_event: str = "") -> Task | None:
        """Queue one task, or None when `dedupe_key` names work already live.

        DEDUPE IS AGAINST LIVE WORK ONLY. A key collapses a submission while the earlier task is
        READY or LEASED and stops collapsing once it is DONE or DEAD -- so "recertify 2026-09-09"
        queues once that day and again tomorrow, while a burst of identical events queues once.
        """
        key = str(dedupe_key or "")
        if key:
            for t in self.tasks().values():
                if t.dedupe_key == key and t.state in ("READY", "LEASED"):
                    return None
        now = _iso(_now())
        task = Task(id=uuid.uuid4().hex[:16], kind=str(kind), payload=dict(payload or {}),
                    priority=float(priority), state="READY", dedupe_key=key,
                    max_attempts=int(max_attempts), created_at=now, updated_at=now,
                    source_event=str(source_event))
        self._append(task.to_dict())
        return task

    # ------------------------------------------------------------------ claiming
    def claim(self, worker: str, *, kinds: Sequence[str] | None = None,
              lease_s: int = DEFAULT_LEASE_S, now: datetime | None = None) -> Task | None:
        """The most valuable ready task, leased to `worker`. None when there is nothing to do.

        ORDERED BY PRIORITY, then by age. Priority is the caller's number -- on this desk it is
        the EVSI the research queue already computes -- and age breaks ties so a task is never
        starved by a stream of equals.
        """
        at = now or _now()
        want = {str(k) for k in kinds} if kinds else None
        ready = [t for t in self.tasks().values()
                 if t.is_ready(at) and (want is None or t.kind in want)]
        if not ready:
            return None
        ready.sort(key=lambda t: (-float(t.priority), str(t.created_at)))
        task = ready[0]
        task.state = "LEASED"
        task.worker = str(worker)
        task.attempts = int(task.attempts) + 1
        task.lease_until = _iso(at + timedelta(seconds=int(lease_s)))
        task.updated_at = _iso(at)
        self._append(task.to_dict())
        return task

    def renew(self, task_id: str, worker: str, *, lease_s: int = DEFAULT_LEASE_S,
              now: datetime | None = None) -> bool:
        """Extend a lease a long job still holds. False when it is no longer this worker's."""
        at = now or _now()
        t = self.tasks().get(str(task_id))
        if t is None or t.state != "LEASED" or t.worker != str(worker):
            return False
        t.lease_until = _iso(at + timedelta(seconds=int(lease_s)))
        t.updated_at = _iso(at)
        self._append(t.to_dict())
        return True

    def complete(self, task_id: str, worker: str = "", *, why: str = "") -> bool:
        """Mark a task DONE. Idempotent: completing a DONE task is True and writes nothing."""
        t = self.tasks().get(str(task_id))
        if t is None:
            return False
        if t.state == "DONE":
            return True
        if worker and t.worker and t.worker != str(worker):
            return False
        t.state, t.why, t.updated_at = "DONE", str(why), _iso(_now())
        self._append(t.to_dict())
        return True

    def fail(self, task_id: str, worker: str = "", *, why: str = "") -> Task | None:
        """Record a failure. Back to READY while attempts remain, DEAD when they do not.

        A POISON TASK MUST STOP. Retrying forever is indistinguishable from working, and the
        queue's own census is what an operator reads to tell the difference.
        """
        t = self.tasks().get(str(task_id))
        if t is None:
            return None
        if worker and t.worker and t.worker != str(worker):
            return None
        exhausted = int(t.attempts) >= int(t.max_attempts)
        t.state = "DEAD" if exhausted else "READY"
        t.worker, t.lease_until = "", ""
        t.why = str(why)
        t.updated_at = _iso(_now())
        self._append(t.to_dict())
        return t

    # ------------------------------------------------------------------ subscriptions
    def subscribe(self, event_kind: str, task_kind: str, *, priority: float = 0.0,
                  dedupe_on: Sequence[str] = ()) -> dict[str, Any]:
        """Say that `event_kind` should queue a `task_kind`. THE I2 GAP, in one call.

        `dedupe_on` names event fields whose values form the task's dedupe key, so "one
        recertification per certificate" is `dedupe_on=("certificate",)` and a burst of the same
        event queues one task.
        """
        subs = self.subscriptions()
        subs.append({"event_kind": str(event_kind), "task_kind": str(task_kind),
                     "priority": float(priority), "dedupe_on": [str(x) for x in dedupe_on]})
        self.subs_path.parent.mkdir(parents=True, exist_ok=True)
        self.subs_path.write_text(json.dumps(subs, indent=1), "utf-8")
        return subs[-1]

    def subscriptions(self) -> list[dict[str, Any]]:
        try:
            got = json.loads(self.subs_path.read_text("utf-8"))
        except (OSError, ValueError):
            return []
        return [x for x in got if isinstance(x, dict)] if isinstance(got, list) else []

    def drain_events(self, rows: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Turn events into tasks, once each. Returns what was queued and what was skipped.

        THE WATERMARK IS WHY "ONCE". Every event carries a timestamp; the last one drained is
        written beside the journal, and a later drain starts after it. Without that, an hourly
        drain would re-queue the whole log every hour -- and the dedupe key would hide it, which
        is worse than the bug, because the queue would look quiet while nothing new was running.
        """
        subs = self.subscriptions()
        if not subs:
            return {"queued": 0, "seen": 0, "skipped": 0, "why": "no subscriptions"}
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for sub in subs:
            by_kind.setdefault(str(sub["event_kind"]), []).append(sub)
        if rows is None:
            rows = self._event_rows()
        mark = self.watermark()
        queued, seen, skipped, newest = 0, 0, 0, mark
        for ev in rows:
            if not isinstance(ev, dict):
                continue
            stamp = str(ev.get("at") or ev.get("ts") or ev.get("time") or "")
            if mark and stamp and stamp <= mark:
                continue
            seen += 1
            if stamp > newest:
                newest = stamp
            for sub in by_kind.get(str(ev.get("kind") or ""), []):
                key = "|".join([str(sub["task_kind"]),
                                *[str(ev.get(f, "")) for f in sub.get("dedupe_on", [])]])
                got = self.submit(str(sub["task_kind"]), payload=dict(ev),
                                  priority=float(sub.get("priority", 0.0)),
                                  dedupe_key=(key if sub.get("dedupe_on") else ""),
                                  source_event=stamp)
                queued += 1 if got else 0
                skipped += 0 if got else 1
        if newest and newest != mark:
            self.watermark_path.parent.mkdir(parents=True, exist_ok=True)
            self.watermark_path.write_text(newest, "utf-8")
        return {"queued": queued, "seen": seen, "skipped": skipped, "watermark": newest}

    def watermark(self) -> str:
        try:
            return self.watermark_path.read_text("utf-8").strip()
        except OSError:
            return ""

    def _event_rows(self) -> list[dict[str, Any]]:
        if self.events_path is None:
            return []
        try:
            text = self.events_path.read_text("utf-8")
        except OSError:
            return []
        out = []
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    # ------------------------------------------------------------------ the census
    def census(self, now: datetime | None = None) -> dict[str, Any]:
        """What an operator reads. `expired` is counted separately from READY because a queue
        whose workers keep dying looks identical to a busy one in a state histogram."""
        at = now or _now()
        tasks = list(self.tasks().values())
        by_state = dict.fromkeys(STATES, 0)
        expired = 0
        for t in tasks:
            by_state[t.state] = by_state.get(t.state, 0) + 1
            if t.state == "LEASED" and t.is_ready(at):
                expired += 1
        oldest = min((t.created_at for t in tasks if t.state == "READY"), default="")
        return {"total": len(tasks), "by_state": by_state, "expired_leases": expired,
                "oldest_ready": oldest, "dead": [t.id for t in tasks if t.state == "DEAD"][:20],
                "subscriptions": len(self.subscriptions()), "watermark": self.watermark(),
                "rule": ("a LEASED task whose lease has expired is READY: a worker that dies "
                         "returns its work without anyone noticing the death")}
