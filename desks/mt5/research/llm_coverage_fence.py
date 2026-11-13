"""LLM COVERAGE FENCE -- RED when any free model, lab or LLM role produced nothing this cycle.

Reads `reports/LLM_COVERAGE.json`, which `llm_lab` writes at the end of every pass (principal
2026-10-13: "all openrouter models must be running producing etc all cycles"). Exit 1 on RED,
on a report older than two hours (the lab leg did not run, which is itself a coverage failure)
and on an absent report; exit 0 on GREEN. UNMEASURED (seat dark, dry run) exits 1 too: a cycle
in which nothing could run is not coverage.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORT = BASE / "reports" / "LLM_COVERAGE.json"
MAX_AGE = timedelta(hours=2)


def verdict(path: Path | None = None, now: datetime | None = None) -> tuple[int, str]:
    p = path or REPORT
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1, f"RED: {p.name} absent or unreadable -- the lab leg has not reported coverage"
    try:
        at = datetime.fromisoformat(str(doc.get("generated_at")))
    except ValueError:
        return 1, "RED: coverage report carries no timestamp"
    if (now or datetime.now(UTC)) - at > MAX_AGE:
        return 1, f"RED: coverage report is stale (generated {doc.get('generated_at')})"
    v = str(doc.get("verdict"))
    head = (f"{v}: {doc.get('models_answered')}/{doc.get('models_available')} models answered; "
            f"{len(doc.get('red') or [])} gap(s)")
    if v == "GREEN":
        return 0, head
    return 1, head + "".join(f"\n  - {r}" for r in (doc.get("red") or [])[:40])


def main() -> int:
    code, text = verdict()
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
