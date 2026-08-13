#!/usr/bin/env python3
"""CROSS-SECTION FLOOR FENCE -- a per-date collapse over a thin cross-section is noise, not a stat.

WHAT THIS WATCHES. Production code that collapses a (dates x symbols) panel down the SYMBOL axis
-- `mean(axis=1)`, a cross-sectional demean, a rank, a z-score -- to produce one value per date.
On a date carrying one or two finite symbols that value is one symbol's noise, and consecutive
thin dates give the resulting SERIES structure the underlying data never had.

WHAT IT WOULD HAVE CAUGHT, MEASURED. Hunting an unrelated defect on 2026-08-13 the falsifier
reported lag-1 rho = +0.856 on a pooled-IC summand series, which would have deflated that cell's
effective sample 12.9x. It was an artifact: TWELVE of 311 dates carried 98.1% of the lag-1
numerator, and the floored answer is -0.06. A statistic 98% determined by 4% of its input read as
a clean, strong, publishable measurement.

THE NEAR-MISS IS THE REASON THIS FENCE EXISTS, AND IT IS THE DOMINANT PATTERN IN THIS REPO. The
idiom the desk reaches for is `if panel.shape[1] < N`. That counts DECLARED COLUMNS -- the panel's
WIDTH -- and a ragged panel's width is a property of its widest date. A 373-column panel clears
`shape[1] >= 8` on a date where six symbols are finite. The guard READS like a breadth guard, is
DOCUMENTED like one, and checks a number that cannot fall when the cross-section empties. That is
the L1.57 defect -- a denominator counting what the author wrote down rather than what the run
found -- one axis over, and a fence that only looked for "is there a guard" would score every one
of those sites green.

THREE CLASSIFICATIONS, BECAUSE THEY DEMAND DIFFERENT REPAIRS.

  FLOORED      -- a per-date finiteness floor (`notna().sum(axis=1) >= N` or equivalent) governs
                  the collapse. Nothing to do.
  NEAR-MISS    -- the enclosing scope guards `shape[1]`/`len(columns)` and NOTHING per-date. The
                  repair is to add the per-date floor; the existing guard is not wrong, it is
                  answering a different question and reads as though it answered this one.
  UNFLOORED    -- no guard of either kind.

WHY THIS FENCE CANNOT GO RED ON DAY ONE, AND WHY THAT IS DELIBERATE. Roughly half the
cross-sectional collapses in this repo are unguarded. A fence that failed on all of them would be
switched off within a day (L1.43), and the honest state of legacy code is "not yet floored", not
"broken". So coverage is a RATCHET whose gap is the work queue (L1.0): PARTIAL exits 0. Only two
things FAIL -- a REGRESSION below the recorded floor, and UNMEASURED.

UNMEASURED IS A REAL ANSWER AND IT IS NOT `OK` (L1.28a). A run that finds zero collapse sites has
not verified anything; it has failed to scope itself, and it says so rather than passing. This is
WS-005, the desk's most-repeated defect class, and a fence about denominators must not commit it.

EVERY SKIPPED FILE IS COUNTED (L1.60). A file that fails to parse stays in the denominator as
`n_unreadable` rather than vanishing from it -- otherwise a fence that stopped being able to read
the repo would report improving coverage as it went blind.

ANTI-TIMIDITY READING (L1.28, required of every restraint clause). A MEASUREMENT duty and a SCOPE
EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens no gate, loosens no statistical
bar, and has no vocabulary for turning a failing verdict into a passing one. Its whole effect is to
make "this statistic rests on a measured cross-section" distinguishable from "this statistic rests
on a guard that counted the wrong thing" -- byte-identical on this desk until now, and only one of
them is evidence.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard  # noqa: E402

_OUT = ROOT / "data/cross_section_floor.json"
_FLOOR = ROOT / "docs/research/CROSS_SECTION_FLOOR_RATCHET.json"
_PASSING = ("MEASURED", "PARTIAL")

# The collapse operations that produce a PER-DATE STATISTIC. `sum(axis=1)` is deliberately out of
# scope: in this repo it is overwhelmingly weight normalisation (`w / w.abs().sum(axis=1)`), which
# is scale-invariant and unharmed by a thin row. Scoping decisions are DECLARED, never silent --
# a reader can see exactly what this fence does and does not look at.
_COLLAPSE = frozenset({"mean", "median", "std", "var", "rank", "nanmean", "nanmedian",
                       "nanstd", "nanvar", "quantile", "nlargest", "nsmallest"})

# A per-date finiteness floor: something that COUNTS finite values along axis=1 and compares it,
# or a call to the desk's shared instrument. The instrument is listed FIRST because a fence that
# does not recognise the correct fix punishes the code that adopted it.
_PER_DATE_FLOOR = (
    "measure_cross_section", "apply_floor", "cross_section_floor",
    "notna().sum(axis=1)", "notnull().sum(axis=1)", "isfinite", "count(axis=1)",
    "ok.sum(axis=1)", "valid.sum(axis=1)", "present.sum(axis=1)", "m.sum(axis=1)",
)
# The near-miss: a guard on the panel's DECLARED width.
_WIDTH_GUARD = ("shape[1]", "len(universe)", "len(members)", "len(peers)", "len(common)",
                "len(columns)", "len(syms)", "len(symbols)")

_SCOPE = ("libs", "scripts")
_SKIP_DIRS = frozenset({"tests", "test", ".venv", "node_modules", "__pycache__", "backups"})


def _enclosing(tree: ast.AST) -> dict[int, ast.AST]:
    """Map every line to the innermost function/module scope containing it."""
    out: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            lo = getattr(node, "lineno", 1)
            hi = getattr(node, "end_lineno", None) or lo
            for ln in range(lo, hi + 1):
                prev = out.get(ln)
                if prev is None or getattr(prev, "lineno", 0) <= lo:
                    out[ln] = node
    return out


def _is_axis1(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "axis" and isinstance(kw.value, ast.Constant) and kw.value.value == 1:
            return True
    return False


def _collapse_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr in _COLLAPSE:
        return f.attr
    if isinstance(f, ast.Name) and f.id in _COLLAPSE:
        return f.id
    return None


def _scope_code(scope: ast.AST) -> str:
    """The scope's CODE, with comments and docstrings removed.

    MATCHING RAW SOURCE IS A DEFECT, AND THIS FENCE COMMITTED IT ON ITS FIRST RUN. The repair to
    `run_derivative_shadow` was scored FLOORED because the COMMENT explaining the fix contained
    the string `notna().sum(axis=1)` -- prose about a guard read as the guard. A fence that can be
    satisfied by describing the fix is worse than no fence, because it certifies exactly the files
    whose authors thought hardest about the problem and then did nothing.

    `ast.unparse` drops comments entirely; docstrings survive as string constants and are stripped
    explicitly. What is left is code, which is the only thing that runs.
    """
    try:
        clone = ast.parse(ast.unparse(scope))
    except (ValueError, SyntaxError, RecursionError, AttributeError):
        return ""
    for node in ast.walk(clone):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                body.pop(0)
    try:
        return ast.unparse(clone)
    except (ValueError, RecursionError):
        return ""


def analyse(path: Path, src: str) -> list[dict[str, Any]]:
    tree = ast.parse(src)
    lines = src.splitlines()
    scopes = _enclosing(tree)
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_axis1(node):
            continue
        name = _collapse_name(node)
        if name is None:
            continue
        scope = scopes.get(node.lineno)
        text = _scope_code(scope) if scope is not None else ""
        floored = any(tok in text for tok in _PER_DATE_FLOOR)
        width = any(tok in text for tok in _WIDTH_GUARD)
        cls = "FLOORED" if floored else ("NEAR-MISS" if width else "UNFLOORED")
        rows.append({
            "file": str(path.relative_to(ROOT)), "line": node.lineno, "op": name,
            "scope": getattr(scope, "name", "<module>"), "classification": cls,
            "expr": lines[node.lineno - 1].strip()[:120],
        })
    return rows


def build() -> dict[str, Any]:
    files: list[Path] = []
    for top in _SCOPE:
        for p in sorted((ROOT / top).rglob("*.py")):
            if _SKIP_DIRS & set(p.relative_to(ROOT).parts):
                continue
            files.append(p)

    rows: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for p in files:
        try:
            rows.extend(analyse(p, p.read_text("utf-8")))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            # COUNTED, never silently skipped (L1.60): a fence going blind must not read as a
            # fence finding nothing wrong.
            unreadable.append(f"{p.relative_to(ROOT)}: {type(exc).__name__}")

    n_floored = sum(1 for r in rows if r["classification"] == "FLOORED")
    n_near = sum(1 for r in rows if r["classification"] == "NEAR-MISS")
    n_unfloored = sum(1 for r in rows if r["classification"] == "UNFLOORED")
    n_sites = len(rows)
    coverage = (n_floored / n_sites) if n_sites else None

    prev = {}
    try:
        prev = json.loads(_FLOOR.read_text("utf-8"))
    except (OSError, ValueError):
        prev = {}
    floor_floored = int(prev.get("n_floored", 0))

    if not n_sites:
        status = "UNMEASURED"
        why = ("no per-date cross-sectional collapse found anywhere in libs/ or scripts/ -- this "
               "fence failed to scope itself and has verified nothing")
    elif n_floored < floor_floored:
        status = "REGRESSED"
        why = (f"floored collapse sites fell from {floor_floored} to {n_floored}: a guard was "
               f"removed, and coverage floors only ratchet UP (L1.0/L1.50)")
    elif n_unfloored or n_near:
        status = "PARTIAL"
        why = (f"{n_floored}/{n_sites} collapse sites floored; {n_near} guard panel WIDTH only "
               f"(the near-miss: shape[1] cannot fall when a date's cross-section empties), "
               f"{n_unfloored} unguarded. Coverage is a ratchet and the gap is the work queue")
    else:
        status = "MEASURED"
        why = f"all {n_sites} per-date collapse sites carry a per-date finiteness floor"

    worst = sorted((r for r in rows if r["classification"] != "FLOORED"),
                   key=lambda r: (r["classification"] != "NEAR-MISS", r["file"], r["line"]))
    return {
        "law": "L1.62-family (cross-section floor); see libs/research/cross_section_floor.py",
        "status": status, "why": why,
        "n_sites": n_sites, "n_floored": n_floored, "n_near_miss": n_near,
        "n_unfloored": n_unfloored,
        "coverage": round(coverage, 4) if coverage is not None else None,
        "n_files_examined": len(files), "n_unreadable": len(unreadable),
        "unreadable": unreadable[:16],
        "recorded_floor": floor_floored,
        "sites": rows,
        "worst": worst[:24],
        "next_action": (
            "add a per-date floor via libs.research.cross_section_floor.measure_cross_section at "
            "the NEAR-MISS sites first -- those already look guarded to a reader, so they are the "
            "ones a future session will trust without checking"),
    }


def main() -> int:
    guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--bless", action="store_true",
                    help="record the current floored count as the ratchet floor")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.bless and rep["status"] != "UNMEASURED":
        _FLOOR.parent.mkdir(parents=True, exist_ok=True)
        _FLOOR.write_text(json.dumps(
            {"n_floored": rep["n_floored"], "n_sites": rep["n_sites"],
             "measured_by": "scripts/check_cross_section_floor.py",
             "note": "floors ratchet UP only (L1.0/L1.50); never edit to fit a measurement"},
            indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        cov = "n/a" if rep["coverage"] is None else f"{rep['coverage']:.1%}"
        print(f"cross-section floor: {rep['status']} -- {rep['n_floored']}/{rep['n_sites']} "
              f"collapse sites floored ({cov}), {rep['n_near_miss']} near-miss, "
              f"{rep['n_unfloored']} unfloored, over {rep['n_files_examined']} files "
              f"[{rep['n_unreadable']} unreadable]")
        print(f"  {rep['why']}")
        for r in rep["worst"][:10]:
            print(f"  {r['classification']:<9s} {r['file']}:{r['line']} "
                  f"({r['scope']}) {r['expr'][:70]}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # L1.57/L1.60: the denominator counts every file HANDED to the scan, including unreadable
    # ones, so this fence cannot shrink its way to a pass.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_files_examined"],
                      of="production python files scanned for per-date cross-sectional collapses",
                      fence="check_cross_section_floor.py")


if __name__ == "__main__":
    raise SystemExit(main())
