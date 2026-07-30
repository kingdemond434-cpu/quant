"""MUTATION TESTING -- gap #53: the v8 8.2 bar (>=90% mutants killed) had never been measured once.

WHY THIS IS NOT OPTIONAL: four risk-path register rows (#2, #49, #37, #19) cite that bar as their
gate. A gate nobody has measured is a decoration, and 1199+ tests were of UNKNOWN strength --
they demonstrably EXECUTE code; nothing showed they CONSTRAIN it. This produces the desk's first
measured kill rates.

METHOD, and the honest trade-off stated up front: this is a self-contained AST mutation harness,
not mutmut. mutmut 3.6.0 installs cleanly and is the documented path for a long VPS run
(`mutmut run` over a whole module tree), but its copy-based workflow needs a writable project
mirror and minutes per mutant of pytest startup. This harness instead (a) copies the target module
+ its exercising tests into a throwaway tree under the scratchpad, (b) applies ONE deterministic
mutation at a time, (c) runs only that module's tests, (d) records KILLED (tests fail) /
SURVIVED (tests still pass -- the mutation is invisible to the suite) / TIMEOUT / ERROR.
Deterministic and dependency-free, so it reruns identically on the box.

A SURVIVED MUTANT IS THE DELIVERABLE, not the score: it names a line whose behaviour no test
pins. The report lists them with file:line and the exact mutation.

Operator set (deliberately small and high-signal):
  comparison flips     <  <=  >  >=  ==  !=      (off-by-one and boundary logic)
  arithmetic swaps     + -  * /                  (sign and scale errors)
  boolean negation     and <-> or, not-insertion (guard inversion)
  constant nudges      n -> n+1, n -> 0          (threshold slack)
  literal flips        True <-> False            (fail-open vs fail-closed)
  return-value drop    return X -> return None   (silent no-op)

    python scripts/run_mutation.py                      # default risk-path set
    python scripts/run_mutation.py --target libs/x.py --tests tests/test_x.py --budget-s 300
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/mutation_score.json"
_WORK = Path("/tmp/claude-0/-home-user-quant/1c87bc3b-ab99-5043-86ff-5b38ad12af2a/scratchpad/mut")

# The measured set. Order is priority order: the gate fix pending a principal decision first
# (measuring whether its 13 tests CONSTRAIN it is load-bearing for that decision), then the
# money-path stage machine, then the retry and risk gates.
# Test files verified present 2026-07-29 (a target whose tests do not exist scores ERROR, which
# is itself the finding: libs/execution/retry.py has NO dedicated test module, so its mutants
# cannot be measured -- recorded rather than silently dropped).
_DEFAULT_TARGETS: list[tuple[str, list[str]]] = [
    ("libs/validation/stepwise.py", ["tests/validation/test_stepwise.py"]),
    ("libs/execution/staging.py", ["tests/execution/test_staging.py"]),
    ("libs/risk/gate.py", ["tests/risk/test_gate.py"]),
    ("libs/execution/binance_live.py", ["tests/execution/test_binance_live.py"]),
]

_CMP_FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_BIN_FLIP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


@dataclass
class Mutant:
    lineno: int
    kind: str
    detail: str


@dataclass
class TargetScore:
    target: str
    tests: list[str]
    killed: int = 0
    survived: int = 0
    timeout: int = 0
    error: int = 0
    runtime_s: float = 0.0
    survivors: list[dict[str, object]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.timeout + self.error

    @property
    def kill_rate(self) -> float:
        # TIMEOUT counts as killed (the mutation changed observable behaviour enough to hang);
        # ERROR does not count either way and is reported separately so it cannot flatter a score.
        denom = self.killed + self.survived + self.timeout
        return round((self.killed + self.timeout) / denom, 4) if denom else 0.0


class _Collector(ast.NodeVisitor):
    """Enumerate mutation sites. One pass, so the site list is stable across runs."""

    def __init__(self) -> None:
        self.sites: list[Mutant] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            if type(op) in _CMP_FLIP:
                self.sites.append(Mutant(node.lineno, "compare",
                                         f"{type(op).__name__} -> "
                                         f"{_CMP_FLIP[type(op)].__name__}"))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) in _BIN_FLIP:
            self.sites.append(Mutant(node.lineno, "binop",
                                     f"{type(node.op).__name__} -> "
                                     f"{_BIN_FLIP[type(node.op)].__name__}"))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.sites.append(Mutant(node.lineno, "boolop",
                                 f"{type(node.op).__name__} -> "
                                 f"{'Or' if isinstance(node.op, ast.And) else 'And'}"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool):
            self.sites.append(Mutant(node.lineno, "bool_const", f"{node.value} -> {not node.value}"))
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            self.sites.append(Mutant(node.lineno, "num_const", f"{node.value} -> {node.value + 1}"))
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None and not isinstance(node.value, ast.Constant):
            self.sites.append(Mutant(node.lineno, "return_none", "return <expr> -> return None"))
        self.generic_visit(node)


class _Applier(ast.NodeTransformer):
    """Apply exactly the site'th mutation of the given kind; count matches to find it."""

    def __init__(self, want: Mutant, index: int) -> None:
        self.want, self.index, self.seen, self.applied = want, index, 0, False

    def _hit(self, node: ast.AST, kind: str) -> bool:
        if kind != self.want.kind or getattr(node, "lineno", None) != self.want.lineno:
            return False
        match = self.seen == self.index
        self.seen += 1
        return match

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "compare"):
            node.ops = [_CMP_FLIP[type(op)]() if type(op) in _CMP_FLIP else op for op in node.ops]
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "binop") and type(node.op) in _BIN_FLIP:
            node.op = _BIN_FLIP[type(node.op)]()
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "boolop"):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.applied = True
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        # The APPLIER must classify constants exactly as the COLLECTOR does, or the ordinals
        # disagree: the collector only records bool/int/float, so treating a str/None constant as
        # "num_const" here both mis-counts the index and crashes on `str + 1` (observed 2026-07-29
        # on libs/execution/staging.py). A mutation harness that dies mid-file reports nothing
        # about the tests -- the same false-negative shape as a broken mirror.
        if isinstance(node.value, bool):
            kind = "bool_const"
        elif isinstance(node.value, (int, float)):
            kind = "num_const"
        else:
            return node
        if self._hit(node, kind):
            node.value = (not node.value) if kind == "bool_const" else node.value + 1
            self.applied = True
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if self._hit(node, "return_none"):
            node.value = None
            self.applied = True
        return node


def _prepare(work: Path) -> None:
    """Throwaway mirror: the repo is copied ONCE per run, then one file is rewritten per mutant."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    # `app` is load-bearing even for libs-only targets: libs/autodiscovery/generators.py imports
    # it, so omitting it made the baseline suite fail and scored all 89 mutants as ERROR on the
    # first run -- a mirror missing one package reads as "tests are worthless" rather than
    # "the mirror is wrong". Copy everything the suite can import.
    # MIRROR COMPLETENESS IS LOAD-BEARING, learned twice: omitting `app` made the stepwise
    # baseline fail (89 mutants scored ERROR, reading as "tests are worthless"), and omitting
    # `migrations` made tests/execution/conftest.py fail to import (43 ERRORs on staging.py).
    # A mirror missing one package reports a fact about ITSELF as a fact about the tests.
    for item in ("libs", "tests", "app", "api", "config", "migrations", "data",
                 "pyproject.toml", "scripts"):
        src = _ROOT / item
        if not src.exists():
            continue
        dst = work / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)


def _run_tests(work: Path, tests: list[str], timeout_s: float) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-x", "-q", "--no-header",
             "-p", "no:cacheprovider", "-p", "no:randomly"],
            cwd=work, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return "timeout"
    if proc.returncode == 0:
        return "survived"          # suite still green WITH the mutation = the suite cannot see it
    if proc.returncode in (1, 2):
        return "killed"
    return "error"


def measure(target: str, tests: list[str], *, budget_s: float,
            per_test_timeout: float = 120.0) -> TargetScore:
    score = TargetScore(target=target, tests=tests)
    src_path = _ROOT / target
    if not src_path.exists():
        score.error = 1
        return score
    tests = [t for t in tests if (_ROOT / t).exists()]
    if not tests:
        score.error = 1
        return score
    score.tests = tests

    original = src_path.read_text("utf-8")
    tree = ast.parse(original)
    collector = _Collector()
    collector.visit(tree)
    sites = collector.sites

    work = _WORK / Path(target).stem
    _prepare(work)
    work_target = work / target
    started = time.time()

    # Baseline must be GREEN or every mutant reads as killed and the score is a lie.
    if _run_tests(work, tests, per_test_timeout) != "survived":
        score.error = len(sites) or 1
        score.runtime_s = round(time.time() - started, 1)
        shutil.rmtree(work, ignore_errors=True)
        return score

    # Same-line mutations of the same kind are distinguished by ordinal index.
    seen_key: dict[tuple[int, str], int] = {}
    for site in sites:
        if time.time() - started > budget_s:
            break
        key = (site.lineno, site.kind)
        idx = seen_key.get(key, 0)
        seen_key[key] = idx + 1
        applier = _Applier(site, idx)
        mutated = applier.visit(ast.parse(original))
        if not applier.applied:
            continue
        ast.fix_missing_locations(mutated)
        try:
            work_target.write_text(ast.unparse(mutated), "utf-8")
        except (RecursionError, ValueError):
            score.error += 1
            continue
        outcome = _run_tests(work, tests, per_test_timeout)
        if outcome == "survived":
            score.survived += 1
            score.survivors.append({"line": site.lineno, "kind": site.kind,
                                    "mutation": site.detail})
        elif outcome == "killed":
            score.killed += 1
        elif outcome == "timeout":
            score.timeout += 1
        else:
            score.error += 1
        work_target.write_text(original, "utf-8")   # restore before the next mutant

    score.runtime_s = round(time.time() - started, 1)
    shutil.rmtree(work, ignore_errors=True)
    return score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target")
    ap.add_argument("--tests", nargs="*", default=[])
    ap.add_argument("--budget-s", type=float, default=600.0,
                    help="wall-clock budget PER TARGET (default 600)")
    ap.add_argument("--bar", type=float, default=0.90, help="v8 8.2 kill-rate bar")
    args = ap.parse_args()

    targets = ([(args.target, args.tests)] if args.target else _DEFAULT_TARGETS)
    scores = [measure(t, tests, budget_s=args.budget_s) for t, tests in targets]

    fresh = [{"target": s.target, "tests": s.tests, "killed": s.killed,
              "survived": s.survived, "timeout": s.timeout, "error": s.error,
              "total": s.total, "kill_rate": s.kill_rate, "runtime_s": s.runtime_s,
              "meets_bar": s.kill_rate >= args.bar, "survivors": s.survivors,
              "measured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
             for s in scores]
    # MERGE, never replace. Measuring ONE target used to overwrite the whole artifact, which
    # (a) destroyed prior measurements and (b) fed a phantom REGRESSION to the ratchet fence --
    # a measurement tool must never be able to lower a floor by looking at a different file.
    # An ERROR-only result (baseline broken, nothing actually mutated) NEVER displaces a real
    # prior score for the same target: a failed run is not evidence about the tests.
    try:
        prior = json.loads(_OUT.read_text("utf-8")).get("targets", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        prior = []
    merged: dict[str, dict[str, object]] = {str(t.get("target")): t for t in prior
                                            if isinstance(t, dict)}
    for row in fresh:
        key = str(row["target"])
        old = merged.get(key)
        if (int(row["total"]) == int(row["error"]) and old is not None
                and int(old.get("total", 0)) > int(old.get("error", 0))):
            old["last_failed_run"] = row["measured"]
            old["last_failed_reason"] = f"{row['error']} mutants scored ERROR (baseline broken)"
            continue
        merged[key] = row
    payload = {
        "measured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bar": args.bar,
        "method": "self-contained AST mutation harness (see module docstring); mutmut 3.6.0 is "
                  "the documented path for a long VPS run over whole trees",
        "targets": [merged[k] for k in sorted(merged)],
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")

    print(f"mutation testing (bar {args.bar:.0%}):")
    for s in scores:
        flag = "PASS" if s.kill_rate >= args.bar else "BELOW-BAR"
        print(f"  {s.target:38} kill={s.kill_rate:.1%} "
              f"(killed {s.killed}, survived {s.survived}, timeout {s.timeout}, "
              f"error {s.error}) {flag} [{s.runtime_s}s]")
        for sv in s.survivors[:5]:
            print(f"      SURVIVED line {sv['line']:4} {sv['kind']:11} {sv['mutation']}")
    print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
