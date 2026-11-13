"""ONLY REAL EDGES ON THE PROP BOOKS: one judge, read by E8 and FTMO alike (principal 2026-11-13).

The principal, 19:23Z: the reopened strategies go live "only if they are" actual edges after
costs, "and ones which are". The judge is `research/policy_lift_reopen.py` (box leg
`policy_lift_reopen`, hourly, right before the promoter), which writes
`reports/REOPEN_VERIFICATION.json`: per clock row, its canonical `certificate`, `verified` and
`why_not` (a fresh cost re-grade STILL_PASSES, forward t >= 2, n >= 30, no certificate drift,
venue evidence, max drawdown above -25R). This module reads that verdict; it never re-judges.

WHAT IT DOES TO EACH BOOK:
  * a certificate the judge lists and does NOT verify is REFUSED by both prop books, by name and
    with the judge's reasons -- on FTMO and E8 alike;
  * a certificate the judge VERIFIES is admitted to E8's book as well, where until now only the
    principal's hand-named CERT_BOOK_LIVE keys were (the principal's "make them all tradeable
    for E8, FTMO and Fusion", 19:19Z). Every other E8 door still applies: principal exclusions,
    the terms fence, the placebo alarm, replication, and the E8 guard's loss limits;
  * a certificate the judge does not list is unaffected (the judge covers the reopened set).

ABSENT OR UNREADABLE: UNMEASURED. Nothing new is admitted to E8 on a verdict that cannot be
read, and the report says so; FTMO keeps its standing universe. Billed as rail `real_edge`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
VERDICT = BASE / "reports" / "REOPEN_VERIFICATION.json"


def load(path: Path | None = None) -> tuple[dict[str, dict[str, Any]], str]:
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
    n_ok = sum(1 for v in out.values() if v["verified"])
    return out, f"OK: {n_ok} of {len(out)} listed certificates verified"


def refusal(cert: str, verdicts: dict[str, dict[str, Any]]) -> str | None:
    """Why the judge refuses `cert`, or None when it is verified or not listed."""
    v = verdicts.get(cert)
    if v is None or v["verified"]:
        return None
    return "not a verified real edge: " + ("; ".join(v["why_not"]) or "unverified")[:200]


def verified(cert: str, verdicts: dict[str, dict[str, Any]]) -> bool:
    v = verdicts.get(cert)
    return bool(v and v["verified"])
