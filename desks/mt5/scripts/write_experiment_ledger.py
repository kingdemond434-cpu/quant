"""Write reports/EXPERIMENT_LEDGER.json on a clock (hourly leg `experiment_ledger`).

THE LEDGER HAD NO WRITER. `external_gauntlet.lifetime_trial_report` says "pf_allocator writes it
hourly through experiment_ledger.lifetime(write=True)", but `pf_allocator.search_trials` calls
`lifetime(write=False)`, and `experiment_ledger.family_trials` only rebuilds the file when it is
unreadable, never when it is old. So nothing on any clock wrote it. Read on the box 2026-11-11
08:50Z: mtime and `generated_utc` both 2026-09-20T23:23:46Z, 52 days old, while the sealed judge
charged its `lifetime union trials 26728834` on every one of 38,620 cells. A frozen count can
only UNDER-charge (trials only grow), so the deflated Sharpe was judged more leniently than the
ledger's own rule says. This leg writes it every hour; it judges nothing and changes no rule.

Exit 0 when the ledger was written, 1 when it could not be. Prints a one-line JSON summary with
the previous file's `generated_utc` and lifetime count beside the new ones, so the leg log shows
how far the file had drifted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import experiment_ledger  # noqa: E402


def _previous() -> dict:
    try:
        doc = json.loads(experiment_ledger.OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def main(argv: list[str] | None = None) -> int:
    del argv  # one form only: one pass
    prev = _previous()
    try:
        doc = experiment_ledger.lifetime(write=True)
    except OSError as exc:
        print(f"experiment_ledger: could not write: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    print(json.dumps({"generated_utc": doc["generated_utc"],
                      "lifetime_trials": doc["lifetime_trials"],
                      "judged_cells": doc["judged_cells"],
                      "screened_cells": doc["screened_cells"],
                      "families": len(doc.get("by_family") or {}),
                      "previous_generated_utc": prev.get("generated_utc"),
                      "previous_lifetime_trials": prev.get("lifetime_trials")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
