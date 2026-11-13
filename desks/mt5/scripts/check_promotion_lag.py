"""PROMOTION LAG: A SLEEVE ELIGIBLE FOR LIVE THAT IS NOT LIVE IS A FLAW (principal 2026-10-13).

The principal's words: "make sure all promotion eligible sleeves r promoted to live fr allocator
to choose from" and, the same afternoon, "sleeves eligible fr promotion but didnt go live yet is
flaw too". Measured that day: 731 certified rows sat RETIRED by a live policy that no longer
refused them, because RETIRED was one-way. Nothing reported it, so it was found by hand. This
lists every eligible sleeve that is not LIVE, every hour, with the reason it is held and how
long it has waited, and fails LOUDLY when one has waited past an allocator cycle for a reason
that is a flaw rather than a decision.

ELIGIBLE means one of:
  STANDBY            on the roster, waiting for the allocator's admitting scans
  RETIRED by policy  retired_by the live policy or the 2026-09-16 gold-only order, holding a
                     ten-gate certificate (exact policy, all ten passed) read now

A REASON IS A DECISION (recorded, does not fail) or A FLAW (fails after LAG_HOURS):
  allocator_declines   DECISION  the optimiser priced it and wants 0 heat at equal total heat
  awaiting_scan        DECISION  admitted once; the promoter needs PROMOTE_ADMIT_STREAK scans
  symbol_policy        DECISION  the live policy in force refuses it (symbol, family, lane,
                                 quarantine), with the policy's own words
  allocator_unpriced   FLAW      no allocator row prices this mechanism: it was never scored
  scan_stale           FLAW      the allocator has not scanned it within LAG_HOURS
  promoter_lag         FLAW      the admit streak is met and the row is still STANDBY
  restore_pending      FLAW      certified, retired by a policy that no longer refuses it, and
                                 still RETIRED (the sealed policy_lifted_restore patch)
  no_reason            FLAW      nothing on the row says why

UNMEASURED IS A VERDICT (L1.28a): an unreadable roster or certificate file is UNMEASURED, never a
clean pass, and a row with no timestamp waits for an UNMEASURED time that fails as a flaw would.

Artifact: desks/mt5/reports/PROMOTION_LAG.json. Exit 1 when any flaw has waited > LAG_HOURS.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "PROMOTION_LAG.json"

#: The allocator scans hourly; one cycle plus one of slack for the promoter's own pass.
LAG_HOURS = 2.0
#: `promoter.PROMOTE_ADMIT_STREAK`; pinned by the test.
PROMOTE_ADMIT_STREAK = 2
#: `promoter.POLICY_RETIREMENTS` once the restore lands; the retirements a widened policy undoes.
POLICY_RETIREMENTS = frozenset({"live_policy", "principal_gold_only_2026-09-16"})
DECISION, FLAW, UNMEASURED = "DECISION", "FLAW", "UNMEASURED"
REASONS = {"allocator_declines": DECISION, "awaiting_scan": DECISION,
           "symbol_policy": DECISION, "allocator_unpriced": FLAW, "scan_stale": FLAW,
           "promoter_lag": FLAW, "restore_pending": FLAW, "no_reason": FLAW}


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def certified_keys(doc: Any) -> set[str] | None:
    """Exact-policy, all-ten-pass certificate keys (`promoter.load_cert_specs`), or None."""
    if not isinstance(doc, Mapping):
        return None
    from gate_policy import all_ten_pass, is_exact_policy
    if not is_exact_policy(doc.get("gate_policy")):
        return set()
    return {k for k, c in (doc.get("survivors") or {}).items()
            if isinstance(c, Mapping) and all_ten_pass(c.get("gates"))
            and isinstance(c.get("shadow_spec"), Mapping)}


def cert_key(row: Mapping[str, Any]) -> str:
    cert = row.get("certificate")
    return str(cert.get("cell") or "") if isinstance(cert, Mapping) else str(cert or "")


def waiting_since(row: Mapping[str, Any]) -> datetime | None:
    if str(row.get("status") or "").upper() == "RETIRED":
        return _ts(row.get("retired_at"))
    stamps = [_ts(row.get(k)) for k in ("demoted_at", "restored_at", "standby_since",
                                         "promoted_at", "canonical_identity_declared_at")]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def classify(row: Mapping[str, Any], *, now: datetime, refuse: Any, policy: Any,
             certs: set[str]) -> tuple[str, str] | None:
    """(reason, why) for an eligible non-LIVE row, or None when the row is not eligible."""
    status = str(row.get("status") or "").upper()
    if status == "STANDBY":
        adm = row.get("admission") if isinstance(row.get("admission"), Mapping) else {}
        why = str(adm.get("why") or "")
        streak = int(row.get("admit_streak") or adm.get("streak") or 0)
        scan = _ts(row.get("admit_scan"))
        if scan is None or (now - scan).total_seconds() > LAG_HOURS * 3600:
            return "scan_stale", (f"last allocator scan {scan.isoformat() if scan else 'never'}")
        if streak >= PROMOTE_ADMIT_STREAK:
            return "promoter_lag", f"admit streak {streak} met and still STANDBY"
        if "has not priced" in why or "no allocator row answers" in why:
            return "allocator_unpriced", why[:300]
        if streak >= 1:
            return "awaiting_scan", f"admitted {streak} of {PROMOTE_ADMIT_STREAK} scans"
        if why:
            return "allocator_declines", why[:300]
        return "no_reason", "STANDBY with no admission reason recorded"
    if status == "RETIRED" and str(row.get("retired_by") or "") in POLICY_RETIREMENTS \
            and cert_key(row) in certs:
        refused = refuse(row, policy)
        if refused:
            return "symbol_policy", str(refused)[:300]
        return "restore_pending", ("certified, and the policy in force no longer refuses it: "
                                   "RETIRED is one-way until promoter."
                                   "restore_lifted_policy_retirements lands (sealed patch "
                                   "policy_lifted_restore)")
    return None


def build(now: datetime | None = None, *, sleeves_doc: Any = None, survivors: Any = None,
          refuse: Any = None, policy: Any = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sleeves_doc = sleeves_doc if sleeves_doc is not None else _json(SLEEVES)
    rows = (sleeves_doc or {}).get("sleeves") if isinstance(sleeves_doc, Mapping) else None
    certs = certified_keys(survivors if survivors is not None else _json(SURVIVORS))
    if not isinstance(rows, list) or certs is None:
        return {"at": now.isoformat(timespec="seconds"), "verdict": UNMEASURED,
                "why": "sleeves.json or UNIVERSAL_SURVIVORS.json unreadable"}
    if refuse is None or policy is None:
        from mt5desk.live_policy import policy as _pol
        from mt5desk.live_policy import refuse as _ref
        refuse, policy = _ref, _pol()
    held: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        got = classify(r, now=now, refuse=refuse, policy=policy, certs=certs)
        if got is None:
            continue
        reason, why = got
        since = waiting_since(r)
        hours = round((now - since).total_seconds() / 3600, 2) if since else None
        kind = REASONS[reason]
        late = kind == FLAW and (hours is None or hours > LAG_HOURS)
        held.append({"name": r.get("name"), "symbol": r.get("symbol"),
                     "family": r.get("family"), "status": r.get("status"), "reason": reason,
                     "kind": kind, "why": why, "waiting_since": since.isoformat() if since
                     else UNMEASURED, "waiting_hours": hours if hours is not None
                     else UNMEASURED, "late": late})
    late = [h for h in held if h["late"]]
    return {"at": now.isoformat(timespec="seconds"),
            "verdict": "FAIL" if late else "PASS",
            "eligible_not_live": len(held), "late": len(late),
            "live": sum(1 for r in rows if str(r.get("status") or "").upper() == "LIVE"),
            "by_reason": dict(Counter(h["reason"] for h in held)),
            "late_by_reason": dict(Counter(h["reason"] for h in late)),
            "certified_keys": len(certs), "lag_hours": LAG_HOURS,
            "certificates_note": (None if certs else "no exact-policy, all-ten-pass certificate "
                                  "readable: RETIRED rows cannot be judged eligible this pass"),
            "held": sorted(held, key=lambda h: (not h["late"], h["reason"], str(h["name"]))),
            "rule": ("every certified sleeve not LIVE is listed with its reason and wait; a "
                     "FLAW reason older than one allocator cycle fails. Principal 2026-10-13.")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.no_write:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"promotion lag: {doc['verdict']} -- {doc.get('eligible_not_live', 0)} eligible not "
          f"live, {doc.get('late', 0)} late; {doc.get('by_reason', {})}")
    return 1 if doc["verdict"] in ("FAIL", UNMEASURED) else 0


if __name__ == "__main__":
    raise SystemExit(main())
