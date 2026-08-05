#!/usr/bin/env python3
"""WEEKLY WHOLE-DESK GRADE -- 100% coverage proven, scored harshly, every aspect pushed at once.

WHAT THIS IS AND WHY THE DAILY RATCHET DOES NOT ALREADY DO IT.
`run_capability_ratchet.py` grades 26 aspects daily and names ONE binding constraint. That is the
right shape for a daily cadence -- fix the worst thing. It has two limits a weekly grade must not
inherit:

  1. ITS ASPECT LIST IS ASSERTED, NOT PROVEN. `ASPECTS` is a hardcoded tuple of 26. An aspect of
     this desk nobody wrote into it is invisible, scores nothing, and drags no number down. So
     this organ DERIVES the desk's surface -- every scheduled cron organ, every libs subsystem,
     every data decision artifact, every constitutional law -- and reports what NO aspect claims.
     Coverage is then a measured fraction rather than a sentence, and it is scored on the same
     0-10 scale so it cannot be excluded from the headline.

  2. ITS HEADLINE IS AN ARITHMETIC MEAN. Measured 2026-08-05: 5.82 across 26 aspects while
     `alerting_pager` sat at 0.0 -- a desk whose pager has never delivered a page. An average lets
     two 10s pay for a zero, which is backwards: capability is a CHAIN. The headline here is the
     HARMONIC mean, which collapses toward the weakest member. On the same numbers it reads ~1.0,
     and that is the honest verdict. The arithmetic mean is still printed, because hiding it would
     be its own dishonesty -- it is simply not the number.

PUSH EVERY ASPECT AT ONCE. The output is the FULL worklist: every aspect below 10 with its
distance-to-ceiling and its own next action, plus every unrated surface ranked ABOVE all of them --
because a part of the desk nobody grades cannot even be known to be broken. A week is planned
against the whole surface rather than against one number seven times.

HARSH BY CONSTRUCTION, NOT BY TONE. Nothing here rounds up, nothing excludes an inconvenient
aspect, and an UNMEASURED component is never counted as a pass. The brutality is in the
arithmetic: harmonic aggregation, coverage as an aspect, and unrated surfaces outranking
everything.

    python scripts/run_weekly_desk_grade.py [--json] [--top N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.desk_coverage import (  # noqa: E402
    CEILING,
    SURFACES,
    desk_grade,
    enumerate_surface,
    n_effective_aspects,
    unclaimed,
    worklist,
)

RATCHET = "data/CAPABILITY_RATCHET.json"
OUT = "reports/weekly_desk_grade.json"
LEDGER = "data/weekly_desk_grade.jsonl"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def run(root: Path | None = None, *, refresh: bool = True) -> dict[str, Any]:
    base = root or _ROOT

    # RE-SCORE FIRST. Grading last week's artifact would report a week-old desk as this week's,
    # and a grade that can silently be stale is the same fail-open this whole file argues against.
    ratchet_ran = ""
    if refresh:
        try:
            proc = subprocess.run(
                [sys.executable, str(base / "scripts/run_capability_ratchet.py")],
                cwd=str(base), capture_output=True, text=True, timeout=900, check=False)
            ratchet_ran = f"rc={proc.returncode}"
        except Exception as exc:
            ratchet_ran = f"FAILED {type(exc).__name__}: {str(exc)[:120]}"

    doc = _load(base / RATCHET)
    aspects = doc.get("aspects") if isinstance(doc, dict) else None
    if not isinstance(aspects, list) or not aspects:
        return {"generated_utc": _now(), "status": "BLOCKED",
                "blocker": (f"{RATCHET} absent or carries no aspect list "
                            f"(capability ratchet: {ratchet_ran or 'not run'})"),
                "consequence": ("no desk grade could be computed. UNKNOWN, never a pass -- a "
                                "missing grade must not read as a healthy week"),
                "surfaces_definition": [{"kind": k, "how": h} for k, h in SURFACES]}

    surface = enumerate_surface(base)
    unrated = unclaimed(surface, aspects)
    grade = desk_grade(aspects, surface, unrated)
    work = worklist(aspects, unrated)

    by_kind: dict[str, dict[str, int]] = {}
    for item in surface:
        slot = by_kind.setdefault(item.kind, {"total": 0, "unrated": 0})
        slot["total"] += 1
        if not item.claimed_by:
            slot["unrated"] += 1

    payload: dict[str, Any] = {
        "generated_utc": _now(),
        "status": "OK",
        "capability_ratchet_refresh": ratchet_ran,
        **grade.as_dict(),
        "n_aspects": len(aspects),
        "n_effective_aspects": n_effective_aspects(aspects),
        "coverage_by_kind": by_kind,
        "surfaces_definition": [{"kind": k, "how": h} for k, h in SURFACES],
        "unrated_surfaces": [i.as_dict() for i in unrated][:120],
        "worklist": work,
        "n_worklist": len(work),
        "law": ("The headline is the HARMONIC mean, dominated by the weakest aspect: capability is "
                "a CHAIN and an arithmetic mean lets two 10s pay for a 0. COVERAGE IS AN ASPECT, "
                "scored on the same scale, so 26 aspects at 10 cannot read as a perfect desk while "
                "a third of the surface goes unrated. An UNRATED surface outranks every low score "
                "in the worklist, because a part of the desk nobody grades cannot be known to be "
                "broken."),
        "authority": ("MEASUREMENT ONLY. Grades nothing into existence, promotes nothing, moves no "
                      "threshold. Every number is derived from artifacts already on disk."),
    }
    (base / OUT).parent.mkdir(parents=True, exist_ok=True)
    (base / OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    (base / LEDGER).parent.mkdir(parents=True, exist_ok=True)
    with (base / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: payload.get(k) for k in
                             ("generated_utc", "grade_harmonic", "grade_arithmetic",
                              "coverage_score", "n_unrated", "n_surface")}) + "\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--no-refresh", action="store_true")
    args = ap.parse_args(argv)

    rep = run(refresh=not args.no_refresh)
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    if rep["status"] == "BLOCKED":
        print(f"weekly desk grade: BLOCKED -- {rep['blocker']}")
        print(f"  {rep['consequence']}")
        return 2

    print(f"WEEKLY DESK GRADE  {rep['grade_harmonic']:.2f}/10   "
          f"(arithmetic {rep['grade_arithmetic']:.2f} -- NOT the number: a chain is only as "
          "strong as its weakest link)")
    print(f"  coverage {rep['coverage_score']:.2f}/10  -- {rep['n_surface'] - rep['n_unrated']}"
          f"/{rep['n_surface']} surfaces rated, {rep['n_unrated']} UNRATED")
    for kind, c in sorted(rep["coverage_by_kind"].items()):
        print(f"     {kind:11s} {c['total'] - c['unrated']:>4}/{c['total']:<4} rated"
              f"{'   <-- ' + str(c['unrated']) + ' unrated' if c['unrated'] else ''}")
    print(f"  {rep['n_aspects']} aspects, {rep['n_effective_aspects']} effective "
          f"(distinct-artifact participation ratio -- breadth that is real, not nominal)")
    print(f"  at ceiling: {', '.join(rep['at_ceiling']) or 'NONE'}")
    print(f"\n  WEEKLY WORKLIST -- every aspect below {CEILING:.0f}, unrated surfaces first "
          f"({rep['n_worklist']} items, top {args.top}):")
    for row in rep["worklist"][:args.top]:
        score = f"{row['score']:.1f}" if row["score"] is not None else " -- "
        print(f"    [{row['kind']:9s} {score:>4} +{row['distance']:>4.1f}] {row['target'][:44]}")
        print(f"        {row['action'][:104]}")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
