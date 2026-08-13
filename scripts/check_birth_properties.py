#!/usr/bin/env python3
"""A NEW OBJECT IS BORN WITH ITS PROPERTIES, OR IT DOES NOT LAND (L1.37 boundary for §36/L1.28b).

THE DEFECT CLASS, NAMED SO IT CANNOT RETURN IN A FOURTH COSTUME. Four of this desk's fences fire
on the same shape -- *an object of class X arrived without a required property P* -- and every one
of them RECURS:

    artifact-ungoverned        a new docs/*.md claimed by no law          6x over 17.4d
    orphan-scripts             a new scripts/*.py referenced by nothing   4x over 12.4d
    mine-conversion-unbacked   a card claiming a disposition, no artifact 3x over 11.1d
    decision-ledger-undated    a decision row with no review_due          2x over 12.0d

They are not neglect. Each was FIXED, correctly, and came back on a NEW instance -- which is the
§37 brief's definition of RECURRING and its explicit instruction: *"its per-instance fix is the
defect: generalise the rule so the class cannot return."*

WHY THE PER-INSTANCE FIX WAS ALWAYS GOING TO BUY EXACTLY ONE CYCLE. All four checks live in
scripts/max_audit.py, which runs at 07:00 on cron and NOWHERE ELSE -- not in run_law_gate, not in
the pre-push hook, not in CI (verified 2026-08-12: max_audit appears in none of the three). So the
sequence is always the same: an organ or a session authors the object, commits, pushes; hours
later the sweep fires; the authoring context is GONE; the item becomes a carry-over row for some
future cycle to classify from cold. The desk's own commit messages are the record --
9f3e2fcf "fix artifact-ungoverned that MY OWN commit introduced" and 9d92d725 "classify
RECORDER_DEPLOY.md on the day it was written, NOT IN A LATER SWEEP". The second one names the
correct behaviour exactly, and implemented it as a habit rather than as a gate; habits do not
survive a context window. scripts/check_row_atomicity.py was authored and orphaned on 2026-08-12
by the very session that was draining this same backlog.

THE GENERALISATION IS A BOUNDARY, NOT A BETTER DETECTOR. The detector is already right; it simply
speaks after the only person who could cheaply answer it has left. This runs the same predicates
at the push and CI boundaries (L1.37), where the author is still present and the answer costs one
line. It cannot find anything max_audit would not find -- it finds the same things EARLIER, which
is the whole value: at 07:00 the question is "why does this file exist?", at push time it is
"say why this file exists."

SCOPE IS THE WHOLE TREE, DELIBERATELY, NOT A DIFF OF NEWLY-ADDED FILES. The obvious design is to
scope to `git diff --diff-filter=A` against a merge-base, and it was rejected on two counts: a
merge-base is not resolvable on the shallow clone `actions/checkout` produces by default, so the
fence would silently degrade to UNMEASURED in exactly one of its four boundaries; and whole-tree
scope is strictly stronger, since it also catches a REGRESSION that un-governs an existing object
(which is precisely how docs/research/cadence_duties.md came to fire -- its governance was an
incidental substring match in a max_audit comment, and it evaporated when that comment changed).
Pre-existing debt is not an argument against whole-tree scope here because the debt is ZERO: all
three predicates were driven green in the same commit that installed this. A fence red on the day
it is built gets switched off (L1.43), so the clearing came first.

WHAT IS DELIBERATELY *NOT* ENFORCED HERE, AND WHY -- NEVER A SILENT CAP. The fourth member of the
class, `mine-conversion-unbacked`, is EXCLUDED, and it is excluded on measurement rather than
taste. Run in a clean `git worktree` at the same sha, check_mine_conversion reports 0 defects on
this box and 10 in the fresh tree, for two independent reasons:

  1. §33 credits conversion against artifacts like `data/coinmetrics_flows.jsonl`, which are
     GITIGNORED -- they exist on the producing box and in no clone.
  2. Its postdates-the-find test compares `p.stat().st_mtime` against the card's first sighting.
     A checkout stamps every file at checkout time, so that comparison carries no information in
     any fresh tree and reads as `stale-evidence` for cards whose work was genuinely done.

A fence whose verdict depends on which machine ran it is not a gate in either direction -- the
lesson check_artifact_governance already paid for and wrote down. So §33 conversion evidence is
verifiable ONLY on the box that produced it, and belongs in _STATE_FENCES, not here. That is a
real gap and it is recorded as one rather than papered over: the class fix for it is to make
conversion evidence portable (commit the receipts, or key the recency test on something a clone
preserves), which is a change to §33's evidence model and not a drive-by in this fence.

    python scripts/check_birth_properties.py [--json] [--report-only]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402

#: THE BIRTH PROPERTIES, each (defect-key, max_audit predicate, what the object is).
#: The predicates are IMPORTED, never re-implemented: a second copy of the claim tables would
#: drift from max_audit's within weeks, and this desk has already paid for exactly that
#: (max_audit.py:356 records ORGAN_ARTIFACTS silently diverging from its organ_catchup sibling
#: "for weeks"). One source of truth, two boundaries.
_PROPERTIES: tuple[tuple[str, str, str], ...] = (
    ("artifact-ungoverned", "check_artifact_governance",
     "every docs/*.md is claimed by a law, or recorded terminal WITH A REASON (§36(2))"),
    ("orphan-scripts", "check_orphan_scripts",
     "every scripts/*.py is reachable, or declared one-shot WITH THE REASON IT RAN ONCE (§36)"),
    ("decision-ledger-undated", "check_decision_ledger_matures",
     "every logged decision carries a review_due, so the scoring cadence has a queue (L2.9)"),
)

_PASSING = frozenset({"OK"})


def _counts() -> dict[str, int]:
    """The DENOMINATOR of this verdict (L1.57), measured from what the run found.

    Every number here is a live count off the filesystem/ledger, never ``len()`` of a
    module-level literal -- a constant denominator cannot fall when the thing it counts
    disappears, which is the one event it exists to reveal.

    IT COUNTS WHAT WAS JUDGED, NOT WHAT WAS WALKED. The predicates skip untracked files
    (max_audit._committed_only: governance applies to what is COMMITTED), so counting the raw
    filesystem would publish a denominator larger than the set actually judged -- overstating
    coverage by exactly the sibling work-in-progress this fence deliberately ignores. A
    denominator that counts objects the verdict never examined is the same lie L1.57 was written
    about, one direction over.
    """
    import scripts.max_audit as m

    docs = len(m._committed_only(
        [p.relative_to(_ROOT).as_posix() for p in (_ROOT / "docs").rglob("*.md")]))
    scripts = len(m._committed_only(
        [p.relative_to(_ROOT).as_posix() for p in (_ROOT / "scripts").glob("*.py")]))
    decisions = 0
    ledger = _ROOT / "data" / "decision_ledger.json"
    if ledger.exists():
        # No silent swallow (L2.4): a malformed ledger must not read as "zero decisions, fine".
        # It raises, the fence dies loudly, and an unrunnable fence counts as FAILED.
        doc = json.loads(ledger.read_text("utf-8"))
        rows = doc.get("decisions", []) if isinstance(doc, dict) else doc
        decisions = sum(1 for r in rows if isinstance(r, dict))
    return {"docs": docs, "scripts": scripts, "decisions": decisions}


def build_report() -> dict[str, Any]:
    import scripts.max_audit as m

    found: list[dict[str, str]] = []
    for key, fn_name, promise in _PROPERTIES:
        defects: list[tuple[str, str]] = []
        getattr(m, fn_name)(defects)
        found.extend({"property": key, "promise": promise, "detail": d}
                     for k, d in defects if k == key)

    counts = _counts()
    n = counts["docs"] + counts["scripts"] + counts["decisions"]
    # A REQUIRED INPUT THAT IS ABSENT IS NOT A CLEAN TREE (L1.28a/L1.55). check_decision_ledger
    # RETURNS SILENTLY when the ledger cannot be read, so without this the fence would publish OK
    # over a property it never actually evaluated -- the exact "absence resolves to a clean
    # verdict" defect (WS-005) this desk repeats most often.
    if not (_ROOT / "data" / "decision_ledger.json").exists():
        status = "UNMEASURED"
    else:
        status = "OK" if not found else "UNBORN-PROPERTY"
    return {
        "status": status,
        "law": "L1.37 boundary for §36 / L2.9",
        "scanned": n,
        "counts": counts,
        "properties_enforced": [k for k, _, _ in _PROPERTIES],
        "excluded": {
            "mine-conversion-unbacked":
                "NOT PORTABLE, measured not assumed: 0 defects on the producing box vs 10 in a "
                "clean worktree at the same sha -- §33 credits gitignored artifacts, and its "
                "postdates-the-find test reads st_mtime, which a checkout resets. A state fence, "
                "not a law fence.",
        },
        "violations": found,
        "detail": (f"{n} object(s) examined "
                   f"({counts['docs']} docs, {counts['scripts']} scripts, "
                   f"{counts['decisions']} decisions); "
                   + ("every one born with its properties" if not found else
                      "; ".join(f"{v['property']}: {v['detail'][:160]}" for v in found))),
    }


def main() -> int:
    # No guard() by design: this runs INSIDE run_law_gate's battery, which verifies the sealed
    # core before any fence executes. Guarding here would re-spawn the seal check per fence --
    # the loop check_build_standard._GUARD_EXEMPT names for its law-gate siblings.
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build_report()
    out = _ROOT / "data" / "birth_properties.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"birth-property fence (L1.37/§36): {rep['status']} -- {rep['detail']}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING,
                      scanned=rep["scanned"], of="docs + scripts + decision rows")


if __name__ == "__main__":
    sys.exit(main())
