"""NO BAR EVER RISES WITH A TRIAL COUNT (principal, 2026-10-13).

    "make sure the bars never raise never ever penalty never inflation due to trials anything
     like that"  /  "yes and this should be permanently monitpred too js incase so it never
     inflates"

The Tier S bar is fixed by the owner's T8 ruling: deflated Sharpe at N = 5 with the per-cell
null variance 1/(T-1) (t about 2.84). `libs.research.trial_count_guard.bar_n` is the only
lawful source of a bar's N. This fence walks the tree and goes RED on:

1. UNPINNED BAR CALL. Any call to a bar function (deflate_t, deflated_sharpe_ratio,
   expected_max_sharpe, expected_max_z, deflation, trials_penalty) whose trial-count argument is
   not `bar_n(...)`, `BAR_N`, or a literal at or below BAR_N. A new file that brings its own
   trial count is caught here on its first commit.
1b. LEN-SCALED MULTIPLICITY (principal 2026-10-14, "yes land my 5 trial bar"). A correction that
   grows with the size of a collection, written as arithmetic rather than a bar call: Bonferroni
   `alpha / len(x)` (and `p * len(x)`), Sidak `1 - (1 - a) ** (1 / len(x))` (and
   `(1 - p) ** len(x)`), and Holm over a growing count `alpha / (len(x) - i)`. Pinned when the
   count is `bar_n(...)`, `BAR_N`, or `min(count, bar_n(...))` (never above the fixed bar, never
   above the count it replaced). Counts are len(x), x.size, np.size(x), x.shape[i],
   sum(1 for ...), count_nonzero, wrappers of those, and locals assigned from them; also seen:
   statsmodels `multipletests` (always), np.minimum(1, p * m), BH / BY step-up thresholds
   `q * arange(1, m + 1) / (m [* c_m])` and e-BH `m / (alpha * ranks)`, and in rule 1 a
   `partial(bar_fn, n_trials=...)` binding and a `bar_fn(..., **kwargs)` call that hides its count.
   OUT OF REACH (no dataflow): a count that arrives as a parameter, a loop variable or an
   attribute (`self.n`), a count computed in another module or function, rebinding through
   containers/getattr, and thresholds built by any other vector idiom.
2. LIFETIME UNION CHARGE in the sealed judge (`charged_lifetime_trials`). The sealed files cannot
   change without the laptop's re-sign, so a sealed site that the T8 patch owns is OWED: WARN
   until SEALED_DEADLINE, then FAIL. An owed sealed site with no named patch FAILs at once.
3. RE-RUN SHARE RISING after the ledger dedupe lands (marker `desks/mt5/data/TRIAL_DEDUPE_LANDED`):
   the share of charged trials that are repeats of an already-charged pass may not rise over the
   last reading. Before the dedupe it is MEASURED and published, never failed.

4. A WRITTEN-DOWN TIER S t (auditor's proposal, coordinator's ruling 2026-10-14; widened on the
   re-audit of 6de7b1a99). A numeric constant in 2.79..2.90, in any notation (2.8, 284e-2), used
   as a bar -- an operand of a comparison or of np.greater_equal & co, directly, wrapped
   (np.float64) or in arithmetic; bound to a t-bar name (`*_T_BAR`, `TIER_S_*`, `t_min`); bound to
   any name or a parameter default that is then compared against a t; a keyword or dict value
   under a t-bar name -- outside `libs/research/tier_s_threshold.py`. A comparison with a moment
   (`kurt > 2.85`) is not a t bar. The t
   the Tier S bar demands depends on T, skew and kurtosis (4.56 at T=5, 2.89 at T=100); a typed
   2.84 is a copy that stops tracking them. Import `tier_s_t_required` / `tier_s_passes` instead.

Writes `desks/mt5/reports/TRIAL_INFLATION.json` with --report; exits 1 on any FAIL.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.trial_count_guard import BAR_N, run_key, trial_id  # noqa: E402

DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "TRIAL_INFLATION.json"
DEDUPE_MARKER = DESK / "data" / "TRIAL_DEDUPE_LANDED"
RULE = "every bar's N comes from trial_count_guard.bar_n (fixed N=5, owner's T8 ruling)"

#: Bar function -> (positional index of its trial count, keyword spellings of it).
BAR_FUNCS: dict[str, tuple[int, tuple[str, ...]]] = {
    "deflate_t": (1, ("n_tests", "n", "n_trials")),
    "deflated_sharpe_ratio": (1, ("n_trials",)),
    "expected_max_sharpe": (0, ("n_trials", "n")),
    "expected_max_z": (0, ("n", "n_tests")),
    "deflation": (0, ("n_trials", "n")),
    "trials_penalty": (0, ("effective_trials",)),
    "deflated_t": (1, ("n_trials",)),
    "expected_max_t": (0, ("n_trials", "n")),
    "sr0": (0, ("n_trials",)),
    # Bonferroni-charged release / regime gates (libs/research/release_gain): their count is a
    # keyword-only `n_cells` / `n_trials`, so the positional index is out of reach on purpose.
    "release_gain": (99, ("n_cells",)),
    "min_detectable_ic": (1, ("n_cells",)),
    "regime_placebo": (99, ("n_trials",)),
}

#: Names that read as a significance level (Bonferroni/Holm numerator) or a p-value
#: (Bonferroni/Holm multiplier, Sidak base). Narrow on purpose: `x / len(x)` is a mean.
_ALPHA_NAMES = {"alpha", "a", "q", "level", "sig", "fwer", "fdr"}
#: Cheap lexical gate before a file is parsed for 1b: an alpha-like numerator over something,
#: a Sidak power, or a min(1, ...) p-adjustment. The AST pass decides; this only skips files
#: that cannot hold one (parsing every file made the fence ~12x slower).
_MULT_HINTS: tuple[tuple[tuple[str, ...], re.Pattern[str]], ...] = (
    (("alpha", "fwer", "fdr", "level", "sig"),
     re.compile(r"(?:alpha|fwer|fdr|level|sig)\w*\s*/\s*\(?\s*[A-Za-z_]")),
    (("q /", "q/"), re.compile(r"[ (,=]q\s*/\s*\(?\s*[A-Za-z_]")),
    (("a /", "a/"), re.compile(r"[ (,=]a\s*/\s*\(?\s*[A-Za-z_]")),           # a / m, a / len(x)
    ((".",), re.compile(r"(?<![\w.])0?\.\d+\s*/\s*\(?\s*[A-Za-z_]")),       # 0.1 / len(x)
    ((")**", ") **"), re.compile(r"\)\s*\*\*\s*(?:\(\s*1(?:\.0)?\s*/|[A-Za-z_])")),  # (1-p)**m
    (("min(", "minimum("), re.compile(r"min(?:imum)?\(\s*1(?:\.0)?\s*,")),  # min(1, len(x)*p)
    (("arange", "multipletests"), re.compile(r"arange|multipletests")),
)

#: A file is only parsed for 1b when it can hold a growing count at all.
_COUNT_HINTS = ("len(", ".size", ".shape[", "sum(1 for", "multipletests", "count_nonzero")


def _mult_hint(text: str) -> bool:
    return any(any(k in text for k in keys) and rx.search(text) for keys, rx in _MULT_HINTS)


_P_NAMES = {"p", "pv", "pval", "pvalue", "p_value", "p_val", "p_raw", "praw", "p_t", "p_min"}

#: Functions that compute a deflation ONLY TO REPORT IT beside the fixed bar, never to rule;
#: each is reviewed and named here, so a new one cannot arrive unnoticed.
REPORTED_ONLY: dict[tuple[str, str], str] = {
    ("desks/mt5/mt5desk/canonical.py", "deflation_pair"):
        "publishes SR0 at the raw and the deduplicated counts side by side; rules nothing",
}

#: Sealed sites the T8 sealed patch rewrites; they change only by the laptop's re-sign.
T8_PATCH = "/mnt/project-files/judging/trial_count_guard/sealed/tier_s_t8_combined.patch"
SEALED_OWED: dict[str, str] = {
    "desks/mt5/scripts/external_gauntlet.py": T8_PATCH,
    "desks/mt5/research/gate_policy.py": T8_PATCH,
    "desks/mt5/research/universal_gate.py": T8_PATCH,
    "desks/mt5/research/multiplicity.py": T8_PATCH,
    "desks/mt5/research/fragility.py": T8_PATCH,      # money path
    "desks/mt5/research/run_hunt12.py": T8_PATCH,     # money path
    # universal_gate's remote worker and its calibration twin: they change WITH universal_gate,
    # or the remote and local verdicts of one sealed gate would disagree.
    "desks/mt5/side_channels/ug_remote.py": T8_PATCH,
    "desks/mt5/side_channels/gate_calibration.py": T8_PATCH,
}
#: The owner's yes was 2026-10-13; the sealed half has fourteen days to reach the box.
SEALED_DEADLINE = datetime(2026, 10, 27, tzinfo=UTC)

#: Never scanned: tests pin behaviour with explicit counts; retired code never runs.
SKIP_PARTS = {".git", "tests", "_retired", "node_modules", "__pycache__", ".venv", "venv",
              "backups", "lesson_vault"}
RERUN_TOL = 0.005


def _callee_expr(e: ast.expr) -> str:
    if isinstance(e, ast.Name):
        return e.id
    if isinstance(e, ast.Attribute):
        return e.attr
    return ""


def _callee(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _pinned(arg: ast.expr, scope: ast.AST | None = None, depth: int = 0) -> bool:
    """bar_n(...), BAR_N, a literal count at or below BAR_N, a conditional whose every branch is
    pinned, or a local name whose every assignment in the enclosing function is pinned."""
    if isinstance(arg, ast.IfExp):
        return _pinned(arg.body, scope, depth) and _pinned(arg.orelse, scope, depth)
    if isinstance(arg, ast.Name) and scope is not None and depth < 3 and arg.id != "BAR_N":
        vals = [n.value for n in ast.walk(scope) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == arg.id for t in n.targets)]
        # THE T8 HURDLE IS A PIN (merge resolution of trial-count-guard with the T8 sealed set,
        # 2026-10-22). `n, var, basis = dsr_hurdle_inputs(T)` hands back the sealed
        # `gate_policy.DSR_FIXED_TRIALS` (N=5, read from the sealed gate_spec) whatever T is;
        # `test_the_t8_hurdle_count_is_the_bar` pins that constant at or below BAR_N. Only the
        # FIRST element of the unpack is the count; any other binding of the name still decides.
        unpacked = [n for n in ast.walk(scope) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Tuple) and t.elts and isinstance(t.elts[0], ast.Name)
                            and t.elts[0].id == arg.id for t in n.targets)]
        if unpacked:
            vals = [*vals, *(ast.Call(func=ast.Name(id="bar_n", ctx=ast.Load()), args=[],
                                      keywords=[])
                             if isinstance(n.value, ast.Call)
                             and _callee(n.value) == "dsr_hurdle_inputs" else n.value
                             for n in unpacked)]
        vals += [n.value for n in ast.walk(scope) if isinstance(n, ast.AnnAssign)
                 and isinstance(n.target, ast.Name) and n.target.id == arg.id and n.value]
        return bool(vals) and all(_pinned(v, scope, depth + 1) for v in vals)
    if isinstance(arg, ast.Call) and _callee(arg) == "bar_n":
        return True
    if isinstance(arg, ast.Call) and _callee(arg) == "min" and arg.args:
        # min(count, bar_n(...)) is never above the fixed bar
        return any(_pinned(a, scope, depth) for a in arg.args)
    if isinstance(arg, ast.Name) and arg.id == "BAR_N":
        return True
    if isinstance(arg, ast.Attribute) and arg.attr == "BAR_N":
        return True
    return (isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float))
            and not isinstance(arg.value, bool) and arg.value <= BAR_N)


class _Scan(ast.NodeVisitor):
    def __init__(self, rel: str = "", aliases: dict[str, str] | None = None) -> None:
        self.rel = rel
        #: `from libs.validation.dsr import deflated_sharpe_ratio as dsr_canon` -- a renamed
        #: import is still the bar function (side_channels/full_pipeline hid its charge this way).
        self.aliases = aliases or {}
        self.stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.hits: list[tuple[int, str, str]] = []
        self.union = False
        self.capped: set[int] = set()       # BinOps sitting directly inside min(1, ...)

    def _fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name == "charged_lifetime_trials":
            self.union = True
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _fn
    visit_AsyncFunctionDef = _fn

    def _exempt(self) -> bool:
        return bool(self.stack) and (self.stack[-1].name in BAR_FUNCS
                                     or (self.rel, self.stack[-1].name) in REPORTED_ONLY)

    def _plumbing(self, arg: ast.expr) -> bool:
        """Inside a bar primitive's own body (a function named in BAR_FUNCS), passing its count
        on is plumbing: its CALLERS are the sites scanned."""
        return bool(self.stack) and self.stack[-1].name in BAR_FUNCS

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee(node)
        name = self.aliases.get(name, name)
        if name == "multipletests" and not self._exempt():
            # statsmodels' corrections divide by len(pvals) internally: never at a fixed N
            self.hits.append((node.lineno, "multipletests", ast.unparse(node)[:80]))
        if name == "partial" and node.args and _callee_expr(node.args[0]) in BAR_FUNCS:
            # partial(bar_fn, ..., n_trials=x): the bound count is the eventual call's count
            inner = _callee_expr(node.args[0])
            ppos, pkws = BAR_FUNCS[inner]
            bound = node.args[1 + ppos] if len(node.args) > 1 + ppos else None
            for kw in node.keywords:
                if kw.arg in pkws:
                    bound = kw.value
            pscope = self.stack[-1] if self.stack else None
            if bound is not None and not _pinned(bound, pscope) and not self._exempt():
                self.hits.append((node.lineno, inner, ast.unparse(bound)[:80]))
        if name in {"min", "minimum"} and any(isinstance(a, ast.Constant) and a.value in (1, 1.0)
                                 and not isinstance(a.value, bool) for a in node.args):
            self.capped.update(id(a) for a in node.args if isinstance(a, ast.BinOp))
        if name in BAR_FUNCS:
            pos, kws = BAR_FUNCS[name]
            arg: ast.expr | None = node.args[pos] if len(node.args) > pos else None
            for kw in node.keywords:
                if kw.arg in kws:
                    arg = kw.value
            reported = bool(self.stack) and (self.rel, self.stack[-1].name) in REPORTED_ONLY
            scope = self.stack[-1] if self.stack else None
            if arg is not None and not _pinned(arg, scope) and not self._plumbing(arg) \
                    and not reported:
                self.hits.append((node.lineno, name, ast.unparse(arg)[:80]))
            elif arg is None and any(kw.arg is None for kw in node.keywords) \
                    and not self._exempt():
                # bar_fn(x, **kwargs): the count rides in a mapping the fence cannot read
                self.hits.append((node.lineno, name, "**kwargs (count not visible)"))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        scope = self.stack[-1] if self.stack else None
        found = _multiplicity(node, scope, id(node) in self.capped)
        if found is not None and not (bool(self.stack) and (
                self.stack[-1].name in BAR_FUNCS
                or (self.rel, self.stack[-1].name) in REPORTED_ONLY)):
            kind, count = found
            if not _pinned(count, scope) and not _pinned_count(count, scope):
                self.hits.append((node.lineno, kind, ast.unparse(node)[:80]))
                return                         # one hit per expression, not per sub-node
        self.generic_visit(node)


def _pinned_count(e: ast.expr, scope: ast.AST | None) -> bool:
    """The count inside a wrapper is pinned: max(1, bar_n(n)), int(BAR_N), bar_n(n) - i."""
    if isinstance(e, ast.Call) and _callee(e) in {"max", "int", "float", "abs", "round"}:
        return all(_pinned(a, scope) or _pinned_count(a, scope) or
                   (isinstance(a, ast.Constant) and not _len_scaled(a, scope))
                   for a in e.args) and any(_pinned(a, scope) or _pinned_count(a, scope)
                                            for a in e.args)
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Sub, ast.Add)):
        return _pinned(e.left, scope) or _pinned_count(e.left, scope)
    return False


def _local_values(name: str, scope: ast.AST | None) -> list[ast.expr]:
    if scope is None:
        return []
    vals = [n.value for n in ast.walk(scope) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    vals += [n.value for n in ast.walk(scope) if isinstance(n, ast.AnnAssign)
             and isinstance(n.target, ast.Name) and n.target.id == name and n.value]
    return vals


def _len_scaled(e: ast.expr, scope: ast.AST | None = None, depth: int = 0) -> bool:
    """A count that grows with a collection: len(x), or max/int/float/abs of one, or len(x) +- k,
    or a local name assigned from one (any assignment -- one moving path is enough)."""
    if isinstance(e, ast.Attribute) and e.attr == "size":
        return True                                         # x.size
    if isinstance(e, ast.Subscript) and isinstance(e.value, ast.Attribute) \
            and e.value.attr == "shape":
        return True                                         # x.shape[0]
    if isinstance(e, ast.Call):
        name = _callee(e)
        if name in {"len", "size", "count_nonzero"}:
            return True                                     # len(x), np.size(x)
        if name == "sum" and e.args and isinstance(e.args[0], ast.GeneratorExp) \
                and isinstance(e.args[0].elt, ast.Constant) and e.args[0].elt.value == 1:
            return True                                     # sum(1 for ...)
        if name in {"max", "int", "float", "abs", "round"}:
            return any(_len_scaled(a, scope, depth) for a in e.args)
        return False
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Sub, ast.Add)):
        return _len_scaled(e.left, scope, depth)
    if isinstance(e, ast.Name) and depth < 3:
        return any(_len_scaled(v, scope, depth + 1) for v in _local_values(e.id, scope))
    return False


def _scaled_den(e: ast.expr, scope: ast.AST | None) -> bool:
    """m, or m * c_m (BY's harmonic factor), with m a growing count."""
    if _len_scaled(e, scope):
        return True
    return isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult) and (
        _len_scaled(e.left, scope) or _len_scaled(e.right, scope))


def _ranked(e: ast.expr, scope: ast.AST | None, depth: int = 0) -> bool:
    """A rank vector: arange(...), a local assigned straight from one, or either scaled by a
    constant/name one level up (q * arange(1, m + 1)). Deliberately shallow."""
    if isinstance(e, ast.Call):
        return _callee(e) == "arange"
    if isinstance(e, ast.Name) and depth < 1:
        return any(_ranked(v, scope, depth + 1) for v in _local_values(e.id, scope))
    if isinstance(e, ast.BinOp) and depth < 1 and isinstance(e.op, (ast.Mult, ast.Div)):
        return _ranked(e.left, scope, depth + 1) or _ranked(e.right, scope, depth + 1)
    return False


def _named(e: ast.expr, names: set[str]) -> bool:
    if isinstance(e, ast.Name):
        return e.id.lower() in names or e.id.lower().startswith(tuple(f"{n}_" for n in names))
    if isinstance(e, ast.Attribute):
        return _named(ast.Name(id=e.attr), names)
    return False


def _alpha_like(e: ast.expr) -> bool:
    if isinstance(e, ast.Constant) and isinstance(e.value, float):
        return 0.0 < e.value <= 0.2
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Sub) \
            and isinstance(e.left, ast.Constant) and e.left.value == 1:
        return _alpha_like(e.right) or _named(e.right, _P_NAMES)   # Sidak base (1 - a)
    return _named(e, _ALPHA_NAMES)


def _multiplicity(node: ast.BinOp, scope: ast.AST | None,
                  capped: bool = False) -> tuple[str, ast.expr] | None:
    """(kind, count expression) when `node` is a len-scaled multiplicity correction."""
    op, left, right = node.op, node.left, node.right
    holm = isinstance(right, ast.BinOp) and isinstance(right.op, ast.Sub)
    if isinstance(op, ast.Div) and _alpha_like(left) and _len_scaled(right, scope):
        return ("holm_len" if holm else "bonferroni_len"), right
    if isinstance(op, ast.Mult) and capped:
        # p * m only inside min(1, ...): the Bonferroni/Holm p-adjustment. A bare p * len(x) is
        # a quantile index or an expected count far more often than a correction.
        for p, m in ((left, right), (right, left)):
            if _named(p, _P_NAMES) and _len_scaled(m, scope):
                return ("holm_len" if isinstance(m, ast.BinOp) and isinstance(m.op, ast.Sub)
                        else "bonferroni_len"), m
    if isinstance(op, ast.Mult):
        # BH step-up threshold: q * (ranks / m) or (ranks / (m * c_m)) * alpha
        for a, d in ((left, right), (right, left)):
            if _alpha_like(a) and isinstance(d, ast.BinOp) and isinstance(d.op, ast.Div) \
                    and _ranked(d.left, scope) and _scaled_den(d.right, scope):
                return "bh_len", d.right
    if isinstance(op, ast.Div) and _len_scaled(left, scope) and isinstance(right, ast.BinOp) \
            and isinstance(right.op, ast.Mult) and any(
                _alpha_like(x) for x in (right.left, right.right)) \
            and any(_ranked(x, scope) for x in (right.left, right.right)):
        return "bh_len", left                      # e-BH: m / (alpha * ranks)
    if isinstance(op, ast.Pow) and _alpha_like(left):
        ex = right
        if isinstance(ex, ast.BinOp) and isinstance(ex.op, ast.Div) \
                and isinstance(ex.left, ast.Constant) and ex.left.value in (1, 1.0):
            ex = ex.right                                 # (1 - a) ** (1 / m)
        if _len_scaled(ex, scope):
            return "sidak_len", ex
    return None


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".")]
        out.extend(Path(dirpath) / f for f in filenames
                   if f.endswith(".py") and not f.startswith("test_"))
    return sorted(out)


def _pins_inside(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """The definition sends its count through bar_n itself, so no caller can raise its bar."""
    return any(isinstance(n, ast.Call) and _callee(n) == "bar_n" for n in ast.walk(fn))


def scan(root: Path = ROOT) -> dict[str, Any]:
    unpinned: list[dict[str, Any]] = []
    union: list[str] = []
    trees: list[tuple[str, ast.AST]] = []
    for p in _files(root):
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not (any(f in text for f in (*BAR_FUNCS, "charged_lifetime_trials"))
                or (any(h in text for h in _COUNT_HINTS) and _mult_hint(text))):
            continue                     # parse only files that can hold a bar call
        try:
            trees.append((rel, ast.parse(text)))
        except (SyntaxError, ValueError):
            continue
    # A bar function whose EVERY definition in the tree pins internally is safe to call with any
    # count; one unpinned definition anywhere keeps every caller under scan.
    defs: dict[str, list[bool]] = {}
    for _rel, tree in trees:
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in BAR_FUNCS:
                defs.setdefault(n.name, []).append(_pins_inside(n))
    safe = {k for k, v in defs.items() if v and all(v)}
    for rel, tree in trees:
        aliases = {a.asname: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   for a in n.names if a.asname and a.name in BAR_FUNCS}
        s = _Scan(rel, aliases)
        s.visit(tree)
        if s.union:
            union.append(rel)
        unpinned += [{"file": rel, "line": ln, "call": fn, "trials_arg": a}
                     for ln, fn, a in s.hits if fn not in safe]
    return {"unpinned": unpinned, "union_charge": union, "pinned_inside": sorted(safe)}


#: Rule 4: the Tier S t's asymptote, the band around it, and the one module allowed to hold it.
#: The band is 2.79..2.90 in ANY notation (2.8, 2.84, 284e-2, 2_84e-2): the t the bar demands runs
#: 2.886 at T=100 down to 2.838, and the old +/-0.05 band is kept as its lower edge.
TIER_S_T = 2.84
TIER_S_LO, TIER_S_HI = 2.79, 2.90
TIER_S_HOME = frozenset({"libs/research/tier_s_threshold.py", "libs/research/trial_count_guard.py",
                         "scripts/check_trial_inflation.py"})
#: Cheap lexical gate: any numeric token. Its VALUE decides (float() of the token), so 2.8,
#: 284e-2 and 2.8_4 reach the AST pass and an unrelated 0.284 does not.
_NUM_TOKEN = re.compile(r"(?<![\w.])(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][-+]?\d+)?(?![\w.])")
_TIER_S_NAME = re.compile(r"(_T_BAR$|^TIER_S_)", re.IGNORECASE)
#: Identifier segments that read as a t statistic or its bar, and as a distribution moment. A
#: moment compared with ~2.85 (`kurt > 2.85`, near the normal's 3) is not a t threshold.
_T_SEGMENTS = frozenset({"t", "tstat", "tstats", "tval", "tvalue", "hurdle", "tier", "nwt",
                         "tgross", "traw", "tnet"})
_MOMENT_HINTS = ("kurt", "skew", "moment", "g3", "g4", "excess")
_COMPARE_CALLS = frozenset({"greater", "greater_equal", "less", "less_equal", "gt", "ge", "lt",
                            "le"})
_WRAPPERS = frozenset({"float", "float64", "float32", "float_", "double", "asarray", "array"})


def _in_band(v: float) -> bool:
    return TIER_S_LO - 1e-12 <= abs(v) <= TIER_S_HI + 1e-12


def _band_value(e: ast.expr | None) -> float | None:
    """The band literal carried by `e`: a bare number, its negation, a float()/np.float64()
    wrapper of one, or an operand of arithmetic on one (2.84 * k, base + 2.84)."""
    if e is None:
        return None
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)):
        return _band_value(e.operand)
    if (isinstance(e, ast.Constant) and isinstance(e.value, (int, float))
            and not isinstance(e.value, bool)):
        return float(e.value) if _in_band(float(e.value)) else None
    if isinstance(e, ast.Call) and _callee(e) in _WRAPPERS and e.args:
        return _band_value(e.args[0])
    if isinstance(e, (ast.List, ast.Tuple)) and len(e.elts) == 1:
        return _band_value(e.elts[0])
    if isinstance(e, ast.BinOp):
        return _band_value(e.left) if _band_value(e.left) is not None else _band_value(e.right)
    return None


def _segments(name: str) -> set[str]:
    return {s for s in re.split(r"_+", name.lower()) if s}


def _names_in(e: ast.expr) -> list[str]:
    out: list[str] = []
    for n in ast.walk(e):
        if isinstance(n, ast.Name):
            out.append(n.id)
        elif isinstance(n, ast.Attribute):
            out.append(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)                  # r["t_gross"], row.get("kurtosis")
    return out


def _t_ish(name: str) -> bool:
    return bool(_TIER_S_NAME.search(name)) or bool(_segments(name) & _T_SEGMENTS)


def _moment_ish(e: ast.expr) -> bool:
    return any(h in nm.lower() for nm in _names_in(e) for h in _MOMENT_HINTS)


def _comparisons(tree: ast.AST) -> list[list[ast.expr]]:
    """Every comparison's operands: `a < b <= c` and np.greater_equal(a, b) / operator.ge(a, b)."""
    out: list[list[ast.expr]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            out.append([n.left, *n.comparators])
        elif isinstance(n, ast.Call) and _callee(n) in _COMPARE_CALLS and len(n.args) >= 2:
            out.append(list(n.args[:2]))
    return out


def _compared_in_t_context(name: str, comps: list[list[ast.expr]]) -> bool:
    """`name` is an operand of a comparison whose other side reads as a t, and none as a moment."""
    for ops in comps:
        mine = [o for o in ops if name in _names_in(o)]
        if not mine or any(_moment_ish(o) for o in ops):
            continue
        others = [o for o in ops if o not in mine]
        if any(_t_ish(nm) for o in others for nm in _names_in(o)):
            return True
    return False


def tier_s_literals(root: Path = ROOT) -> list[dict[str, Any]]:
    """Rule 4: every ~2.84 constant (2.79..2.90, any notation) used as a t bar outside the helper.

    USED AS A BAR means one of: an operand of a comparison (`t >= 2.84`, `t > 2.84 * k`,
    np.greater_equal(t, 2.84)); bound to a name that reads as a t bar (`TIER_S_*`, `*_T_BAR`,
    `t_min`, `hurdle`); bound to any name, or a parameter's default, that is then compared
    against a t (`bar = 2.8` ... `if t_gross >= bar`); or a keyword / dict value under a t-bar
    name. A comparison any of whose operands names a moment (kurt, skew, g3, g4) is not a t bar."""
    hits: list[dict[str, Any]] = []
    for p in _files(root):
        rel = p.relative_to(root).as_posix()
        if rel in TIER_S_HOME:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(_in_band(_num(m.group(0))) for m in _NUM_TOKEN.finditer(text)):
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        comps = _comparisons(tree)
        found: dict[tuple[int | None, float, str], None] = {}

        def hit(node: ast.AST, v: float, use: str,
                _f: dict[tuple[int | None, float, str], None] = found) -> None:
            _f[(getattr(node, "lineno", None), v, use)] = None

        for ops in comps:
            if any(_moment_ish(o) for o in ops):
                continue
            for o in ops:
                v = _band_value(o)
                if v is not None:
                    hit(o, v, "comparison")
        for n in ast.walk(tree):
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                names = [x for tg in targets for x in _target_names(tg)]
                v = _band_value(n.value)
                if v is None:
                    continue
                if any(_t_ish(x) for x in names):
                    hit(n, v, f"bound to {','.join(names)}")
                elif any(_compared_in_t_context(x, comps) for x in names):
                    hit(n, v, f"bound to {','.join(names)}, compared against a t")
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                a = n.args
                pos = [*a.posonlyargs, *a.args]
                pairs = list(zip(pos[len(pos) - len(a.defaults):], a.defaults, strict=False))
                pairs += [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults, strict=False)
                          if d is not None]
                body_comps = _comparisons(n)
                for arg, d in pairs:
                    v = _band_value(d)
                    if v is not None and (_t_ish(arg.arg)
                                          or _compared_in_t_context(arg.arg, body_comps)):
                        hit(d, v, f"default of {arg.arg}")
            elif isinstance(n, ast.keyword) and n.arg and _t_ish(n.arg):
                v = _band_value(n.value)
                if v is not None:
                    hit(n.value, v, f"keyword {n.arg}")
            elif isinstance(n, ast.Dict):
                for k, val in zip(n.keys, n.values, strict=False):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) \
                            and _t_ish(k.value):
                        v = _band_value(val)
                        if v is not None:
                            hit(val, v, f"key {k.value}")
        hits += [{"file": rel, "line": ln, "value": v, "use": u} for ln, v, u in found]
    return hits


def _num(tok: str) -> float:
    try:
        return float(tok.replace("_", ""))
    except ValueError:
        return math.nan


def _target_names(t: ast.expr) -> list[str]:
    if isinstance(t, ast.Name):
        return [t.id]
    if isinstance(t, ast.Attribute):
        return [t.attr]
    if isinstance(t, (ast.Tuple, ast.List)):
        return [n for el in t.elts for n in _target_names(el)]
    return []


def _discovery_rerun_share(root: Path = ROOT) -> dict[str, Any]:
    """Share of discovery-file `tests_run` that repeats an already-charged pass."""
    raw = distinct = 0
    seen: set[str] = set()
    for f in sorted((root / "desks" / "mt5" / "data" / "intelligence").glob(
            "*/discoveries_*.json")):
        try:
            d = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get("tests_run"), (int, float)):
            continue
        n = int(d["tests_run"])
        k = run_key(f.parent.name, n, sorted(trial_id(r) for r in d.get("discoveries") or []
                                             if isinstance(r, dict)))
        raw += n
        if k not in seen:
            seen.add(k)
            distinct += n
    if not raw:
        return {"status": "UNMEASURED", "why": "no discovery file with tests_run on this host"}
    return {"status": "MEASURED", "n_charged": raw, "n_distinct": distinct,
            "rerun_share": round((raw - distinct) / raw, 6)}


def judge(root: Path = ROOT, *, now: datetime | None = None,
          prior: dict[str, Any] | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    found = scan(root)
    checks: list[dict[str, Any]] = []
    owed = [h for h in found["unpinned"] if h["file"] in SEALED_OWED]
    free = [h for h in found["unpinned"] if h["file"] not in SEALED_OWED]
    checks.append({"metric": "unpinned_bar_calls",
                   "state": "FAIL" if free else "OK", "n": len(free), "sites": free[:50],
                   "why": ("every bar's N comes from bar_n" if not free else
                           f"{len(free)} bar call(s) take their own trial count")})
    sealed = owed + [{"file": f, "call": "charged_lifetime_trials", "line": None,
                      "trials_arg": "lifetime union"} for f in found["union_charge"]]
    late = at >= SEALED_DEADLINE
    unowned = [s for s in sealed if s["file"] not in SEALED_OWED]
    state = ("OK" if not sealed else "FAIL" if (late or unowned) else "WARN")
    checks.append({"metric": "sealed_trial_charge", "state": state, "n": len(sealed),
                   "sites": sealed[:50], "owner": T8_PATCH,
                   "deadline_utc": SEALED_DEADLINE.isoformat(),
                   "why": ("no sealed site charges a moving N" if not sealed else
                           f"{len(sealed)} sealed site(s) still charge a moving N or the "
                           f"lifetime union; owed by the T8 sealed re-sign "
                           f"({'PAST' if late else 'due'} {SEALED_DEADLINE.date()})")})
    rr = _discovery_rerun_share(root)
    landed = DEDUPE_MARKER.exists() if root == ROOT else (
        root / "desks" / "mt5" / "data" / "TRIAL_DEDUPE_LANDED").exists()
    was = (prior or {}).get("rerun_share")
    rr_state = "UNMEASURED" if rr["status"] != "MEASURED" else "OK"
    if (rr_state == "OK" and landed and isinstance(was, (int, float))
            and rr["rerun_share"] > float(was) + RERUN_TOL):
        rr_state = "FAIL"
    checks.append({"metric": "ledger_rerun_share", "state": rr_state, "dedupe_landed": landed,
                   "previous": was, **rr,
                   "why": rr.get("why") or (
                       f"{rr['n_charged']} trials charged, {rr['n_distinct']} distinct: "
                       f"{rr['rerun_share']:.1%} are re-runs"
                       + ("" if landed else " (published; ratcheted once the dedupe lands)"))})
    lit = tier_s_literals(root)
    checks.append({"metric": "tier_s_t_literal", "state": "FAIL" if lit else "OK",
                   "n": len(lit), "sites": lit[:50],
                   "why": ("no bar holds a written-down Tier S t" if not lit else
                           f"{len(lit)} bare ~{TIER_S_T} constant(s) used as a bar: import "
                           "tier_s_t_required / tier_s_passes from "
                           "libs.research.trial_count_guard instead")})
    verdict = "FAIL" if any(c["state"] == "FAIL" for c in checks) else "PASS"
    return {"at": at.isoformat(timespec="seconds"), "rule": RULE, "bar_n": BAR_N,
            "verdict": verdict, "checks": checks,
            "rerun_share": rr.get("rerun_share")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="write TRIAL_INFLATION.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        prior = json.loads(REPORT.read_text("utf-8"))
    except (OSError, ValueError):
        prior = None
    doc = judge(prior=prior if isinstance(prior, dict) else None)
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        os.replace(tmp, REPORT)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"trial inflation: {doc['verdict']} (bar N={BAR_N})")
        for c in doc["checks"]:
            print(f"  [{c['state']}] {c['metric']}: {c.get('why', '')}")
            for s in (c.get("sites") or [])[:10]:
                print(f"      {s['file']}:{s['line']} {s['call']}({s['trials_arg']})")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
