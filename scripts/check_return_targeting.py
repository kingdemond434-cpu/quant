#!/usr/bin/env python3
"""RETURN TARGETING (R0143) -- no stated return number may become an objective.

THE DOCTRINE, on the books since 2026-07-12 (docs/PROJECT_HANDOFF.md):

    "Don't chase a CAGR target (targeting a return number corrupts a survival-constrained
     optimizer into over-leverage). Max safe growth; let the number fall out."

WHY IT NEEDED A FENCE. On 2026-07-31 a section titled "What 300% net CAGR actually requires" was
written into docs/DISCRETIONARY_DESK.md -- straight past that line, past a 2026-07-16 decision
that had already triaged a "CAGR-maximisation override" out of a principal-supplied constitution,
and past a decision-ledger success metric reading "no CAGR targeting". Three separate prior
rulings, and the regression still landed. It was caught by the PRINCIPAL, not by any check. By
this desk's own standard that means it was not caught at all (L1.41).

WHY THE DOCTRINE IS MECHANICAL, NOT STYLISTIC. A stated return number anchors every downstream
decision toward the tail of the distribution, and the only lever that reaches a tail outcome is
SIZE. The desk's own simulations show where that ends: at 20% risk per trade the book meets a -90%
drawdown with near-certainty EVEN WHEN THE STRATEGY IS PROFITABLE, and past full Kelly more size
makes growth NEGATIVE. A target high enough to be motivating is therefore a standing instruction
to destroy the thing it aims at.

THE DISTINCTION THIS FENCE MUST GET RIGHT, and the reason it is narrow. Return numbers are
legitimate and necessary as ANALYSIS -- "cost-adjusted breakeven is 31.1%", "the kill floor is
25%", "measured noise is 0.64%". They become a defect only when bound to GOAL language: target,
aim, must earn, should produce, we need. So the fence looks for a goal verb and a return figure in
the same breath, not for numbers on their own. A fence that flagged every percentage would be
switched off within a day, and then the doctrine would have no enforcement at all -- which is the
state it was already in.

REMOVING A TARGET IS NOT TIMIDITY, and the fence says so where it fires: the law stack already
mandates the maximum (L1.28 timidity is a defect, L1.28a idle capacity is unbooked loss, L1.28b
conversion pushes to 100%, L1.28c cadence hunts its own ceiling, L1.25a the hunt never tires).
Those bind harder than a figure in a document because they fail the build. A stated target is the
one instruction that points AWAY from them.

    python scripts/check_return_targeting.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402

#: UNMEASURED here means every governed surface was unreadable -- so the doctrine is UNCHECKED,
#: which the report body already says in prose and the exit code used to contradict by returning
#: 0. The docstring at the status site calls it "NOT a pass"; now the exit code agrees.
_PASSING = frozenset({"OK"})

#: Where a return target does damage: the desk's own doctrine, its money-path organs, and the
#: prompt surfaces that reach a model. Scoped deliberately -- the ledger and research notes RECORD
#: what the principal asked for verbatim, and rewriting a quotation to satisfy a fence would be
#: falsifying the record.
#: NARROWED 2026-09-05 (universe mandate). Six money-path entries left this scope because their
#: FILES left the repo with the retired book: run_conviction_trader, run_llm_trader,
#: resolve_paper_book, run_sleeve_allocator, run_trade_review, build_chart_context. They are
#: removed rather than kept-and-skipped because a scope naming files that cannot be read reports
#: "0 violations" over an empty set -- a fence measuring nothing while looking green, which is the
#: L1.43 welded-gate shape this desk fences elsewhere. The MT5 money path is under desks/mt5/ and
#: carries its own return-language discipline; adding it here is a decision for whoever wires it,
#: not a silent widening by a cleanup.
_SCOPE: tuple[str, ...] = (
    "docs/DISCRETIONARY_DESK.md", "docs/CONSTITUTION.md", "docs/PROJECT_HANDOFF.md",
    "ops/principal_doctrine.txt", "ops/crontab.manifest",
)

#: Goal language. A return figure near ANY of these is a target rather than a measurement.
_GOAL = (r"target", r"aim(?:ing|s)?\s+(?:for|at|high)", r"goal", r"must\s+(?:earn|produce|hit|make)",
         r"should\s+(?:earn|produce|hit|make)", r"we\s+need", r"chase", r"objective\s+of")

#: A return figure: a percentage carrying return/CAGR/growth vocabulary, or a bare percentage of
#: 150%+ (nobody writes "300%" about anything but a return). The bare pattern starts at 150 rather
#: than 100 because on THIS desk 100% is overwhelmingly a COVERAGE figure -- ratchet floors,
#: breadth coverage, conversion pushing to 100% -- and the first run flagged three of those in the
#: constitution itself. Widening the exclusion rather than rewording the constitution is the same
#: rule the build standard and the sizing fence both had to learn.
_FIGURE = (r"\d{2,4}\s*(?:%|pct|percent)\s*(?:net\s*)?(?:cagr|return|growth|annual)",
           r"(?:cagr|return|growth)\s*(?:of\s*)?\d{2,4}\s*(?:%|pct|percent)",
           r"\b(?:1[5-9]\d|[2-9]\d\d|\d{4})\s*%")

#: Passages that legitimately state a target IN ORDER TO FORBID IT. Without this the doctrine line
#: itself trips the fence, which would be an own goal in the most literal sense.
_NEGATED = (r"don'?t\s+chase", r"do\s+not\s+chase", r"no\s+cagr\s+target", r"not\s+a\s+target",
            r"no\s+return\s+number", r"deliberately\s+no", r"is\s+not\s+something\s+to\s+hit",
            r"was\s+a\s+doctrine\s+regression", r"rather\s+than\s+a\s+target",
            r"no\s+stated\s+return", r"not\s+the\s+goal", r"corrupts")

#: Characters either side of a goal word searched for a return figure. 160 is about two lines of
#: prose -- wide enough to catch "our target ... is 300% CAGR" split across a wrap, narrow enough
#: that an unrelated percentage three paragraphs later does not get bound to it.
_WINDOW = 160


def scan_text(text: str) -> list[dict[str, Any]]:
    flat = " ".join(text.split())
    low = flat.lower()
    hits: list[dict[str, Any]] = []
    for gpat in _GOAL:
        for gm in re.finditer(gpat, low):
            lo, hi = max(0, gm.start() - _WINDOW), min(len(low), gm.end() + _WINDOW)
            window = low[lo:hi]
            if any(re.search(n, window) for n in _NEGATED):
                continue                              # stated in order to forbid it
            for fpat in _FIGURE:
                fm = re.search(fpat, window)
                if fm:
                    hits.append({"goal_word": gm.group(0), "figure": fm.group(0),
                                 "context": flat[lo:hi][:220]})
                    break
    return hits


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    files, unreadable = [], []
    for rel in _SCOPE:
        p = root / rel
        try:
            hits = scan_text(p.read_text("utf-8", errors="ignore"))
        except OSError as exc:
            # NOT a pass: an unreadable governed file means this doctrine is UNCHECKED there.
            unreadable.append(f"{rel}: {type(exc).__name__}")
            continue
        if hits:
            files.append({"file": rel, "n": len(hits), "hits": hits[:4]})
    status = ("UNMEASURED" if unreadable and not files else
              "RETURN-TARGETING" if files else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "doctrine": "PROJECT_HANDOFF.md 2026-07-12 -- do not chase a CAGR target; targeting a "
                    "return number corrupts a survival-constrained optimizer into over-leverage. "
                    "Max safe growth; let the number fall out.",
        "status": status,
        "n_scoped": len(_SCOPE), "n_flagged": len(files),
        "unreadable": unreadable,
        "files": files,
        "not_timidity": "Removing a target is NOT a reduction in ambition. L1.28, L1.28a, L1.28b, "
                        "L1.28c and L1.25a already mandate the maximum and are enforced by fences "
                        "that fail the build -- which binds harder than a figure in a document. A "
                        "stated target is the one instruction pointing AWAY from them.",
        "detail": (f"{len(_SCOPE)} governed surfaces scanned; "
                   + ("no return number bound to goal language" if not files else
                      "TARGETING in " + ", ".join(f["file"] for f in files))
                   + (f"; UNREADABLE: {', '.join(unreadable)}" if unreadable else "")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/return_targeting.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"return targeting (L1.23/handoff): {rep['status']} -- {rep['detail']}")
        for f in rep["files"]:
            for h in f["hits"]:
                print(f"  {f['file']}: '{h['goal_word']}' near '{h['figure']}'")
                print(f"      ...{h['context'][:150]}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())
