"""JUDGING_RATE ATTEMPT MARKER -- say which pass of the judging_throughput leg died, and where.

THE DEFECT (measured 2026-10-21 from published box state). `JUDGING_RATE.json` held `at`
2026-10-21T01:52:06Z for hours while the box went on publishing every fifteen minutes and other
hourly artifacts (RESEARCH_BUDGET 03:59Z, REPLICATION) kept moving. `judging_throughput.run()`
measured the box, the queue, the plan, the schtasks limit and the ~970k-row verdict ledger BEFORE
it wrote anything, on a box with ~1.6 GB free while external_gauntlet held ~4.1 GB. A pass killed
at its budget -- or one the scheduler never reached -- left the old file in place, and no reader
could tell an old measurement from a current one, or say why.

WHAT THIS DOES. The first thing `run()` does is write `JUDGING_RATE.attempt.json` (published
beside `JUDGING_RATE.json` by sync_shadow_to_git.ps1) naming the pass's `started_at`, `pid` and
the PHASE it has entered; each later phase rewrites it, atomically (tmp then `os.replace`, with
the Windows PermissionError retry). A pass that dies leaves the phase it died in on disk. The
successful rate write carries a pointer back to its attempt, so the two are tied by `started_at`.

HOW IT IS READ (`read_rate`). The rate is FRESH only when its own `at` is no older than the
marker's `started_at` (this pass produced it) and no older than `max_age_s`. A marker newer than
the rate past the leg's budget reads STALE with "attempt started <t> died in phase <p>"; a marker
newer than the rate inside that budget is a pass still running and the rate is judged by its age.
A torn or unparseable marker, or a rate with no `at`, is UNMEASURED -- never an old number read
as a current one (L1.28a).

Writing the marker can never cost the measurement: every failure to write it is swallowed and
the pass goes on exactly as it did before this module existed.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
RATE_PATH = BASE / "reports" / "JUDGING_RATE.json"
ATTEMPT_PATH = BASE / "reports" / "JUDGING_RATE.attempt.json"
ATTEMPT_REL = "desks/mt5/reports/JUDGING_RATE.attempt.json"

UNMEASURED = "UNMEASURED"
FRESH = "FRESH"
STALE = "STALE"

#: The phases `judging_throughput.run()` enters, in order. The marker names the one ENTERED last,
#: so a marker reading `rate` means the pass died while streaming the verdict ledger.
PHASES = ("started", "measure_box", "queue", "plan", "rate", "rate_written", "task_limit",
          "written", "applied")
#: Phases after which JUDGING_RATE.json on disk is this pass's own.
RATE_PUBLISHED_PHASES = frozenset({"rate_written", "task_limit", "written", "applied"})

#: The leg's own budget in hourly_cycle (the `judging_throughput` entry, 400 s). A marker newer
#: than the rate by less than this is a pass still running, not a pass that died. Read here, never
#: used to change the leg's timing.
ATTEMPT_GRACE_S = 400.0
#: The leg is hourly: a rate older than two hours has missed at least one whole pass.
MAX_AGE_S = 7200.0

REPLACE_RETRIES = 6
REPLACE_BACKOFF_S = 0.05


def write_atomic(path: Path, doc: Any) -> None:
    """tmp then `os.replace`, retrying the Windows PermissionError a reader's open handle causes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    for i in range(REPLACE_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == REPLACE_RETRIES - 1:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise
            time.sleep(REPLACE_BACKOFF_S * (2 ** i))


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _parse(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else None


class Attempt:
    """One pass's marker. `phase()` rewrites it; nothing it does can raise into the pass."""

    def __init__(self, started_at: datetime, path: Path | None = None,
                 enabled: bool = True) -> None:
        self.path = ATTEMPT_PATH if path is None else path
        self.enabled = enabled
        self.started_at = _iso(started_at)
        self.pid = os.getpid()
        self._t0 = time.monotonic()
        self.phases: list[dict[str, Any]] = []
        self.last_error: str | None = None

    def pointer(self) -> dict[str, Any]:
        """The field the successful JUDGING_RATE.json write carries back to its marker."""
        return {"marker": ATTEMPT_REL, "started_at": self.started_at, "pid": self.pid}

    def phase(self, name: str, *, done: bool = False, **extra: Any) -> None:
        if not self.enabled:
            return
        now = datetime.now(UTC)
        self.phases.append({"phase": name, "at": _iso(now),
                            "elapsed_s": round(time.monotonic() - self._t0, 1)})
        doc = {"schema": 1, "started_at": self.started_at, "pid": self.pid, "phase": name,
               "phase_at": _iso(now), "done": bool(done), "phases": self.phases,
               "rule": ("the phase named here is the one this pass ENTERED last; a marker newer "
                        "than JUDGING_RATE.json's `at` past the leg budget is a pass that died "
                        "there, and JUDGING_RATE.json reads STALE with that reason"), **extra}
        try:
            write_atomic(self.path, doc)
        except Exception as exc:   # the marker is evidence, never a reason to fail the pass
            self.last_error = f"{type(exc).__name__}: {exc}"


def _read_doc(path: Path) -> tuple[str, Any]:
    """('absent' | 'torn' | 'ok', doc)."""
    if not path.exists():
        return "absent", None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return "torn", f"{type(exc).__name__}: {exc}"
    if not isinstance(doc, dict):
        return "torn", f"top level is {type(doc).__name__}, not an object"
    return "ok", doc


def read_rate(now: datetime | None = None, *, rate_path: Path | None = None,
              attempt_path: Path | None = None, max_age_s: float = MAX_AGE_S,
              grace_s: float = ATTEMPT_GRACE_S) -> dict[str, Any]:
    """JUDGING_RATE.json with a verdict: {status: FRESH|STALE|UNMEASURED, why, rate, attempt}.

    `rate` is the document as written (the last measured counts stay readable for diagnosis),
    but a caller must use its numbers only when `status` is FRESH."""
    t = datetime.now(UTC) if now is None else now
    rp = RATE_PATH if rate_path is None else rate_path
    ap = ATTEMPT_PATH if attempt_path is None else attempt_path
    rstate, rate = _read_doc(rp)
    astate, att = _read_doc(ap)
    out: dict[str, Any] = {"status": UNMEASURED, "why": "",
                           "rate": rate if rstate == "ok" else None,
                           "attempt": att if astate == "ok" else None}
    if rstate == "absent":
        out["why"] = f"{rp.name} absent: the judging rate is UNMEASURED"
        return out
    if rstate == "torn":
        out["why"] = f"{rp.name} unreadable ({rate}): the judging rate is UNMEASURED"
        return out
    if astate == "torn":
        out["why"] = (f"{ap.name} torn ({att}): which pass wrote {rp.name} cannot be told, so the "
                      "judging rate is UNMEASURED")
        return out
    rate_at = _parse(rate.get("at"))
    if rate_at is None:
        out["why"] = f"{rp.name} carries no timezone-aware `at`: its age is UNMEASURED"
        return out
    if astate == "ok":
        started = _parse(att.get("started_at"))
        phase = str(att.get("phase") or "?")
        if started is None:
            out["why"] = (f"{ap.name} carries no timezone-aware `started_at`: which pass wrote "
                          f"{rp.name} cannot be told, so the judging rate is UNMEASURED")
            return out
        if started > rate_at:
            running_s = (t - started).total_seconds()
            if running_s > grace_s:
                out["status"] = STALE
                out["why"] = (f"attempt started {_iso(started)} died in phase {phase}; "
                              f"{rp.name} still holds the pass of {_iso(rate_at)}")
                out["died_in_phase"] = phase
                return out
            out["attempt_in_progress"] = {"started_at": _iso(started), "phase": phase,
                                          "running_s": round(running_s, 1)}
    age = (t - rate_at).total_seconds()
    out["age_s"] = round(age, 1)
    if age > max_age_s:
        out["status"] = STALE
        out["why"] = (f"{rp.name} `at` {_iso(rate_at)} is {age / 3600.0:.1f} h old (over "
                      f"{max_age_s / 3600.0:.1f} h)"
                      + ("" if astate == "ok" else f"; no {ap.name} says why"))
        return out
    if age < -300:
        out["why"] = f"{rp.name} `at` {_iso(rate_at)} is in the future: UNMEASURED"
        return out
    if str(rate.get("status") or "") == UNMEASURED:
        out["why"] = f"the pass of {_iso(rate_at)} measured nothing: {rate.get('why') or '?'}"
        return out
    out["status"] = FRESH
    out["why"] = f"measured {_iso(rate_at)}"
    return out
