#!/usr/bin/env python
"""A DEPARTMENT THAT STOPS PRODUCING MUST FAIL, NOT GO QUIET.

WHAT THIS FENCE IS FOR, and why it is not another liveness check. Three external reviews of this
repository converged on one closing question -- "does every claimed department actually run 24/7,
use real data, generate real hypotheses, produce measurable artifacts, enter the same canonical
validation pipeline, and have its resource allocation changed according to real survivor yield?"
-- and the desk could not answer it, because it had three censuses whose rosters shared ZERO
producers: PRODUCER_CENSUS (1,568 names), PRODUCTIVITY_CENSUS (2,094), DEAD_ARCHITECTURE (711,
keyed by code path). Union 2,817. Intersection nil. Every total the desk published about itself
was a total in one roster's private vocabulary.

`libs/ops/organ_census.py` joins them and measures the two links nothing else did -- whether an
organ's INPUT is still moving, and whether its artifact carries a PAYLOAD rather than only a
fresh timestamp. This script runs it, publishes `reports/ORGAN_CENSUS.json`, and fails on the
STALL rather than on any particular cause:

  (a) SILENT STOP. An organ that was producing a real artifact at the last census produces none
      now. It does not ask why -- a timeout, a broken donation door, a credential on the wrong
      machine, or the next failure nobody has met yet. "It worked and now it does not" is the one
      question that survives an unknown cause, which is what `check_placement_interlock` and
      `check_judging_coverage` were both built on this week.
  (b) THE JOIN LOSES RESOLUTION. Ambiguous code paths -- one file claimed by many organs -- may
      only fall. A census that cannot say which organ a file belongs to cannot credit its
      production to one, and crediting a shared runner's liveness to forty seats is exactly the
      flattery that would make the whole artifact worthless.
  (c) THE YIELD ORDER LOSES ITS GUARDS. The exploration floor must be positive and the ledger
      must never claim to ration the judge.

IT CAPS NOTHING. The census reports; it never throttles, retires or deprioritises an organ, and
it never refuses a cell judgement -- multiplicity is pinned at `fixed_trial_count: 109`, so
judging one more cell costs nothing at the bar and refusing one would be a pure loss.

PORTABILITY. With no desk state (CI, a fresh clone, the build box) the feeders are absent, every
link reads UNMEASURED and this exits 0 with the reason published: a gate that cries wolf on every
PR is a gate that gets switched off (L1.43). `--require-state` is the box half, where the state
exists and the verdict is real.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import organ_census as oc  # noqa: E402

OUT = ROOT / "desks" / "mt5" / "reports" / "ORGAN_CENSUS.json"
DEBT = ROOT / "docs" / "research" / "organ_census_debt.json"


def load_debt(path: Path | None = None) -> dict[str, Any]:
    """Today's measured residue, declared BY NAME and allowed to shrink only.

    A fence shipped against a clean tree is a fence that passes forever; one shipped red on a
    backlog nobody in the session created is forced off within a day (L1.43). So the residue is
    named here, the ratchet points down, and tomorrow's nineteenth silent stop fails on the day
    it appears.
    """
    try:
        doc = json.loads(Path(path or DEBT).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def previous(path: Path | None = None) -> dict[str, Any] | None:
    """The last census this box wrote. The silent-stop comparison needs no new state path: the
    artifact IS the state, so the check bootstraps itself and reports UNMEASURED on its first run
    rather than inventing a baseline."""
    try:
        doc = json.loads(Path(path or OUT).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def scan(*, root: Path | None = None, require_state: bool = False,
         prev: dict[str, Any] | None = None,
         debt: dict[str, Any] | None = None) -> dict[str, Any]:
    base = root or ROOT
    before = previous() if prev is None else prev
    doc = oc.census(root=base)
    doc["previous_at"] = (before or {}).get("at")
    rules = load_debt() if debt is None else debt
    missing = list(doc.get("feeders_missing") or ())
    problems: list[str] = []
    notes: list[str] = []

    if missing and len(missing) >= 3:
        notes.append(f"{len(missing)} of the census's rosters are absent on this host "
                     f"({missing[:5]}), so most links read UNMEASURED. That is a fact about this "
                     f"checkout, not about the organs")
        if not require_state:
            doc["verdict"] = "UNMEASURED"
            doc["ok"] = True
            doc["problems"], doc["notes"] = problems, notes
            return doc
        problems.append(f"--require-state was asked for and {len(missing)} roster(s) are absent: "
                        f"{missing[:5]}. A census that cannot read its own inputs is not a pass")
    if doc.get("mirror_host"):
        notes.append("this checkout holds none of the desk's clocks, so it judges nobody: an old "
                     "artifact here is a stale git mirror, not a dark organ")
    if before is None:
        notes.append("no previous census exists on this host, so SILENT STOP is UNMEASURED this "
                     "pass -- the comparison begins with the next one")

    problems += oc.breach(doc, previous=before, debt=rules)
    doc["silent_stops"] = oc.silent_stops(doc, before)
    doc["debt"] = {"silent_stops": list(rules.get("silent_stops") or ()),
                   "max_ambiguous_code_paths": rules.get("max_ambiguous_code_paths")}
    doc["ok"] = not problems
    doc["verdict"] = "OK" if not problems else "BROKEN_CHAIN"
    doc["problems"], doc["notes"] = problems, notes
    return doc


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str, sort_keys=False) + "\n",
                    encoding="utf-8")
    return path


def _headline(doc: dict[str, Any]) -> list[str]:
    t = doc.get("totals") or {}
    rec = doc.get("reconciliation") or {}
    led = doc.get("yield_ledger") or {}
    return [
        f"organs claimed {t.get('organs_claimed')} "
        f"(from {rec.get('claims_read')} claims across "
        f"{len(rec.get('claims_by_roster') or {})} rosters; "
        f"{rec.get('organs_seen_by_one_roster_only')} seen by ONE roster only; "
        f"{rec.get('organs_in_all_three_censuses')} in all three censuses)",
        f"  real code           {t.get('real_code')}",
        f"  clocked             {t.get('clocked')}",
        f"  fresh real input    {t.get('fresh_real_input')}",
        f"  producing           {t.get('producing')}",
        f"  reaching pipeline   {t.get('reaching_pipeline')}",
        f"  measured yield      {t.get('with_measured_yield')}",
        f"  allocation by yield {t.get('allocation_follows_yield')}",
        f"  clocked and not producing: {doc.get('n_clocked_but_not_producing')}",
        f"  writes only receipts (runs, writes, donates nothing): "
        f"{doc.get('n_writes_only_receipts')} -- {list(doc.get('writes_only_receipts') or ())[:6]}",
        f"  produces but reaches no pipeline: {doc.get('n_produces_but_reaches_nothing')}",
        f"  yield rows {led.get('n_rows')}, with a measured rate "
        f"{led.get('n_with_measured_rate')}, on the exploration floor "
        f"{led.get('n_unmeasured_on_the_floor')}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--require-state", action="store_true",
                    help="the box half: absent rosters are a failure, not an excuse")
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    args = ap.parse_args(argv)

    doc = scan(require_state=args.require_state)
    if not args.no_write:
        write_artifact(doc)
    if args.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "rows"}, indent=2, default=str))
        return 0

    print(f"organ census: {doc.get('verdict')}")
    for line in _headline(doc):
        print(f"  {line}")
    for note in doc.get("notes") or ():
        print(f"  note: {note}")
    for problem in doc.get("problems") or ():
        print(f"  FAIL: {problem}")
    if args.report_only or doc.get("ok"):
        print("check_organ_census: OK" if doc.get("ok")
              else "check_organ_census: REPORT-ONLY -- problems published, not enforced")
        return 0
    print("check_organ_census: FAILED -- a department stopped producing and did not say so")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
