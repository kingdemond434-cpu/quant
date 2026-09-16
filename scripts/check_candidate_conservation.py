"""CANDIDATE CONSERVATION -- every candidate that entered the docket is still accounted for.

THE CLOSED-LOOP ATTESTATION ASKS `truth.provenance_conservation` and nothing answered it
(2026-09-16: "no candidate-conservation artifact; conservation is derived from counts, not an
event ledger"). This is the count-derived answer, written every hour so the attestation can read
it: a candidate is CONSERVED when it is in the docket (judged or still waiting), or evicted with
its reason on record; it is LOST when a verdict names a cell that the docket no longer holds and
no eviction explains. The docket is append-only (`breadth_sweep.apply`, `merge_docket`), so the
expected reading is zero lost; the value of the artifact is that a nonzero reading is a
measurement, not a belief.

    python scripts/check_candidate_conservation.py        -> desks/mt5/reports/CANDIDATE_CONSERVATION.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
GATES = DESK / "reports" / "universal_gates_external.json"
EVICTED = DESK / "reports" / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "CANDIDATE_CONSERVATION.json"


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _cell_ids(rows: list[dict]) -> set[str]:
    try:
        sys.path.insert(0, str(DESK))
        sys.path.insert(0, str(DESK / "research"))
        from research.frontier_identity import cell_id
    except Exception:
        return set()
    out: set[str] = set()
    for r in rows:
        try:
            out.add(cell_id({"sym": r.get("symbol"), "family": r.get("family"),
                             "params": r.get("params") or {}}))
        except Exception:
            continue
    return out


def measure() -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    docket = _read(DOCKET)
    rows = [r for r in docket if isinstance(r, dict)] if isinstance(docket, list) else []
    gates = _read(GATES) or {}
    verdicts = gates.get("verdicts") if isinstance(gates, dict) else None
    verdicts = [v for v in verdicts if isinstance(v, dict)] if isinstance(verdicts, list) else []
    evicted_doc = _read(EVICTED) or {}
    evicted = set((evicted_doc.get("survivors") or {}).keys()) if isinstance(evicted_doc, dict) else set()
    surv_doc = _read(SURVIVORS) or {}
    survivors = set((surv_doc.get("survivors") or {}).keys()) if isinstance(surv_doc, dict) else set()
    if docket is None or not isinstance(gates, dict):
        return {"at": now, "status": "UNMEASURED", "n_lost": None, "lost": None,
                "why": "docket or gates artifact unreadable; conservation cannot be counted"}
    docket_ids = _cell_ids(rows)
    judged = {str(v.get("cell") or "") for v in verdicts if v.get("cell")}
    judged_stripped = {c.split(".", 1)[1] if c.startswith("external.") else c for c in judged}
    evicted_stripped = {c.split(".", 1)[1] if c.startswith("external.") else c for c in evicted}
    lost = sorted(c for c in judged_stripped
                  if c not in docket_ids and c not in evicted_stripped and c
                  and ("external." + c) not in survivors and c not in survivors)
    n_docket = len(rows)
    n_judged_in_docket = len(judged_stripped & docket_ids) if docket_ids else None
    doc = {
        "at": now,
        "status": "OK" if not lost else "LOST",
        "n_docket": n_docket,
        "n_docket_identities": len(docket_ids),
        "n_verdicts": len(verdicts),
        "n_judged_in_docket": n_judged_in_docket,
        "n_waiting": (len(docket_ids) - n_judged_in_docket) if n_judged_in_docket is not None else None,
        "n_evicted": len(evicted),
        "n_survivors": len(survivors),
        "n_lost": len(lost),
        "lost": lost[:200],
        "rule": ("a verdict that names a cell the docket no longer holds, that no eviction and no "
                 "survivor record explains, is a lost candidate; the docket is append-only so the "
                 "expected reading is zero, and a nonzero reading is measured, never assumed"),
    }
    return doc


def main() -> int:
    doc = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"candidate conservation: {doc.get('status')} docket={doc.get('n_docket')} "
          f"verdicts={doc.get('n_verdicts')} lost={doc.get('n_lost')} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
