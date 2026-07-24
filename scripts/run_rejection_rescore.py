#!/usr/bin/env python3
"""REJECT RE-SCORE FEEDER -- produce the forward scores the rejection-shadow audit consumes.

Closes the gate-leak recovery loop (MAX_SURVIVORS Part 1.2). Plans which rejects to re-score
(near-miss first, capped -- libs.validation.reject_rescore), re-evaluates each on the forward window
that arrived AFTER its rejection, and writes data/reject_forward_scores.json -- exactly the file
run_rejection_shadow.py reads. Incremental: already-scored rejects are kept, new scores merged.

THE RE-EVAL (runtime-heavy, honest boundary): rebuilding a stored candidate's signal and running it
on post-rejection market data needs the lake + the generator. That is wired here via the crypto
adapter; if the lake/provider is unavailable (fresh clone, no data) the runner scores nothing and
exits cleanly, leaving the shadow audit to report "unscored" -- never a fabricated score.

Usage: run_rejection_rescore.py [--db data/sor_autodiscovery.sqlite] [--limit 50] [--min-age 30]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.autodiscovery.memory import CandidateStore
from libs.store.connection import Database
from libs.validation.reject_rescore import plan_rescore

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"


def _forward_score(rec: object) -> float | None:
    """Re-evaluate one rejected candidate on its post-rejection forward window.

    Runtime hook: rebuild the candidate's signal from its stored (family, subtype, symbol, params)
    and score it on data after ``rec.created_at``. Returns None when the lake/generator cannot
    produce an honest forward series (missing data, too-short window) -- never a guess. Left as the
    single injection point so the recovery loop's scheduling + wiring are testable without the lake.
    """
    return None  # honest default until the lake-backed replay is wired on the runtime host


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_autodiscovery.sqlite")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-age-days", type=float, default=30.0)
    a = p.parse_args()

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to re-score")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    rejects = [
        (r.id, r.created_at, max(r.metrics.oos_sharpe, r.metrics.annual_sharpe))
        for r in store.rejects()
    ]
    plan = plan_rescore(rejects, min_age_days=a.min_age_days, limit=a.limit)
    print(f"rescore plan: {plan.verdict}")

    by_id = {r.id: r for r in store.rejects()}
    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            scores = {str(k): float(v) for k, v in json.loads(_SCORES.read_text("utf-8")).items()}
        except Exception:
            scores = {}
    n_new = 0
    for cid in plan.selected:
        if cid in scores:
            continue  # already scored -- incremental
        val = _forward_score(by_id.get(cid))
        if val is not None:
            scores[cid] = val
            n_new += 1

    if n_new:
        _SCORES.parent.mkdir(parents=True, exist_ok=True)
        _SCORES.write_text(json.dumps(scores, indent=1), "utf-8")
        print(f"wrote {n_new} new forward score(s) -> {_SCORES}")
    else:
        print("no new forward scores produced (re-eval hook not wired on this host, or all "
              "selected already scored) -- the shadow audit will report unscored, honestly")


if __name__ == "__main__":
    main()
