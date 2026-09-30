"""THE TIER S VERIFIERS' AUTHORITY AT THE PROMOTION DOOR (principal 2026-09-29: "no approvals
needed", every blueprint wired live).

`block(name)` is called by `research/promoter.py` beside `blind_review_veto`, with the same
consequence and the same limits: it WITHHOLDS A NEW LIVE ROW, it sizes nothing and it never
touches an open position or a row already holding capital. Three verdicts can withhold:

  REPLICATION_MISMATCH   an independent re-execution of the certificate disagreed with it
                         (`reports/REPLICATION.json`, verdict MISMATCH / DISAGREE / FAIL);
  ONLINE_FDR_OVER_BUDGET the certificate was admitted after the desk's lifetime online-FDR
                         budget was spent (`reports/tier_s/ONLINE_FDR_ROWS.json`, certified row
                         with `over_budget`);
  IMMUNE_FREEZE          the production certifier got EASIER TO FOOL on the sealed suite -- a
                         freeze judged by the real certifier (`judge` production:*) whose reason
                         is a DROP. A freeze from the reference validator, from an absolute
                         floor, or from a stale file (> MAX_AGE_H) withholds nothing: a toy's
                         verdict gets no authority over capital.

BILLED LIKE EVERY RAIL (growth governance Rule 1): the rail `tier_s_evidence_block` in
`libs/portfolio/rails.py` is measured by `missed_growth.measure_tier_s_block` from the ledger
this module appends (`data/tier_s/promotion_blocks.jsonl`): every withheld row, with the forward
expectancy its clock carried when it was withheld, so what the door refused is a number.

READ-ONLY OF CERTIFICATES, BY THE FIREWALL: every file this module opens is checked with
`firewall.may("promoter", "read", ...)`, and the promoter role may not read raw hypotheses.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.tiers import firewall

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPLICATION = DESK / "reports" / "REPLICATION.json"
FDR_ROWS = DESK / "reports" / "tier_s" / "ONLINE_FDR_ROWS.json"
FREEZE = DESK / "data" / "tier_s" / "PROMOTION_FREEZE.json"
LEDGER = DESK / "data" / "tier_s" / "promotion_blocks.jsonl"
MAX_AGE_H = 6.0
MISMATCH = frozenset({"MISMATCH", "DISAGREE", "FAIL", "FAILED", "NOT_REPLICATED"})


def _read(p: Path) -> Any:
    firewall.may("promoter", "read", str(p.relative_to(ROOT)).replace("\\", "/"))
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _fresh(doc: Any, key: str = "generated_utc") -> bool:
    try:
        at = datetime.fromisoformat(str((doc or {}).get(key) or (doc or {}).get("at")))
    except (TypeError, ValueError):
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return (datetime.now(UTC) - at).total_seconds() <= MAX_AGE_H * 3600


def _match(cert: str, name: str) -> bool:
    return bool(cert) and (cert == name or cert.endswith("." + name) or name.endswith("." + cert))


def _replication(name: str) -> str | None:
    doc = _read(REPLICATION)
    rows = (doc.get("verdicts") or doc.get("rows") or []) if isinstance(doc, dict) else []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        cert = str(r.get("cell") or r.get("key") or "")
        v = str(r.get("verdict") or r.get("status") or "").upper()
        if v in MISMATCH and _match(cert, name):
            return f"REPLICATION_MISMATCH: re-execution of {cert} returned {v}"
    return None


def _fdr(name: str) -> str | None:
    doc = _read(FDR_ROWS)
    if not isinstance(doc, dict) or not _fresh(doc):
        return None
    for r in doc.get("certified") or []:
        if isinstance(r, dict) and r.get("over_budget") and _match(str(r.get("test_id")), name):
            return (f"ONLINE_FDR_OVER_BUDGET: {r.get('test_id')} was admitted after the lifetime "
                    f"online-FDR budget was spent (p={r.get('p')}, "
                    f"LORD level={r.get('lord_level')})")
    return None


def _freeze() -> str | None:
    doc = _read(FREEZE)
    if not isinstance(doc, dict) or not _fresh(doc, "at"):
        return None
    if str(doc.get("verdict")) != "FREEZE" or not str(doc.get("judge") or "").startswith(
            "production:"):
        return None
    why = str(doc.get("why") or "")
    if "fell" not in why:           # only a DROP freezes; an absolute floor is a report
        return None
    return f"IMMUNE_FREEZE: the production certifier got easier to fool -- {why}"


def block(name: str) -> str | None:
    """The first reason this certificate may not be written LIVE now, or None."""
    for fn in (_replication, _fdr):
        why = fn(name)
        if why:
            return why
    return _freeze()


def record(name: str, why: str, *, lane: str, exp_r: Any = None, n: Any = None) -> None:
    """Append one withheld promotion to the ledger `missed_growth` bills."""
    firewall.may("promoter", "write", str(LEDGER.relative_to(ROOT)))
    row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "name": name, "lane": lane,
           "why": why, "reason": why.split(":", 1)[0], "exp_r": exp_r, "n": n}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass
