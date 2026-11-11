"""Write reports/EXPERIMENT_LEDGER.json on a clock (hourly leg `experiment_ledger`).

Lives in `research/`, not `scripts/`: it is a report writer, never money path.

THE LEDGER HAD NO WRITER. `external_gauntlet.lifetime_trial_report` says "pf_allocator writes it
hourly through experiment_ledger.lifetime(write=True)", but `pf_allocator.search_trials` calls
`lifetime(write=False)`, and `experiment_ledger.family_trials` only rebuilds the file when it is
unreadable, never when it is old. So nothing on any clock wrote it. Read on the box 2026-11-11
08:50Z: mtime and `generated_utc` both 2026-09-20T23:23:46Z, 52 days old, while the sealed judge
charged its `lifetime union trials 26728834` on every one of 38,620 cells. A frozen count can
only UNDER-charge (trials only grow), so the deflated Sharpe was judged more leniently than the
ledger's own rule says. This leg writes it every hour; it judges nothing and changes no rule.

A LEDGER THAT FALLS IS A BAD READ, NEVER A FACT, AND IS NOT WRITTEN. Trials only grow. But
`_graph_counts` returns (0, {}) on any OSError reading the 3.7 GB graph (a rotation, a held lock,
a mid-write), and the claim-selection and prereg counters swallow every exception as 0. Before
this leg nothing rewrote the file, so a transient failure there cost nothing; on a clock, one bad
read would overwrite 26.7M with millions fewer and the sealed judge would charge every cell the
lower number for an hour -- the one direction the ledger's own rule forbids ("consumers may only
deflate MORE, never less"). So the new document is computed first and compared: if its lifetime
total or any family's count is below the file's, nothing is written, the drop is logged and the
leg exits 1. The write itself is a temp file and `os.replace`, because the judge reads this file
concurrently and a torn read fails every cell closed for the pass.

Exit 0 when the ledger was written, 1 when it could not be or was refused. Prints a one-line JSON
summary with the previous file's `generated_utc` and lifetime count beside the new ones, so the
leg log shows how far the file had drifted.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
#: What this leg writes; mirrors `experiment_ledger.OUT` (a test pins them). Bound here so the
#: component registry reads the leg's artifact from its own source.
OUT = DESK / "reports" / "EXPERIMENT_LEDGER.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import experiment_ledger  # noqa: E402


def _previous() -> dict:
    try:
        doc = json.loads(experiment_ledger.OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def drops(prev: dict, doc: dict) -> dict:
    """Every count in `doc` below the same count in `prev`. Empty means the write is safe."""
    out: dict = {}
    try:
        if int(doc.get("lifetime_trials") or 0) < int(prev.get("lifetime_trials") or 0):
            out["lifetime_trials"] = [prev.get("lifetime_trials"), doc.get("lifetime_trials")]
    except (TypeError, ValueError):
        pass
    old_f = prev.get("by_family") if isinstance(prev.get("by_family"), dict) else {}
    new_f = doc.get("by_family") if isinstance(doc.get("by_family"), dict) else {}
    for fam, n in old_f.items():
        try:
            if int(new_f.get(fam) or 0) < int(n or 0):
                out[f"family:{fam}"] = [n, new_f.get(fam, 0)]
        except (TypeError, ValueError):
            continue
    return out


def write_atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    del argv  # one form only: one pass
    prev = _previous()
    out = Path(experiment_ledger.OUT)
    try:
        doc = experiment_ledger.lifetime(write=False)
    except OSError as exc:
        print(f"experiment_ledger: could not count: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    fell = drops(prev, doc)
    summary = {"generated_utc": doc["generated_utc"],
               "lifetime_trials": doc["lifetime_trials"],
               "judged_cells": doc["judged_cells"],
               "screened_cells": doc["screened_cells"],
               "families": len(doc.get("by_family") or {}),
               "previous_generated_utc": prev.get("generated_utc"),
               "previous_lifetime_trials": prev.get("lifetime_trials")}
    if fell:
        summary.update(written=False, refused="a trial count fell; a bad read, never a fact",
                       drops=dict(list(fell.items())[:20]), n_drops=len(fell))
        print(json.dumps(summary, default=str))
        return 1
    try:
        write_atomic(out, doc)
    except OSError as exc:
        print(f"experiment_ledger: could not write: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    summary["written"] = True
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
