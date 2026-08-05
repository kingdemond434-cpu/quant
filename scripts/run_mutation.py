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

SAMPLING: A PARTIAL RUN MUST BE A SAMPLE, NOT A PREFIX. Sites used to be attempted in SOURCE
ORDER, so a run that hit its wall-clock budget measured the TOP OF THE FILE -- module-header
constants, import-time literals, the first few guards -- and nothing at all about the gate logic
below them. Measured 2026-07-30 on libs/autodiscovery/validation.py: 14 of 137 sites, all nine
survivors in the header constant block, 35.7% reported. That number is not a low estimate of the
file's kill rate; it is not an estimate of it AT ALL, because the sample was chosen by position
and position correlates with what a line does. A biased partial number is worse than no number:
it invites exactly one response, which is to run less and report the easy end of the file.
Sites are therefore permuted by a SEEDED shuffle (`--seed`, default 20260805) before the budget
loop. A truncated run is then a simple random sample WITHOUT REPLACEMENT of the site list, so its
kill rate is an unbiased estimate of the whole file's, and the artifact carries a 95% Wilson
interval with the finite-population correction (`kill_rate_ci95`) saying how precise it is.
The correction collapses the interval to a point exactly when the run is a census.
`--order source` restores the old behaviour for debugging and is recorded in the artifact; it is
never the default, because a default that is only right when it happens to finish is not a default.

TRUNCATION IS STILL NOT A SCORE. An unbiased sample is an ESTIMATE, and `budget_truncated`
continues to mean "do not score this": scripts/check_ratchets.py and libs/research/
capability_ratchet.py both refuse truncated targets, which is what stops the desk buying points by
running less. Sampling makes a partial run READABLE, not scoreable. The way to a scoreable number
is `--resume`, which accumulates successive runs into one honest total until coverage reaches 1.0
and the flag clears because the file was actually finished.

    python scripts/run_mutation.py                      # default risk-path set
    python scripts/run_mutation.py --target libs/x.py --tests tests/test_x.py --budget-s 300
    # long run, 4 mirrors in parallel, resumable across sessions:
    python scripts/run_mutation.py --target libs/x.py --tests tests/test_x.py \
        --budget-s 10800 --jobs 4 --resume
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:          # `import libs` works without an editable install
    sys.path.insert(0, str(_ROOT))
_OUT = _ROOT / "data/mutation_score.json"
#: Accumulated per-site outcomes for `--resume`. Separate from the score artifact on purpose: this
#: is the RUN LEDGER (which sites have been attempted, under which source and seed), and merging it
#: into the score would let a reader mistake "attempted" for "measured strength".
_PROGRESS = _ROOT / "data/mutation_progress.json"
#: Default seed. Fixed and recorded so that "an unbiased sample" is also a REPRODUCIBLE one: two
#: operators running a truncated budget on the same file measure the SAME sites and can compare.
_DEFAULT_SEED = 20260805


def _work_root() -> Path:
    """Scratch root for the mutant mirrors.

    Was a hardcoded session-scratchpad path, which made the harness unrunnable on the VPS -- the
    long run this file exists to enable is exactly the one that happens somewhere else. Honours
    $MUTATION_WORK_DIR, falls back to the session scratchpad when it exists, then to the system
    temp dir. Mirrors are deleted at the end of every target either way.
    """
    env = os.environ.get("MUTATION_WORK_DIR")
    if env:
        return Path(env)
    scratch = "/tmp/claude-0/-home-user-quant/1c87bc3b-ab99-5043-86ff-5b38ad12af2a/scratchpad"  # noqa: S108 -- session scratchpad, not a shared world-writable location
    session = Path(scratch) / "mut"
    if session.parent.is_dir():
        return session
    return Path(tempfile.gettempdir()) / "quant-mutation"

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
    #: mutation sites FOUND, vs `total` attempted. Sites are visited in SEEDED-SHUFFLE order, so a
    #: budget-truncated run is a simple random sample of the site list and its rate IS an estimate
    #: of the whole -- with the width the `kill_rate_ci95` below reports. Under `--order source`
    #: the attempted set is a PREFIX instead, which is not a sample of anything.
    n_sites: int = 0
    seed: int = _DEFAULT_SEED
    order: str = "shuffled"
    #: seconds the UNMUTATED suite took, and the per-mutant timeout actually used. Both are
    #: recorded because TIMEOUT counts as KILLED: a timeout set too close to the baseline turns
    #: machine load into kills and silently inflates the score.
    baseline_s: float = 0.0
    timeout_s: float = 0.0
    resumed: int = 0
    #: sha256 prefix of the target AS MEASURED. A mutation score is a statement about one version
    #: of one file; without the hash a reader cannot tell whether the number still describes the
    #: file on disk, and a long run competing with an in-flight edit is exactly when that matters.
    source_sha256: str = ""

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.timeout + self.error

    @property
    def kill_rate(self) -> float:
        # TIMEOUT counts as killed (the mutation changed observable behaviour enough to hang);
        # ERROR does not count either way and is reported separately so it cannot flatter a score.
        denom = self.killed + self.survived + self.timeout
        return round((self.killed + self.timeout) / denom, 4) if denom else 0.0

    @property
    def unbiased(self) -> bool:
        """True when the attempted set is a random sample (or a census) of the site list.

        A complete run is unbiased whatever the order. A PARTIAL run is unbiased only under the
        seeded shuffle -- source order selects by position, and position in a file is not
        independent of what the line does.
        """
        return self.order == "shuffled" or self.total >= self.n_sites

    def kill_rate_ci95(self) -> list[float]:
        """95% Wilson interval for the kill rate, finite-population corrected.

        The FPC term `sqrt((N-n)/(N-1))` is what makes this honest at both ends: sampling 14 of
        137 sites gives a genuinely wide interval, and sampling all 137 gives a POINT -- a census
        has no sampling error, so the interval must not pretend otherwise. Returned as [lo, hi];
        it describes sampling error ONLY, and says nothing about a biased (source-ordered) run,
        which is why `unbiased` is reported next to it rather than folded into it.
        """
        n = self.killed + self.survived + self.timeout
        if n <= 0:
            return [0.0, 1.0]
        big_n = max(self.n_sites, n)
        p, z = (self.killed + self.timeout) / n, 1.96
        fpc = math.sqrt((big_n - n) / (big_n - 1)) if big_n > 1 else 0.0
        za = z * fpc
        denom = 1.0 + za * za / n
        centre = (p + za * za / (2 * n)) / denom
        half = (za / denom) * math.sqrt(p * (1 - p) / n + za * za / (4 * n * n))
        return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


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


def _enumerate_sites(original: str) -> list[tuple[Mutant, int]]:
    """Every site with its same-line-same-kind ordinal, in SOURCE order.

    The ordinal is what lets `_Applier` find one specific mutation among several on a line, so it
    has to be assigned before any reordering -- shuffling first and numbering after would make a
    site's identity depend on the seed, and `--resume` could no longer match yesterday's ledger.
    """
    collector = _Collector()
    collector.visit(ast.parse(original))
    seen: dict[tuple[int, str], int] = {}
    out: list[tuple[Mutant, int]] = []
    for site in collector.sites:
        key = (site.lineno, site.kind)
        idx = seen.get(key, 0)
        seen[key] = idx + 1
        out.append((site, idx))
    return out


def _site_key(site: Mutant, idx: int) -> str:
    return f"{site.lineno}:{site.kind}:{idx}:{site.detail}"


def order_sites(sites: list[tuple[Mutant, int]], *, order: str,
                seed: int) -> list[tuple[Mutant, int]]:
    """Visit order for the budget loop. `shuffled` is the default and the honest one.

    Under a wall-clock budget the visit order DECIDES which sites get measured, so it decides what
    the reported rate is a rate OF. Source order makes that set a prefix of the file, correlated
    with everything about a line except how well it is tested. A seeded permutation makes it a
    simple random sample: unbiased, reproducible from the recorded seed, and interval-estimable.
    """
    out = list(sites)
    if order == "shuffled":
        random.Random(seed).shuffle(out)  # noqa: S311 -- sampling mutants, not minting secrets
    return out


def _source_fingerprint(original: str) -> str:
    return hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]


def _load_progress(target: str, *, fingerprint: str, seed: int, order: str,
                   tests: list[str]) -> dict[str, str]:
    """Previously attempted sites, but ONLY when they describe the same measurement.

    Resume accumulates coverage across runs, which is only sound while the thing being measured
    holds still. The ledger is discarded whenever the source hash, the seed, the order or the test
    list differs: outcomes gathered against a different file, or against a different suite, are
    not evidence about this one, and silently pooling them would manufacture coverage.
    """
    try:
        doc = json.loads(_PROGRESS.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entry = doc.get("targets", {}).get(target) if isinstance(doc, dict) else None
    if not isinstance(entry, dict):
        return {}
    if (entry.get("source_sha256") != fingerprint or entry.get("seed") != seed
            or entry.get("order") != order or entry.get("tests") != tests):
        return {}
    outcomes = entry.get("outcomes")
    return {str(k): str(v) for k, v in outcomes.items()} if isinstance(outcomes, dict) else {}


def _save_progress(target: str, *, fingerprint: str, seed: int, order: str, tests: list[str],
                   n_sites: int, outcomes: dict[str, str]) -> None:
    try:
        doc = json.loads(_PROGRESS.read_text("utf-8"))
        if not isinstance(doc, dict):
            doc = {}
    except (OSError, json.JSONDecodeError):
        doc = {}
    targets = doc.get("targets")
    if not isinstance(targets, dict):
        targets = {}
    targets[target] = {
        "source_sha256": fingerprint, "seed": seed, "order": order, "tests": tests,
        "n_sites": n_sites, "attempted": len(outcomes),
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outcomes": dict(sorted(outcomes.items())),
    }
    doc["targets"] = targets
    doc["note"] = ("run ledger for scripts/run_mutation.py --resume: which mutation sites have "
                   "been ATTEMPTED, per source hash + seed + test list. Not a score; the score "
                   "artifact is data/mutation_score.json.")
    _PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    _PROGRESS.write_text(json.dumps(doc, indent=2), "utf-8")


def _mutant_source(original: str, site: Mutant, idx: int) -> str | None:
    applier = _Applier(site, idx)
    mutated = applier.visit(ast.parse(original))
    if not applier.applied:
        return None
    ast.fix_missing_locations(mutated)
    return _splice(original, mutated, site.lineno)


def measure(target: str, tests: list[str], *, budget_s: float,
            per_test_timeout: float = 120.0, seed: int = _DEFAULT_SEED,
            order: str = "shuffled", jobs: int = 1, resume: bool = False,
            confirm_tests: list[str] | None = None,
            timeout_factor: float = 4.0) -> TargetScore:
    score = TargetScore(target=target, tests=tests, seed=seed, order=order)
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
    fingerprint = _source_fingerprint(original)
    score.source_sha256 = fingerprint
    sites = _enumerate_sites(original)
    score.n_sites = len(sites)
    queue = order_sites(sites, order=order, seed=seed)

    done: dict[str, str] = (_load_progress(target, fingerprint=fingerprint, seed=seed,
                                           order=order, tests=tests) if resume else {})
    detail_by_key = {_site_key(s, i): (s, i) for s, i in sites}
    for key, outcome in done.items():
        if key not in detail_by_key:
            continue
        _tally(score, outcome, detail_by_key[key][0])
    score.resumed = len([k for k in done if k in detail_by_key])
    pending = [(s, i) for s, i in queue if _site_key(s, i) not in done]

    started = time.time()
    if not pending:
        # Nothing left to run: rebuild the artifact from the ledger without paying for a mirror or
        # a baseline. This is the path that turns a series of chunked runs into one finished score.
        score.timeout_s = per_test_timeout
        _finish(score, confirm_tests=confirm_tests, original=original, target=target,
                jobs=1, tests=tests)
        return score

    jobs = max(1, jobs)
    mirrors = [_work_root() / Path(target).stem / f"w{i}" for i in range(jobs)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(_prepare, mirrors))
    # PIN THE MIRROR TO THE SNAPSHOT THAT WAS ENUMERATED. A multi-hour run shares the tree with
    # whoever else is editing it, and the mutants are spliced from the text read at the top of
    # this function. Without this write the BASELINE would be run against whatever landed on disk
    # between that read and the copy -- a green baseline for a different file than the one scored.
    for mirror in mirrors:
        (mirror / target).write_text(original, "utf-8")

    # Baseline must be GREEN or every mutant reads as killed and the score is a lie.
    base_started = time.time()
    if _run_tests(mirrors[0], tests, max(per_test_timeout, 600.0)) != "survived":
        score.error = len(sites) or 1
        score.killed = score.survived = score.timeout = 0
        score.survivors = []
        score.runtime_s = round(time.time() - started, 1)
        for m in mirrors:
            shutil.rmtree(m, ignore_errors=True)
        return score
    score.baseline_s = round(time.time() - base_started, 1)
    # TIMEOUT IS SCORED AS KILLED, so the timeout must be far enough above the OBSERVED baseline
    # that only a real hang reaches it. With `--jobs` the mirrors contend for the same cores, and
    # a timeout pinned near the single-process baseline would convert that contention into kills --
    # a score that rises with machine load is not a measurement of the tests. The effective value
    # is written into the artifact so a reader can judge whether the timeouts in it are plausible.
    score.timeout_s = round(
        max(per_test_timeout, timeout_factor * score.baseline_s * (1.0 + 0.5 * (jobs - 1))), 1)

    lock = threading.Lock()
    supply: Iterator[tuple[Mutant, int]] = iter(pending)

    def worker(mirror: Path) -> None:
        work_target = mirror / target
        while True:
            with lock:
                if time.time() - started > budget_s:
                    return
                site_idx = next(supply, None)
            if site_idx is None:
                return
            site, idx = site_idx
            try:
                text = _mutant_source(original, site, idx)
            except (RecursionError, ValueError):
                text = None
            if text is None:
                with lock:
                    done[_site_key(site, idx)] = "error"
                    _tally(score, "error", site)
                continue
            work_target.write_text(text, "utf-8")
            outcome = _run_tests(mirror, tests, score.timeout_s)
            work_target.write_text(original, "utf-8")   # restore before the next mutant
            with lock:
                done[_site_key(site, idx)] = outcome
                _tally(score, outcome, site)
                if resume and score.total % 10 == 0:
                    _save_progress(target, fingerprint=fingerprint, seed=seed, order=order,
                                   tests=tests, n_sites=len(sites), outcomes=done)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(worker, mirrors))

    if resume:
        _save_progress(target, fingerprint=fingerprint, seed=seed, order=order, tests=tests,
                       n_sites=len(sites), outcomes=done)
    _finish(score, confirm_tests=confirm_tests, original=original, target=target,
            jobs=jobs, tests=tests, mirrors=mirrors)
    score.runtime_s = round(time.time() - started, 1)
    for m in mirrors:
        shutil.rmtree(m, ignore_errors=True)
    return score


def _tally(score: TargetScore, outcome: str, site: Mutant) -> None:
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


def _finish(score: TargetScore, *, confirm_tests: list[str] | None, original: str, target: str,
            jobs: int, tests: list[str], mirrors: list[Path] | None = None) -> None:
    """Stable survivor order, then the optional WIDER-SUITE re-check.

    A survivor is a claim about the whole suite, but a target is measured against a NAMED subset of
    it for affordability -- so a mutant can be reported as unkilled when some test module outside
    that subset would in fact have caught it. `--confirm-tests` re-runs each survivor against the
    wider set and stamps it `wider_suite: killed|survived`. It deliberately does NOT move the
    counts: the kill rate stays a rate over the declared test list, comparable with previous runs,
    and the stamp tells a reader which survivors are real findings and which are artefacts of the
    subset. Reporting a killed mutant as a survivor is still a false finding, and false findings
    are how a survivor list stops being read.
    """
    score.survivors.sort(key=lambda s: (int(str(s["line"])), str(s["kind"]), str(s["mutation"])))
    if not confirm_tests or not score.survivors:
        return
    wider = tests + [t for t in confirm_tests if (_ROOT / t).exists() and t not in tests]
    owned = mirrors is None
    pool_dirs = mirrors or [_work_root() / Path(target).stem / "confirm"]
    if owned:
        _prepare(pool_dirs[0])
        (pool_dirs[0] / target).write_text(original, "utf-8")   # pin to the measured snapshot
    sites = {_site_key(s, i): (s, i) for s, i in _enumerate_sites(original)}
    by_line: dict[tuple[int, str, str], tuple[Mutant, int]] = {
        (s.lineno, s.kind, s.detail): (s, i) for s, i in sites.values()}
    lock = threading.Lock()
    supply = iter(score.survivors)

    def confirm(mirror: Path) -> None:
        work_target = mirror / target
        while True:
            with lock:
                row = next(supply, None)
            if row is None:
                return
            found = by_line.get((int(str(row["line"])), str(row["kind"]), str(row["mutation"])))
            if found is None:
                row["wider_suite"] = "unresolved"
                continue
            text = _mutant_source(original, *found)
            if text is None:
                row["wider_suite"] = "unresolved"
                continue
            work_target.write_text(text, "utf-8")
            outcome = _run_tests(mirror, wider, max(score.timeout_s, 900.0))
            work_target.write_text(original, "utf-8")
            row["wider_suite"] = "survived" if outcome == "survived" else "killed"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        list(pool.map(confirm, pool_dirs))
    if owned:
        shutil.rmtree(pool_dirs[0], ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target")
    ap.add_argument("--tests", nargs="*", default=[])
    ap.add_argument("--budget-s", type=float, default=600.0,
                    help="wall-clock budget PER TARGET (default 600)")
    ap.add_argument("--bar", type=float, default=0.90, help="v8 8.2 kill-rate bar")
    ap.add_argument("--seed", type=int, default=_DEFAULT_SEED,
                    help="seed for the site permutation; recorded in the artifact")
    ap.add_argument("--order", choices=("shuffled", "source"), default="shuffled",
                    help="site visit order. 'shuffled' makes a truncated run an unbiased sample; "
                         "'source' reproduces the old biased prefix and is for debugging only")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel mutant workers, one repo mirror each (default 1)")
    ap.add_argument("--resume", action="store_true",
                    help="accumulate coverage across runs via data/mutation_progress.json; the "
                         "ledger resets whenever the source, seed, order or test list changes")
    ap.add_argument("--per-test-timeout", type=float, default=120.0,
                    help="floor for the per-mutant timeout; the effective value also scales with "
                         "the measured baseline and --jobs so load cannot be scored as kills")
    ap.add_argument("--timeout-factor", type=float, default=4.0,
                    help="multiple of the MEASURED baseline a mutant may take before it counts as "
                         "a hang (default 4). Lower it to stop hangs eating the budget, but not so "
                         "low that a slow machine starts scoring as kills")
    ap.add_argument("--confirm-tests", nargs="*", default=[],
                    help="extra test modules run against SURVIVORS ONLY, to mark which survivors "
                         "the wider suite would already have caught. Never changes the counts")
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
    scores = [measure(t, tests, budget_s=args.budget_s, per_test_timeout=args.per_test_timeout,
                      seed=args.seed, order=args.order, jobs=args.jobs, resume=args.resume,
                      confirm_tests=list(args.confirm_tests), timeout_factor=args.timeout_factor)
              for t, tests in targets]

    # EQUIVALENT-MUTANT ADJUSTMENT. An equivalent mutant cannot be killed by any test, so a target
    # carrying them can never reach the bar on the raw number -- and a metric permanently red for
    # a reason nobody can fix trains the desk to ignore it, which is the same false-red failure
    # that let gate.py sit at a phantom 23.5%. The register demands a written argument per claim
    # and expires it the moment the claimed source line changes; RAW is always reported too, so
    # nothing is hidden. meets_bar uses the ADJUSTED rate; both numbers land in the artifact.
    from libs.testing.equivalent_mutants import adjust

    fresh = []
    for s in scores:
        # `killed + timeout` is THIS HARNESS'S killed count -- a mutation that hangs the suite
        # changed observable behaviour, which is what `kill_rate` above already encodes. Passing
        # bare `killed` made `adjusted_kill_rate` silently DISAGREE with `kill_rate` the moment a
        # mutant timed out (libs/risk/sizing.py, 2026-08-05: 86.2% raw against 82.8% adjusted with
        # zero equivalences registered), and the ratchet reads the adjusted number -- so a single
        # hang would have been filed as a REGRESSION on an unchanged file.
        adj = adjust(s.target, s.survivors, s.killed + s.timeout, s.total)
        rate = float(adj["adjusted_kill_rate"]) if s.total else s.kill_rate
        fresh.append({
            "target": s.target, "tests": s.tests, "killed": s.killed,
            "survived": s.survived, "timeout": s.timeout, "error": s.error,
            "total": s.total, "kill_rate": s.kill_rate, "runtime_s": s.runtime_s,
            "n_sites": s.n_sites,
            # UNCHANGED SEMANTICS, DELIBERATELY. `budget_truncated` means "fewer sites attempted
            # than exist", and both readers (scripts/check_ratchets.py, libs/research/
            # capability_ratchet.py) treat it as DO NOT SCORE. Seeded sampling makes a truncated
            # run READABLE -- an unbiased estimate with an interval -- not scoreable. Loosening
            # this to let a sample count would restore the exact incentive the flag exists to
            # remove: run less, report the easy end of the file.
            "budget_truncated": bool(s.n_sites and s.total < s.n_sites),
            "coverage_of_sites": (round(s.total / s.n_sites, 4) if s.n_sites else None),
            "site_order": s.order, "seed": s.seed,
            #: True when the attempted set is a random sample or a census, so `kill_rate` is an
            #: unbiased estimate of the file's. False means the number describes a prefix.
            "unbiased_sample": s.unbiased,
            "kill_rate_ci95": s.kill_rate_ci95(),
            "baseline_s": s.baseline_s, "per_mutant_timeout_s": s.timeout_s,
            "resumed_sites": s.resumed, "source_sha256": s.source_sha256,
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
        cov = (s.total / s.n_sites) if s.n_sites else 0.0
        lo, hi = s.kill_rate_ci95()
        print(f"  {s.target:38} kill={s.kill_rate:.1%} "
              f"(killed {s.killed}, survived {s.survived}, timeout {s.timeout}, "
              f"error {s.error}) {flag} [{s.runtime_s}s]")
        if s.n_sites:
            state = "CENSUS" if s.total >= s.n_sites else (
                "SAMPLE (unbiased, NOT scoreable while truncated)" if s.unbiased
                else "PREFIX -- BIASED, not an estimate of the file")
            print(f"      {s.total}/{s.n_sites} sites ({cov:.1%}) {state}; "
                  f"95% CI [{lo:.1%}, {hi:.1%}] seed={s.seed} order={s.order}")
        for sv in s.survivors[:5]:
            wider = f"  wider_suite={sv['wider_suite']}" if "wider_suite" in sv else ""
            print(f"      SURVIVED line {sv['line']:4} {sv['kind']:11} {sv['mutation']}{wider}")
    print(f"-> {_OUT.relative_to(_ROOT) if _OUT.is_relative_to(_ROOT) else _OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
