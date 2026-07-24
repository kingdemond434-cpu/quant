#!/usr/bin/env python3
"""REJECTION-SHADOW RUNNER -- activate the gate-calibration audit over the existing reject ledger.

Recovers wrongly-rejected survivors with ZERO new data (MAX_SURVIVORS Part 1.2). The reject ledger
already exists (CandidateStore ``survived = 0`` rows); this runner reads it, pairs each eligible
reject with its forward score, runs the tested audit (libs.validation.rejection_shadow), and writes
web/reject_shadow.json for the daily sweep. If a non-trivial slice of rejects would have paid
out-of-sample, the gate is over-strict and is leaking survivors -- re-calibrate.

FORWARD SCORES (the injected, never-fabricated input): data/reject_forward_scores.json maps a
candidate id to its realized metric measured on data that arrived AFTER rejection. The desk's
forward evaluator produces it; a reject with no entry is carried as pending (never guessed). Absent
file == no scores yet == the audit reports "cannot judge until scored", which is itself the honest
standing signal to wire the evaluator.

Usage: run_rejection_shadow.py [--db data/sor_autodiscovery.sqlite] [--threshold 0.5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.autodiscovery.memory import CandidateStore
from libs.store.connection import Database
from libs.validation.rejection_shadow import build_shadow_report

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"
_OUT = _ROOT / "web/reject_shadow.json"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_autodiscovery.sqlite")
    p.add_argument("--threshold", type=float, default=0.5,
                   help="forward metric a reject must clear to count as 'would have paid'")
    p.add_argument("--min-age-days", type=float, default=30.0)
    a = p.parse_args()

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to audit yet")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    rejects = [(r.id, r.created_at) for r in store.rejects()]

    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            raw = json.loads(_SCORES.read_text("utf-8"))
            scores = {str(k): float(v) for k, v in raw.items()}
        except Exception:
            scores = {}

    report = build_shadow_report(
        rejects, scores, deploy_threshold=a.threshold, min_age_days=a.min_age_days,
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(report.model_dump_json(indent=1), "utf-8")
    print(f"rejection-shadow: {report.n_rejects_total} rejects, {report.n_eligible} eligible, "
          f"{report.n_pending_rescore} pending re-score")
    print(f"  {report.verdict}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()
