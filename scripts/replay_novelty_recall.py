#!/usr/bin/env python3
"""Measure the novelty gate's RECALL by replaying the 420-hypothesis campaign through it.

Ordering matters and the ledger row says so: validate the gate BEFORE wiring it. A gate with 0%
recall wired into generation is worse than no gate -- it costs compute and buys a false sense of
protection.

THE NATURAL EXPERIMENT. The 420 campaign (data/sor_crypto.sqlite, everything before 2026-07-30)
is not one blob; it is three campaigns with a structure that makes it a ready-made labelled set:

  camp_d8b4f80e  195 rows  2026-07-11T07:44   13 mechanism signatures, 15 symbols
  camp_8292eb62  195 rows  2026-07-11T07:56   THE SAME 13 signatures, 15 DISJOINT symbols
  camp_607b962f   30 rows  2026-07-22T05:20   cross_asset/inverse_reference -- a NEW family

Campaign 2 is a pure symbol-extension of campaign 1, fired twelve minutes later: 13 of 13 identical
(family, subtype, mechanism, params) signatures, 0 of 15 shared symbols. Every one of those 195
trials re-tested ground campaign 1 had just killed, and the content-hash dedupe that guards
generation today (`orchestrator.py:111`) caught NONE of them, because the symbol differs.

So:
  POSITIVES = campaign 2 (195). A working gate flags these REDUNDANT.  -> recall
  NEGATIVES = campaign 3  (30). A new family; a working gate says NOVEL. -> false-positive rate

The negative set is what stops this being a rigged test: a matcher that flags everything scores
100% recall and is useless. Both numbers are reported, always, and the redundancy threshold is
held FIXED at the shipped default -- the corpus and the matcher may be fixed, never the bar.

PRIOR SETS form a ladder, so the gain is attributable rather than asserted:
  B0  docs/graveyard.md only                    (what a naive compile gives you)
  B1  + research_memory failures                (free text, still no machine mechanism)
  B2  + campaign 1's collapsed mechanisms       (the canonical build, time-restricted)

B2's candidate priors are restricted to campaign 1 alone: it precedes both test sets, so no later
campaign can leak backwards into the priors.

    .venv/bin/python scripts/replay_novelty_recall.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_graveyard_priors import (  # noqa: E402
    candidate_features,
    candidate_priors,
    candidate_statement,
    graveyard_md_priors,
    research_memory_priors,
)

from libs.alpha_factory.hypothesis_novelty import (  # noqa: E402
    PriorIdea,
    hypothesis_novelty,
)

CRYPTO_DB = ROOT / "data/sor_crypto.sqlite"
OUT = ROOT / "data/novelty_recall_replay.json"

PRIOR_CAMPAIGN = "camp_d8b4f80ebe834605b5b0aacd59e34240"   # 195, 07-11T07:44
POSITIVE_CAMPAIGN = "camp_8292eb62b211406cab914c6eb9b539b2"  # 195, 07-11T07:56 (same mechanisms)
NEGATIVE_CAMPAIGN = "camp_607b962faab94e658eb1a7ab6653e320"  # 30, 07-22 (new family)


def _campaign_rows(campaign_id: str) -> list[dict]:
    con = sqlite3.connect(f"file:{CRYPTO_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute(
            "SELECT family, subtype, symbol, params_json, mechanism FROM research_candidates "
            "WHERE campaign_id=? AND status='rejected'", (campaign_id,))]
    finally:
        con.close()
    return rows


def _as_candidate(row: dict) -> tuple[str, tuple[str, ...]]:
    """Render one historical reject exactly as generation would present it to the gate."""
    statement = candidate_statement(
        row["family"], row["subtype"], row["mechanism"] or "", row["params_json"] or "",
        [row["symbol"]],
    )
    features = candidate_features(
        row["family"], row["subtype"], row["mechanism"] or "", row["params_json"] or "")
    return statement, features


def _score(rows: list[dict], priors: Sequence[PriorIdea], threshold: float) -> dict:
    flagged = 0
    sims: list[float] = []
    for row in rows:
        statement, features = _as_candidate(row)
        r = hypothesis_novelty(statement, features=features, priors=priors,
                               redundant_threshold=threshold)
        sims.append(r.nearest_similarity)
        flagged += int(r.is_redundant)
    n = len(rows)
    sims.sort()
    return {
        "n": n,
        "flagged_redundant": flagged,
        "rate": round(flagged / n, 4) if n else 0.0,
        "median_nearest_similarity": round(sims[n // 2], 4) if n else 0.0,
        "min_nearest_similarity": round(sims[0], 4) if n else 0.0,
        "max_nearest_similarity": round(sims[-1], 4) if n else 0.0,
    }


def run(threshold: float = 0.7) -> dict:
    positives = _campaign_rows(POSITIVE_CAMPAIGN)
    negatives = _campaign_rows(NEGATIVE_CAMPAIGN)

    grave = graveyard_md_priors()
    memory = research_memory_priors()
    early_mechanisms, _ = candidate_priors(include_campaigns=[PRIOR_CAMPAIGN])

    ladder = {
        "B0_graveyard_md_only": list(grave),
        "B1_plus_research_memory": [*grave, *memory],
        "B2_plus_campaign1_mechanisms": [*early_mechanisms, *grave, *memory],
    }

    results = {}
    for name, priors in ladder.items():
        pos = _score(positives, priors, threshold)
        neg = _score(negatives, priors, threshold)
        results[name] = {
            "n_priors": len(priors),
            "recall_on_redundant_retests": pos,
            "false_positive_on_new_family": neg,
        }
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "redundant_threshold": threshold,
        "design": {
            "prior_campaign": PRIOR_CAMPAIGN,
            "positive_campaign": POSITIVE_CAMPAIGN,
            "negative_campaign": NEGATIVE_CAMPAIGN,
            "positives": len(positives),
            "negatives": len(negatives),
            "note": "positives are mechanism-identical re-tests of the prior campaign on disjoint "
                    "symbols; negatives are a family absent from every prior set",
        },
        "ladder": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=0.7,
                    help="redundancy threshold; the shipped default is 0.7 and moving it to "
                         "flatter the replay would be fitting the guard to the sample")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    report = run(threshold=args.threshold)
    Path(args.out).write_text(json.dumps(report, indent=1), "utf-8")

    d = report["design"]
    print(f"NOVELTY RECALL REPLAY  (threshold {report['redundant_threshold']})")
    print(f"  positives (redundant re-tests): {d['positives']}   "
          f"negatives (new family): {d['negatives']}")
    print(f"  {'prior set':32s} {'#priors':>7s} {'RECALL':>16s} {'FALSE-POS':>16s}")
    for name, r in report["ladder"].items():
        rec, fp = r["recall_on_redundant_retests"], r["false_positive_on_new_family"]
        print(f"  {name:32s} {r['n_priors']:7d} "
              f"{rec['flagged_redundant']:5d}/{rec['n']:<4d} {rec['rate']:6.1%} "
              f"{fp['flagged_redundant']:5d}/{fp['n']:<4d} {fp['rate']:6.1%}")
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
