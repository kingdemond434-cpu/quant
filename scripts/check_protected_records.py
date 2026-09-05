#!/usr/bin/env python3
"""A protected artifact may not lose RECORDS. Enforced where it is actually attacked: the commit.

THE DEFECT THIS EXISTS TO END (measured 2026-08-29). `ecc14ab0 "desk snapshot 2026-08-29T04:22Z"`
rewrote `docs/GAP_REGISTER.md` with 1 insertion and 813 deletions -- 1718 lines to 906, destroying
87 gap rows (ids 89 and 111-196). Among them were five rows the gap-fixer had closed three hours
earlier and row 194, a PRINCIPAL CONSOLE item carrying a 2026-09-10 deadline. HEAD's version was a
byte-identical PREFIX of the good one, so this was a truncation, not a merge.

THE DESK SAW IT COMING AND WROTE IT DOWN. `libs/ops/protected_artifacts.py` already lists
GAP_REGISTER.md, with the reason: "the ranked open-defect list every session reads to choose work.
Regenerated from a partial cycle it drops rows -- and a gap that vanishes reads exactly like a gap
closed." The prediction was exact. It did not help, because that list had exactly ONE enforcer --
the pytest conftest -- and a snapshot commit written by another box never runs pytest. A guard
wired only to the path the attack does not take is a guard in name.

WHY RECORDS AND NOT LINES. A line-count threshold is a heuristic, and heuristics on a shared tree
either eat real edits or are set so loose they miss the real case. These files are LEDGERS, and a
ledger has one invariant worth enforcing: a record that existed must still exist. Rewriting a
row's text is ordinary work and passes; making a row vanish is the failure and does not. Emptying
the file entirely is the degenerate case of the same rule and is called out separately because it
is what a partial regeneration actually produces.

THE OVERRIDE IS DELIBERATE AND VISIBLE. Set ALLOW_PROTECTED_RECORD_LOSS=1 in the environment of
the commit that genuinely retires records. It is one variable, it appears in shell history, and
it forces the decision to be made by someone rather than inherited from a default.

    git diff --cached  ->  this only ever inspects what is ABOUT to be committed.

Usage:
    python scripts/check_protected_records.py            # pre-commit: staged vs HEAD
    python scripts/check_protected_records.py --range A B # audit two arbitrary commits
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDE = "ALLOW_PROTECTED_RECORD_LOSS"

#: `| 197 | **Gap title** | ...` -- the GAP_REGISTER row shape.
_MD_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
#: Keys a record-shaped payload uses for its identity, most specific first.
_ID_KEYS = ("id", "rowid", "row_id", "name", "slug", "key")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       check=False, timeout=120)
    return r.stdout


def _protected() -> dict[str, str]:
    """The one list, imported rather than restated (promotion rule: import the number)."""
    sys.path.insert(0, str(ROOT))
    from libs.ops.protected_artifacts import PROTECTED
    return {k: (v[0] if isinstance(v, tuple) else str(v)) for k, v in PROTECTED.items()}


def _ident(obj: object, fallback: str) -> str:
    if isinstance(obj, dict):
        for k in _ID_KEYS:
            if k in obj:
                return f"{k}={obj[k]!r}"
    return fallback


def records(rel: str, text: str) -> set[str]:
    """Identity of every record in this payload, or an empty set when the shape is unknown.

    AN UNKNOWN SHAPE YIELDS NO RECORDS, so an unrecognised file is governed only by the
    empty-file rule. That is the honest direction: inventing record identities for a format this
    function cannot read would fabricate both the losses and the passes.
    """
    if not text.strip():
        return set()
    if rel.endswith(".md"):
        return {m.group(1) for line in text.splitlines() if (m := _MD_ROW.match(line))}
    if rel.endswith(".jsonl"):
        out: set[str] = set()
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                out.add(_ident(json.loads(line), f"line{i}"))
            except json.JSONDecodeError:
                continue
        return out
    if rel.endswith(".json"):
        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            return set()
        if isinstance(d, dict):
            # A REGISTRY LOSES FIELDS, NOT KEYS. If every value is itself a record, the identity
            # that matters is key.FIELD -- otherwise a commit that strips one column from all 251
            # rows passes with every key intact. Measured 2026-08-29: the same snapshot commit
            # that deleted 87 gap rows also dropped `currency_profit` from all 251 symbols in
            # desks/mt5/data/universe/universe.json. It is MetaTrader5's own answer to "what
            # currency is this denominated in", the only correct route for a share or index CFD
            # whose name carries no denomination, and this desk has already paid once for a cost
            # field silently vanishing from this exact file (tick_value: 0/197 costable and a
            # 184x JPY commission undercharge).
            vals = list(d.values())
            if vals and all(isinstance(v, dict) for v in vals):
                return {f"{k}.{f}" for k, v in d.items() for f in v}
            return set(map(str, d))
        if isinstance(d, list):
            return {_ident(x, f"idx{i}") for i, x in enumerate(d)}
    return set()


def compare(rel: str, before: str, after: str) -> dict[str, object] | None:
    """None when nothing was lost; otherwise the finding, with the lost ids NAMED."""
    if before.strip() and not after.strip():
        return {"file": rel, "kind": "EMPTIED", "lost": [],
                "detail": f"{len(before.splitlines())} lines -> 0"}
    lost = sorted(records(rel, before) - records(rel, after),
                  key=lambda s: (len(s), s))
    if lost:
        return {"file": rel, "kind": "RECORDS_LOST", "lost": lost,
                "detail": f"{len(lost)} record(s) present in the old version and absent from the "
                          f"new one"}
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--range", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="audit two commits instead of staged-vs-HEAD")
    args = ap.parse_args(argv)

    prot = _protected()
    findings: list[dict[str, object]] = []
    for rel in sorted(prot):
        if args.range:
            before = _git("show", f"{args.range[0]}:{rel}")
            after = _git("show", f"{args.range[1]}:{rel}")
        else:
            staged = _git("diff", "--cached", "--name-only")
            if rel not in staged.split():
                continue
            before = _git("show", f"HEAD:{rel}")
            after = _git("show", f":{rel}")          # the staged blob, not the working tree
        if not before.strip():
            continue                                  # nothing to lose
        finding = compare(rel, before, after)
        if finding:
            findings.append(finding)

    if not findings:
        print(f"protected records: OK over {len(prot)} guarded artifact(s)")
        return 0
    for f in findings:
        print(f"  {f['kind']:<14} {f['file']} -- {f['detail']}")
        lost = [str(x) for x in f["lost"]]
        if lost:
            # HEAD **AND** TAIL. Truncating to the first N hides exactly the records a session
            # just wrote -- the newest ids, the ones no other copy holds yet. Caught by this
            # guard's own test: the first cut named 20 of 87 lost rows and buried row 194, the
            # principal-console item with a deadline, in a "+67 more".
            if len(lost) <= 24:
                body = ", ".join(lost)
            else:
                body = (", ".join(lost[:12]) + f" ... +{len(lost) - 24} more ... "
                        + ", ".join(lost[-12:]))
            print(f"                 lost: {body}")
    if os.environ.get(OVERRIDE) == "1":
        print(f"  {OVERRIDE}=1 -- allowed, and recorded in this output. Say in the commit "
              "message WHICH records are being retired and why.")
        return 0
    print(f"\n  A protected artifact may not lose records. These files are ledgers, and a record "
          f"that vanishes reads exactly like a record resolved.\n"
          f"  If this retirement is deliberate, re-run with {OVERRIDE}=1 and name the records in "
          f"the commit message.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
