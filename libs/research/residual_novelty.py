"""How many DIFFERENT edges are in a set of strategies, after their shared exposure is removed.

WHY THIS EXISTS

A desk can hold six hundred candidates and own one idea. Measured on this desk 2026-08-29: 615
cells cleared every validity gate across eight families -- and family labels are not evidence of
independence. `EMA trend`, `Donchian breakout`, `ADX trend` and a Hawkes-gated trend look like
four mechanisms and four programs; if their returns correlate 0.93 once common market exposure is
removed, they are one research branch wearing four costumes, and calling them four is how a book
reports breadth it does not have.

That matters here more than anywhere else, because ORTHOGONALITY is this desk's binding
constraint. The certificate count is not what limits the book -- the effective number of
independent bets is (n_eff ~5.5 across 23 certificates). Adding a ninth costume to an existing
branch adds risk and no diversification, while consuming a certificate slot and a forward clock.

WHAT IS MEASURED, AND WHY RESIDUALS

Raw return correlation is dominated by the common factor every long-ish strategy on the same
universe shares. Two genuinely different mechanisms can correlate 0.6 simply because both are
long risk in a rising market, and two identical mechanisms can correlate 0.6 for the same reason
-- so the raw number does not separate them. Removing the leading principal components first
strips that shared exposure and leaves what each strategy contributes that the others do not.
Correlation on THAT is a claim about mechanism rather than about beta.

TWO NUMBERS, BECAUSE THEY ANSWER DIFFERENT QUESTIONS:

  * `n_branches` -- how many distinct groups survive clustering at a correlation threshold. This
    is the honest answer to "how many different things do we have", and it is the number to quote
    instead of the candidate count.
  * `n_eff` -- the participation ratio of the residual correlation spectrum, a continuous
    effective count. It does not need a threshold, so it cannot be tuned by choosing one, and it
    degrades smoothly where clustering flips between answers.

Deliberately NOT a gate. This measures and reports; nothing here rejects a candidate. Whether a
crowded branch should be admitted is a decision about portfolio construction, and this desk's
rule is that AI and analysis propose while deterministic gates dispose.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Residual correlation at or above which two strategies are the SAME branch. 0.7 is a deliberate
#: choice and a reportable one: at 0.7 two strategies share roughly half their residual variance,
#: which is far past "related" and well short of demanding they be identical. `n_eff` is reported
#: alongside precisely so a reader can see whether the answer depends on this number.
SAME_BRANCH_RHO = 0.7

#: Leading principal components treated as shared exposure and removed before comparing. One
#: strips the common long/risk factor; more starts removing genuine mechanism, so this stays low
#: and is stated rather than tuned.
DEFAULT_FACTORS = 1


@dataclass(frozen=True)
class BranchReport:
    n_strategies: int
    n_branches: int
    n_eff: float
    largest_branch: int
    branch_of: dict[str, int] = field(default_factory=dict)
    representatives: list[str] = field(default_factory=list)
    note: str = ""


def _zscore(matrix: np.ndarray) -> np.ndarray:
    """Columns to zero mean, unit variance. Zero-variance columns become zeros, never NaN."""
    mu = matrix.mean(axis=0, keepdims=True)
    sd = matrix.std(axis=0, ddof=1, keepdims=True)
    sd = np.where(sd <= 0, np.inf, sd)          # a flat series correlates with nothing
    return (matrix - mu) / sd


def _safe_corr(z: np.ndarray) -> np.ndarray:
    """Correlation matrix that tolerates FLAT columns instead of dividing by their zero variance.

    A cell that produced no trades has a flat series, and that is a real state on this desk --
    300 of them in the sweep this was built against. `np.corrcoef` divides by the standard
    deviation, so a flat column raises `invalid value encountered in divide`, and this repo runs
    `filterwarnings = error`, which turns that into a failure. Suppressing the warning would be
    the wrong repair: the honest answer is that a constant series correlates with NOTHING, so its
    row and column are zero and it lands in its own branch.
    """
    sd = z.std(axis=0, ddof=1)
    live = sd > 0
    n = z.shape[1]
    corr = np.zeros((n, n), dtype=float)
    if live.any():
        sub = np.corrcoef(z[:, live], rowvar=False)
        sub = np.atleast_2d(np.nan_to_num(sub, nan=0.0, posinf=0.0, neginf=0.0))
        idx = np.flatnonzero(live)
        corr[np.ix_(idx, idx)] = sub
    np.fill_diagonal(corr, 1.0)
    return corr


def strip_factors(matrix: np.ndarray, n_factors: int = DEFAULT_FACTORS) -> np.ndarray:
    """Remove the leading `n_factors` principal components -- the exposure everything shares.

    Uses the SVD of the standardised matrix rather than an explicit covariance eigendecomposition:
    same subspace, better conditioned when columns are near-duplicates, which is exactly the case
    this function exists to detect.
    """
    if n_factors <= 0 or matrix.shape[1] <= 1:
        return matrix
    z = _zscore(matrix)
    k = min(n_factors, min(z.shape) - 1)
    if k <= 0:
        return z
    u, s, vt = np.linalg.svd(z, full_matrices=False)
    common = (u[:, :k] * s[:k]) @ vt[:k, :]
    return z - common


def participation_ratio(corr: np.ndarray) -> float:
    """Effective number of independent directions in a correlation matrix.

    (sum of eigenvalues)^2 / sum(eigenvalues^2). For N perfectly independent strategies this is
    N; for N identical ones it is 1. Threshold-free, which is why it is reported next to a
    clustering that is not.
    """
    if corr.size == 0:
        return 0.0
    eig = np.linalg.eigvalsh(corr)
    eig = np.clip(eig, 0.0, None)
    total = float(eig.sum())
    sq = float((eig**2).sum())
    if sq <= 0 or total <= 0:
        return 0.0
    return (total**2) / sq


def branch_report(matrix: np.ndarray, labels: list[str], *,
                  n_factors: int = DEFAULT_FACTORS,
                  rho: float = SAME_BRANCH_RHO) -> BranchReport:
    """Group strategies into research branches by residual return correlation.

    `matrix` is (T observations x N strategies); `labels[k]` names column k. Clustering is single
    linkage on |rho| >= threshold: transitive on purpose, because A~B and B~C means all three sit
    on one branch even when A and C are individually below the line. That is the conservative
    direction -- it reports FEWER distinct edges, and over-reporting breadth is the failure this
    exists to prevent.
    """
    if matrix.ndim != 2 or matrix.shape[1] != len(labels):
        raise ValueError("matrix must be (T x N) with one label per column")
    n = matrix.shape[1]
    if n == 0:
        return BranchReport(0, 0, 0.0, 0, {}, [], "no strategies")
    if n == 1:
        return BranchReport(1, 1, 1.0, 1, {labels[0]: 0}, [labels[0]], "single strategy")

    # LINK ON EITHER RAW OR RESIDUAL CORRELATION, because each alone has a blind spot and they
    # are opposite blind spots.
    #
    # Residual-only fails exactly when it matters most: if EVERY candidate shares one edge, that
    # edge IS the leading principal component, so stripping it leaves independent noise and nine
    # costumes of one idea report as nine branches. Verified while building this -- nine
    # synthetic clones came back as 9 branches with n_eff 7.9, which is the fake breadth this
    # module exists to prevent, produced by the module itself.
    #
    # Raw-only fails the other way: two genuinely different mechanisms both long risk in a rising
    # market correlate on beta alone and collapse into one branch.
    #
    # A pair is the same branch if it is close on EITHER view. That is the conservative
    # direction: it reports FEWER distinct edges, and over-reporting breadth is the failure with
    # a cost attached -- a book that believes it holds nine bets and holds one.
    corr_raw = _safe_corr(_zscore(matrix))
    resid = strip_factors(matrix, n_factors)
    z = _zscore(resid)
    corr = _safe_corr(z)

    linkage = np.maximum(np.abs(corr), np.abs(corr_raw))

    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    linked = np.argwhere(np.triu(linkage, k=1) >= rho)
    for i, j in linked:
        ri, rj = find(int(i)), find(int(j))
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    roots: dict[int, int] = {}
    branch_of: dict[str, int] = {}
    for k in range(n):
        r = find(k)
        if r not in roots:
            roots[r] = len(roots)
        branch_of[labels[k]] = roots[r]

    sizes: dict[int, int] = {}
    for b in branch_of.values():
        sizes[b] = sizes.get(b, 0) + 1

    # One representative per branch: the column with the highest residual variance, i.e. the
    # member contributing most of what that branch contributes.
    var = z.var(axis=0)
    best: dict[int, tuple[float, str]] = {}
    for k, name in enumerate(labels):
        b = branch_of[name]
        if b not in best or var[k] > best[b][0]:
            best[b] = (float(var[k]), name)

    return BranchReport(
        n_strategies=n,
        n_branches=len(roots),
        n_eff=round(participation_ratio(corr), 3),
        largest_branch=max(sizes.values()) if sizes else 0,
        branch_of=branch_of,
        representatives=[best[b][1] for b in sorted(best)],
        note=(f"{n} strategies -> {len(roots)} branch(es) at |rho|>={rho} on EITHER raw or "
              f"residual returns (residual = after removing {n_factors} common factor(s)); "
              f"n_eff={participation_ratio(corr):.2f} on the residual spectrum"),
    )
