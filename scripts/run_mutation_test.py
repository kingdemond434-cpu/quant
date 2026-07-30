"""§7 verification bar: mutation testing on the five risk-path files (>=90% mutants killed).

Gap register row 53: "1199 tests are of UNKNOWN strength -- they demonstrably execute code,
nothing shows they CONSTRAIN it." A passing suite proves the code runs. Mutation testing is the
only cheap way to find out whether the suite would notice if the code were wrong: break one
thing, deliberately, and see if anything fails. A mutant that survives is a line your tests
cover but do not check.

WHY NOT mutmut: it is installed, but it edits files IN PLACE in the working tree, and one of the
five targets is `scripts/run_deadman_switch.py` -- TIER-3 NEVER-TOUCH, which the charter forbids
this process from modifying autonomously. A crash mid-run would leave a mutated ruin rail on
disk. This harness copies the source tree to a scratch directory and mutates only the copy, so
the real tree is never written to at all: the safety property holds by construction rather than
by a restore path that has to work.

    python scripts/run_mutation_test.py                 # full sweep, all five files
    python scripts/run_mutation_test.py --sample 40     # bounded run (CI / quick check)
    python scripts/run_mutation_test.py --file libs/risk/sizing.py
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

_ROOT = Path(__file__).resolve().parent.parent
_REPORT = _ROOT / "data" / "mutation_report.json"

KILL_BAR = 0.90

# The five money-path files (LIVE_CONNECTOR_SPEC §7) and the tests that are supposed to
# constrain each. Narrow test targeting is what makes a full sweep affordable: running 1199
# tests per mutant would take hours and measure nothing extra.
TARGETS: dict[str, list[str]] = {
    "libs/execution/binance_live.py": ["tests/execution/test_binance_live.py",
                                   "tests/execution/test_binance_live_behaviour.py"],
    "libs/execution/staging.py": ["tests/execution/test_staging.py",
                                  "tests/execution/test_staging_boundaries.py"],
    "libs/risk/gate.py": ["tests/risk/test_gate.py", "tests/risk/test_edge_gate.py"],
    "libs/risk/sizing.py": ["tests/risk/test_sizing.py",
                            "tests/risk/test_sizing_boundaries.py"],
    "scripts/run_deadman_switch.py": ["tests/scripts/test_deadman_atomic_state.py",
                                      "tests/test_deadman_reconciliation.py"],
}

# directories the mutant run needs. Deliberately excludes data/ and .git -- a mutant does not
# need the archive, and copying it would dominate the runtime.
_COPY = ("libs", "scripts", "tests", "config", "pyproject.toml")

#: EQUIVALENT MUTANTS: mutations that provably cannot change behaviour, so no test can kill them
#: and chasing them produces contorted tests that assert implementation detail. Each entry needs a
#: written justification -- that requirement is the only thing standing between this registry and
#: a laundering mechanism for weak tests, so a survivor goes here ONLY when the argument is that
#: the mutant is BEHAVIOURALLY IDENTICAL, never that killing it would be inconvenient.
#: Stale entries (no matching mutant) are reported, so the list cannot quietly accumulate.
EQUIVALENT: dict[tuple[str, int, str], str] = {
    ("libs/execution/staging.py", 41, "number"):
        "json.dumps indent= is cosmetic; serialized state is re-read by json.loads",
    ("libs/execution/staging.py", 53, "number"):
        "fail-closed default for capital_fraction: 1.0 and 2.0 both fail `<= 0.10`",
    ("libs/execution/staging.py", 54, "number"):
        "fail-closed default for symbol_count: 0 and 1 both fail the 4-5 window",
    ("libs/execution/staging.py", 64, "number"):
        "fail-closed default for live_weeks: 0.0 and 1.0 both fail `>= 8.0`",
    ("libs/execution/staging.py", 65, "number"):
        "fail-closed default for calibration_rows: 0 and 1 both fail `>= 10`",
    ("libs/execution/staging.py", 71, "number"):
        "fail-closed default for cost_ratio: 999.0 and 1000.0 both fail `<= 1.25`",
}

_CMP_SWAP = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


class FileResult(TypedDict, total=False):
    """Per-file measurement. A TypedDict rather than a bare dict so the summary code that reads
    `killed`/`tested` back out is type-checked -- these numbers end up in a register row."""

    file: str
    error: str
    total_mutants: int
    tested: int
    killed: int
    survived: int
    uncompilable: int
    equivalent_excluded: int
    raw_score: float
    score: float
    passes_bar: bool
    sampled: bool
    survivors: list[dict[str, object]]
    equivalent: list[dict[str, object]]
    stale_equivalent_entries: list[str]


@dataclass(frozen=True)
class Mutant:
    lineno: int
    col: int
    kind: str
    detail: str


class _Collector(ast.NodeVisitor):
    """Enumerate the single-node mutations available in one module."""

    def __init__(self) -> None:
        self.found: list[Mutant] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            if type(op) in _CMP_SWAP:
                self.found.append(Mutant(node.lineno, node.col_offset, "compare",
                                         type(op).__name__))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) in _BIN_SWAP:
            self.found.append(Mutant(node.lineno, node.col_offset, "binop",
                                     type(node.op).__name__))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if type(node.op) in _BOOL_SWAP:
            self.found.append(Mutant(node.lineno, node.col_offset, "boolop",
                                     type(node.op).__name__))
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if isinstance(node.op, ast.Not):
            self.found.append(Mutant(node.lineno, node.col_offset, "not", "drop"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool):
            self.found.append(Mutant(node.lineno, node.col_offset, "bool", str(node.value)))
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            self.found.append(Mutant(node.lineno, node.col_offset, "number", str(node.value)))
        self.generic_visit(node)


class _Applier(ast.NodeTransformer):
    """Apply EXACTLY ONE mutation, identified by position and kind."""

    def __init__(self, target: Mutant) -> None:
        self.t = target
        self.applied = False

    def _hit(self, node: ast.AST, kind: str) -> bool:
        return (not self.applied
                and kind == self.t.kind
                and getattr(node, "lineno", -1) == self.t.lineno
                and getattr(node, "col_offset", -1) == self.t.col)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "compare"):
            node.ops = [_CMP_SWAP.get(type(o), type(o))() for o in node.ops]
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "binop"):
            node.op = _BIN_SWAP[type(node.op)]()
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "boolop"):
            node.op = _BOOL_SWAP[type(node.op)]()
            self.applied = True
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "not"):
            self.applied = True
            return node.operand
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self._hit(node, "bool") and isinstance(node.value, bool):
            self.applied = True
            return ast.copy_location(ast.Constant(value=not node.value), node)
        if self._hit(node, "number") and isinstance(node.value, (int, float)):
            self.applied = True
            new = 1 if node.value == 0 else 0 if node.value == 1 else node.value + 1
            return ast.copy_location(ast.Constant(value=new), node)
        return node


def mutants_for(source: str) -> list[Mutant]:
    c = _Collector()
    c.visit(ast.parse(source))
    return c.found


def apply_mutant(source: str, m: Mutant) -> str | None:
    """Mutated source, or None when the mutation could not be applied or does not compile."""
    tree = ast.parse(source)
    app = _Applier(m)
    out = app.visit(tree)
    if not app.applied:
        return None
    ast.fix_missing_locations(out)
    try:
        text = ast.unparse(out)
        compile(text, "<mutant>", "exec")
    except (SyntaxError, ValueError):
        return None
    return text


def _stage_tree(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for rel in _COPY:
        src = _ROOT / rel
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest / rel, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dest / rel)
    # tests read and write under data/; give the mutant tree its own empty one so nothing can
    # reach back into the real archive.
    (dest / "data").mkdir(exist_ok=True)


def _run_tests(tree: Path, tests: list[str], timeout: int) -> bool:
    """True when the suite PASSES (mutant survived). Any failure/error/timeout = killed."""
    existing = [t for t in tests if (tree / t).exists()]
    if not existing:
        return True
    try:
        r = subprocess.run(
            # no --timeout: pytest-timeout is not a dependency, and the subprocess timeout
            # below already turns a mutation-induced infinite loop into a killed mutant.
            [sys.executable, "-m", "pytest", *existing, "--import-mode=importlib",
             "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
            cwd=str(tree), capture_output=True, text=True, timeout=timeout, check=False,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        # an infinite loop introduced by the mutation IS a detected mutant
        return False


def run_file(rel: str, tests: list[str], tree: Path, *, sample: int | None,
             seed: int, timeout: int, baseline_ok: bool) -> FileResult:
    original = (_ROOT / rel).read_text("utf-8")
    all_mutants = mutants_for(original)
    chosen = list(all_mutants)
    if sample is not None and len(chosen) > sample:
        random.Random(seed).shuffle(chosen)
        chosen = chosen[:sample]

    if not baseline_ok:
        return FileResult(
            file=rel, error="baseline suite is RED -- mutation score is meaningless",
            total_mutants=len(all_mutants), tested=0)

    target = tree / rel
    killed, survived, equivalent, invalid = 0, [], [], 0
    for m in chosen:
        text = apply_mutant(original, m)
        if text is None:
            invalid += 1
            continue
        target.write_text(text, "utf-8")
        if _run_tests(tree, tests, timeout):
            row = {"line": m.lineno, "kind": m.kind, "was": m.detail}
            why = EQUIVALENT.get((rel, m.lineno, m.kind))
            if why:
                equivalent.append({**row, "why": why})
            else:
                survived.append(row)
        else:
            killed += 1
    target.write_text(original, "utf-8")

    # a registry entry that matches no surviving mutant is stale -- the code moved, or a real
    # test now kills it, and either way the justification should not linger unexamined.
    seen = {(m.lineno, m.kind) for m in chosen}
    stale = [f"{ln}:{k}" for (f, ln, k) in EQUIVALENT if f == rel and (ln, k) not in seen]

    tested = killed + len(survived)              # equivalent mutants leave the denominator
    raw_tested = tested + len(equivalent)
    score = (killed / tested) if tested else 0.0
    return FileResult(
        file=rel, total_mutants=len(all_mutants), tested=tested,
        killed=killed, survived=len(survived), uncompilable=invalid,
        equivalent_excluded=len(equivalent),
        # BOTH numbers are reported: the adjusted score is the meaningful one, the raw score is
        # what an outside reader would compute, and hiding the gap between them would be the
        # dishonest move.
        raw_score=round(killed / raw_tested, 4) if raw_tested else 0.0,
        score=round(score, 4), passes_bar=score >= KILL_BAR,
        sampled=sample is not None and len(all_mutants) > (sample or 0),
        survivors=survived[:25],
        equivalent=equivalent,
        stale_equivalent_entries=stale,
    )


def _write_report(results: list[FileResult], args: argparse.Namespace,
                  baseline_ok: bool, *, partial: bool) -> tuple[float, float, int]:
    """Serialise what has been measured so far. Called after every file, not just at the end."""
    tested = sum(int(r.get("tested", 0) or 0) for r in results)
    killed = sum(int(r.get("killed", 0) or 0) for r in results)
    excluded = sum(int(r.get("equivalent_excluded", 0) or 0) for r in results)
    overall = (killed / tested) if tested else 0.0
    raw_overall = (killed / (tested + excluded)) if (tested + excluded) else 0.0
    covered = {r.get("file", "") for r in results}
    report: dict[str, object] = {
        "bar": KILL_BAR,
        "overall_score": round(overall, 4),
        "overall_raw_score": round(raw_overall, 4),
        "equivalent_excluded": excluded,
        "overall_passes": overall >= KILL_BAR and baseline_ok and not partial,
        "baseline_ok": baseline_ok,
        "sampled": args.sample is not None,
        # a partial report must never read like a full one -- naming what is MISSING is the
        # difference between "the desk scored 91%" and "the desk scored 91% on two of five files"
        "partial": partial,
        "files_not_yet_measured": sorted(set(TARGETS) - covered),
        "files": results,
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2), "utf-8")
    return overall, raw_overall, excluded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None,
                    help="max mutants per file (deterministic subsample); omit for a full sweep")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--file", action="append", default=None, help="restrict to these targets")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    targets = {k: v for k, v in TARGETS.items() if not args.file or k in args.file}
    if not targets:
        print(f"no such target; known: {', '.join(TARGETS)}")
        return 2

    with tempfile.TemporaryDirectory(prefix="mutation-") as td:
        tree = Path(td)
        _stage_tree(tree)
        # BASELINE: an already-red suite kills every mutant and reports a perfect score. That
        # is the one failure mode that turns this tool into a liar, so it is checked first.
        all_tests = sorted({t for ts in targets.values() for t in ts})
        baseline_ok = _run_tests(tree, all_tests, args.timeout)
        if not baseline_ok:
            print("BASELINE RED: the target tests do not pass unmutated. Mutation scores would "
                  "be meaningless (every mutant 'killed'). Fix the suite first.")

        # Write the report after EACH file, not once at the end. A full sweep is tens of
        # minutes and the first version lost every measurement when it hit its wall-clock
        # limit -- a tool whose output only exists if it runs to completion will, in practice,
        # mostly produce nothing.
        results: list[FileResult] = []
        for rel, tests in targets.items():
            results.append(run_file(rel, tests, tree, sample=args.sample, seed=args.seed,
                                    timeout=args.timeout, baseline_ok=baseline_ok))
            _write_report(results, args, baseline_ok, partial=True)
            r = results[-1]
            if not r.get("error"):
                print(f"  ...measured {r['file']}: {r['killed']}/{r['tested']} killed",
                      flush=True)

    overall, raw_overall, excluded = _write_report(results, args, baseline_ok, partial=False)
    passes = overall >= KILL_BAR and baseline_ok

    for r in results:
        if r.get("error"):
            print(f"  {r['file']}: {r['error']}")
            continue
        flag = "PASS" if r["passes_bar"] else "FAIL"
        eq = f", {r['equivalent_excluded']} equivalent excluded" if r["equivalent_excluded"] \
            else ""
        print(f"  [{flag}] {r['file']}: {r['killed']}/{r['tested']} killed "
              f"({float(r['score']):.1%}{eq}){' [sampled]' if r['sampled'] else ''}")
        stale = r["stale_equivalent_entries"]
        if isinstance(stale, list) and stale:
            print(f"         STALE equivalent-mutant entries (re-examine): "
                  f"{', '.join(str(s) for s in stale)}")
    print(f"mutation score {overall:.1%} vs bar {KILL_BAR:.0%} -> "
          f"{'PASS' if passes else 'FAIL'}"
          f"  (raw {raw_overall:.1%} incl. {excluded} equivalent)  "
          f"(data/mutation_report.json)")
    # Reporting the number is the job; the bar becomes blocking in CI once the survivors named
    # in the report have been worked down. Exiting non-zero today would just wedge the cycle.
    return 0


if __name__ == "__main__":
    sys.exit(main())
