"""ALERT LIFECYCLE -- an alert that nobody closes is not a control loop, it is a notification.

WHAT WAS ACTUALLY WRONG. Every ntfy path in this repo is a SENDER. `run_alerts.py` pushes to the
principal's phone, dedupes for six hours, and stops. `data/.last_alerts.json` stores when something
last fired, which is dedup state, not lifecycle. So an alert firing every six hours forever is
indistinguishable, on the phone and on disk, from one that fired once and was fixed. The desk could
not tell those apart, which means the human had to -- and that is precisely the work the principal
asked not to be doing.

THE STATES, AND WHY EACH EXISTS:

  OPEN            seen, nothing attempted yet.
  ATTEMPTED       a bounded remediation ran. NOT a claim that it worked.
  FIXED           the check was RE-RUN after the remediation and no longer fires. The only state
                  that may be reported as resolved, and it requires evidence rather than an
                  absence of complaint.
  FAILED          remediation ran and the check still fires. Escalates.
  NEEDS_HUMAN     nothing the desk can run will close it -- credits, keys, hardware, procurement.
                  Naming this class is what stops the loop retrying forever and stops the pager
                  crying about work nobody could have done.
  REGRESSED       fired again AFTER being verified fixed. Different information from a new alert:
                  it says the fix did not hold, and a system that reports it as new will keep
                  applying the same failing remediation indefinitely.

DEDUP IS NOT CLOSURE, and conflating them is the original defect. Suppressing a repeat for six
hours makes the pager quieter; it does nothing about the condition. This ledger keeps `last_seen`
for noise control and `state` for truth, and they are never the same field.

Pure stdlib. JSON persistence, because a lifecycle that dies with the process is not one.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

__all__ = [
    "OPEN_STATES",
    "STATES",
    "Alert",
    "AlertLedger",
    "AlertLedgerBusy",
    "AlertLedgerUnreadable",
    "os_lock",
]

STATES = ("OPEN", "ATTEMPTED", "FIXED", "FAILED", "NEEDS_HUMAN", "REGRESSED")

#: States that still demand something. FIXED is the only one that does not, and NEEDS_HUMAN is
#: deliberately in here: it is not resolved, it is merely not resolvable by the desk.
OPEN_STATES = ("OPEN", "ATTEMPTED", "FAILED", "NEEDS_HUMAN", "REGRESSED")


@dataclass
class Alert:
    """One condition, its history, and what has been tried."""

    id: str
    message: str = ""
    state: str = "OPEN"
    scope: str = "UNSCOPED"          # REPO / RUNTIME / UNSCOPED, from max_audit
    first_seen: str = ""
    last_seen: str = ""
    fixed_at: str = ""
    attempts: int = 0
    last_action: str = ""
    history: list[str] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return self.state in OPEN_STATES

    def age_hours(self, now: datetime | None = None) -> float:
        if not self.first_seen:
            return 0.0
        ref = now or datetime.now(tz=UTC)
        return (ref - datetime.fromisoformat(self.first_seen)).total_seconds() / 3600.0


#: os.replace retries on PermissionError (Windows: the target is open in another process).
REPLACE_RETRIES = 20
#: How long a writer waits for the lock before it gives up -- and RAISES (v5f): it never goes on
#: unlocked, because a writer that proceeds unlocked is a second holder.
LOCK_WAIT_S = 10.0


class AlertLedgerBusy(TimeoutError):
    """The ledger's lock was not obtained within the wait: nothing was written."""


class AlertLedgerUnreadable(OSError):
    """The ledger exists and could not be read: saving now would replace it with less."""


def _acquire(fh: BinaryIO, timeout_s: float) -> bool:
    """An OS lock on byte 0 of the sidecar, polled: msvcrt on Windows, flock elsewhere."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, ImportError):
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)


def _release(fh: BinaryIO) -> None:
    with contextlib.suppress(OSError, ImportError):
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def os_lock(lock: Path, timeout_s: float = LOCK_WAIT_S) -> Iterator[None]:
    """An exclusive OS lock on a sidecar file that is never deleted (v5f).

    THE OLD LOCK COULD BE HELD TWICE. It was an O_EXCL lock file that a waiter deleted once it
    looked older than 60 s: two waiters could both judge it stale, the first could delete it and
    take a fresh one, and the second then deleted THAT one and took another -- two holders. A
    kernel lock has no stale state to judge: it is released when its holder's handle closes,
    including when the holder dies, so there is nothing to break and no second holder. The
    sidecar stays on disk because deleting it races every other opener on Windows. A wait that
    expires raises AlertLedgerBusy; it never proceeds unlocked."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock, "a+b")   # noqa: SIM115 -- held for the whole body, closed below
    try:
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        if not _acquire(fh, timeout_s):
            raise AlertLedgerBusy(f"{lock.name} held by another writer for {timeout_s:g}s")
        try:
            yield
        finally:
            _release(fh)
    finally:
        fh.close()


#: Kept for callers of the v5e name; it is the OS lock now.
_locked = os_lock


def _parse(text: str) -> dict[str, Alert]:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("ledger is not an object")
    alerts = raw.get("alerts") or {}
    if not isinstance(alerts, dict):
        raise ValueError("'alerts' is not an object")
    out: dict[str, Alert] = {}
    for aid, d in alerts.items():
        known = {k: v for k, v in d.items() if k in Alert.__dataclass_fields__}
        out[aid] = Alert(id=aid, **{k: v for k, v in known.items() if k != "id"})
    return out


class AlertLedger:
    """Persistent alert lifecycle. Survives the process, which is the whole point.

    LOAD, MODIFY AND SAVE UNDER ONE LOCK (v5f). `AlertLedger.transaction(path)` holds the OS lock
    from the read to the write. A plain `save()` outside one re-reads the ledger UNDER the lock and
    lays only this instance's changes (alerts added or changed since it loaded) over what is on
    disk, so another process's alert written in between is kept, never overwritten by a stale
    copy. A ledger that EXISTS and cannot be read is never saved over: a transient OSError would
    otherwise empty it. One that reads but does not parse is moved aside (kept, never lost) and
    the ledger starts again from it."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.alerts: dict[str, Alert] = {}
        self.load_error: str | None = None
        self._snapshot: dict[str, dict[str, object]] = {}
        self._in_txn = False
        self._load()

    @classmethod
    @contextlib.contextmanager
    def transaction(cls, path: Path, timeout_s: float = LOCK_WAIT_S) -> Iterator[AlertLedger]:
        """Lock, load, yield, save -- one critical section. Raises (and writes nothing) when the
        ledger is unreadable or the body raises."""
        led = cls.__new__(cls)
        led.path = Path(path)
        led.alerts, led.load_error, led._snapshot, led._in_txn = {}, None, {}, True
        with os_lock(led._lock_path(), timeout_s):
            led._load()
            if led.load_error and not led.load_error.startswith("unparseable"):
                raise AlertLedgerUnreadable(f"{led.path.name}: {led.load_error}")
            yield led
            led._write(led.alerts)
        led._in_txn = False

    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".flock")

    def _read(self) -> tuple[dict[str, Alert] | None, str | None]:
        """(alerts, None) on a read; ({}, None) when absent; (None, why) when it cannot be read;
        ({}, "unparseable ...") when it reads but does not parse."""
        try:
            text = self.path.read_text("utf-8")
        except FileNotFoundError:
            return {}, None
        except OSError as exc:
            return None, f"unreadable ({type(exc).__name__})"
        try:
            return _parse(text), None
        except (ValueError, TypeError, AttributeError) as exc:
            return {}, f"unparseable ({type(exc).__name__})"

    def _load(self) -> None:
        got, why = self._read()
        self.load_error = why
        self.alerts = got if got is not None else {}
        self._snapshot = {aid: asdict(a) for aid, a in self.alerts.items()}

    def _set_aside_unparseable(self) -> None:
        with contextlib.suppress(OSError):
            os.replace(self.path, self.path.with_name(
                f"{self.path.name}.unparseable-{time.time_ns()}"))

    def save(self) -> None:
        """ATOMIC (v5e) and MERGED UNDER THE LOCK (v5f): see the class docstring."""
        if self._in_txn:
            return   # the transaction writes once, on its way out, under its own lock
        with os_lock(self._lock_path()):
            disk, why = self._read()
            if disk is None:
                raise AlertLedgerUnreadable(f"{self.path.name}: {why}; not saved over")
            if why:
                self._set_aside_unparseable()
            for aid, a in self.alerts.items():
                if asdict(a) != self._snapshot.get(aid):
                    disk[aid] = a
            for aid in set(self._snapshot) - set(self.alerts):
                disk.pop(aid, None)
            self._write(disk)
            self.alerts = disk
            self._snapshot = {aid: asdict(a) for aid, a in disk.items()}
            self.load_error = None

    def _write(self, alerts: dict[str, Alert]) -> None:
        """Temp file, fsync, os.replace (retried on a Windows PermissionError). Lock held."""
        if self.load_error and self.load_error.startswith("unparseable") and self.path.exists():
            self._set_aside_unparseable()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({
            "updated": datetime.now(tz=UTC).isoformat(),
            "alerts": {a.id: asdict(a) for a in alerts.values()},
            "note": ("`last_seen` is dedup state and `state` is truth -- they are never the same "
                     "field. Suppressing a repeat makes the pager quieter and does nothing about "
                     "the condition."),
        }, indent=1)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(REPLACE_RETRIES):
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == REPLACE_RETRIES - 1:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()

    # ------------------------------------------------------------------ transitions

    def observe(self, aid: str, message: str, *, scope: str = "UNSCOPED") -> Alert:
        """Record that a condition is currently firing.

        A condition firing after it was verified FIXED is a REGRESSION, not a new alert. Reporting
        it as new would let the loop apply the same failing remediation forever while the counter
        reset each time -- the fix did not hold, and that is the fact worth carrying.
        """
        now = datetime.now(tz=UTC).isoformat()
        a = self.alerts.get(aid)
        if a is None:
            a = Alert(id=aid, message=message, scope=scope, first_seen=now, last_seen=now)
            a.history.append(f"{now} OPEN")
            self.alerts[aid] = a
            return a
        a.message, a.scope, a.last_seen = message, scope, now
        if a.state == "FIXED":
            a.state = "REGRESSED"
            a.history.append(f"{now} REGRESSED -- fired again after being verified fixed")
        return a

    def attempted(self, aid: str, action: str) -> Alert:
        a = self.alerts[aid]
        a.state = "ATTEMPTED"
        a.attempts += 1
        a.last_action = action
        a.history.append(f"{datetime.now(tz=UTC).isoformat()} ATTEMPTED {action}")
        return a

    def verify(self, aid: str, *, still_firing: bool) -> Alert:
        """Close an alert ONLY on re-run evidence.

        The distinction that matters: `still_firing` comes from executing the check again, never
        from the absence of a new report. A condition nobody re-tested is not fixed, and marking it
        so is the desk's own "not measured = fine" failure applied to its own repairs.
        """
        a = self.alerts[aid]
        now = datetime.now(tz=UTC).isoformat()
        if still_firing:
            a.state = "FAILED"
            a.history.append(f"{now} FAILED -- check re-run and still firing")
        else:
            a.state, a.fixed_at = "FIXED", now
            a.history.append(f"{now} FIXED -- verified by re-running the check")
        return a

    def needs_human(self, aid: str, why: str) -> Alert:
        """Mark what no command can close. Stops the loop retrying and the pager crying."""
        a = self.alerts[aid]
        a.state = "NEEDS_HUMAN"
        a.last_action = why
        a.history.append(f"{datetime.now(tz=UTC).isoformat()} NEEDS_HUMAN -- {why}")
        return a

    def resolve_absent(self, seen_ids: set[str]) -> list[Alert]:
        """Anything previously open and NOT observed this run has stopped firing.

        Absence is weaker evidence than a re-run, so these are marked FIXED with the reason
        recorded as such. The alternative -- leaving them open forever -- turns the ledger into a
        graveyard nobody reads, which is how the original pager failed.
        """
        out = []
        now = datetime.now(tz=UTC).isoformat()
        for a in self.alerts.values():
            if a.open and a.state != "NEEDS_HUMAN" and a.id not in seen_ids:
                a.state, a.fixed_at = "FIXED", now
                a.history.append(f"{now} FIXED -- no longer reported by the sweep")
                out.append(a)
        return out

    # ---------------------------------------------------------------------- views

    def open_alerts(self) -> list[Alert]:
        return [a for a in self.alerts.values() if a.open]

    def escalations(self, *, min_age_h: float = 24.0) -> list[Alert]:
        """What genuinely warrants the principal's attention.

        FAILED and REGRESSED always: the desk tried and could not. NEEDS_HUMAN only once it has
        aged, because paging instantly about something only a human can do -- at 3am, about a
        credit top-up -- is how a pager gets muted, and a muted pager is worse than none.
        """
        return [a for a in self.alerts.values()
                if a.state in ("FAILED", "REGRESSED")
                or (a.state == "NEEDS_HUMAN" and a.age_hours() >= min_age_h)]

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.alerts.values():
            out[a.state] = out.get(a.state, 0) + 1
        return out
