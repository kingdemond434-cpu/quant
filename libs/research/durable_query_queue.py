"""Durable, leased native-query queue used by country packs and regional forests.

Report previews may be bounded; work may not be.  Every query is content addressed, persisted
before publication, and has exactly one current operational state.  Consumers lease work and
acknowledge it by id.  Expired leases return to QUEUED on the next read, so a killed process does
not strand research.  This module is intentionally transport-only: an acknowledgement proves a
query reached its declared consumer, not that it found an edge.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

STATES = ("QUEUED", "ACTIVE", "BLOCKED", "RESOLVED")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def query_id(row: Mapping[str, Any]) -> str:
    body = {k: row.get(k) for k in ("country", "layer", "domain", "query", "languages")}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str,
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
        return dict(doc) if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def enqueue(path: Path, rows: Iterable[Mapping[str, Any]], *,
            at: str | None = None) -> dict[str, int]:
    """Idempotently persist every row before any caller truncates a display."""
    stamp = at or _iso()
    doc = _read(path)
    items = dict(doc.get("items") or {})
    added = 0
    for source in rows:
        row = dict(source)
        qid = query_id(row)
        if qid in items:
            continue
        items[qid] = {"query_id": qid, "payload": row, "state": "QUEUED",
                      "enqueued_at": stamp, "updated_at": stamp,
                      "owner": "", "lease_until": "", "consumer_acknowledgement": None,
                      "resolution": None}
        added += 1
    _write(path, {"schema": 1, "updated_at": stamp, "items": items})
    return {"added": added, "total": len(items)}


def _expired(row: Mapping[str, Any], now: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(row.get("lease_until") or "")) <= now
    except ValueError:
        return True


def lease(path: Path, *, owner: str, limit: int, countries: Iterable[str] = (),
          lease_s: int = 1800, now: datetime | None = None) -> list[dict[str, Any]]:
    """Lease queued/expired rows.  Country filtering is optional and never drops unmatched work."""
    instant = now or _now()
    wanted = {str(c).lower() for c in countries if str(c)}
    doc = _read(path)
    items = dict(doc.get("items") or {})
    out: list[dict[str, Any]] = []
    for qid in sorted(items):
        row = dict(items[qid])
        payload = dict(row.get("payload") or {})
        if wanted and str(payload.get("country") or "").lower() not in wanted:
            continue
        state = str(row.get("state") or "QUEUED")
        if state == "ACTIVE" and _expired(row, instant):
            state = "QUEUED"
        if state != "QUEUED":
            continue
        row.update({"state": "ACTIVE", "owner": owner,
                    "lease_until": _iso(instant + timedelta(seconds=max(1, int(lease_s)))),
                    "updated_at": _iso(instant)})
        items[qid] = row
        out.append(dict(row))
        if len(out) >= max(0, int(limit)):
            break
    _write(path, {"schema": 1, "updated_at": _iso(instant), "items": items})
    return out


def acknowledge(path: Path, ids: Iterable[str], *, owner: str, outcome: str = "TRANSFERRED",
                evidence: str = "", at: str | None = None) -> int:
    stamp = at or _iso()
    doc = _read(path)
    items = dict(doc.get("items") or {})
    changed = 0
    for qid in dict.fromkeys(str(x) for x in ids):
        row = dict(items.get(qid) or {})
        if not row or (row.get("owner") and row.get("owner") != owner):
            continue
        row.update({"state": "RESOLVED", "updated_at": stamp, "lease_until": "",
                    "consumer_acknowledgement": {"consumer": owner, "at": stamp,
                                                 "outcome": outcome, "evidence": evidence},
                    "resolution": "CONSUMED"})
        items[qid] = row
        changed += 1
    _write(path, {"schema": 1, "updated_at": stamp, "items": items})
    return changed


def reconcile(path: Path) -> dict[str, Any]:
    """Independent ID/state reconciliation over the persisted artifact, never producer counts."""
    items = dict(_read(path).get("items") or {})
    states = dict.fromkeys(STATES, 0)
    invalid: list[str] = []
    missing_ack: list[str] = []
    for qid, row in items.items():
        state = str((row or {}).get("state") or "")
        if state not in states or qid != query_id(dict((row or {}).get("payload") or {})):
            invalid.append(str(qid))
            continue
        states[state] += 1
        if state == "RESOLVED" and not (row or {}).get("consumer_acknowledgement"):
            missing_ack.append(str(qid))
    return {"total_ids": len(items), "states": states, "invalid_ids": invalid,
            "resolved_missing_ack": missing_ack,
            "balanced": len(items) == sum(states.values()) and not invalid and not missing_ack}
