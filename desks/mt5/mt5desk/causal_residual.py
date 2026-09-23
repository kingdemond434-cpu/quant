"""The residual of one instrument against its drivers, priced by betas that have not seen the bar.

WHY THIS FILE EXISTS AT ALL, which is a defect report.

`family_cross_asset_residual` -- the desk's one executable statement of "what is left of this
instrument after the common factors are removed" -- fitted its hedge ratios like this:

    beta, *_ = np.linalg.lstsq(xv, yv, rcond=None)      # xv, yv = THE WHOLE SAMPLE
    resid = pd.Series(yv - xv @ beta, index=...)

and then traded the mean reversion of that residual from the first bar onward. The beta that
defines "unexplained" was fitted on the very move being called unexplained, on every bar,
including every bar of every out-of-sample fold the gauntlet later carved. `residual_alpha.py`
sitting two directories away opens its docstring with exactly this warning -- "lookahead of the
purest kind" -- and implements the causal version. The research module told the truth and the
executable family committed the error, which is the worst possible arrangement of the two.

The measured consequence is in `funnel_census`: cross_asset_residual failed 348 times and
certified zero. Leakage does not make a family pass; it makes it pass the screen and fail the
walk-forward, over and over, which is precisely the shape of those 348. This desk's one
non-directional, N_eff-breaking mechanism has been structurally unable to certify since it was
written, and the reason was four lines of arithmetic rather than the market.

WHAT CAUSAL MEANS HERE, EXACTLY. beta[t] is fitted on rows [t-win, t-1]. Row t is priced by a
model built from rows strictly before it. eps[t] for t < win is NaN, because there is no honest
answer for those bars and inventing one is how the error came back last time.

WHY IT IS NOT A LOOP. `residual_alpha.rolling_residual` writes the same definition as a Python
loop over `np.linalg.lstsq`, deliberately, "easier to verify by eye". That is right for a script
run on one symbol on demand and wrong for a family the gauntlet builds hundreds of cells from:
50,000 bars x 600 hypotheses is 30 million least-squares solves. This computes the identical
quantity from cumulative normal equations -- the window's X'X and X'y are differences of running
sums -- and solves the whole stack in one batched call. `test_causal_residual` asserts agreement
with the naive loop to 1e-10 on random data, so the fast path is checked against the readable
one rather than trusted.

THE INTERCEPT IS NOT OPTIONAL. The old family regressed returns on returns with no constant, so
any drift in the target that the drivers did not carry was left inside the "residual" and the
z-score of its cumulative sum then read a trend as a dislocation. A fitted constant is what makes
the leftover a residual rather than a mispriced drift.
"""
from __future__ import annotations

import numpy as np

#: Diagonal loading, as a fraction of the window's mean diagonal, applied ONLY so that a window
#: whose driver columns happen to be collinear over those particular bars solves instead of
#: raising. At 1e-10 it moves a well-conditioned beta by parts in ten billion -- it is a
#: numerical device, not a shrinkage prior, and nothing statistical may be claimed from it. The
#: pinv fallback below covers windows too degenerate for even this to rescue.
RIDGE_FRAC = 1e-10


def rolling_betas(y: np.ndarray, X: np.ndarray, win: int,
                  ridge_frac: float = RIDGE_FRAC) -> np.ndarray:
    """beta[t] from rows [t-win, t-1], as an (n, k+1) array whose column 0 is the intercept.

    Rows before `win` are NaN. The regression always carries a constant.
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != y.size:
        X = X.T
    n = y.size
    if X.shape[0] != n:
        raise ValueError(f"driver matrix has {X.shape[0]} rows for {n} target rows")
    k1 = X.shape[1] + 1
    out = np.full((n, k1), np.nan)
    if win < k1 + 1 or n <= win:
        return out

    Z = np.column_stack([np.ones(n), X])
    finite = np.isfinite(Z).all(axis=1) & np.isfinite(y)
    # A non-finite row must not poison the running sums for every later window, so it is zeroed
    # and its contribution is simply absent. The count of usable rows per window is tracked so a
    # window that is mostly holes refuses rather than fitting a beta on three observations.
    Zc = np.where(finite[:, None], Z, 0.0)
    yc = np.where(finite, y, 0.0)

    outer = Zc[:, :, None] * Zc[:, None, :]
    csum_A = np.concatenate([np.zeros((1, k1, k1)), np.cumsum(outer, axis=0)], axis=0)
    csum_b = np.concatenate([np.zeros((1, k1)), np.cumsum(Zc * yc[:, None], axis=0)], axis=0)
    csum_n = np.concatenate([[0], np.cumsum(finite.astype(np.int64))])

    t = np.arange(win, n)
    A = csum_A[t] - csum_A[t - win]
    b = csum_b[t] - csum_b[t - win]
    have = csum_n[t] - csum_n[t - win]

    diag = np.einsum("tii->t", A) / k1
    A = A + (ridge_frac * np.maximum(diag, 1e-300))[:, None, None] * np.eye(k1)[None, :, :]
    try:
        # b[..., None] is not cosmetic: NumPy 2 reads a stacked (t, k) right-hand side as ONE
        # matrix rather than t vectors, and raises on the shape rather than solving the wrong
        # system, which is the better of the two failures but still a failure.
        beta = np.linalg.solve(A, b[:, :, None])[:, :, 0]
    except np.linalg.LinAlgError:
        # Batched solve is all-or-nothing: one degenerate window would deny every other one an
        # answer, so fall back to the pseudo-inverse for the whole stack rather than dropping
        # the sweep on the floor.
        beta = np.einsum("tij,tj->ti", np.linalg.pinv(A), b)

    # A window needs more observations than parameters before its beta means anything.
    beta[have < k1 + 1] = np.nan
    out[win:] = beta
    return out


def causal_residual(y: np.ndarray, X: np.ndarray, win: int,
                    ridge_frac: float = RIDGE_FRAC) -> np.ndarray:
    """eps[t] = y[t] - [1, X[t]] . beta[t], with beta[t] fitted strictly before t."""
    y = np.asarray(y, dtype=float).ravel()
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != y.size:
        X = X.T
    beta = rolling_betas(y, X, win, ridge_frac=ridge_frac)
    Z = np.column_stack([np.ones(y.size), X])
    fit = np.einsum("tj,tj->t", Z, beta)
    return y - fit


def naive_rolling_residual(y: np.ndarray, X: np.ndarray, win: int) -> np.ndarray:
    """The same definition written as an obvious loop. The fast path is tested against THIS.

    Kept in the shipped module rather than in the test file on purpose: the readable statement of
    what `causal_residual` means should live next to the optimised one, so a future reader can
    see the definition without reconstructing it from cumulative sums.
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != y.size:
        X = X.T
    n = y.size
    eps = np.full(n, np.nan)
    for t in range(win, n):
        xs = np.column_stack([np.ones(win), X[t - win:t]])
        ys = y[t - win:t]
        ok = np.isfinite(xs).all(axis=1) & np.isfinite(ys)
        if ok.sum() < xs.shape[1] + 1:
            continue
        try:
            beta, *_ = np.linalg.lstsq(xs[ok], ys[ok], rcond=None)
        except np.linalg.LinAlgError:
            continue
        eps[t] = y[t] - float(beta[0] + X[t] @ beta[1:])
    return eps
