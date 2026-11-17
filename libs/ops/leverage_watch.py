"""Watch the trading account's leverage and name every change (CRO finding K3, 2026-11-13).

WHY. Brokers cut leverage before events and weekends. Margin feasibility for every sized order
moves with it, and until now nothing on the desk kept a reading from one pass to the next: only
`financing_lab` read `account_info().leverage`, used it for that one pass, and forgot it. A cut
was therefore visible only as orders refused for margin.

WHAT. `observe` keeps a small history (`desks/mt5/reports/ACCOUNT_LEVERAGE.json`): the last
reading, when it was read, and every change with its old and new value. A change emits an
`ACCOUNT_LEVERAGE_CHANGED` event row (priority 2, so the pager and the board see it). A pass
with no readable leverage writes nothing new and the verdict ages to STALE after
`STALE_AFTER_H`; an absent reading is never recorded as a change. The file carries the venue
label only -- no login, server or account number (the repository is public).

This is a REPORT. It sets no cap, no size and no veto (GROWTH_GOVERNANCE): the allocator already
reads the live leverage through `financing_lab.load_terms` on every pass.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STALE_AFTER_H = 36.0
MAX_CHANGES_KEPT = 200


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def observe(path: Path, leverage: float | None, *, venue: str = "fusion",
            now: datetime | None = None, emit: Any = None) -> dict[str, Any]:
    """Record one reading; return the document written (or that would stand, when unreadable)."""
    now = now or datetime.now(tz=UTC)
    doc = _read(path)
    raw_venues = doc.get("venues")
    venues: dict[str, Any] = raw_venues if isinstance(raw_venues, dict) else {}
    raw_row = venues.get(venue)
    row: dict[str, Any] = raw_row if isinstance(raw_row, dict) else {}
    raw_changes = row.get("changes")
    changes: list[Any] = raw_changes if isinstance(raw_changes, list) else []
    lev = float(leverage) if isinstance(leverage, (int, float)) and leverage > 0 else None
    prev = row.get("leverage")
    changed: dict[str, Any] | None = None
    if lev is not None:
        if isinstance(prev, (int, float)) and float(prev) != lev:
            changed = {"at": now.isoformat(timespec="seconds"), "from": float(prev), "to": lev,
                       "direction": "CUT" if lev < float(prev) else "RAISED"}
            changes = [*changes, changed][-MAX_CHANGES_KEPT:]
        row = {"leverage": lev, "read_at": now.isoformat(timespec="seconds"),
               "changes": changes}
    read_at = _parse(row.get("read_at"))
    age_h = None if read_at is None else round((now - read_at).total_seconds() / 3600.0, 2)
    if read_at is None:
        verdict = "UNMEASURED"
    elif age_h is not None and age_h > STALE_AFTER_H:
        verdict = "STALE"
    elif changed is not None:
        verdict = "CHANGED"
    else:
        verdict = "MEASURED"
    row = {**row, "verdict": verdict, "age_h": age_h}
    venues = {**venues, venue: row}
    out = {"generated_utc": now.isoformat(timespec="seconds"),
           "producer": "libs/ops/leverage_watch.py (via research/financing_lab.py)",
           "stale_after_h": STALE_AFTER_H, "venues": venues,
           "boundary": "REPORT ONLY: no cap, size or veto; the allocator reads live leverage "
                       "through financing_lab.load_terms on every pass"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    if changed is not None:
        try:
            if emit is None:
                from libs.ops.events import emit as emit_fn
            else:
                emit_fn = emit
            fields: dict[str, Any] = {"producer": "research/financing_lab.py", "priority": 2,
                                      "venue": venue, "from": changed["from"],
                                      "to": changed["to"], "direction": changed["direction"]}
            emit_fn("ACCOUNT_LEVERAGE_CHANGED", **fields)
        except Exception:
            pass
    return out
