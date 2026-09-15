"""EVERY MINED ROW CONVERTS TO CELLS, OR IS REFUSED BY NAME. The gate, and the fixer's worklist.

THE LAW (principal, 2026-09-15): every single mined row should be converted to cells. Its
enforceable form is not "force a cell out of every row" -- some rows must NOT become cells, and
manufacturing one from a leaderboard position or from an empty page is worse than leaving it. The
enforceable form is:

    EVERY MINED ROW MUST REACH A TERMINAL DISPOSITION: a cell, or a NAMED refusal.
    "Needs extraction" is NOT terminal. It is a BACKLOG, and a backlog that never shrinks is a
    claim the desk cannot cash (L1.49).

That distinction is what this gate exists to hold, because the alternative was measured and it is
ugly. Before 2026-09-15 the compiler labelled 63,126 rows NEEDS_SYMBOL_EXTRACTION, and inside that
number were three completely different things wearing one label:

    a real bug          10,926 broker_swaps rows naming Accenture, Adobe, AlibabaGroup -- every
                        mixed-case Fusion symbol -- which `resolve_symbols` upper-cased into
                        nothing. The row already carried the instrument in a structured field and
                        was queued for an LLM call to recover it.
    a missing converter 4,640 central-bank speeches whose currency is stated in the institution
                        and nowhere else, and 28,077 public track records carrying a phenotype.
    a collector defect  38,657 rows with no text, no instrument and no structure: the crawler
                        captured a LINK and not a page. No extraction can succeed on those, ever.

One label, three remedies, and the label pointed at the wrong one for all of them -- it sent every
case to the deepening queue, where a bug and a broken crawler look exactly like research in
progress. So the census below separates them, and the RANKED WORKLIST at the end names the exact
(seat, kind) shapes that would convert next, largest first. That list is the fixer: it says what to
build, not that something should be built.

    python scripts/check_row_conversion.py
    python scripts/check_row_conversion.py --limit 400   # sample the files, for a fast check
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "ROW_CONVERSION.json"

#: Dispositions that END the row's life legitimately. A row here is DONE: either it produced
#: cells or the desk has stated, in its own vocabulary, why it must not.
TERMINAL_CELL = ("EXACT_RECIPE", "STRUCTURED_COT", "STRUCTURED_EVENT", "STRUCTURED_CARRY",
                 "STRUCTURED_LEAD_LAG", "STRUCTURED_CROSS_ASSET_RESIDUAL",
                 "STRUCTURED_RELATIVE_VALUE", "STRUCTURED_CALENDAR", "STRUCTURED_HYPOTHESIS",
                 "STRUCTURED_CB_SPEECH", "STRUCTURED_TRACK_RECORD", "TEXT_EXTRACTED")
TERMINAL_REFUSAL = ("OPERATIONAL_ROW", "EMPTY_CAPTURE")
#: NOT terminal. Work, waiting to be done, and the number that must ratchet DOWN.
BACKLOG = ("NEEDS_SYMBOL_EXTRACTION", "NEEDS_EXACT_RULE_EXTRACTION")


def _rows_of(path: str) -> list[dict[str, Any]]:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        d = json.loads(text)
        return [x for x in (d if isinstance(d, list) else [d]) if isinstance(x, dict)]
    except ValueError:
        pass
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            x = json.loads(ln)
        except ValueError:
            continue
        if isinstance(x, dict):
            out.append(x)
    return out


def audit(limit: int | None = None) -> dict[str, Any]:
    from research.miner_candidate_compiler import compile_row

    universe = set(json.loads((DESK / "data" / "universe" / "universe.json")
                              .read_text(encoding="utf-8")))
    files: list[str] = []
    for root in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        for pat in ("**/*.json", "**/*.jsonl"):
            files.extend(glob.glob(str(root / pat), recursive=True))
    files.sort()
    if limit:
        files = files[:limit]

    disp: Counter = Counter()
    shapes: Counter = Counter()
    cells = 0
    rows = 0
    for f in files:
        seat = os.path.basename(os.path.dirname(f))
        for r in _rows_of(f):
            rows += 1
            try:
                c, d = compile_row(seat, r, universe)
            except Exception as exc:                       # a crash is a disposition too
                c, d = [], f"ERROR:{type(exc).__name__}"
            disp[d] += 1
            cells += len(c)
            if d in BACKLOG:
                shapes[(seat, str(r.get("kind") or r.get("type") or ""), d)] += 1

    n_cell = sum(v for k, v in disp.items() if k in TERMINAL_CELL)
    n_ref = sum(v for k, v in disp.items() if k in TERMINAL_REFUSAL)
    n_back = sum(v for k, v in disp.items() if k in BACKLOG)
    n_other = rows - n_cell - n_ref - n_back

    worklist = [{"seat": s, "kind": k, "disposition": d, "rows": n,
                 "remedy": ("write a structured converter for this (seat, kind): the rows carry "
                            "an instrument or a structure the compiler is not reading"
                            if d == "NEEDS_SYMBOL_EXTRACTION" else
                            "these rows name an instrument but no rule; either a phenotype/tag "
                            "map exists for them or they genuinely need the deepening worker")}
                for (s, k, d), n in shapes.most_common(25)]

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY MINED ROW REACHES A TERMINAL DISPOSITION: a cell, or a refusal named in "
                "the desk's own vocabulary. 'Needs extraction' is a BACKLOG, never an answer, "
                "and a backlog that does not shrink is a claim the desk cannot cash."),
        "n_files": len(files),
        "n_rows": rows,
        "n_candidates": cells,
        "census": dict(disp.most_common()),
        "summary": {
            "terminal_cells": n_cell,
            "terminal_refusals": n_ref,
            "backlog": n_back,
            "unclassified_disposition": n_other,
            "terminal_share": round((n_cell + n_ref) / max(rows, 1), 4),
            "backlog_share": round(n_back / max(rows, 1), 4),
        },
        "what_the_refusals_are": {
            "EMPTY_CAPTURE": ("no text, no instrument, no structure: the crawler captured a LINK "
                              "and not a page. A COLLECTOR defect, and no extraction can ever "
                              "succeed on it. Fixing it means fixing the miner, not the "
                              "compiler."),
            "OPERATIONAL_ROW": "a fetch error or a status row; it was never evidence",
        },
        "worklist": worklist,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None, help="sample only the first N files")
    args = ap.parse_args(argv)

    doc = audit(limit=args.limit)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    s = doc["summary"]
    print(f"row conversion: {doc['n_rows']} mined row(s) in {doc['n_files']} file(s) -> "
          f"{doc['n_candidates']} candidate(s)")
    print(f"  terminal cells     {s['terminal_cells']:8}")
    print(f"  terminal refusals  {s['terminal_refusals']:8}   (named, and correct to refuse)")
    print(f"  BACKLOG            {s['backlog']:8}   {s['backlog_share']:.1%} -- must ratchet DOWN")
    print(f"  terminal share     {s['terminal_share']:.1%}")
    print("\n  WORKLIST -- the (seat, kind) shapes that would convert next, largest first:")
    for w in doc["worklist"][:12]:
        print(f"    {w['rows']:7}  {w['seat']:22} {str(w['kind'])[:16]:16} {w['disposition']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
