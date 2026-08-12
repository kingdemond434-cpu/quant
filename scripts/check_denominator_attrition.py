#!/usr/bin/env python3
"""DENOMINATOR ATTRITION FENCE (L1.60) -- the count exists; does it count what it claims?

L1.57 asked whether a fence declared a denominator and whether that number was >= 1. This asks
the question one level in, which is the one that moves a verdict: how many things did the run
LOSE on the way to that number, and can a reader tell? A fence that walks 1000 files, drops 991
in an ``except OSError: continue``, and declares ``scanned=9`` is recorded by L1.57 as DECLARED,
non-vacuous and CLEAN. Nine is an int >= 1. The number is honest about what it counted and
silent about what it lost, and silence reads as coverage.

THE PROVING INSTANCE IS L1.57'S OWN SUPPLIER: ``check_calendar_gates.py`` publishes
``scanned=N_SCANNED`` from an ``n += 1`` that sits one line below its ``except ...: continue``.
The denominator built to reveal a hollow verdict was itself hollowed by the same mechanism.

THE RULE IS ONE RULE WITH ONE REPAIR: a loop producing a scope denominator must publish how many
iterations it ATTEMPTED. Skipping is fine and often correct; skipping INVISIBLY is not, because
it makes "out of scope" and "could not be read" byte-identical to every reader, and only one of
those is a defect. Where a skip records its own discard -- ``malformed += 1; continue``, the
practice L2.4 already names and ``check_funding_capture`` already follows -- this fence is
silent by design.

THE VERDICTS:
  OK         (exit 0) -- every governed file parsed; no uncounted attrition on a scope count.
  PARTIAL    (exit 0) -- no attrition found, but some governed file could not be parsed or read.
                         Reported, never hidden: those files are in the denominator as UNPARSED,
                         and the gap is a work queue rather than a cliff (L1.0/L1.43).
  ATTRITION  (exit 2) -- a scope denominator can be skipped with the skip counted nowhere.
  UNMEASURED (exit 2) -- no governed file discovered, or not one of them parsed. This fence is
                         SUBJECT TO ITS OWN LAW: it declares ``scanned=n_examined``, so a scope
                         discovery that returns nothing refuses its own pass rather than
                         printing a clean board (L1.28a).

ANTI-TIMIDITY READING (L1.28): a MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes
nothing, loosens no bar, and forbids no skip -- it requires only that skips be counted, which
strictly increases what the desk can see. Every error it catches points the same way: toward a
fence looking better covered than it was.

    python scripts/check_denominator_attrition.py [--scope fences|scripts|repo] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.attrition import analyse_paths, summarise  # noqa: E402
from libs.ops.denominator import governed_fences  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data" / "denominator_attrition.json"
_PASSING = frozenset({"OK", "PARTIAL"})

#: Directories whose contents are not desk-authored decision code.
#: ``.claude`` holds sibling git WORKTREES -- scanning them reports another checkout's copy of a
#: file as a finding in this one, which is duplication masquerading as scale.
_SKIP_PARTS = {".venv", "node_modules", "__pycache__", ".git", "build", "dist", "data", ".claude"}


def scope_paths(scope: str, root: Path | None = None) -> list[Path]:
    """The files to examine. DISCOVERED, never enumerated -- a hardcoded roster inside a fence
    about hardcoded denominators would be the defect it detects (the L1.57 substrate argument).

    ``fences`` reuses ``libs.ops.denominator.governed_fences`` verbatim rather than re-deriving
    it, so this law and L1.57 can never disagree about which fences exist.
    """
    r = root or _ROOT
    if scope == "fences":
        return [r / "scripts" / n for n in governed_fences(r)]
    if scope == "scripts":
        return sorted((r / "scripts").glob("*.py"))
    return sorted(p for p in r.rglob("*.py")
                  if not (_SKIP_PARTS & set(p.relative_to(r).parts)))


def build(scope: str = "fences", root: Path | None = None) -> dict[str, Any]:
    r = root or _ROOT
    paths = scope_paths(scope, r)
    s = summarise(analyse_paths(paths, r))

    if s["n_examined"] == 0 or s["n_parsed"] == 0:
        status = "UNMEASURED"
        why = ("no governed file discovered" if s["n_examined"] == 0 else
               f"{s['n_examined']} file(s) discovered, NOT ONE parsed -- no attrition on this "
               "desk is currently detectable")
        nxt = "repair scope discovery in libs.ops.denominator.governed_fences"
    elif s["n_findings"]:
        status = "ATTRITION"
        first = s["findings"][0]
        why = (f"{s['n_findings']} scope denominator(s) can be skipped with the skip counted "
               f"nowhere ({s['n_from_handler']} from a caught exception); e.g. {first['path']} "
               f"counter `{first['counter']}` at L{first['counter_line']}, skipped at "
               f"L{first['skip_lines'][0]}")
        nxt = ("count the attempt before the first skip in each loop below, and publish it "
               "beside the count -- see libs/research/extractor_invariants.py for the shape")
    elif s["n_unparsed"]:
        status = "PARTIAL"
        why = (f"no attrition in {s['n_parsed']} parsed file(s); {s['n_unparsed']} could not be "
               "read or parsed and are counted as UNPARSED, not dropped")
        nxt = f"restore: {', '.join(u['path'] for u in s['unparsed'][:5])}"
    else:
        status = "OK"
        why = (f"all {s['n_parsed']} governed file(s) parsed; every scope denominator either "
               f"has no skip before it or counts its discards ({s['n_exempt']} tagged exempt)")
        nxt = "none"

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.60 -- a denominator that silently loses its members is a coverage claim the "
               "desk cannot cash; every skip on the path to a scope count is counted. "
               "Second half of L1.57, enforcement for L2.4.",
        "status": status,
        "scope": scope,
        **{k: s[k] for k in ("n_examined", "n_parsed", "n_unparsed", "n_findings",
                             "n_from_handler", "n_exempt")},
        "findings": s["findings"],
        "exempt": s["exempt"],
        "unparsed": s["unparsed"],
        "detail": why,
        "next_action": nxt,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scope", choices=("fences", "scripts", "repo"), default="fences",
                    help="what to examine (default: the L1.57 governed fence set)")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build(args.scope)
    if args.scope == "fences":          # only the governed scope owns the artifact
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"denominator attrition (L1.60): {rep['status']} -- {rep['n_findings']} leaking "
              f"denominator(s) over {rep['n_examined']} file(s) [{rep['scope']}], "
              f"{rep['n_unparsed']} unparsed, {rep['n_exempt']} exempt")
        for f in rep["findings"]:
            src = "except" if f["from_handler"] else "guard"
            print(f"  ATTRITION  {f['path']}:{f['counter_line']} `{f['counter']}` -- skipped by "
                  f"{src} at L{', L'.join(str(x) for x in f['skip_lines'])}")
        for e in rep["exempt"]:
            print(f"  exempt     {e['path']}:{e['counter_line']} `{e['counter']}` "
                  f"-- {e['exempt_reason']}")
        for u in rep["unparsed"]:
            print(f"  UNPARSED   {u['path']}: {u['error']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to its own law: n_examined counts every path handed to the analyser, including the
    # ones that could not be read, so this fence cannot shrink its way to a pass.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_examined"],
                      of=f"{args.scope} python modules", fence="check_denominator_attrition.py")


if __name__ == "__main__":
    raise SystemExit(main())
