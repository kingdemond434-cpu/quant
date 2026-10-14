"""Principal stops: a sleeve the principal or the CRO stopped never trades again until the
principal's own resume decision is recorded.

WHY THIS EXISTS (measured 2026-10-14). On 2026-10-13 at 21:30Z the AUDCHF, EURZAR and USDZAR
overnight-gap-decay sleeves were stood down on the box (status STANDBY, risk 0.0) after the
principal said "Yes remove from fusion live" (20:41Z) and left them out of the book (20:53-20:57Z).
The stand-down wrote its reason as `standby_reason`, a field `scripts/heal_silent_demotions.py`
did not read, so the healer took it for an accident and lifted all three back to LIVE: EURZAR at
21:48Z, USDZAR at 23:48Z and AUDCHF at 01:48Z. (#397 now makes the healer read any `*_reason`.) The promoter's principal-book path then found them LIVE and re-applied the
0.10 risk from CERT_BOOK_LIVE.json. Nothing anywhere recorded that a human had stopped them.

So a stop is now a RECORD, not a status. data/PRINCIPAL_STOPS.json lists each stopped identity
with who stopped it and on whose word. While a stop is active:
  - the gateway's roster (`decision_core.load_sleeves_verbose`) drops every LIVE row it matches,
    so no new risk is placed however the row became LIVE;
  - `heal_silent_demotions` never lifts a matching row;
  - `scripts/check_principal_stops.py` goes RED for any matching LIVE row with risk above 0.
Open positions are not touched here: the gateway manages them on the unfiltered roster.

A stop lifts only when its entry carries `resumed` with `by: "principal"` and a non-empty
`message` naming the principal's decision. Anything else keeps it stopped (fail closed).

MATCHING. A stop names a canonical identity `symbol|family|selector`, lowercased (the join the
promoter and the gauntlet already use), or an exact sleeve name. An identity stop covers every
re-mint of that sleeve: a `_principal_YYYYMMDD` copy, a new parameter hash, a different exec lane.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STOPS_NAME = "PRINCIPAL_STOPS.json"


def identity(row: dict[str, Any]) -> str:
    """symbol|family|selector, lowercased; the row's own `canonical_identity` when it has one."""
    ci = row.get("canonical_identity")
    if isinstance(ci, str) and ci.count("|") == 2:
        return ci.strip().lower()
    return "|".join(str(row.get(k) or "").strip().lower() for k in ("symbol", "family", "selector"))


def resumed(entry: dict[str, Any]) -> bool:
    """True only for a recorded principal resume decision."""
    res = entry.get("resumed")
    return (isinstance(res, dict) and str(res.get("by") or "").strip().lower() == "principal"
            and bool(str(res.get("message") or "").strip()))


def load(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """(active stop entries, problem). An absent file holds no stops. An unreadable or malformed
    file returns its problem so the fence reads RED; it stops nothing it cannot name."""
    if not path.exists():
        return [], None
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return [], f"{path.name} unreadable ({type(exc).__name__}: {exc})"
    stops = doc.get("stops") if isinstance(doc, dict) else None
    if not isinstance(stops, list):
        return [], f"{path.name} has no `stops` list"
    active: list[dict[str, Any]] = []
    for e in stops:
        if not isinstance(e, dict) or not (e.get("identity") or e.get("name")):
            return [], f"{path.name} holds an entry with neither identity nor name: {e!r}"
        if not resumed(e):
            active.append(e)
    return active, None


def match(row: dict[str, Any], stops: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The active stop entry covering `row`, or None."""
    ident, name = identity(row), str(row.get("name") or "")
    for e in stops:
        if e.get("name") and str(e["name"]) == name:
            return e
        if e.get("identity") and str(e["identity"]).strip().lower() == ident:
            return e
    return None


def why(entry: dict[str, Any]) -> str:
    return (f"principal stop on {entry.get('identity') or entry.get('name')} "
            f"({entry.get('by')}, {entry.get('at')}): {entry.get('authority')}")


def split(rows: list[dict[str, Any]], path: Path
          ) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]], str | None]:
    """(rows to keep, [(stopped row, why)], problem)."""
    stops, problem = load(path)
    keep: list[dict[str, Any]] = []
    stopped: list[tuple[dict[str, Any], str]] = []
    for r in rows:
        e = match(r, stops)
        if e is None:
            keep.append(r)
        else:
            stopped.append((r, why(e)))
    return keep, stopped, problem
