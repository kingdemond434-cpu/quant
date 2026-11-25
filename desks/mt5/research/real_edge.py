"""ONLY REAL EDGES ON THE PROP BOOKS: one judge, read by E8 and FTMO alike (principal 2026-11-13).

The principal, 19:23Z: the reopened strategies go live "only if they are" actual edges after
costs, "and ones which are". The judge is `research/policy_lift_reopen.py` (box leg
`policy_lift_reopen`, hourly, right before the promoter), which writes
`reports/REOPEN_VERIFICATION.json`: per clock row, its canonical `certificate`, `verified` and
`why_not` (a fresh cost re-grade STILL_PASSES, forward t >= 2, n >= 30, no certificate drift,
venue evidence, max drawdown above -25R). This module reads that verdict; it never re-judges.

WHAT IT DOES TO EACH BOOK (r3, Audit MF2 on #1211; zuck 2026-11-24 18:34Z "no blockers for
anything. Only exotics are blocked"):
  * a certificate the judge lists and does NOT verify is PRICED, never refused: both prop books
    write doubt code `real_edge_unverified` on the row and size it x DOUBT_MULT through the one
    allocator's evidence path (prop/e8_book.evidence_mult), inside the E8 ceiling. The judge's
    reasons are journaled with the row;
  * a certificate the judge VERIFIES carries `real_edge_verified` on its row (the widening half:
    E8's book admits every promoted non-exotic sleeve, and a verified edge is not doubted);
  * a certificate the judge does not list is unaffected (the judge covers the reopened set).

ABSENT, UNREADABLE OR STALE: UNMEASURED. Billed as rail `real_edge`.
STALE (Auditor HOLD on #1211): the judge stamps `at` every hourly pass; a verdict whose stamp is
missing, unparseable, in the future or older than MAX_AGE_S (three judge cadences) verifies
NOTHING -- its verified rows are dropped, so a stopped judge can never mark a certificate verified
by its last good reading. Its unverified rows still price their doubt (size only; nothing is
ever refused by this module).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
VERDICT = BASE / "reports" / "REOPEN_VERIFICATION.json"
#: The judge (`policy_lift_reopen`) runs hourly; after three missed passes it verifies nothing.
MAX_AGE_S = 3 * 3600


def _age_s(doc: dict[str, Any], now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(doc["at"]))
    except (KeyError, TypeError, ValueError):
        return None
    if at.tzinfo is None:
        return None
    return (now - at).total_seconds()


def load(path: Path | None = None, *,
         now: datetime | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    """{certificate: {"verified": bool, "why_not": [...]}} and a status line.

    A certificate several clock rows share is verified only if every listed row verifies it
    (one failing clock is a failing edge)."""
    path = path or VERDICT
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {}, f"UNMEASURED: {path.name} unreadable ({type(exc).__name__})"
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return {}, f"UNMEASURED: {path.name} has no rows"
    out: dict[str, dict[str, Any]] = {}
    for row in rows.values():
        if not isinstance(row, dict) or not row.get("certificate"):
            continue
        cert = str(row["certificate"])
        ok = row.get("verified") is True
        why = [str(w) for w in (row.get("why_not") or [])]
        prev = out.get(cert)
        if prev is None:
            out[cert] = {"verified": ok, "why_not": why}
        else:
            prev["verified"] = prev["verified"] and ok
            prev["why_not"] = sorted(set(prev["why_not"]) | set(why))
    age = _age_s(doc, now or datetime.now(tz=UTC))
    if age is None or age < -300 or age > MAX_AGE_S:
        doubted = {k: v for k, v in out.items() if not v["verified"]}
        when = "no usable `at` stamp" if age is None else f"{age / 3600:.1f}h old"
        return doubted, (f"UNMEASURED: {path.name} stale ({when}); nothing verified, "
                         f"{len(doubted)} doubt(s) kept")
    n_ok = sum(1 for v in out.values() if v["verified"])
    return out, f"OK: {n_ok} of {len(out)} listed certificates verified"


def doubt(cert: str, verdicts: dict[str, dict[str, Any]]) -> str | None:
    """The judge's doubt about `cert` (a SIZING note, never a refusal), or None when it is
    verified or not listed."""
    v = verdicts.get(cert)
    if v is None or v["verified"]:
        return None
    return "unverified real edge: " + ("; ".join(v["why_not"]) or "unverified")[:200]


def verified(cert: str, verdicts: dict[str, dict[str, Any]]) -> bool:
    v = verdicts.get(cert)
    return bool(v and v["verified"])
