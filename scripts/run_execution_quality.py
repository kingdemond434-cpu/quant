"""EXECUTION-QUALITY DECOMPOSITION (R0334, principal 2026-08-01) -> data/execution_quality.json.

Scores the conviction sleeve on the six components R0334 names -- entry, stop, target, sizing,
trade management, exit timing -- separately rather than as one blended hit-rate, because a blended
score cannot tell a good thesis exited badly from a bad thesis rescued by the trailing ladder.

WHY IT IS DETERMINISTIC. run_trade_review already interrogates each close, but it does so through
an LLM and is currently returning nothing at all: data/trade_review.json carries n_reviewed 5 with
every result NO-REVIEW ("no parseable review"), and the playbook holds 0 supported lessons against
12 provisional. A numeric decomposition cannot fail to parse, and it gives that reviewer something
to interrogate rather than replacing it.

WHAT IT DOES NOT DO. It sizes nothing and promotes nothing. R0334 also asks that size auto-reduce
as measured expectancy decays; on 14 paper closes an expectancy estimate is noise, and the sleeve
already owns that decision through its own kill_condition at n=50. Publishing a number here and
letting it move size would be sizing on unproven edge.

    python scripts/run_execution_quality.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.execution_quality import score  # noqa: E402

_BOOK = "data/conviction_book.jsonl"
_PNL = "data/paper_book_pnl.json"
_MARKS = "data/paper_book_marks.jsonl"
_OUT = "data/execution_quality.json"

#: A decomposition over too few closes is still a correct artifact -- it says INSUFFICIENT on each
#: component. The fence fails only when it cannot read its inputs at all.
_PASSING = frozenset({"MEASURED", "INSUFFICIENT", "UNMEASURED"})


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue          # a torn last line is skipped, never defaulted into a fake record
        if isinstance(row, dict):
            rows.append(row)
    return rows


def build_report(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    inp = Inputs("run_execution_quality")

    entries = _jsonl(root / _BOOK)
    if not entries:
        inp.defaulted(_BOOK, "no conviction entries readable")
    history = _jsonl(root / _MARKS)
    if not history:
        inp.defaulted(_MARKS, "no mark history readable -- MFE/MAE cannot be derived")
    pnl = inp.read_json(root / _PNL, default={}, max_age_h=48.0) or {}

    marks = pnl.get("marks") if isinstance(pnl, dict) else None
    closes = [m for m in (marks or [])
              if isinstance(m, dict) and m.get("kind") == "conviction"
              and m.get("closed") and isinstance(m.get("realised_R"), (int, float))]

    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        key = row.get("key")
        if key:
            paths[str(key)].append(row)

    if not closes:
        return {
            "generated": now.isoformat(), "status": "UNMEASURED",
            "law": "R0334 -- execution quality is six decisions, not one score",
            "detail": ("no closed conviction trade carries a realised_R -- UNMEASURED, never a "
                       "clean scorecard (L1.28a)"),
            "n_closes": 0, "n_entries": len(entries),
            "provenance": inp.block(), "provenance_status": inp.status(),
        }

    components = [c.as_dict() for c in score(entries, closes, dict(paths))]
    measured = sum(1 for c in components if c["state"] == "MEASURED")
    return {
        "generated": now.isoformat(),
        "law": "R0334 -- execution quality is six decisions, not one score",
        "status": "MEASURED" if measured else "INSUFFICIENT",
        "book": "PAPER -- data/conviction_book.jsonl is marked paper:true on every row; none of "
                "this is live-capital evidence",
        "n_closes": len(closes),
        "n_entries": len(entries),
        "n_components_measured": measured,
        "n_components": len(components),
        "components": components,
        "sizing_note": ("this artifact moves no size. R0334 asks that size auto-reduce as measured "
                        f"expectancy decays; on {len(closes)} paper closes an expectancy estimate "
                        "is noise, and the sleeve's own kill_condition at n=50 owns that decision"),
        "provenance": inp.block(),
        "provenance_status": inp.status(),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build_report(_ROOT)
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"execution quality: {rep['status']} over {rep['n_closes']} paper close(s)")
        for comp in rep.get("components", []):
            val = "n/a" if comp["value"] is None else f"{comp['value']:g} {comp['unit']}"
            print(f"  {comp['state']:<24} {comp['name']:<18} {val:>22}  (n={comp['n']})")
            print(f"      {comp['why']}")

    # Subject to L1.57: the denominator is the closed trades this run actually found, so an empty
    # book refuses its own pass rather than reporting a clean scorecard.
    return fence_exit(rep["status"], _PASSING, scanned=int(rep.get("n_closes") or 0),
                      of="closed conviction trades carrying realised_R",
                      fence="run_execution_quality.py")


if __name__ == "__main__":
    raise SystemExit(main())
