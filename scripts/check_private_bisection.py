#!/usr/bin/env python3
"""FAIL THE BUILD ON A PRIVATE DRAWDOWN BISECTION -- the bug that reads ruin as a passed check.

THE DEFECT THIS FENCES, IN ONE SHAPE

    eq = np.cumprod(1.0 + q * x)
    if (1.0 - eq / np.maximum.accumulate(eq)).max() > target:
        hi = q
    else:
        lo = q

Past the point where some day has `1 + q*x <= 0` the account is not drawn down, it is **GONE**.
From there `cumprod` goes negative, the drawdown expression yields NaN, and `NaN > target`
evaluates to **False** -- so the search concludes the budget was respected and moves q UP. Every
arm of `research/push_ceiling.py` returned q = 2.0000, the hard upper bound, reporting CAGR of
+inf and -100%.

WHY A FENCE AND NOT A CODE REVIEW

`mt5desk/sizing.py` was made the single implementation on 2026-08-19 and its commit named the
latent siblings it knew about. Two more copies -- `research/exit_sweep.py` and
`research/pyramid_sweep.py` -- survived anyway and were found by grep on 2026-08-20, because they
reached the merged tree from MASTER rather than from the branch that did the rewiring. A
same-branch sweep could not have found them, and no gate on either branch would have.

That is the third time this desk has fixed a defect where it was found and left a twin (row 110's
class). The difference between a fix and a fence is that a fix ends one instance and a fence ends
the shape.

WHAT IT LOOKS FOR, AND WHY IT IS SYNTACTIC

A drawdown bisection is recognisable without running it: a function that computes a running
maximum of a cumulative product AND rebinds a `lo`/`hi` pair. Detecting it by AST means the check
costs milliseconds and cannot be defeated by a value that only appears at runtime.

**IT DOES NOT TRY TO DECIDE WHETHER A GIVEN COPY IS SAFE.** A copy that happens to carry a ruin
guard today is still a copy, and the next edit to it is not reviewed against `sizing.py`. The rule
is one implementation, so the finding is "this is a second implementation", not "this one is
buggy". Delegate to `mt5desk.sizing.q_for_drawdown` instead.

    python scripts/check_private_bisection.py [--json]

Exit 0 clean, 1 on any finding. Writes data/private_bisection.json.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "private_bisection.json"

#: The one place a drawdown solver may live. Everything else delegates.
CANONICAL = "desks/mt5/mt5desk/sizing.py"

#: Trees to walk. `scratch/` is excluded for the same reason ruff excludes it -- it is debris,
#: not desk code, and a fence that fires on debris gets switched off.
SEARCH = ("desks/mt5", "libs", "scripts", "app")
SKIP_PARTS = {".git", "__pycache__", "scratch", ".venv", "node_modules"}

#: A running maximum over a cumulative product IS the drawdown computation. Either spelling.
_CUMPROD = {"cumprod", "nancumprod"}
_RUNMAX = {"maximum", "fmax"}


def _names(node: ast.AST) -> set[str]:
    """EVERY attribute and call name under `node`, not just the outermost callee.

    **THE FIRST VERSION OF THIS COLLECTED ONLY CALLEES AND THEREFORE CAUGHT NOTHING.** The
    drawdown idiom is `np.maximum.accumulate(eq)`, where the thing being CALLED is `accumulate`
    and `maximum` is an intermediate attribute. Matching on callees alone missed it, the fence
    scanned 1,362 files, reported a clean tree, and that clean report was worthless -- the exact
    L1.49 shape, a gate that never actually ran passing itself.

    It was caught only because the tests carry the shipped code verbatim as a positive control.
    A fence without one asserts its own correctness.
    """
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def _rebinds_a_bracket(fn: ast.AST) -> bool:
    """Does the function assign to BOTH ends of a search bracket? That is a bisection.

    Both ends, not either: a single `hi = ...` is an ordinary bound, while rebinding `lo` and `hi`
    in the same function is the search itself. Names are matched loosely (`lo`/`low`/`q_lo`) so a
    rename does not slip past.
    """
    lo = hi = False
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    s = t.id.lower()
                    lo = lo or s in {"lo", "low", "q_lo", "qlo", "left"}
                    hi = hi or s in {"hi", "high", "q_hi", "qhi", "right"}
    return lo and hi


def scan(path: Path) -> list[dict]:
    """Findings in one file. A syntax error is reported, never skipped."""
    try:
        # utf-8-SIG, not utf-8: the MT5 desk is edited on Windows and several files carry a BOM
        # (`_sum6.py`, `GATEWAY_PAUSED`). `ast.parse` chokes on U+FEFF while the interpreter
        # itself strips it, so a plain utf-8 read makes this fence report a defect in a file that
        # runs perfectly. A fence that cries wolf on encoding gets switched off, and then it is
        # not there for the bug it exists to catch.
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [{"file": str(path.relative_to(ROOT)), "line": getattr(exc, "lineno", 0) or 0,
                 "function": "<unparseable>", "why": f"cannot parse: {exc}"}]
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = _names(node)
        if not (calls & _CUMPROD and calls & _RUNMAX):
            continue
        if not _rebinds_a_bracket(node):
            continue
        found.append({
            "file": str(path.relative_to(ROOT)), "line": node.lineno,
            "function": node.name,
            "why": ("a private drawdown bisection: it runs a cumulative product under a running "
                    "maximum and rebinds a lo/hi bracket. Past ruin the drawdown is NaN, "
                    "`NaN > target` is False, and the search sizes UP. Delegate to "
                    "mt5desk.sizing.q_for_drawdown -- one implementation, guarded once.")})
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact instead of a report")
    args = ap.parse_args()

    canonical = ROOT / CANONICAL
    findings: list[dict] = []
    scanned = 0
    for tree_name in SEARCH:
        base = ROOT / tree_name
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if SKIP_PARTS & set(p.parts) or p == canonical:
                continue
            scanned += 1
            findings.extend(scan(p))

    art = {
        "canonical": CANONICAL,
        "canonical_present": canonical.is_file(),
        "files_scanned": scanned,
        "findings": findings,
        "state": "OK" if not findings else "PRIVATE-BISECTION",
    }
    if not canonical.is_file():
        # The fence cannot say "delegate to sizing.py" if sizing.py is gone. Absence of the
        # canonical implementation is itself the finding (L1.28a) -- not a clean pass.
        art["state"] = "CANONICAL-ABSENT"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1), encoding="utf-8")

    if args.json:
        print(json.dumps(art, indent=1))
    else:
        print(f"private bisection fence: {art['state']}")
        print(f"  {scanned} files scanned, canonical = {CANONICAL}"
              f"{'' if art['canonical_present'] else '  *** ABSENT ***'}")
        for f in findings:
            print(f"  {f['file']}:{f['line']}  {f['function']}()")
            print(f"      {f['why']}")
        if not findings and art["canonical_present"]:
            print("  no second implementation found")
        print(f"-> {OUT}")
    return 0 if art["state"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
