"""DURABLE CHECKPOINT / RESUME -- gate item 16, mandate V-A and V-B.

THE LAW: economically important sweeps, backfills, replications and large experiments must
support durable checkpoint/resume where practical, so high-VOI work can preempt lower-value work
WITHOUT DESTROYING COMPLETED COMPUTATION (V-A).

THE GAP IT CLOSES, measured on this desk. The research miner issues ~1,000 rate-limited network
units per deep sweep across nine hosts and takes minutes. When it dies -- a 429, a container
restart, a timeout -- every completed unit is lost and the next run refetches from zero. That is
not merely wasted wall-clock: refetching a host that just rate-limited you is how a temporary
refusal becomes a durable block, which the miner's own bilibili backoff comment already says in
so many words. So restart-from-zero actively DAMAGES the sources the desk depends on. RESTART
WASTE is one of V-B's named research-factory metrics precisely because it is invisible without a
counter.

THE FOUR FAILURE MODES THIS REFUSES, all of which are worse than having no checkpoint at all:

  * SILENT RESTART FROM ZERO. A truncated or corrupt checkpoint that reads as "nothing to resume"
    hands back a clean-looking full rerun. The caller cannot tell a fresh start from a lost one.
    load() returns CORRUPT as its own state and run() refuses by default.
  * SPLICED EXPERIMENTS. Resuming a sweep whose inputs or parameters changed silently welds half
    of one experiment onto half of another. Every checkpoint carries a SIGNATURE of its work
    definition; a mismatch is STALE_SIGNATURE, never a quiet reuse.
  * STALE RESUME. A checkpoint from days ago is not a resume, it is a time machine serving old
    observations as fresh ones. Checkpoints EXPIRE.
  * FAILURE RECORDED AS COMPLETION. A unit that raised must not be checkpointed, or a transient
    429 becomes a permanently skipped query that no later run ever retries.

And one mechanical guarantee underneath all four: TORN WRITES ARE IMPOSSIBLE. Saves go to a
same-directory temp file and os.replace() atomically. Same-directory matters -- os.replace is
atomic only within one filesystem, and a cross-device replace degrades to copy-then-delete, which
is the exact torn write this is meant to prevent.

AUTHORITY: MECHANICAL ONLY. This module stores and returns completed work. It never decides what
work is worth doing, never re-runs anything on its own, and never suppresses an error.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CheckpointCorrupt",
    "Load",
    "SweepResult",
    "clear",
    "load",
    "restart_waste",
    "run",
    "save",
    "signature_of",
]

_ROOT = Path(__file__).resolve().parents[2]
DIR = "data/checkpoints"

#: A checkpoint older than this is EXPIRED, not resumable. Default 3h sits below the miner's 4h
#: cron spacing, so a resume can only ever pick up a run that died within the current cycle.
DEFAULT_MAX_AGE_H = 3.0


class CheckpointCorrupt(RuntimeError):
    """Raised when a checkpoint exists but cannot be trusted, and the caller did not opt in to
    discarding it. Loud by construction: the alternative is a silent restart from zero."""


@dataclass(frozen=True)
class Load:
    """The result of reading a checkpoint. ``status`` is never a guess.

    RESUMABLE       -- verified, in-signature, fresh; ``done`` holds completed units
    NONE            -- no checkpoint exists (a genuine fresh start)
    CORRUPT         -- unreadable or hash-mismatched: a LOSS, distinct from NONE (L1.41)
    STALE_SIGNATURE -- exists but describes different work
    EXPIRED         -- exists and verifies, but is too old to be evidence about now
    """

    status: str
    done: dict[str, Any] = field(default_factory=dict)
    why: str = ""
    saved_utc: str = ""
    age_h: float | None = None
    #: Units a prior attempt claimed to have completed but which this load cannot hand back.
    #: None means UNKNOWABLE -- a corrupt checkpoint destroys even the accounting of what was
    #: lost, which is why CORRUPT is a worse state than NONE and must never collapse into it.
    n_prior: int | None = None

    @property
    def n_done(self) -> int:
        return len(self.done)

    @property
    def resumable(self) -> bool:
        return self.status == "RESUMABLE"


@dataclass(frozen=True)
class SweepResult:
    """What a resumable sweep produced, plus the V-B metrics that make waste visible."""

    results: dict[str, Any]
    executed: list[str]
    resumed: list[str]
    failed: dict[str, str]
    load_status: str
    why: str
    units_total: int = 0
    n_prior_lost: int | None = None

    @property
    def restart_waste(self) -> float | None:
        """V-B RESTART_WASTE: the share of this attempt's units that a PRIOR attempt had already
        completed and this one had to pay for again.

        0.0 on a genuine fresh start (nothing existed to reuse) and on a clean resume (prior work
        was handed back). It rises only when completed computation was destroyed. It is None --
        UNMEASURED, never zero -- after a CORRUPT load, because a checkpoint too damaged to read
        is also too damaged to say how much it held. Reporting that as 0% waste would be exactly
        the silent-restart lie this module exists to prevent (L1.41).
        """
        if self.load_status == "CORRUPT" and self.n_prior_lost is None:
            return None
        lost = min(int(self.n_prior_lost or 0), len(self.executed))
        return (lost / self.units_total) if self.units_total else 0.0

    @property
    def reuse_rate(self) -> float:
        return (len(self.resumed) / self.units_total) if self.units_total else 0.0

    @property
    def complete(self) -> bool:
        return not self.failed


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _path(name: str, root: Path | None = None) -> Path:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in str(name))[:120]
    return (root or _ROOT) / DIR / f"{safe}.json"


def signature_of(*parts: Any) -> str:
    """A stable fingerprint of the work DEFINITION: unit list, parameters, code version.

    Two runs share a signature only if they are the same experiment. Anything that would change
    what a unit MEANS belongs in here -- otherwise a resume splices two experiments together.
    """
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _digest(signature: str, done: dict[str, Any]) -> str:
    blob = json.dumps({"s": signature, "d": done}, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def save(name: str, signature: str, done: dict[str, Any], *, root: Path | None = None) -> Path:
    """Write a checkpoint ATOMICALLY. A crash mid-write leaves the previous checkpoint intact."""
    p = _path(name, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "v": 1,
        "name": str(name),
        "signature": str(signature),
        "saved_utc": _now().isoformat(timespec="seconds"),
        "n_done": len(done),
        "done": done,
        "sha256": _digest(str(signature), done),
    }
    tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)
    return p


def load(name: str, signature: str | None = None, *, root: Path | None = None,
         max_age_h: float = DEFAULT_MAX_AGE_H) -> Load:
    """Read a checkpoint and say precisely what it is. Never raises, never guesses.

    The verification ORDER matters: integrity BEFORE signature BEFORE age. A corrupt file must be
    reported as corrupt even if it also happens to be old, because "we lost work" and "the work
    aged out" call for different responses from the caller and from whoever reads the log.
    """
    p = _path(name, root)
    try:
        raw = p.read_text("utf-8")
    except FileNotFoundError:
        return Load("NONE", {}, "no checkpoint on disk -- a genuine fresh start, not a lost one")
    except OSError as exc:
        return Load("CORRUPT", {}, f"checkpoint unreadable: {type(exc).__name__}: {exc}")

    try:
        doc = json.loads(raw)
    except ValueError as exc:
        return Load("CORRUPT", {},
                    f"checkpoint is not valid JSON ({exc}) -- almost certainly a torn write. This "
                    "is a LOSS of completed work, not an absence of it")
    if not isinstance(doc, dict):
        return Load("CORRUPT", {}, "checkpoint is not an object")

    done = doc.get("done")
    if not isinstance(done, dict):
        return Load("CORRUPT", {}, "checkpoint has no 'done' map")
    sig = str(doc.get("signature", ""))
    if str(doc.get("sha256", "")) != _digest(sig, done):
        return Load("CORRUPT", {},
                    "checkpoint content hash does not match its payload -- truncated or edited. "
                    "Refusing to treat damaged state as completed work")

    saved = str(doc.get("saved_utc", ""))
    try:
        ts = datetime.fromisoformat(saved)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        age_h = (_now() - ts).total_seconds() / 3600.0
    except ValueError:
        # L1.41: an unparseable timestamp is UNKNOWN age, and unknown must not read as fresh --
        # that would make a checkpoint with a mangled date resumable forever.
        age_h = float("inf")

    if signature is not None and sig != str(signature):
        return Load("STALE_SIGNATURE", {},
                    f"checkpoint describes different work (saved sig {sig!r} != current "
                    f"{signature!r}) -- resuming would splice two experiments together",
                    saved, age_h, len(done))
    if age_h > float(max_age_h):
        return Load("EXPIRED", {},
                    f"checkpoint is {age_h:.1f}h old (limit {float(max_age_h):.1f}h) -- resuming "
                    "would serve stale observations as current ones", saved, age_h, len(done))
    return Load("RESUMABLE", dict(done),
                f"{len(done)} completed unit(s) verified, in-signature, {age_h:.2f}h old",
                saved, age_h, len(done))


def clear(name: str, *, root: Path | None = None) -> bool:
    """Delete a checkpoint. Called on SUCCESSFUL completion -- a finished sweep has nothing to
    resume, and a stale success record is the fastest route to a spliced next run."""
    try:
        _path(name, root).unlink()
        return True
    except OSError:
        return False


def restart_waste(*, units_total: int, units_executed: int) -> dict[str, Any]:
    """V-B metric, standalone. What share of an attempt's units had already been done before?

    Reported as a RATIO plus its two counts, because the ratio alone hides scale: 100% waste on a
    2-unit sweep is noise, and 30% on a 200-unit rate-limited sweep is a source being hammered.
    """
    total = max(0, int(units_total))
    ex = max(0, int(units_executed))
    reused = max(0, total - ex)
    return {
        "units_total": total,
        "units_executed": ex,
        "units_reused": reused,
        "restart_waste": (ex / total) if total else 0.0,
        "reuse_rate": (reused / total) if total else 0.0,
        "what": "restart_waste is the share of units this attempt paid for again; reuse_rate is "
                "the share served from durable state",
    }


def run(name: str, units: Sequence[Any], work: Callable[[Any], Any], *,
        key: Callable[[Any], str] = str,
        signature: str | None = None,
        root: Path | None = None,
        max_age_h: float = DEFAULT_MAX_AGE_H,
        save_every: int = 1,
        on_corrupt: str = "REFUSE",
        clear_on_success: bool = True,
        stop_on_error: bool = False) -> SweepResult:
    """GATE ITEM 16. Make any enumerable sweep durably resumable.

    ``work(unit)`` runs once per unit and its return value is checkpointed. It must therefore be
    JSON-serialisable, and the caller must accept that a unit recorded as done will NOT run again.

    on_corrupt:
      REFUSE  (default) -- raise CheckpointCorrupt. Correct for economically important work: a
                           human must see that completed computation was lost.
      RESTART -- start from zero, but record CORRUPT in load_status and leave restart_waste
                 UNMEASURED. Correct only where the work is idempotent and cheap to redo. Never
                 silent either way.

    A unit that raises is recorded in ``failed`` and is NOT checkpointed, so the next attempt
    retries it. Failure is not completion.
    """
    materialised = list(units)
    keys = [key(u) for u in materialised]
    sig = signature if signature is not None else signature_of(keys)
    st = load(name, sig, root=root, max_age_h=max_age_h)
    if st.status == "CORRUPT":
        if str(on_corrupt).upper() == "REFUSE":
            raise CheckpointCorrupt(
                f"checkpoint {name!r}: {st.why}. Completed work was lost -- refusing to restart "
                "from zero silently. Pass on_corrupt='RESTART' to redo it deliberately")
        clear(name, root=root)

    done: dict[str, Any] = dict(st.done) if st.resumable else {}
    resumed = sorted(done)
    executed: list[str] = []
    failed: dict[str, str] = {}
    pending = 0

    for unit, k in zip(materialised, keys, strict=True):
        if k in done:
            continue
        try:
            done[k] = work(unit)
        except Exception as exc:  # recorded in `failed`, never swallowed
            failed[k] = f"{type(exc).__name__}: {exc}"
            if stop_on_error:
                save(name, sig, done, root=root)
                raise
            continue
        executed.append(k)
        pending += 1
        if pending >= max(1, int(save_every)):
            save(name, sig, done, root=root)
            pending = 0

    if pending:
        save(name, sig, done, root=root)

    finished = not failed and len(done) >= len(set(keys))
    if finished and clear_on_success:
        clear(name, root=root)
    else:
        save(name, sig, done, root=root)

    return SweepResult(
        results=done, executed=executed, resumed=resumed, failed=failed,
        load_status=st.status,
        units_total=len(set(keys)),
        n_prior_lost=(st.n_prior if st.status in ("STALE_SIGNATURE", "EXPIRED", "CORRUPT")
                      else 0),
        why=(f"{len(resumed)} unit(s) resumed from durable state, {len(executed)} executed, "
             f"{len(failed)} failed ({st.status}: {st.why})"))
