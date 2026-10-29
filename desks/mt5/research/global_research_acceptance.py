"""Independent evidence audit for GLOBAL_RESEARCH_MAXIMUM_V1_20260927.

This does not turn file existence into completion.  It separately measures implementation,
tests, a downstream consumer, and fresh runtime evidence.  Only all four earns
CURRENT_VERIFIED; everything else remains PARTIAL with exact missing evidence.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs" / "research" / "global_research_maximum_v1.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "GLOBAL_RESEARCH_ACCEPTANCE.json"
MAX_RUNTIME_AGE_H = 26.0
MAX_FUTURE_SKEW_S = 300
FAIL_STATUSES = {"FAILED", "FAIL", "ERROR", "DEGRADED", "BROKEN", "STALE"}
PASS_STATUSES = {"OK", "PASS", "PASSED", "SUCCESS", "HEALTHY", "COMPLETE", "COMPLETED"}


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _release_id(root: Path) -> str:
    named = os.environ.get("QUANT_RELEASE_ID", "").strip()
    if named:
        return named
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNMEASURED"


def _runtime_document(path: Path) -> dict[str, Any] | None:
    """Read a JSON proof or the last valid receipt in a JSONL ledger."""
    try:
        if path.suffix.casefold() == ".jsonl":
            for line in reversed(path.read_text("utf-8-sig").splitlines()):
                if line.strip():
                    doc = json.loads(line)
                    return doc if isinstance(doc, dict) else None
            return None
        doc = json.loads(path.read_text("utf-8-sig"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def _runtime_proof(path: Path, *, instant: datetime,
                   release: str) -> tuple[dict[str, Any], list[str]]:
    """Verify behavior, not mtime. Missing claims remain evidence debt, never implicit success."""
    rel = str(path)
    doc = _runtime_document(path)
    if doc is None:
        return {"path": rel, "status": "INVALID"}, ["invalid_json"]
    reasons: list[str] = []
    status = str(doc.get("status") or doc.get("verdict") or "").upper()
    if status in FAIL_STATUSES:
        reasons.append(f"failed_status:{status}")
    successful = status in PASS_STATUSES or doc.get("ok") is True or doc.get("success") is True
    completed = doc.get("completed_work", doc.get("completed", doc.get("work_completed")))
    if completed is None:
        reasons.append("completed_work_unmeasured")
    else:
        try:
            count = float(completed)
            if isinstance(completed, bool) or not math.isfinite(count) or count <= 0:
                reasons.append("invalid_completed_work")
        except (TypeError, ValueError):
            reasons.append("invalid_completed_work")
    if not successful:
        reasons.append("no_success_receipt")
    tests_passed = doc.get("tests_passed")
    if tests_passed is not True:
        reasons.append("tests_not_attested")
    claimed_release = str(doc.get("release") or doc.get("commit") or
                          doc.get("git_commit") or doc.get("code_commit") or "")
    if not claimed_release:
        reasons.append("release_unbound")
    elif not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", claimed_release):
        reasons.append("invalid_release_identity")
    if release == "UNMEASURED":
        reasons.append("current_release_unmeasured")
    elif claimed_release.lower() != release.lower():
        reasons.append(f"wrong_release:{claimed_release}")
    stamp_raw = (doc.get("completed_at") or doc.get("at") or doc.get("updated_utc") or
                 doc.get("generated_at") or doc.get("swept_at"))
    try:
        stamp = datetime.fromisoformat(str(stamp_raw).replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
        age_h = (instant - stamp).total_seconds() / 3600.0
        if age_h < -MAX_FUTURE_SKEW_S / 3600.0:
            reasons.append("future_internal_timestamp")
        if age_h > MAX_RUNTIME_AGE_H:
            reasons.append("stale_content")
    except (TypeError, ValueError):
        age_h = None
        reasons.append("missing_internal_timestamp")
    return {"path": rel, "status": "VERIFIED" if not reasons else "INVALID",
            "age_h": None if age_h is None else round(age_h, 3),
            "claimed_release": claimed_release or None, "proof_errors": reasons}, reasons


def audit(*, root: Path = ROOT, manifest: Path = MANIFEST, report: Path = REPORT,
          now: datetime | None = None) -> dict[str, Any]:
    instant = now or datetime.now(tz=UTC)
    release = _release_id(root)
    spec = json.loads(manifest.read_text("utf-8"))
    requirements = list(spec["requirements"])
    loaded_addenda: list[str] = []
    for rel in spec.get("addenda") or []:
        addendum_path = root / str(rel)
        if not addendum_path.exists():
            # The missing addendum is itself evidence debt.  Add a synthetic requirement so the
            # report cannot silently shrink its denominator when a referenced spec disappears.
            requirements.append({"id": f"MISSING:{rel}", "title": "missing acceptance addendum",
                                 "priority": "P0", "implementation": [str(rel)], "tests": [],
                                 "consumers": [], "runtime": []})
            continue
        addendum = json.loads(addendum_path.read_text("utf-8"))
        name = str(addendum.get("specification") or rel)
        requirements.extend({**r, "specification": name}
                            for r in addendum.get("requirements") or [])
        loaded_addenda.append(str(rel))
    rows: list[dict[str, Any]] = []
    for req in requirements:
        checks: dict[str, Any] = {}
        missing: list[str] = []
        for kind in ("implementation", "tests", "consumers"):
            values = list(req.get(kind) or [])
            if not values:
                missing.append(f"{kind}:UNDECLARED")
            absent = [p for p in values if not (root / p).exists()]
            checks[kind] = {"declared": len(values), "present": len(values) - len(absent),
                            "missing": absent}
            missing.extend(f"{kind}:{p}" for p in absent)
        runtime_rows: list[dict[str, Any]] = []
        runtime_values = list(req.get("runtime") or [])
        if not runtime_values:
            missing.append("runtime:UNDECLARED")
        for rel in runtime_values:
            path = root / rel
            if not path.exists():
                runtime_rows.append({"path": rel, "status": "ABSENT"})
                missing.append(f"runtime:{rel}")
                continue
            proof, errors = _runtime_proof(path, instant=instant, release=release)
            proof["path"] = rel
            runtime_rows.append(proof)
            missing.extend(f"runtime:{rel}:{reason}" for reason in errors)
        checks["runtime"] = runtime_rows
        # A named, still-open defect keeps the requirement PARTIAL however complete its files
        # look: four kinds of evidence present is not proof that the handoff they serve works.
        blockers = [b for b in req.get("blockers") or [] if isinstance(b, dict)
                    and str(b.get("status") or "OPEN").upper() != "CLOSED"]
        missing.extend(f"blocker:{b.get('id')}" for b in blockers)
        rows.append({"id": req["id"], "title": req["title"], "priority": req["priority"],
                     "specification": req.get("specification") or spec["specification"],
                     "lane": req.get("lane") or "UNDECLARED",
                     "status": "CURRENT_VERIFIED" if not missing else "PARTIAL",
                     "missing_evidence": missing, "blockers": blockers, "checks": checks})
    counts = {status: sum(r["status"] == status for r in rows)
              for status in ("CURRENT_VERIFIED", "PARTIAL")}
    by_spec: dict[str, dict[str, int]] = {}
    for r in rows:
        tally = by_spec.setdefault(r["specification"], {"CURRENT_VERIFIED": 0, "PARTIAL": 0})
        tally[r["status"]] += 1
    doc = {"specification": spec["specification"], "at": instant.isoformat(),
           "release": release,
           "addenda": loaded_addenda,
           "requirements": len(rows), "counts": counts,
           "all_current_verified": counts["PARTIAL"] == 0,
           # "complete against spec version X" is said only of a version with nothing PARTIAL
           "by_specification": by_spec,
           "complete_against": sorted(k for k, v in by_spec.items() if v["PARTIAL"] == 0),
           "rows": rows, "unresolved": [r["id"] for r in rows if r["status"] != "CURRENT_VERIFIED"],
           "rule": spec["completion_rule"], "frontier_rule": spec["frontier_rule"]}
    _atomic(report, doc)
    return doc


if __name__ == "__main__":
    result = audit()
    print(f"{result['specification']}: {result['counts']}; "
          f"unresolved={len(result['unresolved'])}")
