"""Publish the typed research API's coverage: which of the eleven verbs reach their delegate.

The facade (libs/research/research_api.py) is the one deterministic truth every researcher
calls; this leg writes reports/RESEARCH_API.json every core hour so the wiring hunter, the
closed-loop attestation and the dashboard can see the API's coverage and the call log's size.

    python scripts/research_api_status.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "RESEARCH_API.json"
CALLS = DESK / "data" / "research_api_calls.jsonl"


def build() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from libs.research import research_api
        verbs = research_api.verbs()
    except Exception as exc:
        return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "status": "UNMEASURED", "why": f"research_api unavailable: {type(exc).__name__}: {exc}"}
    table = verbs.get("verbs") if isinstance(verbs, dict) else {}
    rows = dict(table) if isinstance(table, dict) else {}
    available = sum(1 for v in rows.values()
                    if isinstance(v, dict) and str(v.get("status", "")).lower() == "available")
    n_calls = 0
    try:
        n_calls = sum(1 for ln in CALLS.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
    except OSError:
        n_calls = 0
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "status": "OK",
            "verbs": rows, "n_verbs": len(rows), "n_available": available, "n_calls_logged": n_calls,
            "rule": "every researcher calls the same deterministic facade; coverage is measured, not assumed"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"research api: {doc.get('status')} {doc.get('n_available')}/{doc.get('n_verbs')} verbs "
          f"available, {doc.get('n_calls_logged')} calls logged")
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
