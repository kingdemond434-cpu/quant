#!/usr/bin/env python3
"""PROMPT RATCHET CHECK -- a prompt may be sharpened; it may never be quietly disarmed.

Every governed prompt on this desk is compared against docs/research/PROMPT_RATCHET.json, the
high-water mark of which LOAD-BEARING RULES each prompt asserts. Three outcomes, and the asymmetry
between them is the entire mechanism:

  UNCHANGED   silent, exit 0. Rewrite the prose however you like -- shorter, sharper, translated,
              merged into a neighbouring paragraph. As long as the rule is still asserted, this
              check has nothing to say, which is what makes it safe to leave in the cron plane.
  ADDED       the mark RISES automatically and the file is rewritten. No ceremony, no flag, no
              approval: a prompt that gains a rule should never have to argue for it.
  DROPPED     exit 1, naming the prompt, the invariant, why it mattered, and THE WORDS THAT USED
              TO CARRY IT. Nothing is written -- a failing run must never quietly re-baseline the
              mark it just failed against.

THE ESCAPE HATCH, because a rule can become genuinely wrong. The scam pre-filter was struck from
every miner prompt on 2026-08-01 and that was a real improvement. So an invariant CAN be retired --
by a dated, signed, argued entry in docs/research/PROMPT_RATCHET_WAIVERS.json, and by nothing else.
Editing the prompt's prose retires nothing; it just fails this check. That is the point: the cost
of removing a rule is one reviewable line in a git-tracked file, and the cost of removing it by
accident is a red gate.

WHAT THIS PROVES AND WHAT IT DOES NOT. It proves NON-REGRESSION: no prompt silently stopped saying
something it used to say. It does NOT prove a rewrite is SHARPER -- that is a claim about the
organ's measured output, not about its text. libs/doctrine/prompt_ratchet.py states the limit and
names the desk's own outcome artifacts as the only honest proxy. Read it before citing this check
as evidence that a prompt improved.

    python3 scripts/check_prompt_ratchet.py [--check-only] [--json] [--verbose]

Exit: 1 on a dropped invariant (the regression this exists to catch); 2 when the ratchet itself
cannot be trusted (an unreadable or malformed waiver file -- fail-closed, never fail-open);
0 clean. stdlib-only apart from the desk's own module.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.prompt_ratchet import (  # noqa: E402
    INVARIANTS,
    RECORD_PATH,
    WAIVER_PATH,
    check,
    load_record,
    load_waivers,
    scan,
    update_high_water,
)

_JSON_REL = "data/prompt_ratchet_report.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-only", action="store_true",
                    help="never write the record, even to RAISE it (for CI and for tests)")
    ap.add_argument("--json", action="store_true",
                    help=f"also write {_JSON_REL} (best-effort; a reporting failure never masks "
                         "a ratchet verdict)")
    ap.add_argument("--verbose", action="store_true",
                    help="print per-prompt invariant counts even when everything is fine")
    a = ap.parse_args()

    cur = scan(ROOT)
    base = load_record(ROOT / RECORD_PATH)
    wv, bad_waivers = load_waivers(ROOT / WAIVER_PATH)
    rep = check(current=cur, baseline=base, waivers=wv, root=ROOT)

    slots = sum(len(v) for v in cur.values())
    print(f"prompt-ratchet: {len(cur)} governed prompts, {slots} invariant assertions across "
          f"{len(INVARIANTS)} defined invariants (mark: {len(base)} prompts, "
          f"{sum(len(v) for v in base.values())} assertions)")

    if a.verbose:
        width = max((len(k) for k in cur), default=1)
        for rel in sorted(cur):
            was = len(base.get(rel, {}))
            delta = len(cur[rel]) - was
            mark = "" if delta == 0 else (f"  (+{delta})" if delta > 0 else f"  ({delta})")
            print(f"    {rel:<{width}}  {len(cur[rel]):2d}{mark}")

    for line in rep.retired:
        print(f"  RETIRED  {line}")

    for line in bad_waivers:
        print(f"  BAD WAIVER  {line}")

    for line in rep.violations:
        print(f"\n  REGRESSION  {line}")

    wrote = False
    if rep.ok and not bad_waivers and rep.raised and not a.check_only:
        update_high_water(ROOT / RECORD_PATH, current=cur, waivers=wv, root=ROOT)
        wrote = True
        for line in rep.raised:
            print(f"  RAISED   {line}")
        print(f"  mark raised in {RECORD_PATH} -- commit it")
    elif rep.raised:
        for line in rep.raised:
            print(f"  WOULD RAISE  {line}")

    if a.json:
        try:
            out = ROOT / _JSON_REL
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "ok": rep.ok and not bad_waivers,
                "prompts": len(cur),
                "invariant_slots": slots,
                "coverage": rep.counts,
                "violations": rep.violations,
                "raised": rep.raised,
                "retired": rep.retired,
                "bad_waivers": bad_waivers,
                "record_written": wrote,
            }, indent=1) + "\n", "utf-8")
        except OSError as exc:  # a reporting failure must never mask a ratchet truth
            print(f"  (note: could not write {_JSON_REL}: {type(exc).__name__}: {exc})")

    if bad_waivers:
        print("\n  FAIL -- a waiver file that cannot be parsed retires NOTHING and is not "
              "allowed to pass either. Fix the entries above; a typo must never be the cheapest "
              "way to disable a rule.")
        return 2
    if not rep.ok:
        print(f"\n  FAIL -- {len(rep.violations)} invariant(s) LOST. A prompt optimisation that "
              "drops a load-bearing rule is not an optimisation; it is a regression wearing one's "
              "costume, and the cost is paid later by the failure the rule existed to prevent. "
              "Restore the rule (any wording), or retire it deliberately in "
              f"{WAIVER_PATH}.")
        return 1
    if not rep.raised:
        print("  OK -- every prompt still asserts every rule it used to. (Non-regression only: "
              "this cannot tell you a rewrite was SHARPER; see the module docstring.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
