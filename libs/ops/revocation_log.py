"""An append-only `revocation` record for a certificate store (2026-10-20).

A store's `revocation` block was a single dict, overwritten on every pass: the second holdback
replaced the first, so the record the authority ratchet accepts for a falling count lost its own
history (audited 2026-10-20: 2 -> 1). It is now a LIST of entries, deduped on (kind, keys),
that only ever grows; a legacy single dict is read as a one-entry list. `at` is NOT part of the
key (audit v2 delta): a held row the judge keeps republishing would otherwise add one entry per
pass; the FIRST entry for an identical (kind, keys) is kept, so its `at` is when it began.
"""
from __future__ import annotations

import json
from typing import Any


def _entries(v: Any) -> list[dict[str, Any]]:
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [e for e in v if isinstance(e, dict)]
    return []


def _key(e: dict[str, Any]) -> str:
    return json.dumps([e.get("kind"), sorted(map(str, e.get("keys") or []))])


def merge_revocations(*records: Any) -> list[dict[str, Any]]:
    """The union of every record, oldest first, each (kind, keys) once -- the earliest `at`
    wins. Never shrinks."""
    seen: dict[str, dict[str, Any]] = {}
    for rec in records:
        for e in _entries(rec):
            k = _key(e)
            if k not in seen or str(e.get("at") or "") < str(seen[k].get("at") or ""):
                seen[k] = e
    return sorted(seen.values(), key=lambda e: str(e.get("at") or ""))
