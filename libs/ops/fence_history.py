#!/usr/bin/env python3
"""FENCE YIELD RECENCY (L1.43) -- "has it EVER fired" is an ABSORBING claim, and an absorbing
counter is structurally incapable of reporting the one event it exists to reveal: a fence going
dark.

THE DEFECT, MEASURED AT THE CODE. `check_fence_yield` records what each fence has ever said into
`data/fence_yield_history.json` as a DEDUPLICATED SET OF VERDICT STRINGS under ONE GLOBAL
timestamp:

    {"seen": {"law_families": ["FAILING", "OK"]}, "updated": "2026-08-19T20:06:15+00:00"}

and then asks `any(v in fire_values for v in seen)`. Once a firing verdict enters that list it
NEVER LEAVES. A fence that fired five hundred times last week and one that fired once in July are
BYTE-IDENTICAL in that structure, and both read FIRED forever. Measured 2026-08-19 over the 16
registered fences: 10 are already permanently immune to ever reading QUIET again through
ACCUMULATED live verdicts, 4 more through deliberate seeding, and 2 remain able to report
silence. The census that exists to find inert checks had made itself unable to find them, and it
becomes MORE blind every day it runs -- every new firing is another verdict that can never expire.

THE DESK HAS ALREADY KILLED THIS EXACT SHAPE TWICE and never turned the logic on the organ that
grades fences: R0352 (the carry-bleed alarm, a cumulative lifetime ratio that could never clear
once tripped) and R0492 (the panel seat-blank counter, a bare integer with no window). An
absorbing counter is not a memory, it is a ratchet pointed at the reader.

WHAT THIS DOES NOT CLAIM, AND THE LIMIT IS REAL. Recency here is the last time THE CENSUS SAW a
fence firing, never the last time it ACTUALLY fired. `check_fence_yield` reads each fence's
current artifact once a day, so a fence that fires at 03:00 and is repaired by 04:00 is never
observed at all -- which is precisely why `_SEEDED` exists in that file. This module inherits that
aliasing and must not launder it: a firing this census never saw is not a firing this census may
report on. Closing THAT gap needs the producers to append their own verdict history, which is a
different build and is rowed separately, not quietly assumed here.

FIVE STATES, and the two absence states stay DISTINCT (L1.28a, L1.55):
  FIRED-RECENTLY  a firing verdict was observed within the last `quiet_after` observations.
  FIRED-STALE     it fired, and has been silent for longer than that. THE NEW SIGNAL: a fact with
                  a number attached, routed to the weekly sweep exactly as QUIET already is.
  FIRED-UNDATED   a firing is known -- from the legacy migration or from seeded historical
                  evidence -- but WHEN is unknown. It must never read as RECENT (that preserves
                  the absorbing bug) and never as STALE (that is an unearned accusation against a
                  possibly-healthy fence). It is its own answer, and it SELF-HEALS: the next live
                  observation carries a real date and supersedes it.
  NEVER           no firing verdict has ever been recorded for this fence.
  UNREADABLE      the history exists and could not be parsed. NOT the same as absent: one means
                  no census has ever run, the other means one ran and wrote garbage, and they
                  demand opposite repairs (L1.55).

EVIDENCE-DENOMINATED, NOT CALENDAR (L1.48). The window counts OBSERVATIONS OF THIS CENSUS, never
elapsed days, so a fence looked at hourly and one looked at weekly are judged by how many times
each was actually examined. Days are published alongside as descriptive metadata for a human
reader; nothing keys on them.

THIS LIFTS NOTHING AND FAILS NOTHING. `check_fence_yield` is an evidence organ that proposes no
retirements and fails no build (L1.26/L1.43), and it stays one: every state this module can
return maps to a passing status. Its whole effect is to make "this fence caught something
yesterday" distinguishable from "this fence caught something once, in July" -- byte-identical on
this desk until now, and only one of them is evidence that the fence still works.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Observations of the census a fence may go without firing before its silence is REPORTED as a
#: fact. Counts runs, never days (L1.48). At the scheduled daily cadence this is ~30 days; the
#: point of denominating it in runs is that a cadence change cannot silently redefine it.
QUIET_AFTER_RUNS = 30

#: The four states a firing question can resolve to, plus the parse failure. Every one of them is
#: a PASSING state for the census: this module reports, it does not judge (L1.26).
STATES = ("FIRED-RECENTLY", "FIRED-STALE", "FIRED-UNDATED", "NEVER", "UNREADABLE")


@dataclass
class History:
    """Dated per-verdict observation history for the fence census.

    `seen` is `{fence: {verdict: {"last": iso|None, "last_run": int|None, "count": int}}}`.
    `last_run` is the value of `runs` at the observation, which is what recency is measured in;
    `last` is the ISO stamp, carried for humans and never keyed on.
    """

    runs: int = 0
    seen: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    source: str = "NEW"
    n_migrated: int = 0

    # ---- observation -------------------------------------------------------------------

    def bump(self) -> int:
        """One census run = one observation. Called ONCE per run, not once per fence."""
        self.runs += 1
        return self.runs

    def record(self, fence: str, verdict: str, *, now: datetime | None = None) -> None:
        """Record that `fence` was observed saying `verdict` at the current run."""
        stamp = (now or datetime.now(tz=UTC)).isoformat()
        entry = self.seen.setdefault(fence, {}).setdefault(
            verdict, {"last": None, "last_run": None, "count": 0})
        entry["last"] = stamp
        entry["last_run"] = self.runs
        entry["count"] = int(entry.get("count") or 0) + 1

    def seed(self, fence: str, verdict: str) -> None:
        """Record a firing known from the commit record but never observed by this census.

        Deliberately UNDATED. Seeded evidence proves the fence CAUGHT something once; it carries
        no information about whether the fence still works, and dating it `now` would manufacture
        exactly the false recency this module exists to remove.
        """
        self.seen.setdefault(fence, {}).setdefault(
            verdict, {"last": None, "last_run": None, "count": 0})

    # ---- the question ------------------------------------------------------------------

    def recency(self, fence: str, firing_values: tuple[str, ...] | frozenset[str],
                *, quiet_after: int = QUIET_AFTER_RUNS) -> dict[str, Any]:
        """When did `fence` last fire, and is that recent? See the module docstring for states."""
        if self.source == "UNREADABLE":
            return {"state": "UNREADABLE", "runs_since": None, "days_since": None,
                    "last": None, "fired_verdicts": [],
                    "note": "the yield history exists and could not be parsed -- a census ran "
                            "and wrote garbage, which is not the same as no census ever running "
                            "(L1.55). Repair the file; do not read this as clean."}
        entries = self.seen.get(fence, {})
        firing = {v: e for v, e in entries.items() if v in set(firing_values)}
        if not firing:
            return {"state": "NEVER", "runs_since": None, "days_since": None, "last": None,
                    "fired_verdicts": [], "note": "no firing verdict has ever been recorded"}
        dated = {v: e for v, e in firing.items() if e.get("last_run") is not None}
        if not dated:
            return {"state": "FIRED-UNDATED", "runs_since": None, "days_since": None,
                    "last": None, "fired_verdicts": sorted(firing),
                    "note": "it fired -- from the legacy set or from seeded evidence -- and WHEN "
                            "is unknown. Not recent, not stale: unmeasured (L1.28a). The next "
                            "live observation carries a date and supersedes this."}
        best_v = max(dated, key=lambda v: int(dated[v]["last_run"] or 0))
        best = dated[best_v]
        since = self.runs - int(best["last_run"] or 0)
        state = "FIRED-RECENTLY" if since <= quiet_after else "FIRED-STALE"
        return {
            "state": state,
            "runs_since": since,
            "days_since": _days_since(best.get("last")),
            "last": best.get("last"),
            "fired_verdicts": sorted(firing),
            "count": int(best.get("count") or 0),
            "note": (f"last observed firing {best_v!r} {since} census run(s) ago"
                     + ("" if state == "FIRED-RECENTLY" else
                        f" -- silent for longer than the {quiet_after}-run window; report it, "
                        f"never auto-retire (L1.23/L1.43)")),
        }

    # ---- serialisation -----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"seen": self.seen, "runs": self.runs,
                "updated": datetime.now(tz=UTC).isoformat(),
                "format": "dated-v2",
                "note": "per-verdict last_run/last/count. The v1 format was a deduplicated set "
                        "of verdict strings under one global timestamp, in which a fence that "
                        "fired once in July was indistinguishable from one firing daily "
                        "(L1.43)."}


def _days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return round((datetime.now(tz=UTC) - then).total_seconds() / 86400.0, 2)


def load(path: Path) -> History:
    """Read the history, migrating the legacy set-of-strings format WITHOUT inventing dates.

    THE MIGRATION IS THE LOAD-BEARING PART. The legacy file records THAT a verdict was seen and
    never WHEN, so every carried-over verdict resolves to FIRED-UNDATED -- honest, and it decays
    into a real signal as live observations arrive. Stamping the migration date onto those
    entries would have read as "every fence fired today", turning a fourteen-day blind spot into
    a fabricated clean bill of health on the day the fix shipped.
    """
    if not path.exists():
        return History(source="NEW")
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return History(source="UNREADABLE")
    if not isinstance(doc, dict):
        return History(source="UNREADABLE")
    raw = doc.get("seen")
    if not isinstance(raw, dict):
        return History(source="UNREADABLE")

    hist = History(runs=int(doc.get("runs") or 0), source="DATED")
    migrated = 0
    for fence, verdicts in raw.items():
        if isinstance(verdicts, list):                       # v1: ["OK", "FAILING"]
            hist.source = "LEGACY"
            hist.seen[fence] = {str(v): {"last": None, "last_run": None, "count": 0}
                                for v in verdicts}
            migrated += len(verdicts)
        elif isinstance(verdicts, dict):                     # v2: {"OK": {...}}
            out: dict[str, dict[str, Any]] = {}
            for verdict, entry in verdicts.items():
                if isinstance(entry, dict):
                    out[str(verdict)] = {
                        "last": entry.get("last"),
                        "last_run": (int(entry["last_run"])
                                     if isinstance(entry.get("last_run"), int) else None),
                        "count": int(entry.get("count") or 0),
                    }
                else:                                        # a malformed entry is UNDATED, not
                    out[str(verdict)] = {"last": None, "last_run": None, "count": 0}
                    migrated += 1                            # silently dropped (L1.60)
            hist.seen[fence] = out
    hist.n_migrated = migrated
    return hist
