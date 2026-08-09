#!/usr/bin/env python3
"""MECHANISM SUPPLY CENSUS -- run it, write data/mechanism_census.json, print the gap list.

WHAT THIS ANSWERS, and it is one question: WHICH UNTESTED OR UNDER-TESTED ECONOMIC MECHANISM
CLASS IS THE HIGHEST-VALUE NEXT TARGET, AND WHAT DATA WOULD IT TAKE TO TEST IT.

The per-class table above the gap list exists to make that ranking auditable, not for its own
sake. The reading it supports: the desk's maximum-power campaign put 44 pooled candidates and
920 per-symbol backtests through the gauntlet, and those 44 "mechanisms" resolve to a handful of
economic classes, all of them derived from one OHLCV tape. That is not a gate problem. Adding
candidates inside those classes cannot move the diversity number, which is exactly why the
number is reported volume-invariant.

ZERO AUTHORITY. This script measures and writes one JSON file. It promotes nothing, blocks
nothing, changes no gate or threshold, and places no orders.

    python3 scripts/run_mechanism_census.py [--out data/mechanism_census.json] [--top 8]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.research.mechanism_census import (  # noqa: E402
    Coverage,
    census,
)

_BAR = "=" * 100


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/mechanism_census.json",
                    help="artifact path, relative to the repo root")
    ap.add_argument("--top", type=int, default=8, help="how many gap rows to print in full")
    args = ap.parse_args(argv)

    report = census(ROOT)
    payload = report.to_dict()

    # ------------------------------------------------------------------ sources, read first ---
    print(_BAR)
    print("EVIDENCE SOURCES -- what this checkout can and cannot see")
    print(_BAR)
    for src in report.sources:
        mark = "OK " if src.readable else "!! "
        print(f"  {mark}{src.path!s:42s} {'READABLE' if src.readable else 'NOT-READABLE-HERE':18s}"
              f" n={src.n_records:<4d} {src.detail[:70]}")
    missing = [s for s in report.sources if not s.readable]
    if missing:
        print(f"\n  {len(missing)} runtime-only artifact(s) absent. Their classes are marked "
              f"NOT-READABLE-HERE or carry a lower-bound tested count -- never zero.")

    # ---------------------------------------------------------------------- the class table ---
    print()
    print(_BAR)
    print("MECHANISM CLASS CENSUS -- one row per ECONOMIC mechanism, not per feature family")
    print(_BAR)
    print(f"  {'class':34s} {'coverage':18s} {'cand':>4s} {'test':>4s} {'cons':>4s} {'par':>4s} "
          f"{'bestOOS':>8s}  verdicts")
    for c in sorted(report.classes, key=lambda x: (-x.n_tested, x.class_id)):
        oos = "     n/a" if c.best_oos_sharpe is None else f"{c.best_oos_sharpe:+8.3f}"
        verdicts = " ".join(f"{k}={v}" for k, v in c.verdicts.items()) or "(none -- untested)"
        print(f"  {c.class_id:34s} {c.coverage!s:18s} {c.n_candidates:4d} {c.n_tested:4d} "
              f"{c.n_constructions:4d} {c.n_parameterisations:4d} {oos}  {verdicts}")
    print("\n  cand=readable records  test=records that were actually run  cons=distinct "
          "constructions  par=parameterisations")
    print("  bestOOS is null, never 0.0, where no record carries an out-of-sample number.")

    # ------------------------------------------------------------------------- the numbers ----
    counts = report.coverage_counts()
    div, camp = report.diversity, report.campaign_diversity
    print()
    print(_BAR)
    print("MECHANISM COVERAGE and DIVERSITY")
    print(_BAR)
    for state in (Coverage.TESTED_DEEP, Coverage.TESTED_SHALLOW, Coverage.NAMED_UNTESTED,
                  Coverage.NO_CANDIDATE, Coverage.NOT_READABLE_HERE):
        print(f"  {state!s:20s} {counts.get(str(state), 0):3d} / {len(report.classes)} classes")
    print(f"\n  ALL READABLE TESTED SUPPLY : {div.n_candidates} records occupy "
          f"{div.n_classes_occupied}/{div.n_classes_in_taxonomy} classes -> effective classes "
          f"{div.effective_classes} -> DIVERSITY {div.diversity}")
    print(f"    largest class '{div.top_class}' holds {div.top_class_share:.1%} of it; "
          f"HHI {div.hhi}")
    print(f"\n  MAXIMUM-POWER CAMPAIGN ONLY: {camp.n_candidates} pooled candidates occupy "
          f"{camp.n_classes_occupied}/{camp.n_classes_in_taxonomy} classes -> effective classes "
          f"{camp.effective_classes} -> DIVERSITY {camp.diversity}")
    print(f"    largest class '{camp.top_class}' holds {camp.top_class_share:.1%} of it; "
          f"HHI {camp.hhi}")
    print("\n  Diversity is exp(Shannon) over the taxonomy: VOLUME-INVARIANT by construction, so "
          "\n  another hundred candidates inside classes already occupied cannot move it.")

    # ------------------------------------------------------------------- THE DELIVERABLE ------
    print()
    print(_BAR)
    print("RANKED GAP LIST -- highest-value untested / under-tested classes, and what each needs")
    print(_BAR)
    print("  score = plausibility x orthogonality x data-feasibility x depth-deficit. Declared "
          "constants,\n  never fitted, and carrying zero promotion authority: this orders a "
          "reading list.\n")
    for gap in report.gaps[:max(0, args.top)]:
        req = gap.data_required
        print(f"  #{gap.rank} {gap.name}  [{gap.class_id}]")
        print(f"      score {gap.gap_score:.4f} = plaus {gap.plausibility:.2f} x orth "
              f"{gap.orthogonality:.2f} x feas {gap.feasibility:.2f} x deficit "
              f"{gap.depth_deficit:.2f}   ({gap.coverage})")
        print(f"      WHO PAYS   : {gap.payer}")
        print(f"      DATA NEEDED: [{req.availability}]")
        for dataset in req.datasets:
            print(f"                   - {dataset}")
        print(f"      NOTE       : {req.note}")
        if gap.prior_kills:
            print(f"      PRIOR KILLS: {', '.join(gap.prior_kills)}")
        print()
    tail = report.gaps[max(0, args.top):]
    if tail:
        print("  lower-ranked: "
              + ", ".join(f"{g.class_id} {g.gap_score:.3f}" for g in tail))
    for gap in report.unrankable:
        print(f"\n  UNRANKABLE  {gap.class_id}: {gap.why}")

    # ------------------------------------------------------------------------------ artifact --
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=False), "utf-8")
    print(f"\n-> {out} ({len(report.classes)} classes, {payload['totals']['n_records']} readable "
          f"records, {payload['totals']['n_unclassified']} unclassified)")
    if report.unclassified:
        print("   UNCLASSIFIED (reported, never assigned to the nearest plausible class):")
        for row in report.unclassified[:12]:
            print(f"     - {row.candidate_id}  [{row.source}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
