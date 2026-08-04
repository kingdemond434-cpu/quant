"""GENERATION DIVERSITY -- the wiring for HYPOTHESIS_MAX #2/#3/#6 (single Lane-A task).

The spec's wiring clause: *"metrics computed per batch and appended to the seat scoreboard
(data/panel_scorecard.json field `gen_diversity`)"*. This is that task, and it is what stops the
three components from being three more built-and-never-called modules -- the defect L2.9 exists
for, and the one this desk has repeatedly produced.

WHAT IT REPORTS, and why each number is one the desk did not previously have:

  novel_rate           of the ideas generated, the share that were genuinely NEW questions rather
                       than reparameterisations. Volume without this is throughput, not
                       information -- and "420 candidates tested" versus "one question asked 420
                       ways" are identical from a count. The desk has never been able to tell
                       those apart, and 420/0 is exactly the record that needed telling apart.
  mechanism_entropy    diversity of the fingerprints in the batch, normalised by ITEM count.
  market_breadth       names actually spanned, counting a cross-sectional universe properly.
  cross_generator_dup  whether separate seats are producing the same idea (herding).

IT NEVER BLOCKS GENERATION. Per the spec, the collapse detector is instrumentation that pages the
process, not a gate on ideas -- a diversity metric with veto power would be a second unvalidated
filter on a funnel this desk has already measured as too tight. The variation blocker DOES block,
but only on an exact fingerprint match or a >=0.90 Jaccard near-duplicate, and every block is
recorded with what it duplicated so "blocked" never means "lost".

    python scripts/run_generation_diversity.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import collapse_detector as CD  # noqa: E402
from libs.research import variation_blocker as VB  # noqa: E402

_OUT = _ROOT / "data/gen_diversity.json"
_SCORECARD = _ROOT / "data/panel_scorecard.json"
#: The lab candidate store. Was `data/research_memory.db` until 2026-08-01 (R0079) -- a path
#: NOTHING in this repo has ever written, so `_DB.exists()` was always False and every 6-hourly run
#: reported PERFECT diversity (entropy 1.0, breadth 1.0, distinctness 1.0) over an EMPTY batch.
#: A collapse detector that cannot see the generator is not a quiet detector, it is an absent one.
#: `.all()` is deliberate here and is NOT the survivors-only rule that governs the promotion queue:
#: diversity is a property of what the desk GENERATES, so rejects belong in the sample -- excluding
#: them would measure the gauntlet, not the generator.
_DB = _ROOT / "data/sor_research.sqlite"


def _batch() -> tuple[list[Any], list[str]]:
    """The most recent generation batch, with the seat that produced each idea.

    Reads the candidate store. Returns ([], []) when the lab db is absent -- this box may not be
    the research box, and an empty batch is a fact worth reporting rather than an error.
    """
    if not _DB.exists():
        return [], []
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        rows = CandidateStore(Database(_DB, read_only=True)).all()
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        return [], []
    rows = sorted(rows, key=lambda c: str(getattr(c, "created_at", "")))[-200:]
    gens = [str(getattr(c, "campaign_id", "") or "unknown") for c in rows]
    return list(rows), gens


def build() -> dict[str, Any]:
    batch, gens = _batch()
    div = CD.measure(batch, generators=gens)
    assessment = CD.assess(div)
    tel = VB.telemetry()
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "n_in_batch": len(batch),
        "gen_diversity": div.as_dict(),
        "assessment": assessment,
        "variation_telemetry": tel,
        "law": "HYPOTHESIS_MAX #2/#3/#6. The detector NEVER blocks generation; the blocker blocks "
               "only exact-fingerprint or >=0.90-Jaccard duplicates, and records what each block "
               "duplicated so the ledger stays a map of the searched space.",
    }


def _append_scorecard(rep: dict[str, Any]) -> bool:
    """Append `gen_diversity` to the seat scoreboard, per the spec's wiring clause."""
    try:
        card = json.loads(_SCORECARD.read_text("utf-8")) if _SCORECARD.exists() else {}
    except (OSError, ValueError):
        card = {}
    if not isinstance(card, dict):
        return False
    card["gen_diversity"] = {
        "at": rep["generated"], "n": rep["n_in_batch"],
        **{k: rep["gen_diversity"][k] for k in
           ("mechanism_entropy", "feature_breadth", "market_breadth",
            "semantic_distinctness", "cross_generator_dup_rate")},
        "verdict": rep["assessment"]["verdict"],
        "novel_rate": rep["variation_telemetry"].get("novel_rate"),
    }
    _SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    _SCORECARD.write_text(json.dumps(card, indent=2), "utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build()
    rep["scorecard_updated"] = _append_scorecard(rep)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    d, a, t = rep["gen_diversity"], rep["assessment"], rep["variation_telemetry"]
    print(f"generation diversity [{a['verdict']}] over {rep['n_in_batch']} candidates")
    if rep["n_in_batch"] == 0:
        print("  NO BATCH -- no research db on this box. That is a supply fact, not a health "
              "reading; the metrics below would be fabricated if reported as measured.")
    else:
        print(f"  mechanism entropy   {d['mechanism_entropy']:.3f}  "
              f"({d['n_fingerprints']} distinct fingerprints)")
        print(f"  feature breadth     {d['feature_breadth']:.3f}")
        print(f"  market breadth      {d['market_breadth']} names")
        print(f"  semantic distinct.  {d['semantic_distinctness']:.3f}")
        print(f"  cross-gen duplicate {d['cross_generator_dup_rate']:.1%}")
        for fp, n in d["top_fingerprints"][:3]:
            print(f"      most attempted: {fp}  x{n}")
    for f in a["flags"]:
        print(f"  FLAG {f[:110]}")
    if t.get("n"):
        print(f"  variation blocker: {t['n_novel']}/{t['n']} genuinely new "
              f"(novel_rate {t['novel_rate']:.1%}), {t['n_blocked']} blocked")
    print(f"-> {_OUT.relative_to(_ROOT)}"
          + ("  + panel_scorecard.gen_diversity" if rep["scorecard_updated"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
