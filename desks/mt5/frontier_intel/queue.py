"""THE FRONTIER WORK QUEUE: no discovery disappears, and no state is reached by accident.

    "No discovery disappears."                                       -- the mandate, section 6

WHY APPEND-ONLY JSONL AND NOT A DATABASE. The mandate names sqlite and sqlite would be fine, but
the property that matters is not the storage engine: it is that a candidate's HISTORY survives.
An append-only log of state transitions gives that for free and gives it in a form the rest of
this desk already reads -- the worked-ledger, the compute ledger, the module-rent history are all
jsonl for the same reason. A row is never edited, so a card that was REJECTED in March and is
resurrected in June carries both facts, and "why did we drop this" is answerable.

THE STATES ARE A LADDER, NOT A SET. Each transition has to be legal, and the illegal ones are the
interesting half: nothing may jump from DISCOVERED to PROVEN, and nothing reaches PROVEN without
passing MEASURING. That is the same rule the capability ladder applies to this desk's own organs,
for the same reason -- a frontier miner that can mark its own imports PROVEN is a machine for
manufacturing confidence.

GRAVEYARD IS NOT DELETION. A refused candidate stays, with its reason, because the record of what
did not transfer is what stops the same article being re-mined every quarter -- and because a
cluster of graveyarded cards from one firm is itself a measurement about that firm.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
LEDGER = BASE / "frontier_intel" / "data" / "frontier_queue.jsonl"

#: The ladder, in order. `DISCOVERED` is what a scout produces; `PROVEN` is the only success.
STATES = ("DISCOVERED", "EXTRACTED", "DEDUPED", "GAP_CONFIRMED", "PRIORITIZED", "IMPLEMENTING",
          "TESTING", "CHALLENGER", "MEASURING", "PROVEN", "REJECTED", "GRAVEYARD")

#: Legal transitions. TWO RULES ARE ENCODED HERE AND BOTH ARE LOAD-BEARING:
#:   nothing skips MEASURING on its way to PROVEN -- an import cannot be believed because it was
#:   implemented well;
#:   anything may fall to REJECTED or GRAVEYARD from anywhere -- killing is always legal, and a
#:   ladder that made it hard to kill things would fill up.
_NEXT: dict[str, tuple[str, ...]] = {
    "DISCOVERED": ("EXTRACTED",),
    "EXTRACTED": ("DEDUPED",),
    "DEDUPED": ("GAP_CONFIRMED",),
    "GAP_CONFIRMED": ("PRIORITIZED",),
    "PRIORITIZED": ("IMPLEMENTING",),
    "IMPLEMENTING": ("TESTING",),
    "TESTING": ("CHALLENGER",),
    "CHALLENGER": ("MEASURING",),
    "MEASURING": ("PROVEN",),
    "PROVEN": (),
    "REJECTED": ("PRIORITIZED",),          # a rejection may be revisited on new evidence
    "GRAVEYARD": (),
}
_ALWAYS = ("REJECTED", "GRAVEYARD")


def candidate_id(firm: str, capability: str, source_url: str, claim: str) -> str:
    """A stable identity for one finding, so the same article read twice is one candidate.

    KEYED ON THE CLAIM, NOT THE URL. The same principle is described by three firms on five pages,
    and keying on the page would queue it five times; keying on (firm, capability, claim) collapses
    a re-publication and keeps two genuinely different claims from the same page apart.
    """
    raw = "|".join((firm or "", capability or "", (claim or "").strip().lower()[:400],
                    (source_url or "").split("?")[0]))
    return "F-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def can_transition(old: str, new: str) -> tuple[bool, str]:
    """May a candidate move from `old` to `new`, and why not when it may not."""
    if new not in STATES:
        return False, f"{new!r} is not a state on the ladder"
    if new in _ALWAYS:
        return True, ""
    if old not in STATES:
        return False, f"{old!r} is not a state on the ladder"
    if new in _NEXT.get(old, ()):
        return True, ""
    return False, (f"{old} -> {new} is not a legal step. The ladder exists so nothing reaches "
                   f"PROVEN without being MEASURED: an import cannot be believed because it was "
                   f"implemented well")


def append(row: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Write one state row. Append-only: a candidate's history is never edited away."""
    p = LEDGER if path is None else path
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), **row}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass
    return row


def rows(path: Path | None = None) -> list[dict[str, Any]]:
    p = LEDGER if path is None else path
    if not p.exists():
        return []
    out = []
    try:
        for line in p.read_text("utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def current(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Latest row per candidate -- the queue as it stands, rebuilt from the append-only log."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows(path):
        cid = str(r.get("candidate_id") or "")
        if cid:
            out[cid] = {**out.get(cid, {}), **r}
    return out


def discover(*, firm: str, capability: str, source_url: str, claim: str,
             evidence_grade: str, source_kind: str, path: Path | None = None) -> dict[str, Any]:
    """Enter a finding at DISCOVERED, or return the existing row if it is already known."""
    cid = candidate_id(firm, capability, source_url, claim)
    have = current(path).get(cid)
    if have:
        return {**have, "already_known": True}
    return append({"candidate_id": cid, "state": "DISCOVERED", "firm": firm,
                   "capability": capability, "source_url": source_url, "claim": claim[:600],
                   "evidence_grade": evidence_grade, "source_kind": source_kind}, path)


def advance(candidate_id_: str, new_state: str, why: str = "",
            path: Path | None = None, **extra: Any) -> dict[str, Any]:
    """Move a candidate one legal step, or record the refusal. Never raises on an illegal move.

    A REFUSED TRANSITION IS ITSELF APPENDED, because the attempt is information: an implementer
    repeatedly trying to jump a card to PROVEN is a defect in the implementer, and a version that
    silently returned False would hide it.
    """
    have = current(path).get(candidate_id_)
    old = str((have or {}).get("state") or "")
    ok, refusal = can_transition(old, new_state)
    if not ok:
        return append({"candidate_id": candidate_id_, "state": old, "refused_transition": new_state,
                       "why": refusal}, path)
    return append({"candidate_id": candidate_id_, "state": new_state, "why": why,
                   "from_state": old, **extra}, path)


def summary(path: Path | None = None) -> dict[str, Any]:
    cur = current(path)
    by_state: dict[str, int] = {}
    for r in cur.values():
        by_state[str(r.get("state") or "?")] = by_state.get(str(r.get("state") or "?"), 0) + 1
    return {
        "candidates": len(cur),
        "by_state": dict(sorted(by_state.items())),
        "proven": [c for c, r in cur.items() if r.get("state") == "PROVEN"],
        "in_flight": [c for c, r in cur.items()
                      if r.get("state") in ("IMPLEMENTING", "TESTING", "CHALLENGER", "MEASURING")],
        "note": ("GRAVEYARD is not deletion: the record of what did not transfer is what stops "
                 "the same article being re-mined every quarter"),
    }
