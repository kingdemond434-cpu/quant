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

Usage: run_rejection_shadow.py [--db data/sor_crypto.sqlite] [--threshold 0.5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.autodiscovery.memory import CandidateStore
from libs.self_improvement.adaptive_thresholds import ThresholdBook
from libs.store.connection import Database
from libs.validation.rejection_shadow import build_shadow_report

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"
_OUT = _ROOT / "web/reject_shadow.json"


def main() -> None:
    book = ThresholdBook(_ROOT / "data/adaptive_thresholds.json")
    p = argparse.ArgumentParser()
    # MUST match run_rejection_rescore.py: the rescorer feeds scores keyed by candidate id, so
    # pointing the two at different stores makes every score a miss and every reject read as
    # pending -- an unscored audit that looks exactly like a broken evaluator.
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--threshold", type=float, default=None,
                   help="forward metric a reject must clear to count as 'would have paid' "
                        "(default: the evidence-adjusted reject_deploy_threshold)")
    p.add_argument("--min-age-days", type=float, default=30.0)
    a = p.parse_args()
    threshold = a.threshold if a.threshold is not None else book.get("reject_deploy_threshold")
    leak_tol = book.get("reject_leak_tolerance")
    min_sample = int(book.get("reject_min_sample"))

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to audit yet")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    rejects = [(r.id, r.created_at) for r in store.rejects()]

    # Entries are {"sharpe": float, "n_fwd_bars": int} (judged at the noise-adjusted bar for
    # that window) or legacy bare floats (judged at the raw bar until the rescorer upgrades
    # them in place). Both pass through; build_shadow_report normalizes.
    scores: dict[str, object] = {}
    if _SCORES.exists():
        try:
            scores = {str(k): v for k, v in json.loads(_SCORES.read_text("utf-8")).items()}
        except Exception:
            scores = {}

    report = build_shadow_report(
        rejects, scores, deploy_threshold=threshold, min_age_days=a.min_age_days,
        leak_tolerance=leak_tol, min_sample=min_sample,
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(report.model_dump_json(indent=1), "utf-8")
    print(f"rejection-shadow: {report.n_rejects_total} rejects, {report.n_eligible} eligible, "
          f"{report.n_pending_rescore} pending re-score")
    print(f"  {report.verdict}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()
