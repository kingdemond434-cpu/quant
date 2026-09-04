"""Point-in-time provenance, stamped at ingestion rather than described in a document.

WHAT THE CENSUS FOUND. The data-governance doctrine names event_time, available_time,
ingested_time, revision_time, source_version and a payload hash for every ingested row. Across
61,699 discovery rows from 46 miner sources, the fields actually present were `found_at` (68%),
`captured_at` and `event_date` (6%), and none of the others -- so the doctrine was documentary,
and a lookahead through a row's availability time could not be caught by anything that reads the
rows, because nothing on the row says when it became knowable.

THE STAMP. `stamp(row, source, ...)` adds, without overwriting anything the producer set:

    event_time      when the thing the row describes happened (the producer's best field)
    available_time  when the desk COULD have known it -- the producer's publish/capture time,
                    else `ingested_time`; a row is usable for a decision at t only if
                    available_time <= t
    ingested_time   now, when this stamp was applied
    source_version  the producer's declared version, else the code's git HEAD
    payload_hash    sha256 of the row's content EXCLUDING the stamp -- so the same finding
                    ingested twice hashes the same and a changed row does not

`usable_at(row, t)` is the one check the backtester and every joiner should make. It is
deliberately conservative: a row with no stamp is NOT usable at any time, because "absence is
not permission" is the doctrine this exists to make mechanical.

WIRED WHERE ROWS ARE MADE. `proposer_common.donate` stamps every proposer's rows; the fund
playbook stamps its cards; `scripts/check_pit.py` publishes the census so the fraction of rows
carrying the stamp is a generated number rather than a claim.

REVISIONS (2026-09-04). A row that is corrected later -- a COT figure restated, a calendar
consensus revised, a card re-scored -- must not overwrite the row the desk actually decided on,
because the backtest must see what was knowable THEN and the audit must see what was learned
SINCE. `revise(row, revision_of=...)` returns a fresh stamped copy chained to its predecessor:

    revision_id      sha256(revision_of + payload_hash)[:16] -- the edge in the chain
    revision_of      the predecessor's payload_hash
    revision_time    when the revision was made (ISO, UTC)
    revision_n       1 for the first revision, the predecessor's n + 1 after that
    revision_reason  why, in the producer's words

A revision is knowable when it is MADE: its available_time is never earlier than its
revision_time, whatever the original row said, because a decision taken before the correction
existed could not have used it. `latest_as_of(rows, key_fields, t)` is the joiner's read: per
key, the newest revision usable at `t` -- so a backtest at t sees the vintage that existed at t
and the live desk sees the latest. The revision fields, like the stamp fields, are OUTSIDE the
payload hash: a restatement carrying the same content hashes the same, and only content moves
the hash.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STAMP_FIELDS = ("event_time", "available_time", "ingested_time", "source_version",
                "payload_hash")
#: Revision provenance, written by `revise` only. Excluded from the payload hash for the same
#: reason the stamp is: they describe the row's history, not its content.
REVISION_FIELDS = ("revision_id", "revision_of", "revision_time", "revision_n",
                   "revision_reason")

#: Producer fields consulted, in order, for each stamp field. DECLARED so a new producer can
#: see what it must write for its rows to be point-in-time by construction.
EVENT_KEYS = ("event_time", "event_date", "date", "datetime", "timestamp", "published_at")
AVAILABLE_KEYS = ("available_time", "published_at", "captured_at", "found_at")

_HEAD: str | None = None


def _git_head() -> str:
    global _HEAD
    if _HEAD is None:
        try:
            _HEAD = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                   cwd=Path(__file__).resolve().parents[2],
                                   capture_output=True, text=True, timeout=5).stdout.strip() \
                or "unknown"
        except (OSError, subprocess.SubprocessError):
            _HEAD = "unknown"
    return _HEAD


def _first(row: dict[str, Any], keys: Iterable[str]) -> str | None:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def payload_hash(row: dict[str, Any]) -> str:
    body = {k: v for k, v in row.items()
            if k not in STAMP_FIELDS and k not in REVISION_FIELDS}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:24]


def stamp(row: dict[str, Any], source: str, source_version: str | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """Return a stamped COPY. Never overwrites a field the producer already set."""
    out = dict(row)
    ts = (now or datetime.now(tz=UTC)).isoformat()
    out.setdefault("source", source)
    out.setdefault("event_time", _first(row, EVENT_KEYS))
    out.setdefault("available_time", _first(row, AVAILABLE_KEYS) or ts)
    out.setdefault("ingested_time", ts)
    out.setdefault("source_version", source_version or _git_head())
    out["payload_hash"] = payload_hash(out)
    return out


def is_stamped(row: dict[str, Any]) -> bool:
    return all(isinstance(row.get(k), str) and row.get(k) for k in
               ("available_time", "ingested_time", "source_version", "payload_hash"))


def usable_at(row: dict[str, Any], decision_time: datetime) -> bool:
    """Could the desk have known this row at `decision_time`? Unstamped rows: NO."""
    if not is_stamped(row):
        return False
    try:
        avail = datetime.fromisoformat(str(row["available_time"]))
    except (TypeError, ValueError):
        return False
    if avail.tzinfo is None:
        avail = avail.replace(tzinfo=UTC)
    if decision_time.tzinfo is None:
        decision_time = decision_time.replace(tzinfo=UTC)
    return avail <= decision_time


def _parse_time(v: Any) -> datetime | None:
    """An ISO string as an aware UTC datetime; None when it is not one."""
    try:
        t = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _revision_n(row: dict[str, Any]) -> int:
    try:
        n = int(row.get("revision_n") or 0)
    except (TypeError, ValueError):
        return 0
    return max(n, 0)


def revise(row: dict[str, Any], *, revision_of: str, reason: str, source: str,
           now: datetime | None = None) -> dict[str, Any]:
    """A stamped COPY of `row` chained to the payload it corrects. The input is never mutated.

    The predecessor's stamp (available/ingested time, source version, hash) and its revision
    fields are dropped before re-stamping -- a revision is a new ingestion of the same finding,
    not the old ingestion with edits -- while `event_time` (when the thing happened) survives,
    because the correction does not move the event. `available_time` is floored at the revision
    time: the desk could not have known revision n before revision n existed.
    """
    when = now or datetime.now(tz=UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    ts = when.isoformat()
    body = {k: v for k, v in row.items()
            if k not in REVISION_FIELDS
            and k not in ("available_time", "ingested_time", "source_version", "payload_hash",
                          "source")}
    out = stamp(body, source, now=when)
    avail = _parse_time(out.get("available_time"))
    if avail is None or avail < when:
        out["available_time"] = ts
    out["revision_of"] = str(revision_of)
    out["revision_time"] = ts
    out["revision_n"] = _revision_n(row) + 1
    out["revision_reason"] = str(reason)
    out["revision_id"] = hashlib.sha256(
        f"{revision_of}{out['payload_hash']}".encode()).hexdigest()[:16]
    return out


def latest_as_of(rows: Iterable[dict[str, Any]], key_fields: tuple[str, ...],
                 decision_time: datetime) -> list[dict[str, Any]]:
    """Per key, the newest revision the desk could have known at `decision_time`.

    Ordering is revision_time first (an unrevised original ranks below any usable revision),
    then available_time. Rows that are not usable at `decision_time` -- unstamped, or made
    available later -- are not candidates at all, so a backtest at t sees the vintage of t.
    Keys are returned in first-seen order.
    """
    floor = datetime.min.replace(tzinfo=UTC)
    best: dict[tuple[str, ...], tuple[tuple[datetime, datetime], dict[str, Any]]] = {}
    order: list[tuple[str, ...]] = []
    for r in rows:
        if not isinstance(r, dict) or not usable_at(r, decision_time):
            continue
        key = tuple(json.dumps(r.get(f), sort_keys=True, default=str) for f in key_fields)
        rank = (_parse_time(r.get("revision_time")) or floor,
                _parse_time(r.get("available_time")) or floor)
        if key not in best:
            order.append(key)
            best[key] = (rank, r)
        elif rank > best[key][0]:
            best[key] = (rank, r)
    return [best[k][1] for k in order]


def census(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    n = 0
    have = dict.fromkeys(STAMP_FIELDS, 0)
    stamped = 0
    n_revised = 0
    max_revision_n = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        n += 1
        for k in STAMP_FIELDS:
            if r.get(k):
                have[k] += 1
        if is_stamped(r):
            stamped += 1
        rev_n = _revision_n(r)
        if rev_n or r.get("revision_id"):
            n_revised += 1
        max_revision_n = max(max_revision_n, rev_n)
    return {"rows": n, "stamped": stamped,
            "stamped_frac": (round(stamped / n, 4) if n else None),
            "field_frac": {k: (round(v / n, 4) if n else None) for k, v in have.items()},
            "n_revised": n_revised, "max_revision_n": max_revision_n}
