"""How many searches did we ACTUALLY perform? Not how many cells did we count.

WHY THIS IS A VALIDATION MODULE AND NOT A CACHE

The deflated Sharpe threshold scales with E[max of N trials]. That expectation is derived for N
INDEPENDENT draws: it asks how high the best of N unrelated coin-flip strategies would look by
luck alone. Feed it a trial count inflated by cells that are near-copies of each other and the
threshold is computed for a far wider search than was really run, so genuine edges are killed by
arithmetic.

THIS IS LIVE, NOT HYPOTHETICAL. The nine MT5 candidates fail the gauntlet on deflated Sharpe
ALONE -- against n_trials = 2,464 -- while passing PBO at 0.034 and walk-forward stability at 1.0.
Those two say the candidates are not curve-fits. The DSR failure says the sample cannot be
distinguished from the best of 2,464 coin flips. If a material fraction of those 2,464 cells are
functional clones, the honest count is lower and the verdict changes.

A sweep over (symbol x family x side x window x state x params) manufactures clones structurally:
XAUUSD/asia/rr=2.0/ttl=12 and XAUUSD/asia/rr=2.0/ttl=13 are not two independent searches for an
edge. They are one search, sampled twice.

THE MEASURE

Effective trials from the correlation matrix of trial return series:

    N_eff = (sum of eigenvalues)^2 / sum(eigenvalues^2)

the participation ratio, also called effective rank. N identical columns give N_eff = 1; N
independent columns give N_eff = N; block structure -- which is what a parameter sweep actually
produces -- is handled correctly without anyone choosing a clustering threshold.

Chosen over the simpler N/(1+(N-1)*rho_bar) because a mean correlation collapses the difference
between "twelve cells all mildly related" and "two tight clusters of six", and a parameter sweep
is always the second. The participation ratio sees the clusters.

THE GUARD, WHICH MATTERS MORE THAN THE MEASURE

Lowering N makes every threshold easier. That makes this module a tempting place to manufacture
passes, so:

  - the method is FIXED here, not passed in, not tuned per run;
  - N_raw and N_eff are always reported together, and the deflation is shown at both;
  - N_eff is floored at 2 and capped at N_raw, so it can never exceed the search performed;
  - a correlation matrix that cannot be built returns N_raw unchanged -- absence of a
    deduplication is never permission to assume one.

Lowering the trial count is a claim that requires evidence exactly as much as raising a Sharpe.
"""

from __future__ import annotations

import ast
import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

#: Correlation at or above which two trials are reported as the same bet in the clone listing.
#: Reporting only -- N_eff never depends on it, precisely so no threshold choice can move a gate.
CLONE_RHO = 0.95

#: Series shorter than this cannot support a correlation worth acting on.
MIN_SERIES = 30


# ---------------------------------------------------------------- structural fingerprint

_NORMALISE = [
    (re.compile(r"\s+"), ""),
    (re.compile(r"\.0\b"), ""),          # 20.0 and 20 are the same window
]


class _Canon(ast.NodeTransformer):
    """Rewrite an expression AST into a canonical form.

    Commutative operators get their operands sorted, so `a+b` and `b+a` fingerprint identically,
    and numeric literals are normalised. This catches the algebraically-equivalent rediscoveries
    that an industrial mining loop produces by the thousand -- (close-SMA20)/ATR20 written two
    ways is one hypothesis, not two.
    """

    _COMMUTATIVE = (ast.Add, ast.Mult, ast.BitAnd, ast.BitOr)

    def visit_BinOp(self, node):                                    # noqa: N802
        self.generic_visit(node)
        if isinstance(node.op, self._COMMUTATIVE):
            left, right = ast.dump(node.left), ast.dump(node.right)
            if right < left:
                node.left, node.right = node.right, node.left
        return node

    def visit_Constant(self, node):                                 # noqa: N802
        if isinstance(node.value, float) and node.value.is_integer():
            return ast.Constant(value=int(node.value))
        return node


def canonical_formula(expr: str) -> str:
    """Canonical text of an expression. Falls back to normalised source if it will not parse."""
    try:
        tree = ast.parse(expr, mode="eval")
        tree = ast.fix_missing_locations(_Canon().visit(tree))
        out = ast.dump(tree, annotate_fields=False)
    except SyntaxError:
        out = expr
    for pat, rep in _NORMALISE:
        out = pat.sub(rep, out)
    return out


def fingerprint(expr: str, *, data_lineage: str = "", horizon: str = "") -> str:
    """Stable id for a hypothesis: canonical form + its inputs + its horizon.

    Lineage and horizon are part of the identity deliberately. The same formula on H1 gold and on
    H1 CADJPY are genuinely two hypotheses; the same formula on the same series at two parameter
    values usually is not, and that case is caught functionally below rather than structurally.
    """
    payload = f"{canonical_formula(expr)}|{data_lineage}|{horizon}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------ functional dedup

@dataclass(frozen=True)
class TrialCensus:
    n_raw: int
    n_effective: float
    method: str
    clone_pairs: list[tuple[int, int, float]] = field(default_factory=list)
    why: str = ""

    @property
    def inflation(self) -> float:
        """How many times larger the raw count is than the search actually performed."""
        return self.n_raw / self.n_effective if self.n_effective > 0 else 1.0


def _corr_matrix(cols: list[np.ndarray]) -> np.ndarray | None:
    n = len(cols)
    if n < 2:
        return None
    m = np.column_stack(cols)
    if m.shape[0] < MIN_SERIES:
        return None
    sd = m.std(axis=0)
    keep = sd > 0                       # a constant column has no correlation, not zero
    if keep.sum() < 2:
        return None
    c = np.corrcoef(m[:, keep], rowvar=False)
    return np.nan_to_num(c, nan=0.0, posinf=0.0, neginf=0.0)


def effective_trials(series: Iterable[np.ndarray]) -> TrialCensus:
    """Independent searches actually performed, from the trial return matrix.

    The columns must already be DATE-ALIGNED -- row t the same calendar day in every column. An
    unaligned matrix reports a correlation structure that never existed, which is exactly the
    defect `qquant_gates.build_matrix` carried until it was made to join on the date index.
    """
    cols = [np.asarray(s, dtype=float) for s in series]
    n_raw = len(cols)
    if n_raw < 2:
        return TrialCensus(n_raw, float(max(n_raw, 1)), "n<2",
                           why="fewer than two trials; nothing to deduplicate")

    c = _corr_matrix(cols)
    if c is None:
        # FAILS CLOSED. No correlation matrix means no evidence of duplication, and absence of
        # evidence must not become a discount on the threshold.
        return TrialCensus(n_raw, float(n_raw), "unmeasurable",
                           why=("could not build a correlation matrix (series too short, or all "
                                "constant); N_eff left at N_raw -- no deduplication is assumed"))

    ev = np.linalg.eigvalsh(c)
    ev = np.clip(ev, 0.0, None)
    denom = float((ev ** 2).sum())
    if denom <= 0:
        return TrialCensus(n_raw, float(n_raw), "degenerate",
                           why="degenerate correlation spectrum; N_eff left at N_raw")
    n_eff = float(ev.sum() ** 2 / denom)
    n_eff = max(2.0, min(n_eff, float(n_raw)))       # never below 2, never above what was run

    pairs = []
    k = c.shape[0]
    for i in range(k):
        for j in range(i + 1, k):
            if abs(c[i, j]) >= CLONE_RHO:
                pairs.append((i, j, float(c[i, j])))
    return TrialCensus(
        n_raw, n_eff, "participation_ratio", pairs,
        why=(f"participation ratio of the trial correlation spectrum: {n_raw} cells behave as "
             f"{n_eff:.1f} independent searches ({n_raw / n_eff:.1f}x inflation); "
             f"{len(pairs)} pair(s) at |rho| >= {CLONE_RHO}"))


# ------------------------------------------------------------- deflation at both counts

def expected_max_z(n: float) -> float:
    """E[max of n iid standard normals]. The term the DSR threshold is built on.

    Accepts a non-integer n because N_eff is a continuous measure. Uses the standard asymptotic
    with the Euler-Mascheroni correction, which is accurate to ~1% by n=10 and is what the desk's
    `multiplicity.expected_max_t` integrates numerically for the integer case.
    """
    n = max(float(n), 2.0)
    from math import log, sqrt
    a = sqrt(2.0 * log(n))
    return a - (log(log(n)) + log(4.0 * math.pi)) / (2.0 * a)


def deflation_pair(census: TrialCensus, sd_sharpe: float) -> dict:
    """SR0 at the raw count and at the effective one. BOTH, always.

    Reporting only the deduplicated threshold would let this module quietly relax every gate it
    touches. The pair makes the size of the correction visible, so a reader can judge whether the
    deduplication is doing real work or doing the reviewer's job for them.
    """
    raw = sd_sharpe * expected_max_z(census.n_raw)
    eff = sd_sharpe * expected_max_z(census.n_effective)
    return {
        "n_raw": census.n_raw, "n_effective": round(census.n_effective, 2),
        "inflation": round(census.inflation, 2),
        "sr0_raw": round(raw, 4), "sr0_effective": round(eff, 4),
        "threshold_relief": round(raw - eff, 4),
        "method": census.method, "why": census.why,
        "guard": ("both counts are reported deliberately. Lowering N makes every threshold "
                  "easier, so the correction must be visible and defensible, not silent."),
    }


def census_report(series: Iterable[np.ndarray], sd_sharpe: float,
                  labels: list[Any] | None = None) -> dict:
    """One call: census + deflation at both counts + the clone listing, ready to serialise."""
    census = effective_trials(series)
    out = deflation_pair(census, sd_sharpe)
    if labels and census.clone_pairs:
        out["clone_pairs"] = [
            {"a": labels[i] if i < len(labels) else i,
             "b": labels[j] if j < len(labels) else j, "rho": round(r, 4)}
            for i, j, r in census.clone_pairs[:200]
        ]
        out["n_clone_pairs"] = len(census.clone_pairs)
    return out
