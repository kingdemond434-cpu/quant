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
ARCHIVE = DESK / "data" / "hypotheses" / "external_survivors_archive.json"
QUEUE_ARCHIVE = DESK / "data" / "research_queue_archive.json"


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


def _accounted(lost: list[str]) -> dict[str, Any]:
    """Which of the docket-lost cells the archives or the canonical registry explain."""
    ids: set[str] = set()
    by: dict[str, int] = {"archive": 0, "queue_archive": 0, "registry_trials": 0,
                          "registry_candidates": 0}
    for name, path in (("archive", ARCHIVE), ("queue_archive", QUEUE_ARCHIVE)):
        try:
            if path.exists() and path.stat().st_size < 400_000_000:
                doc = json.loads(path.read_text(encoding="utf-8-sig"))
                rows = doc if isinstance(doc, list) else (doc.get("rows") or doc.get("cells")
                                                          or doc.get("survivors") or [])
                found = _cell_ids([r for r in rows if isinstance(r, dict)]) if isinstance(
                    rows, list) else set(rows.keys()) if isinstance(rows, dict) else set()
                hit = {c for c in lost if c in found or ("external." + c) in found}
                by[name] = len(hit)
                ids |= hit
        except (OSError, ValueError):
            continue
    try:
        import sys as _sys
        if str(ROOT) not in _sys.path:
            _sys.path.insert(0, str(ROOT))
        from libs.moat import registry as reg
        conn = reg.connect()
        try:
            want = [c for c in lost if c not in ids]
            for chunk in (want[i:i + 500] for i in range(0, len(want), 500)):
                marks = ",".join("?" * len(chunk))
                for r in conn.execute(f"SELECT DISTINCT hypothesis_id FROM trials_ledger "  # noqa: S608
                                      f"WHERE hypothesis_id IN ({marks})", chunk):
                    ids.add(str(r[0]))
                    by["registry_trials"] += 1
                for r in conn.execute(f"SELECT id, donated_cell FROM research_candidates "  # noqa: S608
                                      f"WHERE id IN ({marks}) OR donated_cell IN ({marks})",
                                      chunk + chunk):
                    for v in r:
                        if v and str(v) in lost and str(v) not in ids:
                            ids.add(str(v))
                            by["registry_candidates"] += 1
        finally:
            conn.close()
    except Exception as exc:  # the registry is optional here; the docket count still stands
        by["registry_error"] = f"{type(exc).__name__}: {exc}"[:120]
    return {"ids": ids, "by": by}


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
    # UNDER THE CANONICAL REGISTRY (2026-09-17). The old accounting read 14,627 lost cells: the
    # docket is compacted and archived by the queue organs, so a judged cell the live docket no
    # longer holds is not lost when the archive holds it or the registry's append-only trials
    # ledger / candidate rows carry it (the verdict was recorded; nothing vanished). The old
    # count stays published as n_lost_docket_only; the headline status reads the registry.
    accounted = _accounted(lost)
    lost_registry = sorted(c for c in lost if c not in accounted["ids"])
    n_docket = len(rows)
    n_judged_in_docket = len(judged_stripped & docket_ids) if docket_ids else None
    doc = {
        "at": now,
        "status": "OK" if not lost_registry else "LOST",
        "n_lost_docket_only": len(lost),
        "accounted_by": accounted["by"],
        "n_docket": n_docket,
        "n_docket_identities": len(docket_ids),
        "n_verdicts": len(verdicts),
        "n_judged_in_docket": n_judged_in_docket,
        "n_waiting": (len(docket_ids) - n_judged_in_docket) if n_judged_in_docket is not None else None,
        "n_evicted": len(evicted),
        "n_survivors": len(survivors),
        "n_lost": len(lost_registry),
        "lost": lost_registry[:200],
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
