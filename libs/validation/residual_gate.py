"""Incremental alpha AFTER neutralisation, as a statistic. C9.

    s = B f + e      for every candidate, against the book the desk actually holds

THE POINT OF THE ROW, AND THE REASON THIS IS A LIBRARY AND NOT A GATE. C9 asks for
factor-neutral research *everywhere*: every candidate regressed on the latent factors of the
current book and on the survivors' own returns, with the t of the residual mean as an admission
statistic. Its `next_step` proposed mounting that as a stage inside `external_gauntlet`. That
file is SEALED (LAWS: the four never-touch files), so the shape here is the one the desk already
uses for `hostile` -> `blind_reviewer`: a LIBRARY with no side effects, and a MOUNT that runs it
on a clock and PUBLISHES. Nothing in this module refuses, blocks, caps or shrinks anything, and
`blocking` is always False -- a statistic that vetoed would be a new gate on research, which the
standing order of 2026-09-08 forbids without a proof that robust forward E[log W] rises.

WHAT IS ACTUALLY MEASURED, and why each choice is the conservative one:

  * the FACTORS are the PCA scores of the funded book's own daily-R matrix, built through
    `libs.portfolio.latent_factors.factor_model` so the desk has ONE convention for "the latent
    factors of the book" rather than two that disagree by a standardisation;
  * the REGRESSORS are those factors AND the individual survivor series, because a candidate can
    be orthogonal to every principal component and still be a re-spelling of one live sleeve;
  * the STATISTIC is the t of the regression's INTERCEPT -- the alpha the book cannot explain --
    computed on the OVERLAPPING days only. It is NOT the t of the residual mean: a least-squares
    residual measured against a design that carries an intercept has mean exactly zero by
    construction, so that t is identically 0 and would report every candidate as explained.
    Overlap is published, because an alpha t computed on eleven shared days is arithmetic;
  * anything under `MIN_OBS` overlapping finite observations is UNMEASURED WITH A REASON, never
    0.0 -- a fabricated zero would read as "no incremental alpha", which is a verdict this module
    did not earn (L1.28a).

A candidate that the book cannot explain keeps its whole t. A candidate that is the book in
other clothes loses it here, which is the entire content of the measurement.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

#: Fewest overlapping finite observations before a residual t is a measurement. The same 30 the
#: rest of the desk uses for a daily series (`libs/research/alpha_fitness.MIN_OBS`), restated
#: rather than imported so this module has no reason to fail when that one moves.
MIN_OBS = 30
#: Latent factors extracted from the book. Three is what `latent_factors.effective` uses for the
#: factor heat the allocator already sizes on; a different k here would measure a different book.
K_FACTORS = 3
#: Ridge on the loadings' Gram only, where the matrix is k x k and well conditioned by
#: construction. The REGRESSION deliberately carries no ridge: see `independent_columns`.
RIDGE = 1e-8
#: A design column that retains less than this share of its own norm after the columns already
#: kept is a re-spelling of them, not a control. 1e-6 is loose enough to keep a genuinely weak
#: but distinct sleeve and tight enough to drop an exact duplicate.
COLLINEAR_TOL = 1e-6
#: Residual variance share below which the book reproduces the candidate exactly and an
#: intercept t is 0/0. Named rather than inlined so the degenerate case is one constant.
EXACT_FIT = 1e-10

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"


@dataclass(frozen=True)
class ResidualVerdict:
    """One candidate against one book. `blocking` is False and stays False."""

    name: str
    status: str
    why: str = ""
    n_overlap: int = 0
    raw_t: float | None = None
    residual_t: float | None = None
    alpha_per_obs: float | None = None
    explained_share: float | None = None
    t_retained: float | None = None
    betas: dict[str, float] = field(default_factory=dict)
    basis: str = ""
    blocking: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_pairs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rows of `b` (T x N) whose row and the matching `a` entry are all finite."""
    ok = np.isfinite(a)
    if b.size:
        ok = ok & np.isfinite(b).all(axis=1)
    return np.asarray(ok, dtype=bool)


def _t_of_mean(arr: np.ndarray) -> float | None:
    if arr.size < 2:
        return None
    sd = float(arr.std(ddof=1))
    if not math.isfinite(sd) or sd <= 0.0:
        return None
    return float(arr.mean() / (sd / math.sqrt(arr.size)))


def factor_scores(book: np.ndarray, *, k: int = K_FACTORS) -> tuple[np.ndarray, str]:
    """The book's latent factor TIME SERIES (T x k), and how they were built.

    `factor_model` publishes loadings B (N x k) on the EW correlation. The scores are the
    projection of the standardised columns onto those loadings, which is the only reading of
    "the latent factors of the current book" consistent with the heat the allocator already
    sizes on. A book of one column has no factor structure to extract and says so.
    """
    m = np.asarray(book, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2 or m.shape[0] < MIN_OBS:
        return np.empty((m.shape[0] if m.ndim == 2 else 0, 0)), (
            "book has fewer than two sleeves or fewer than "
            f"{MIN_OBS} days: no latent factor is extractable")
    clean = np.nan_to_num(m, nan=0.0, posinf=0.0, neginf=0.0)
    sd = clean.std(axis=0, ddof=1)
    sd = np.where(np.isfinite(sd) & (sd > 0.0), sd, 1.0)
    # SCALED, NOT CENTERED, AND THAT IS THE WHOLE POINT OF THE INTERCEPT. Demeaning the book's
    # columns here strips the book's own mean return out of the factor series, and the intercept
    # then absorbs it: a candidate that is 0.9 x sleeve_a came back with t = -25.7 on a design
    # that reproduced it to float noise. Alpha is only alpha when every regressor is in the same
    # raw return units as the thing being explained.
    z = clean / sd
    try:
        from libs.portfolio.latent_factors import factor_model
    except Exception as exc:                                # pragma: no cover - import env
        return np.empty((m.shape[0], 0)), (
            f"libs.portfolio.latent_factors unimportable ({type(exc).__name__}): "
            "the book's factors are UNMEASURED and only the survivor series are controlled for")
    fm = factor_model(clean, k=int(min(k, clean.shape[1])))
    b = np.asarray(fm.get("loadings"), dtype=float)
    if b.ndim != 2 or not b.size:
        return np.empty((m.shape[0], 0)), "factor_model returned no loadings"
    gram = b.T @ b + RIDGE * np.eye(b.shape[1])
    scores = z @ b @ np.linalg.pinv(gram)
    return np.asarray(scores, dtype=float), (
        f"PCA scores of {b.shape[0]} funded sleeve(s) on {b.shape[1]} factor(s) "
        f"(latent_factors.factor_model, explained={float(fm.get('explained') or 0.0):.3f})")


def independent_columns(x: np.ndarray, *, tol: float = COLLINEAR_TOL) -> list[int]:
    """Indices of `x`'s columns that add a direction the earlier ones do not already span.

    THIS IS NOT TIDINESS, IT IS THE STATISTIC. The design here is [factors | survivors], and when
    the book has k sleeves and k factors are extracted the factor block spans the survivor block
    EXACTLY -- the two halves of C9's own specification are the same subspace written twice. The
    first pass measured that: every candidate came back with a residual t of -0.0 and a retained
    share of 1e-4, because a ridge-stabilised inverse of an exactly singular Gram matrix inverted
    a 1e-8 eigenvalue into 1e8 and inflated the intercept's standard error by four orders of
    magnitude. A near-zero t that is an artefact of collinearity reads exactly like a candidate
    the book explains, which is the most expensive possible way to be wrong here.

    Greedy Gram-Schmidt with a relative tolerance: a column whose residual after the kept columns
    retains less than `tol` of its own norm carries no new information and is dropped.
    """
    if not x.size:
        return []
    kept: list[int] = []
    basis: list[np.ndarray] = []
    for j in range(x.shape[1]):
        v = np.asarray(x[:, j], dtype=float)
        norm0 = float(np.linalg.norm(v))
        if not math.isfinite(norm0) or norm0 <= 0.0:
            continue
        for b in basis:
            v = v - float(v @ b) * b
        if float(np.linalg.norm(v)) / norm0 < tol:
            continue
        basis.append(v / float(np.linalg.norm(v)))
        kept.append(j)
    return kept


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Residuals, coefficients and coefficient standard errors of y on [1, x].

    The design is pruned to independent columns first, then inverted with a plain pseudo-inverse
    whose default cutoff drops what is left of the numerical noise. The standard errors are the
    ordinary homoskedastic ones; the intercept's is the only one this module publishes a t from.
    """
    design = np.column_stack([np.ones(y.size), x]) if x.size else np.ones((y.size, 1))
    gram_inv = np.linalg.pinv(design.T @ design)
    coef = gram_inv @ design.T @ y
    resid = y - design @ coef
    dof = max(y.size - design.shape[1], 1)
    s2 = float(resid @ resid) / dof
    se = np.sqrt(np.clip(s2 * np.diag(gram_inv), 0.0, None))
    return resid, coef, se


def residual_alpha(candidate: Sequence[float] | np.ndarray,
                   book: Mapping[str, Sequence[float] | np.ndarray],
                   *, name: str = "candidate", k: int = K_FACTORS) -> ResidualVerdict:
    """`candidate`'s incremental alpha after neutralising the book. C9's admission statistic.

    The candidate and every book column are assumed to share an index (the desk's daily-R matrix
    is one frame, so they do). Rows where anything is not finite are dropped from ALL series
    together, which is why `n_overlap` is published beside the t.
    """
    y_full = np.asarray(candidate, dtype=float).ravel()
    names = [str(n) for n in book]
    cols = [np.asarray(book[n], dtype=float).ravel() for n in names]
    width = min([y_full.size, *[c.size for c in cols]]) if cols else y_full.size
    if width < MIN_OBS:
        return ResidualVerdict(name=name, status=UNMEASURED, n_overlap=int(max(width, 0)),
                               why=(f"{int(max(width, 0))} shared observation(s), under the "
                                    f"{MIN_OBS} this desk requires: a residual t here would be "
                                    "arithmetic, not evidence"))
    y = y_full[-width:]
    m = np.column_stack([c[-width:] for c in cols]) if cols else np.empty((width, 0))
    ok = _finite_pairs(y, m)
    n = int(ok.sum())
    if n < MIN_OBS:
        return ResidualVerdict(name=name, status=UNMEASURED, n_overlap=n,
                               why=(f"{n} jointly finite observation(s) after alignment, under "
                                    f"{MIN_OBS}"))
    y, m = y[ok], m[ok]
    raw_t = _t_of_mean(y)
    scores, basis = factor_scores(m, k=k)
    regressors = [a for a in (scores, m) if a.size]
    x_full = np.column_stack(regressors) if regressors else np.empty((n, 0))
    labels = ([f"factor_{i + 1}" for i in range(scores.shape[1])] if scores.size else []) + (
        list(names) if m.size else [])
    keep = independent_columns(x_full)
    x = x_full[:, keep] if keep else np.empty((n, 0))
    kept_labels = [labels[j] for j in keep]
    dropped = [labels[j] for j in range(len(labels)) if j not in set(keep)]
    resid, coef, se = _ols(y, x)
    var_all = float(y.var(ddof=1))
    if math.isfinite(var_all) and var_all > 0.0 and float(resid.var(ddof=1)) / var_all < EXACT_FIT:
        # THE DEGENERATE CASE, NAMED. A series that IS a linear combination of the book leaves a
        # residual variance at float noise, and an intercept t formed from it is a ratio of two
        # numbers that are both zero -- it can come out at 40 as easily as at 0. This is the one
        # candidate the desk can say something certain about, and the certain thing is that it
        # carries no incremental alpha, not that it carries an enormous amount.
        return ResidualVerdict(name=name, status=UNMEASURED, n_overlap=n, raw_t=raw_t,
                               explained_share=1.0, basis=basis,
                               why=("the book reproduces this series exactly (residual variance "
                                    "at float noise): there is no incremental alpha to test, "
                                    "and an intercept t here would be 0/0"))
    res_t = None
    if se.size and math.isfinite(float(se[0])) and float(se[0]) > 0.0:
        res_t = float(coef[0] / se[0])
    if res_t is None or not math.isfinite(res_t):
        return ResidualVerdict(name=name, status=UNMEASURED, n_overlap=n, raw_t=raw_t,
                               basis=basis,
                               why=("the intercept has no finite standard error: the book "
                                    "explains this series exactly and alpha is undefined"))
    var_y = float(y.var(ddof=1))
    explained = None
    if math.isfinite(var_y) and var_y > 0.0:
        explained = float(np.clip(1.0 - resid.var(ddof=1) / var_y, 0.0, 1.0))
    betas = {lab: round(float(coef[1 + i]), 6) for i, lab in enumerate(kept_labels)
             if 1 + i < coef.size}
    retained = None
    if raw_t is not None and abs(raw_t) > 1e-12:
        retained = round(float(res_t / raw_t), 4)
    return ResidualVerdict(
        name=name, status=MEASURED, n_overlap=n, raw_t=round(float(raw_t), 4) if raw_t else raw_t,
        residual_t=round(float(res_t), 4), alpha_per_obs=round(float(coef[0]), 8),
        explained_share=round(explained, 4) if explained is not None else None,
        t_retained=retained, betas=betas,
        basis=(basis + f"; {len(names)} survivor series offered, "
               f"controls kept {kept_labels}"
               + (f", dropped as collinear {dropped}" if dropped else "")),
        why=("t of the INTERCEPT after regressing this series on the book's latent factors and "
             "on every funded sleeve -- the alpha the book cannot explain; published, never "
             "subtracted from anything"))


def run_all(cells: Mapping[str, Sequence[float] | np.ndarray],
            book: Mapping[str, Sequence[float] | np.ndarray],
            *, k: int = K_FACTORS) -> dict[str, Any]:
    """Every candidate against one book. Returns rows plus a census; refuses nothing.

    `blocking` is False at every level. This exists so a caller can assert that the desk's
    residual statistic never became a veto by accident -- the one property C9 must keep.
    """
    rows = [residual_alpha(series, book, name=str(cell), k=k).as_dict()
            for cell, series in cells.items()]
    measured = [r for r in rows if r["status"] == MEASURED]
    ranked = sorted(measured, key=lambda r: -(r.get("residual_t") or 0.0))
    return {
        "rule": ("s = Bf + e against the CURRENT book: latent factors plus every funded sleeve; "
                 "the admission statistic is t of the intercept -- the alpha it cannot explain"),
        "n_cells": len(rows), "n_measured": len(measured),
        "n_unmeasured": len(rows) - len(measured),
        "book_sleeves": sorted(book),
        "rows": rows,
        "ranked": [{"name": r["name"], "residual_t": r["residual_t"],
                    "t_retained": r["t_retained"], "n": r["n_overlap"]} for r in ranked],
        "blocking": False,
        "authority": ("PUBLISHES, NEVER VETOES. No cell is refused, delayed, capped or shrunk "
                      "by this statistic; the sealed gauntlet and the promoter remain the only "
                      "judges (standing order 2026-09-08: never reduce aggressiveness)"),
    }
