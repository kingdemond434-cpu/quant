"""Independent evidence audit for GLOBAL_RESEARCH_MAXIMUM_V1_20260927.

This does not turn file existence into completion.  It separately measures implementation,
tests, a downstream consumer, and fresh runtime evidence.  Only all four earns
CURRENT_VERIFIED; everything else remains PARTIAL with exact missing evidence.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs" / "research" / "global_research_maximum_v1.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "GLOBAL_RESEARCH_ACCEPTANCE.json"
MAX_RUNTIME_AGE_H = 26.0


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def audit(*, root: Path = ROOT, manifest: Path = MANIFEST, report: Path = REPORT,
          now: datetime | None = None) -> dict[str, Any]:
    instant = now or datetime.now(tz=UTC)
    spec = json.loads(manifest.read_text("utf-8"))
    rows: list[dict[str, Any]] = []
    for req in spec["requirements"]:
        checks: dict[str, Any] = {}
        missing: list[str] = []
        for kind in ("implementation", "tests", "consumers"):
            values = list(req.get(kind) or [])
            absent = [p for p in values if not (root / p).exists()]
            checks[kind] = {"declared": len(values), "present": len(values) - len(absent),
                            "missing": absent}
            missing.extend(f"{kind}:{p}" for p in absent)
        runtime_rows: list[dict[str, Any]] = []
        for rel in req.get("runtime") or []:
            path = root / rel
            if not path.exists():
                runtime_rows.append({"path": rel, "status": "ABSENT"})
                missing.append(f"runtime:{rel}")
                continue
            stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            age_h = max(0.0, (instant - stamp).total_seconds() / 3600.0)
            status = "FRESH" if age_h <= MAX_RUNTIME_AGE_H else "STALE"
            runtime_rows.append({"path": rel, "status": status, "age_h": round(age_h, 3)})
            if status != "FRESH":
                missing.append(f"runtime_stale:{rel}")
        checks["runtime"] = runtime_rows
        rows.append({"id": req["id"], "title": req["title"], "priority": req["priority"],
                     "status": "CURRENT_VERIFIED" if not missing else "PARTIAL",
                     "missing_evidence": missing, "checks": checks})
    counts = {status: sum(r["status"] == status for r in rows)
              for status in ("CURRENT_VERIFIED", "PARTIAL")}
    doc = {"specification": spec["specification"], "at": instant.isoformat(),
           "requirements": len(rows), "counts": counts,
           "all_current_verified": counts["PARTIAL"] == 0,
           "rows": rows, "unresolved": [r["id"] for r in rows if r["status"] != "CURRENT_VERIFIED"],
           "rule": spec["completion_rule"], "frontier_rule": spec["frontier_rule"]}
    _atomic(report, doc)
    return doc


if __name__ == "__main__":
    result = audit()
    print(f"{result['specification']}: {result['counts']}; "
          f"unresolved={len(result['unresolved'])}")
