"""A box read that survives its own timeout: live read, else the last good read with its age.

WHY (2026-10-29, MT5-ProcessHealth). `schtasks /query` measured 34.5 s idle on the trading box
and went past its 45 s bound -- and past the detached retry's 180 s bound -- on three hourly
passes in a row, so every one of 73 tasks read SCHEDULER_UNMEASURED. A single slow read threw
away everything the board knew an hour earlier. The class is "a bounded box read whose only
failure mode is UNMEASURED"; this is the one helper every such read in ops/process_health.py
goes through, so none of them can regress to that shape on its own.

THE CONTRACT, per read (a `key`):

    live      the read answered: its value is stored with its timestamp, the counter resets
    cache     the read failed, the last good value is younger than `max_age_s`: it is served
              with its age, never passed off as fresh
    unmeasured  no live read and no cache inside its max age: the consecutive-unmeasured
              counter goes up, and past RED_AFTER_RUNS it is `red` -- a read that stays dark
              is a defect the board must shout about, not a grey row to scroll past

The BOUNDED RETRY with a longer timeout is the caller's (process_health's detached
below-normal child, so the hourly pass never overruns its own slot). That child reads through
here with `count=False`: a retry is part of the same run, so it can reset the counter by
landing but never double-count a failure.

The state file is the caller's, gitignored, and written atomically. A cache that cannot be read
or written is reported in the outcome and never raises: losing the cache costs a fallback, it
must never cost the live read.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: A read UNMEASURED for MORE than this many consecutive runs is RED (coordinator, rule 23).
RED_AFTER_RUNS = 2


class ReadFailed(Exception):
    """The read did not produce a value this caller can trust; the message says why."""


@dataclass
class Outcome:
    source: str                     # "live" | "cache" | "unmeasured"
    value: Any = None
    at: str | None = None           # when the value served was read (live: now)
    age_s: float | None = None      # 0 for live, None for unmeasured
    unmeasured_runs: int = 0
    red: bool = False
    error: str = ""                 # why the live read failed ("" when it answered)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """The JSON-safe facts about this read, for the report (never the value itself)."""
        return {"source": self.source, "at": self.at,
                "age_min": None if self.age_s is None else round(self.age_s / 60.0, 1),
                "unmeasured_runs": self.unmeasured_runs, "red": self.red,
                "error": self.error[:300] or None, "notes": self.notes or None}


def _load(path: Path) -> tuple[dict[str, Any], str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, ""
    except (OSError, ValueError) as exc:
        return {}, f"cache unreadable ({type(exc).__name__}); treated as empty"
    return (doc, "") if isinstance(doc, dict) else ({}, "cache not a mapping; treated as empty")


def _save(path: Path, doc: dict[str, Any]) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        return ""
    except OSError as exc:
        with contextlib.suppress(OSError, UnboundLocalError):
            tmp.unlink(missing_ok=True)
        return f"cache not written ({type(exc).__name__})"


def _parse_at(raw: Any) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def read_through(path: Path, key: str, read: Callable[[], Any], max_age_s: float, *,
                 count: bool = True, now: datetime | None = None) -> Outcome:
    """Run `read()`; on any exception fall back to the cached value for `key` if young enough.

    `read` returns a JSON-serialisable value or raises (ReadFailed for an answer it rejects).
    Only a value `read` returned is ever stored, so the cache holds good reads only.
    """
    now = now or datetime.now(tz=UTC)
    state, note = _load(path)
    notes = [note] if note else []
    raw = state.get(key)
    entry: dict[str, Any] = raw if isinstance(raw, dict) else {}
    try:
        runs = int(entry.get("unmeasured_runs") or 0)
    except (TypeError, ValueError):
        runs = 0
    try:
        value = read()
    except Exception as exc:
        error = str(exc) if isinstance(exc, ReadFailed) else f"{type(exc).__name__}: {exc}"
    else:
        state[key] = {"at": now.isoformat(timespec="seconds"), "value": value,
                      "unmeasured_runs": 0}
        if saved := _save(path, state):
            notes.append(saved)
        return Outcome("live", value, now.isoformat(timespec="seconds"), 0.0, 0, False, "",
                       notes)

    at = _parse_at(entry.get("at")) if entry else None
    age = (now - at).total_seconds() if at is not None else None
    if at is not None and "value" in entry and age is not None and 0 <= age <= max_age_s:
        if count and runs:
            entry["unmeasured_runs"] = 0     # a served cache is not an unmeasured run
            state[key] = entry
            if saved := _save(path, state):
                notes.append(saved)
        return Outcome("cache", entry["value"], str(entry["at"]), age, 0, False, error, notes)

    if count:
        runs += 1
        state[key] = {**entry, "unmeasured_runs": runs,
                      "last_unmeasured_at": now.isoformat(timespec="seconds")}
        if saved := _save(path, state):
            notes.append(saved)
    if at is not None and age is not None:
        notes.append(f"cache {age / 3600:.1f} h old, past its {max_age_s / 3600:g} h max age")
    return Outcome("unmeasured", None, None, None, runs, runs > RED_AFTER_RUNS, error, notes)
