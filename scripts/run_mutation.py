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
if str(_ROOT) not in sys.path:          # `import libs` works without an editable install
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "data/mutation_score.json"
_WORK = Path("/tmp/claude-0/-home-user-quant/1c87bc3b-ab99-5043-86ff-5b38ad12af2a/scratchpad/mut")

# The measured set. Order is priority order: the gate fix pending a principal decision first
# (measuring whether its 13 tests CONSTRAIN it is load-bearing for that decision), then the
# money-path stage machine, then the retry and risk gates.
# Test files verified present 2026-07-29 (a target whose tests do not exist scores ERROR, which
# is itself the finding: libs/execution/retry.py has NO dedicated test module, so its mutants
# cannot be measured -- recorded rather than silently dropped).
#
# EVERY TARGET LISTS ITS *_strength.py COMPANION, and the omission of one is not cosmetic.
# Measured 2026-07-30: gate.py was listed with `tests/risk/test_gate.py` alone while
# `tests/risk/test_gate_strength.py` -- the suite written specifically to kill its mutants --
# existed and was never run. The nightly job therefore recorded 23.5% instead of the true 86.3%
# and the ratchet reported a permanent REGRESSION on the money path. A false red is not a
# harmless conservative error: it trains the desk to ignore the one metric measuring whether its
# risk gate is actually constrained. `_missing_strength_suites()` below now fails the run rather
# than leaving this to whoever edits this list next.
_DEFAULT_TARGETS: list[tuple[str, list[str]]] = [
    ("libs/validation/stepwise.py",
     ["tests/validation/test_stepwise.py", "tests/validation/test_stepwise_strength.py"]),
    ("libs/execution/staging.py",
     ["tests/execution/test_staging.py", "tests/execution/test_staging_strength.py"]),
    ("libs/risk/gate.py",
     ["tests/risk/test_gate.py", "tests/risk/test_gate_strength.py"]),
    ("libs/execution/binance_live.py", ["tests/execution/test_binance_live.py"]),
]


def _missing_strength_suites() -> list[str]:
    """Targets with a *_strength.py suite on disk that the target list does not run.

    A strength suite exists for exactly one reason -- to kill mutants -- so not running it
    guarantees an understated score, and an understated score on the money path is the most
    expensive kind of false alarm: it makes the true number unreadable.
    """
    out = []
    for target, tests in _DEFAULT_TARGETS:
        listed = {Path(t).name for t in tests}
        for t in tests:
            companion = Path(_ROOT / t).with_name(Path(t).stem + "_strength.py")
            if companion.exists() and companion.name not in listed:
                out.append(f"{target}: {companion.relative_to(_ROOT)} exists but is not listed")
    return out

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


def _splice(original: str, mutated_tree: ast.AST, lineno: int) -> str:
    """Write the mutant by replacing ONLY the mutated region, keeping the rest byte-identical.

    THE DEFECT THIS FIXES, and it fabricated a 100%. The harness used to write every mutant as
    `ast.unparse(whole_module)`, which is a REFORMAT of the entire file: `ast.unparse` normalises
    double-quoted string literals to single quotes, drops comments, and rewrites whitespace. Any
    test that asserts on its module's own source text therefore fails for EVERY mutant, killing all
    of them for a reason that has nothing to do with the mutation.

    Measured 2026-07-30 on libs/autodiscovery/validation.py: 137/137 "killed", a perfect score --
    produced entirely by tests/autodiscovery/test_validation_cpcv_baselines.py asserting
    `'"beats_baselines"' in inspect.getsource(validate)`, a literal that ast.unparse renders as
    `'beats_baselines'`. Verified directly: the double-quoted form is present in the original and
    absent from the unparsed text. That fake 100% would have been written into
    data/ratchet_floors.json as a PERMANENT FLOOR the real tests could never meet again.

    Splicing keeps the file byte-identical except for the mutated statement, so a source-asserting
    test sees the code it expects and only a real behavioural change can kill a mutant. The
    unparsed replacement is taken for the mutated statement's own line span, which is why the
    span is recomputed from the ORIGINAL tree rather than trusted from the mutated one.
    """
    lines = original.splitlines(keepends=True)
    stmt = None
    for node in ast.walk(mutated_tree):
        if (isinstance(node, ast.stmt) and getattr(node, "lineno", None) is not None
                and node.lineno <= lineno <= (node.end_lineno or node.lineno)
                and (stmt is None or node.lineno > stmt.lineno)):
            stmt = node
    if stmt is None or stmt.end_lineno is None:
        # No enclosing statement resolved: fall back to the old whole-file behaviour rather than
        # skipping the mutant. A reformatted mutant is a weaker measurement; a dropped one is a
        # silently smaller denominator, which is worse.
        return ast.unparse(mutated_tree)
    indent = " " * (stmt.col_offset or 0)
    body = "\n".join(indent + ln for ln in ast.unparse(stmt).splitlines())
    return "".join(lines[:stmt.lineno - 1]) + body + "\n" + "".join(lines[stmt.end_lineno:])


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
            work_target.write_text(_splice(original, mutated, site.lineno), "utf-8")
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

    if missing := _missing_strength_suites():
        print("REFUSING: a *_strength.py suite exists on disk but is not run:")
        for m in missing:
            print(f"  {m}")
        print("  A strength suite exists only to kill mutants; not running it guarantees an")
        print("  understated score, and a false RED on the money path makes the true number")
        print("  unreadable. Add it to _DEFAULT_TARGETS.")
        return 2

    targets = ([(args.target, args.tests)] if args.target else _DEFAULT_TARGETS)
    scores = [measure(t, tests, budget_s=args.budget_s) for t, tests in targets]

    # EQUIVALENT-MUTANT ADJUSTMENT. An equivalent mutant cannot be killed by any test, so a target
    # carrying them can never reach the bar on the raw number -- and a metric permanently red for
    # a reason nobody can fix trains the desk to ignore it, which is the same false-red failure
    # that let gate.py sit at a phantom 23.5%. The register demands a written argument per claim
    # and expires it the moment the claimed source line changes; RAW is always reported too, so
    # nothing is hidden. meets_bar uses the ADJUSTED rate; both numbers land in the artifact.
    from libs.testing.equivalent_mutants import adjust

    fresh = []
    for s in scores:
        adj = adjust(s.target, s.survivors, s.killed, s.total)
        rate = float(adj["adjusted_kill_rate"]) if s.total else s.kill_rate
        fresh.append({
            "target": s.target, "tests": s.tests, "killed": s.killed,
            "survived": s.survived, "timeout": s.timeout, "error": s.error,
            "total": s.total, "kill_rate": s.kill_rate, "runtime_s": s.runtime_s,
            "adjusted_kill_rate": rate, "equivalent_mutants": adj["equivalent_mutants"],
            "equivalences_applied": adj["equivalences_applied"],
            "equivalences_lapsed": adj["equivalences_lapsed"],
            "meets_bar": rate >= args.bar, "survivors": s.survivors,
            "real_survivors": adj["real_survivors"],
            "measured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
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
